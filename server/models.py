import typing
from datetime import datetime

from pydantic import BaseModel


class UserCreate(BaseModel):
    name: str
    email: str
    age: int

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    age: int
    created_at: datetime

class UserUpdate(BaseModel):
    name: typing.Optional[str] = None
    email: typing.Optional[str] = None
    age: typing.Optional[int] = None