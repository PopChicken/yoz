from abc import ABC, abstractmethod
from typing import Dict, overload
from core.message import Message
from core.entity.group import Group
from core.model import Contact
from pydantic import BaseModel


class App(ABC):

    def __init__(self) -> None:
        self.nickname: str
        self.commandHead: str

    @abstractmethod
    def run(self):
        pass
    
    @abstractmethod
    @overload
    def sendGroupMessage(self, target: Group, message: Message):
        pass

    @abstractmethod
    @overload
    def sendGroupMessage(self, target: Group, message: str):
        pass

    @abstractmethod
    def sendGroupMessage(self, target, message):
        """发送群消息"""
        pass
    
    @abstractmethod
    def mute(self, group: Group, id: int, time: int):
        """对群成员禁言，单位分钟"""
        pass

    def unmute(self, group: Group, id: int, time: int):
        """对群成员解除禁言"""
        pass

    @abstractmethod
    def muteAll(self, group: Group):
        """对群开启全体禁言"""
        pass

    @abstractmethod
    def unmuteAll(self, group: Group):
        """对群关闭群体禁言"""
        pass