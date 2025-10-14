from pydantic import BaseModel
from datetime import datetime

class MessageRequestDTO(BaseModel):
    pergunta: str
    usuario_id: str

class MessageResponseDTO(BaseModel):
    response: str
    timestamp: datetime = datetime.now()