from pydantic import BaseModel, validator

class ChatMessage(BaseModel):
    content: str

    @validator('content')
    def content_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Message cannot be empty')
        if len(v) > 2000:
            raise ValueError('Message too long — max 2000 characters')
        return v.strip()

class CustomCase(BaseModel):
    case_text: str

    @validator('case_text')
    def case_text_valid(cls, v):
        if not v or len(v.strip()) < 50:
            raise ValueError('Case text too short — add more clinical details')
        if len(v) > 5000:
            raise ValueError('Case text too long — max 5000 characters')
        return v.strip()