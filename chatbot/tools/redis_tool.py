# redis_tool.py
import redis
import json
import numpy as np
from sentence_transformers import SentenceTransformer
from langchain_core.tools import Tool 
import os

REDIS_URL = os.getenv("REDIS_URL")

# Conecta ao Redis usando a URL completa (Host, porta, autenticação)
redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True
)

model = SentenceTransformer("all-MiniLM-L6-v2")

def cosine_similarity(vec1, vec2):
    """Calcula similaridade de cosseno entre dois vetores"""
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

def buscar_no_redis(consulta, top_k=3):
    """
    Gera embedding para a consulta e busca os embeddings mais próximos no Redis.
    Retorna uma lista de mensagens relevantes.
    """
    consulta_emb = model.encode(consulta).tolist()

    chaves = redis_client.keys("info*")
    if not chaves:
        return ["Nenhuma informação cadastrada no Redis."]

    resultados = []
    for chave in chaves:
        dados = redis_client.hgetall(chave)
        if "embedding" in dados:
            emb_salvo = json.loads(dados["embedding"])
            score = cosine_similarity(consulta_emb, emb_salvo)
            resultados.append((score, dados.get("mensagem", "")))

    # Ordenar por similaridade e pegar os top_k
    resultados = sorted(resultados, key=lambda x: x[0], reverse=True)[:top_k]
    mensagens = [msg for _, msg in resultados]

    return mensagens


# TOOL no formato correto (lista de instâncias de Tool)
TOOLS = [
    Tool(
        name="buscar_no_redis",
        func=buscar_no_redis,
        description="Busca informações relevantes no Redis com base na pergunta do usuário. Use quando a dúvida for sobre a empresa, o aplicativo ou dados salvos."
    )
]