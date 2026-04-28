from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import uuid


AgentStatus = Literal["running", "stopped", "starting", "error"]
MessageRole = Literal["user", "assistant", "system"]
MessageType = Literal["text", "command", "output", "error"]


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: Optional[str] = Field(None, max_length=256)


class Agent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    description: Optional[str] = None
    status: AgentStatus = "stopped"
    container_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    last_active: Optional[str] = None


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    role: MessageRole
    type: MessageType = "text"
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
