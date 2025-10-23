# redis_tool.py
import redis
import json
import numpy as np
from langchain_core.tools import Tool
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from common.env import ENV

# Conexão com Redis
# redis_client = redis.Redis.from_url(
#     ENV.REDIS_URL,
#     decode_responses=True
# )

redis_client = redis.Redis(
    host="localhost",   
    port=6379,
    db=0,
    decode_responses=True
)

# Modelo de embeddings Google
embeddings_model = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004",
    google_api_key=ENV.GEMINI_API_KEY
)

def cosine_similarity(vec1, vec2):
    """Calcula similaridade de cosseno entre dois vetores."""
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

def buscar_no_redis(consulta):
    """
    Busca as 3 informações mais próximas no Redis com base no embedding da consulta.
    Estrutura esperada:
      - info0, info1, ... → strings com os textos
      - embeddings_list → lista JSON com todos os embeddings (na mesma ordem)
    """
    # Gera embedding da consulta
    consulta_emb = embeddings_model.embed_query(consulta)

    # Recupera lista de embeddings
    embeddings_json = redis_client.get("embeddings_list")
    if not embeddings_json:
        return ["Nenhum embedding armazenado no Redis."]

    embeddings_list = json.loads(embeddings_json)

    # Recupera todas as chaves infoX
    chaves = sorted(redis_client.keys("info*"), key=lambda c: int(c.replace("info", "")))
    if not chaves:
        return ["Nenhuma informação cadastrada no Redis."]

    resultados = []
    for idx, chave in enumerate(chaves):
        texto = redis_client.get(chave)
        if texto and idx < len(embeddings_list):
            score = cosine_similarity(consulta_emb, embeddings_list[idx])
            resultados.append((score, texto))

    # Ordena por maior similaridade e retorna as 3 mais próximas
    resultados = sorted(resultados, key=lambda x: x[0], reverse=True)[:3]

    mensagens = [msg for _, msg in resultados]
    return mensagens or ["Nenhuma informação relevante encontrada."]

# TOOL no formato correto (lista de instâncias de Tool)
TOOLS = [
    Tool(
        name="buscar_no_redis",
        func=buscar_no_redis,
        description=(
            "Busca as 3 informações mais relevantes no Redis com base na pergunta do usuário. "
            "Use quando a dúvida for sobre dados, informações ou conteúdos armazenados."
        )
    )
]