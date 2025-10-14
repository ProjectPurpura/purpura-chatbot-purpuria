import redis
import json
from common.env import ENV


# Conecta ao Redis usando a URL completa (Host, porta, autenticação)
redis_client = redis.Redis.from_url(
    ENV.REDIS_URL,
    decode_responses=True
)

def _chat_key(usuario: str, chat_id: str) -> str:
    """Monta a chave do Redis para armazenar histórico"""
    return f"chat:{usuario}:{chat_id}"

def get_history(usuario: str, chat_id: str):
    """Busca histórico salvo no Redis"""
    key = _chat_key(usuario, chat_id)
    data = redis_client.lrange(key, 0, -1)
    if not data:
        return []
    return [json.loads(d) for d in data]

def add_message(usuario: str, chat_id: str, role: str, conteudo: str):
    """Adiciona mensagem ao histórico"""
    key = _chat_key(usuario, chat_id)
    redis_client.rpush(key, json.dumps({"role": role, "conteudo": conteudo}))