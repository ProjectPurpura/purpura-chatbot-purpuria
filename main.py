from fastapi import FastAPI
from purpuria.core import executar_fluxo_purpuria
from dto import MessageResponseDTO, MessageRequestDTO

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