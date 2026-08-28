from pydantic import BaseModel

class UserPrompt(BaseModel):
    message: str

class AIResponse(BaseModel):
    reply: str
    status: str