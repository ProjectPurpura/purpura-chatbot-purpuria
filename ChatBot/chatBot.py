from dotenv import load_dotenv
load_dotenv()
import os
import re
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts.few_shot import FewShotChatMessagePromptTemplate
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.messages import HumanMessage, AIMessage 
from redis_tool import TOOLS as DUVIDAS_TOOLS 
from pedidos_tool import PEDIDOS_TOOLS
from residuos_tool import RESIDUOS_TOOLS
from redis_history import get_history, add_message 

# Configurações Iniciais

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.7,
    top_p=0.95,
    google_api_key=os.getenv("GEMINI_API_KEY") 
)

llm_fast = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0,
    google_api_key=os.getenv("GEMINI_API_KEY")
)

# --- CONFIGURAÇÃO DO GUARDRAIL ---

LISTA_PALAVRAS_OFENSIVAS = ["bosta", "merda", "puta", "viado", "caralho", "foda-se"] # Adicione mais conforme necessário
RESPOSTA_RECUSA_ENTRADA = "Desculpe, a pergunta toca em um tópico fora do meu escopo e/ou é inapropriada para este canal de suporte. Por favor, reformule sua questão sobre resíduos, pedidos ou dúvidas do aplicativo PurPurIA."
RESPOSTA_RECUSA_SAIDA = "Houve uma falha na geração da resposta. Por favor, tente novamente mais tarde." 


def check_input_guardrail(pergunta: str) -> bool:
    """Verifica se a pergunta do usuário é sugestiva, política ou inapropriada."""
    pergunta_lower = pergunta.lower()
    if any(palavra in pergunta_lower for palavra in ["presidente", "política", "religião", "sexo", "partido"]):
        return True 
    if re.search(r"o\s+que\s+o\s+melhor\s+presidente\s+falou", pergunta_lower):
        return True 
    return False 


def check_output_guardrail(resposta: str) -> bool:
    """Verifica se a resposta final contém linguagem ofensiva."""
    resposta_lower = re.sub(r'[^\w\s]', '', resposta).lower()
    if any(palavra in resposta_lower.split() for palavra in LISTA_PALAVRAS_OFENSIVAS):
        return True 
    return False 


# AGENTE 1: ROTEAR
# AJUSTE NO PROMPT DO ROTTEADOR
system_prompt_roteador = ("system", """
### PERSONA SISTEMA
Você é o Roteador do PurPurIA. Decida a **melhor rota (apenas uma)** para a pergunta. Domínios: **duvidas_app**, **pedidos**, **residuos**.

### REGRAS
- Escolha **apenas uma rota**. 
- **SE FOR FORA DE ESCOPO**: Responda diretamente ao usuário com uma frase educada (ex: "Consigo ajudar apenas com questões da Purpura..."). **NÃO** use o protocolo ROUTE=...
- **SE FOR DENTRO DE ESCOPO**: Use **APENAS** o protocolo abaixo e **NÃO** responda ao usuário.

### PROTOCOLO DE ENCAMINHAMENTO (texto puro)
ROUTE=<duvidas_app | pedidos | residuos> # Rota Única
PERGUNTA_ORIGINAL=<mensagem completa do usuário, sem edições>
CLARIFY=<pergunta mínima se precisar; senão deixe vazio>
""")

example_prompt_base = ChatPromptTemplate.from_messages([
    ("human", "{human}"),
    ("ai", "{ai}"),
])

# Shots do roteador (mantidos com a lógica de resposta direta para fora de escopo)
shots_roteador = [
    {"human": "Quais pedidos ativos eu tenho?", "ai": "ROUTE=pedidos\nPERGUNTA_ORIGINAL=Quais pedidos ativos eu tenho?\nCLARIFY="},
    {"human": "Onde fica a sede da Purpura?", "ai": "ROUTE=duvidas_app\nPERGUNTA_ORIGINAL=Onde fica a sede da Purpura?\nCLARIFY="},
    {"human": "Meus resíduos de plástico estão prontos?", "ai": "ROUTE=residuos\nPERGUNTA_ORIGINAL=Meus resíduos de plástico estão prontos?\nCLARIFY="},
    {"human": "Me conta uma piada.", "ai": "Consigo ajudar apenas com questões da Purpura. Quer saber mais sobre reciclagem ou checar seu último pedido?"},
]

fewshots_roteador = FewShotChatMessagePromptTemplate(examples=shots_roteador, example_prompt=example_prompt_base)

prompt_roteador = ChatPromptTemplate.from_messages([
    system_prompt_roteador,
    fewshots_roteador,
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

# AGENTES 2/3/4: ESPECIALISTAS (Ajuste de Segurança de Dados na Resposta)

SYSTEM_PROMPT_ESPECIALISTA = """
### OBJETIVO
Você é o Agente Especialista no domínio {dominio_key}. Use a PERGUNTA_ORIGINAL e opere as ferramentas para gerar a resposta.
A saída SEMPRE é um objeto JSON (contrato abaixo) para o Orquestrador.

### CONTEXTO CRÍTICO
Você **SEMPRE** receberá o ID do usuário no campo `USER_ID` do seu input.
**NUNCA PERGUNTE** ao usuário qual é o ID. Use-o como o argumento `user_id` em todas as chamadas de ferramenta (Tools) que o exigem.

### REGRA CRÍTICA DE SEGURANÇA DE DADOS
- O campo `resposta` deve conter APENAS informações que o usuário pode ver no aplicativo (ex: Status, Data, Tipo de Resíduo, Peso). **NUNCA INCLUA IDs de Pedido (#123)** ou qualquer outra chave/ID **na resposta final** (use a data ou status como referência).

### REGRAS GERAIS
- Sua saída é sempre a resposta final.

### SAÍDA (JSON)
# Obrigatórios:
  - dominio  : "{dominio_key}"
  - resposta : uma frase objetiva com a informação principal, **sem IDs de Pedido**.
  - recomendacao : ação prática (pode ser string vazia se não houver)
# Opcionais (incluir só se necessário):
  - acompanhamento : texto curto de follow-up/próximo passo.
"""

def criar_prompt_especialista(dominio: str, tools):
    """Cria o Prompt Template e Executor para um Especialista específico."""
    system_content = SYSTEM_PROMPT_ESPECIALISTA.format(dominio_key=dominio)
    
    system_prompt_tuple = ("system", system_content)

    prompt = ChatPromptTemplate.from_messages([
        system_prompt_tuple,
        fewshots_especialista, 
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad")
    ])
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        handle_parsing_errors=True
    )
    return executor

# Few-Shots dos Especialistas (Simplificados para Rota Única)
shots_especialista = [
    # Exemplo de Pedidos
    {
        "human": "ROUTE=pedidos\nPERGUNTA_ORIGINAL=Quais pedidos ativos eu tenho?\nDADO_ANTERIOR=\nUSER_ID=user_123",
        "ai": """{{"dominio":"pedidos","resposta":"Você tem 2 pedidos ativos: um para 15/01/2025 (pronto) e outro para 20/01/2025 (em preparo).","recomendacao":"Gostaria de detalhes de um deles?"}}"""
    },
    # Exemplo de Resíduos
    {
        "human": "ROUTE=residuos\nPERGUNTA_ORIGINAL=Quais resíduos estão prontos para coleta?\nDADO_ANTERIOR=\nUSER_ID=user_123",
        "ai": """{{"dominio":"residuos","resposta":"Você tem 5kg de plástico e 2kg de metal prontos para coleta.","recomendacao":"Deseja agendar a coleta?"}}"""
    },
]
fewshots_especialista = FewShotChatMessagePromptTemplate(examples=shots_especialista, example_prompt=example_prompt_base)

# Criação dos Agentes Executores
duvidas_executor = criar_prompt_especialista("duvidas_app", DUVIDAS_TOOLS)
pedidos_executor = criar_prompt_especialista("pedidos", PEDIDOS_TOOLS)
residuos_executor = criar_prompt_especialista("residuos", RESIDUOS_TOOLS)

ESPECIALISTAS_MAP = {
    "duvidas_app": duvidas_executor,
    "pedidos": pedidos_executor,
    "residuos": residuos_executor
}

# AGENTE 5: ORQUESTRADOR
system_prompt_orquestrador = ("system", """
### PAPEL
Você é o Agente Orquestrador. Sua função é entregar a resposta final ao usuário **somente** quando o Especialista retornar o JSON.

### REGRAS
- Use **exatamente** `resposta` do especialista como a **primeira linha** do output.
- Inclua a seção *Recomendação* se `recomendacao` existir; caso contrário, **omita**.
- Inclua a seção *Acompanhamento* se sugerir follow-up; caso contrário, **omita**.
- Não retorne JSON; **sempre** retorne no FORMATO DE SAÍDA.

### FORMATO DE SAÍDA (sempre ao usuário)
<sua resposta será 1 frase objetiva sobre a situação>
""")

shots_orquestrador = [
    {
        "human": """ESPECIALISTA_JSON:\n{{"dominio":"residuos","resposta":"Você tem 5kg de plástico e 2kg de metal prontos para coleta.","recomendacao":"Deseja agendar a coleta?"}}""",
        "ai": "Você tem 5kg de plástico e 2kg de metal prontos para coleta.\n- *Recomendação*:\nDeseja agendar a coleta?"
    },
]

fewshots_orquestrador = FewShotChatMessagePromptTemplate(examples=shots_orquestrador, example_prompt=example_prompt_base)

prompt_orquestrador = ChatPromptTemplate.from_messages([
    system_prompt_orquestrador,
    fewshots_orquestrador,
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

# --- AGENTE 6: VALIDADOR/JUIZ ---

system_prompt_juiz = ("system", """
### PAPEL
Você é o **Agente Juiz/Validador** do PurPurIA. Sua função é garantir que a resposta final seja **coerente**, **completa** e **apropriada** ao contexto da pergunta, da rota e da informação bruta do especialista.

### REGRAS DE VALIDAÇÃO
1.  **Coerência:** A resposta final deve estar alinhada com a PERGUNTA_ORIGINAL e o CONTEXTO_ESPECIALISTA.
2.  **Formato:** O formato do Orquestrador deve estar intacto (frase inicial, - *Recomendação*, etc.).
3.  **Completo:** A resposta deve abordar a pergunta do usuário de forma satisfatória.

### ENTRADA
Você receberá 4 campos-chave para sua análise.

### SAÍDA
- Se a resposta for **validada**, retorne **EXATAMENTE** a RESPOSTA_FINAL, sem alterações, comentários ou formatação extra.
- Se a resposta for **incoerente** ou **faltar informação crítica**, faça uma **REESCRITA** que corrija o problema, mantendo o formato recebido.
""")

prompt_juiz = ChatPromptTemplate.from_messages([
    system_prompt_juiz,
    MessagesPlaceholder("chat_history"), 
    ("human", """
PERGUNTA_ORIGINAL: {pergunta_original}
ROTA_USADA: {rota_usada}
CONTEXTO_ESPECIALISTA: {contexto_especialista} 
RESPOSTA_FINAL: {resposta_final}
""")
])

# Chain do Juiz
juiz_chain = prompt_juiz | llm_fast | StrOutputParser()

def formatar_historico_para_langchain(usuario: str, chat_id: str) -> list:
    """Busca o histórico no Redis e formata para lista de Human/AIMessage."""
    historico_do_redis = get_history(usuario, chat_id)
    chat_msgs = []
    for msg in historico_do_redis:
        if msg["role"] == "user":
            chat_msgs.append(HumanMessage(content=msg["conteudo"]))
        elif msg["role"] == "assistant":
            chat_msgs.append(AIMessage(content=msg["conteudo"]))
    return chat_msgs

# FUNÇÃO EXECUTORA SIMPLIFICADA
def executar_fluxo_purpuria(pergunta_usuario: str, usuario: str, chat_id: str) -> str:
    """Executa o fluxo completo do roteador ao orquestrador, seguindo a lógica de Rota Única."""
    
    # --- PASSO 0: GUARDRAIL DE ENTRADA ---
    if check_input_guardrail(pergunta_usuario):
        add_message(usuario, chat_id, "user", pergunta_usuario)
        add_message(usuario, chat_id, "assistant", RESPOSTA_RECUSA_ENTRADA)
        return RESPOSTA_RECUSA_ENTRADA
    
    # 1. Recuperar o histórico
    historico = formatar_historico_para_langchain(usuario, chat_id)

    # 2. EXECUTAR O ROTTEADOR
    roteador_chain = prompt_roteador | llm_fast | StrOutputParser()
    res_roteador = roteador_chain.invoke(
        {"input": pergunta_usuario, "chat_history": historico}
    )

    # 3. ANÁLISE DA SAÍDA DO ROTTEADOR
    # O Roteador só responde com ROUTE=... se for DENTRO de escopo.
    match = re.search(r"ROUTE=([\w]+)", res_roteador)

    # Se NÃO houver ROUTE=... significa que é Rota Direta / Fora de Escopo
    if not match:
        # --- VALIDAÇÃO DO JUIZ (ROTA DIRETA) ---
        # A res_roteador é a resposta final do Roteador (ex: "Consigo ajudar apenas...")
        res_juiz_direta = juiz_chain.invoke({
            "pergunta_original": pergunta_usuario,
            "rota_usada": "fora_escopo",
            "contexto_especialista": "N/A - Rota Direta",
            "resposta_final": res_roteador,
            "chat_history": historico
        })
        
        # --- VERIFICAÇÃO DE SAÍDA NO JUIZ DIRETO ---
        if check_output_guardrail(res_juiz_direta):
            res_final = RESPOSTA_RECUSA_SAIDA
            add_message(usuario, chat_id, "user", pergunta_usuario)
            add_message(usuario, chat_id, "assistant", res_final)
            return res_final
        # -------------------------------------------
        
        add_message(usuario, chat_id, "user", pergunta_usuario)
        add_message(usuario, chat_id, "assistant", res_juiz_direta)
        return res_juiz_direta
    
    # 4. EXECUTAR O ÚNICO ESPECIALISTA (CASO DENTRO DE ESCOPO)
    rota = match.group(1).strip()
    
    if rota not in ESPECIALISTAS_MAP:
        return f"Erro: Rota '{rota}' não mapeada para um agente especialista."
            
    agente_especialista = ESPECIALISTAS_MAP[rota]
        
    # Cria o INPUT do Especialista
    input_especialista = (
        f"ROUTE={rota}\n" 
        f"PERGUNTA_ORIGINAL={pergunta_usuario}\n" 
        f"DADO_ANTERIOR=\n" 
        f"USER_ID={usuario}"
    )
    
    # Executa o Especialista
    res_especialista = agente_especialista.invoke({
        "input": input_especialista,
        "chat_history": historico
    })

    json_str = res_especialista.get('output', '{}')
        
    # Limpa o JSON 
    json_limpo = json_str.strip()
    if json_limpo.startswith("```json"):
        json_limpo = json_limpo.replace("```json", "", 1).strip()
    if json_limpo.endswith("```"):
        json_limpo = json_limpo.rstrip("`").strip()

    try:
        dados_especialista = json.loads(json_limpo)
    except json.JSONDecodeError:
        return f"Erro interno: O agente especialista '{rota}' retornou um JSON inválido. Saída: {json_str}"

    resposta_final_json = json_limpo
    dados_ult_especialista = dados_especialista

    # 5. EXECUTAR O ORQUESTRADOR
    input_orquestrador = f"ESPECIALISTA_JSON:\n{resposta_final_json}"
    
    orquestrador_chain = prompt_orquestrador | llm_fast | StrOutputParser()
    
    res_orquestrador = orquestrador_chain.invoke({
        "input": input_orquestrador,
        "chat_history": historico
    })

    # 6. EXECUTAR O JUIZ/VALIDADOR
    contexto_juiz = json.dumps(dados_ult_especialista) if dados_ult_especialista else "N/A"

    res_final_juiz = juiz_chain.invoke({
        "pergunta_original": pergunta_usuario,
        "rota_usada": rota,
        "contexto_especialista": contexto_juiz,
        "resposta_final": res_orquestrador,
        "chat_history": historico
    })
    
    # --- PASSO 7: GUARDRAIL DE SAÍDA FINAL ---
    if check_output_guardrail(res_final_juiz):
        res_final = RESPOSTA_RECUSA_SAIDA
        add_message(usuario, chat_id, "user", pergunta_usuario)
        add_message(usuario, chat_id, "assistant", res_final)
        return res_final

    # 8. Salvar e Retornar
    add_message(usuario, chat_id, "user", pergunta_usuario)
    add_message(usuario, chat_id, "assistant", res_final_juiz)
    
    return res_final_juiz

# Execução Simplificada (Sem loop/if __main__)
print("--- PurPurIA Multi-Agente Ativo (Orquestrador) ---")

# Defina aqui um ID de usuário (user_id) real
usuario_id = "17424290000101"
chat_id_sessao = "02_teste" 
pergunta_usuario_teste = "quais são meus residuos"

# Execução do fluxo
try:
    resposta_final = executar_fluxo_purpuria(
        pergunta_usuario=pergunta_usuario_teste,
        usuario=usuario_id,
        chat_id=chat_id_sessao
    )
    
    print("\n<< PurPurIA:", resposta_final)
except Exception as e:
    if os.getenv("GEMINI_API_KEY") is None:
        print("\n[ERRO DE CONFIGURAÇÃO] Por favor, defina a variável GEMINI_API_KEY no seu arquivo .env para executar o código.")
    else:
        print(f"\n[ERRO FATAL] Ocorreu uma exceção: {type(e).__name__}")
        print(f"Detalhes do erro: {e}")