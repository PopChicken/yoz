from pydantic.main import BaseModel
from .message import Message


class Contact(BaseModel):

    def __init__(self) -> None:
        self.id: int
        self.remarkName: str
