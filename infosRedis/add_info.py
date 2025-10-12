import json
import redis
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import os

load_dotenv()

print("Carregando o modelo de embeddings...")

model = SentenceTransformer("all-MiniLM-L6-v2")

REDIS_URL = os.getenv("REDIS_URL")

# Conecta ao Redis usando a URL completa (Host, porta, autenticação)
redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True
)

def gerar_embedding_offline(texto):
    """Gera um embedding para o texto fornecido usando o modelo local."""
    embedding = model.encode(texto)
    return embedding.tolist()  # Converte para lista serializável

def proxima_chave():
    """Gera o próximo nome de chave disponível (info1, info2, ...)."""
    # Busca todas as chaves que começam com "info"
    chaves = redis_client.keys("info*")
    
    if not chaves:
        return "info1"
        
    # Filtra e extrai os números das chaves válidas
    indices = [int(c.replace("info", "")) for c in chaves if c.replace("info", "").isdigit()]
    
    # Retorna o próximo índice. Se não houver índices (chaves inválidas), começa em 1.
    return f"info{max(indices) + 1}" if indices else "info1"

def adicionar_embedding_interativo():
    """
    Solicita a entrada de texto do usuário, gera o embedding e salva no Redis,
    repetindo o processo até que o usuário decida parar.
    """
    print("\n" + "="*50)
    print("MODO INTERATIVO: Adicionar Embeddings ao Redis")
    print("Digite 'sair' ou 'parar' a qualquer momento para finalizar.")
    print("="*50 + "\n")

    while True:
        # 1. Solicitar conteúdo
        conteudo = input("Digite a informação/pergunta (ou 'sair'): ").strip()

        if not conteudo or conteudo.lower() in ('sair', 'parar'):
            print("\nEncerrando o modo interativo. Tchau!")
            break
        
        if len(conteudo) < 5:
            print("Conteúdo muito curto. Digite uma frase mais longa.")
            continue

        try:
            # 2. Gerar embedding
            embedding = gerar_embedding_offline(conteudo)
            
            # 3. Gerar chave única no Redis
            chave = proxima_chave()

            # 4. Salvar no Redis como hash
            redis_client.hset(chave, mapping={
                "mensagem": conteudo,
                "embedding": json.dumps(embedding)  # Salva o embedding como string JSON
            })

            print(f"Chave '{chave}' criada no Redis. Próxima...")

        except redis.exceptions.ConnectionError:
            print("\nERRO: Não foi possível conectar ao Redis. Verifique se o servidor está rodando em localhost:6379.")
            break
        except Exception as e:
            print(f"Erro inesperado ao processar: {e}")
            
if __name__ == "__main__":
    adicionar_embedding_interativo()