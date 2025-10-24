from purpuria.core import executar_fluxo_purpuria
from purpuria.redis_history import get_history
from dto import MessageResponseDTO, MessageRequestDTO, EmbeddingRequestDTO, ChatHistoryRequestDTO
from infoRedis import add_embedding, limpar_embedding, pegar_embeddings
from fastapi import FastAPI

app = FastAPI(
    title="API Purpúria Chatbot",
    description="API para interação com o chatbot Purpúria, incluindo gerenciamento de conversas e embeddings",
    version="1.0.0"
)


@app.get("/alive",
         summary="Verificar status da API",
         description="Endpoint simples para verificar se a API está rodando e respondendo corretamente",
         tags=["Saúde"]
)
async def alive():
    return {"status": "banana", "content": "API is alive!"}


@app.post('/chat/{chat_id}', 
          response_model=MessageResponseDTO,
          summary="Enviar mensagem para o chat",
          description="Envia uma mensagem para o chatbot e retorna a resposta gerada. "
                      "Cada chat é identificado por um chat_id único.",
          tags=["Chat"],
          responses={
              200: {
                  "description": "Mensagem processada com sucesso",
                  "content": {
                      "application/json": {
                          "example": {
                              "senderId": "user123",
                              "content": "Olá! Como posso ajudar você hoje?"
                          }
                      }
                  }
              }
          })
async def doMessage(chat_id: str, msg: MessageRequestDTO):
    """
    Processa uma mensagem do usuário e retorna a resposta do chatbot.
    
    - **chat_id**: Identificador único da conversa
    - **msg**: Objeto contendo o conteúdo da mensagem e o ID do remetente
    """
    resposta = executar_fluxo_purpuria(msg.content, msg.senderId, chat_id)

    return MessageResponseDTO(
        senderId=msg.senderId,
        content=resposta
    )

@app.get(
    "/chat", 
    response_model = list[MessageResponseDTO],
    summary = "Obter histórico do chat",
    description = "Recupera o histórico completo de mensagens de uma conversa específica",
    tags = ["Chat"]
)
async def getMessages(historyRequest: ChatHistoryRequestDTO):
    """
    Retorna todas as mensagens de um chat baseado no senderId e chatId.
    
    - **senderId**: ID do usuário que está solicitando o histórico
    - **chatId**: ID do chat do qual recuperar as mensagens
    """
    history = get_history(historyRequest.senderId, historyRequest.chatId)
    def toSenderId(role: str):
        return historyRequest.senderId if role == "user" else None

    return [
        MessageResponseDTO(senderId=toSenderId(message['role']), content=message['conteudo'])
        for message in history
    ]


@app.post(
    "/embed",
    summary="Adicionar embedding",
    description="Adiciona um novo texto ao sistema de embeddings no Redis para melhorar "
                "as respostas do chatbot com informações contextuais",
    tags=["Embeddings"],
    responses={
        200: {
            "description": "Embedding adicionado com sucesso",
            "content": {
                "application/json": {
                    "example": {"status": "Embedding added to Redis!"}
                }
            }
        }
    }
)
async def embed(embedding: EmbeddingRequestDTO):
    """
    Adiciona um texto ao banco de embeddings.
    
    - **texto**: Texto que será convertido em embedding e armazenado
    """
    add_embedding(embedding.texto)
    return {"status": "Embedding added to Redis!"}


@app.get(
    "/embed",
    summary="Obter embeddings",
    description="Retorna todos os embeddings armazenados no Redis",
    tags=["Embeddings"],
    responses={
        200: {
            "description": "Embeddings encontrados",
            "content": {
                "application/json": {
                    "example": {"embeddings": ["embedding1", "embedding2"]}
                }
            }
        }
    }
)
async def get_embeddings():
    return {"embeddings": pegar_embeddings()}

@app.delete(
    "/embed",
    summary="Limpar embeddings",
    description="Remove todos os embeddings armazenados no Redis. Use com cuidado!",
    tags=["Embeddings"],
    responses={
        200: {
            "description": "Embeddings removidos com sucesso",
            "content": {
                "application/json": {
                    "example": {"status": "Embeddings cleared from Redis!"}
                }
            }
        }
    }
)
async def clear_embeddings():
    """
    Remove todos os embeddings do sistema.
    
    **Atenção**: Esta operação é irreversível e afetará o contexto do chatbot.
    """
    limpar_embedding()
    return {"status": "Embeddings cleared from Redis!"}