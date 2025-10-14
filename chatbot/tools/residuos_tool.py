import os
import json
from langchain.tools import tool
from pymongo import MongoClient
import psycopg2 

# CONFIGURAÇÃO DE CONEXÃO

MONGO_URL = os.getenv("URL_MONGO")
POSTGRES_URL = os.getenv("URL_POSTGRES")

if not MONGO_URL:
    raise ValueError("URL_MONGO não encontrada no .env. Configure a URL do Atlas/Mongo.")
if not POSTGRES_URL:
    raise ValueError("URL_POSTGRES não encontrada no .env. Necessária para residuoPedido.")

# TOOLS PARA O AGENTE RESÍDUOS

@tool
def consultar_catalogo_residuos(user_id: str) -> str:
    """
    Retorna o catálogo completo de resíduos disponíveis para a empresa (user_id) no MongoDB.
    
    Args:
        user_id: O ID de autenticação do usuário, que corresponde ao campo '_id' no Mongo. OBRIGATÓRIO.
    Retorna: Um JSON com a lista de resíduos da empresa.
    """
    client = None
    try:
        # 1. Conexão e Seleção de Coleção
        client = MongoClient(MONGO_URL)
        db = client['purpura'] 
        collection = db['empresas']

        # 2. Consulta: Filtra por _id
        empresa = collection.find_one(
            {"_id": user_id},
            {"nome": 1, "residuos": 1, "_id": 0} # Projeta apenas os campos necessários
        )
        
        if empresa:
            # 3. Retorna apenas a lista de 'residuos'
            return json.dumps(empresa.get('residuos', []), indent=2, default=str)
        else:
            return json.dumps({"erro": f"Nenhuma empresa encontrada para o ID: {user_id}"})

    except Exception as e:
        return f"ERRO_DB_MONGO: Falha ao consultar o MongoDB. Detalhes: {e}"
    finally:
        if client:
            client.close()

@tool
def obter_residuos_de_pedido(pedido_id: str) -> str:
    """
    Consulta os detalhes (fkResiduo, quantidade, peso, unidade) dos resíduos de um pedido específico na tabela residuoPedido (PostgreSQL).
    
    Args:
        pedido_id: O ID do pedido (fkPedido) do qual buscar os resíduos. OBRIGATÓRIO.
    Retorna: Um JSON com os resíduos daquele pedido.
    """
    sql = f"""
    SELECT rp.fkResiduo, rp.quantidadeResiduo, rp.pesoComprado, rp.tipoUnidade
    FROM residuoPedido rp
    WHERE rp.fkPedido = {pedido_id};
    """
    
    conn = None
    try:
        # 1. Conexão
        conn = psycopg2.connect(POSTGRES_URL)
        cur = conn.cursor()
        cur.execute(sql)
        
        # 2. Formatação dos resultados
        colnames = [desc[0] for desc in cur.description]
        results = [dict(zip(colnames, row)) for row in cur.fetchall()]
        
        cur.close()
        return json.dumps(results, indent=2, default=str)

    except psycopg2.Error as e:
        return f"ERRO_DB_POSGRES: Falha ao executar consulta. Detalhes: {e}"
    except Exception as e:
        return f"ERRO_GERAL_POSGRES: {e}"
    finally:
        if conn:
            conn.close()

RESIDUOS_TOOLS = [consultar_catalogo_residuos, obter_residuos_de_pedido]