from pydantic import BaseModel
from datetime import datetime


class ChatHistoryRequestDTO(BaseModel):
    senderId: str
    chat_id: str


class MessageRequestDTO(BaseModel):
    senderId: str
    content: str

class MessageResponseDTO(BaseModel):
    content: str
    senderId: str | None
    read: bool = True
    timestamp: datetime = datetime.now()

class EmbeddingRequestDTO(BaseModel):
    texto: str