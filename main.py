from purpuria.core import executar_fluxo_purpuria
from purpuria.redis_history import get_history
from dto import MessageResponseDTO, MessageRequestDTO, EmbeddingRequestDTO, ChatHistoryRequestDTO
from infoRedis import add_embedding
from fastapi import FastAPI

app = FastAPI()


@app.get("/alive")
async def alive():
    return {"status": "banana", "content": "API is alive!"}


@app.post('/chat/{chat_id}', response_model=MessageResponseDTO)
async def doMessage(chat_id: str, msg: MessageRequestDTO):

    resposta = executar_fluxo_purpuria(msg.content, msg.senderId, chat_id)

    return MessageResponseDTO(
        senderId=msg.senderId,
        content = resposta
    )

@app.get("/chat", response_model=list[MessageResponseDTO])
async def getMessages(historyRequest: ChatHistoryRequestDTO):
    history = get_history(historyRequest.senderId, historyRequest.chatId)
    def toSenderId(role: str):
        return historyRequest.senderId if role == "user" else None

    return [
        MessageResponseDTO(senderId=toSenderId(message['role']), content=message['content'])
        for message in history
    ]


@app.post("/embed")
async def embed(embedding: EmbeddingRequestDTO):
    add_embedding(embedding.texto)
    return {"status": "Embedding added to Redis!"}