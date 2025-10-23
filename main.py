from fastapi import FastAPI
from purpuria.core import executar_fluxo_purpuria
from dto import MessageResponseDTO, MessageRequestDTO, EmbeddingRequestDTO
from infoRedis import add_embedding

app = FastAPI()


@app.get("/alive")
async def alive():
    return {"status": "banana", "content": "API is alive!"}


@app.post('/chat/{chat_id}', response_model=MessageResponseDTO)
async def doMessage(chat_id: str, msg: MessageRequestDTO):

    resposta = executar_fluxo_purpuria(msg.pergunta, msg.usuario_id, chat_id)

    return MessageResponseDTO(
        resposta = resposta
    )

@app.post("/embed")
async def embed(embedding: EmbeddingRequestDTO):
    add_embedding(embedding.texto)
    return {"status": "Embedding added to Redis!"}