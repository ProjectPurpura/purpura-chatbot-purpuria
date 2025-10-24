import json
import redis
from common.env import ENV
from langchain_google_genai import GoogleGenerativeAIEmbeddings

print("Carregando o modelo de embeddings...")

# Inicializa o modelo de embeddings (Google)
embeddings_model = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004",
    google_api_key=ENV.GEMINI_API_KEY
)

# Conexão Redis
redis_client = redis.Redis.from_url(
    ENV.REDIS_URL,
    decode_responses=True
)

# redis_client = redis.Redis(
#     host="localhost",
#     port=6379,
#     db=0,
#     decode_responses=True
# )

def gerar_embedding(texto: str):
    """Gera um embedding usando o modelo Google Generative AI."""
    emb = embeddings_model.embed_query(texto)
    return emb

def proxima_chave():
    """Gera o próximo nome de chave disponível (info0, info1, ...)."""
    chaves = redis_client.keys("info*")

    if not chaves:
        return "info0"
    
    indices = [int(c.replace("info", "")) for c in chaves if c.replace("info", "").isdigit()]
    return f"info{max(indices) + 1}" if indices else "info0"


def add_embedding(texto: str) -> bool:
    try:
        # Gera o embedding
        embedding = gerar_embedding(texto)

        # Define a próxima chave
        chave = proxima_chave()

        # Salva o texto simples no Redis
        redis_client.set(chave, texto)

        # Recupera lista existente de embeddings ou cria uma nova
        embeddings_json = redis_client.get("embeddings_list")
        embeddings_list = json.loads(embeddings_json) if embeddings_json else []

        # Adiciona novo embedding à lista
        embeddings_list.append(embedding)

        # Atualiza lista no Redis
        redis_client.set("embeddings_list", json.dumps(embeddings_list))

        print(f"Texto salvo como '{chave}' e embedding armazenado (índice {len(embeddings_list) - 1}).")
        return True
    except redis.exceptions.ConnectionError:
        print("\nERRO: Não foi possível conectar ao Redis. Verifique se o servidor está ativo.")
    except Exception as e:
        print(f"Erro inesperado: {e}")

    return False

def limpar_embedding():
    redis_client.flushdb()
    print("Embeddings limpos do Redis.")

def pegar_embeddings():
    embeddings_json = redis_client.get("embeddings_list")
    if not embeddings_json:
        return []
    return json.loads(embeddings_json)


def adicionar_embedding_interativo():
    """
    Modo interativo: o usuário adiciona textos, e o sistema gera e salva os embeddings.
    - Texto é salvo em uma chave individual (info0, info1, ...).
    - Embeddings são armazenados juntos em uma lista (embeddings_list).
    """
    print("\n" + "="*60)
    print("MODO INTERATIVO: Adicionar informações e embeddings ao Redis")
    print("Digite 'sair' para encerrar.")
    print("="*60 + "\n")

    while True:
        conteudo = input("Digite a informação/pergunta (ou 'sair'): ").strip()


        if not conteudo or conteudo.lower() in ('sair', 'parar'):
            print("\nEncerrando o modo interativo. Até mais!")
            break
        
        if len(conteudo) < 5:
            print("Conteúdo muito curto. Digite algo mais descritivo.")
            continue


        if add_embedding(conteudo):
            continue
        else:
            print('Erro ao adicionar o texto. Tente novamente.')

if __name__ == "__main__":
    adicionar_embedding_interativo()