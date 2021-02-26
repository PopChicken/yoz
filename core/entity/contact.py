import re
from core.message import Message


class Contact:

    def __init__(self, id: int, nickname: str, remark: str) -> None:
        self.id: int = id
        self.nickname: str = nickname
        self.remark: str = remark
