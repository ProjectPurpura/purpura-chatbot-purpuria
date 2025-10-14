from fastapi import FastAPI
from chatbot.core import executar_fluxo_purpuria
from dto import MessageResponseDTO, MessageRequestDTO

app = FastAPI()


@app.get("/alive")
async def alive():
    return {"status": "Api is alive!"}


@app.post('/chat/{chat_id}', response_model=MessageResponseDTO)
async def doMessage(chat_id: str, msg: MessageRequestDTO):

    response = executar_fluxo_purpuria(msg.pergunta, msg.usuario_id, chat_id)

    return MessageResponseDTO(
        response = response
    )