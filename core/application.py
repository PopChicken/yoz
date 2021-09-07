import logging
import coloredlogs

from abc import ABC, abstractmethod
from logging.handlers import QueueHandler, QueueListener
from queue import Queue
from typing import Callable, Dict, List, overload
from core.message import Message
from core.entity.group import Group, Member
from core.entity.contact import Contact
from core.log import PackagePathFilter


class App(ABC):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    def __init__(self) -> None:
        self.nickname: str = ''
        self.commandHead: str = ''

        logQueue = Queue()

        App.logger.addHandler(QueueHandler(logQueue))
        App.logger.addFilter(PackagePathFilter())

        cformatter = coloredlogs.ColoredFormatter('%(asctime)s  %(relativepath)s:%(lineno)s\t: %(levelname)s %(message)s')
        chandler = logging.StreamHandler()
        chandler.setFormatter(cformatter)

        formatter = logging.Formatter('%(asctime)s  %(relativepath)s:%(lineno)s\t: %(levelname)s %(message)s')
        fhandler = logging.FileHandler("yoz.log")
        fhandler.setFormatter(formatter)

        listener = QueueListener(logQueue, chandler, fhandler)
        listener.start()

    @abstractmethod
    def run(self):
        """启动运行"""
        pass

    @abstractmethod
    def redirect(self, guid: str, filter: dict, hook: Callable) -> None:
        pass

    @abstractmethod
    def redirectMember(self, guid: str, groupId: int, memberId: int, hook: Callable) -> None:
        pass

    @abstractmethod
    def redirectContact(self, guid: str, contactId: int, hook: Callable) -> None:
        pass

    @abstractmethod
    def unredirect(self, guid: str) -> None:
        pass
    
    @abstractmethod
    @overload
    def sendGroupMessage(self, group: int, message: Message) -> Message:
        pass

    @abstractmethod
    @overload
    def sendGroupMessage(self, group: int, message: str) -> Message:
        pass

    @abstractmethod
    def sendGroupMessage(self, group, message) -> Message:
        """发送群消息"""
        pass

    @abstractmethod
    def setSpecialTitle(self, group: int, id: int, title: str) -> None:
        pass
    
    @abstractmethod
    def mute(self, group: int, id: int, time: int) -> None:
        """对群成员禁言，单位分钟"""
        pass

    def unmute(self, group: int, id: int) -> None:
        """对群成员解除禁言"""
        pass

    @abstractmethod
    def muteAll(self, group: int) -> None:
        """对群开启全体禁言"""
        pass

    @abstractmethod
    def unmuteAll(self, group: int) -> None:
        """对群关闭群体禁言"""
        pass

    @abstractmethod
    @overload
    def sendContactMessage(self, contact: int, message: Message, group: int=None) -> Message:
        pass
    
    @abstractmethod
    @overload
    def sendContactMessage(self, contact: int, message: str, group: int=None) -> Message:
        pass

    @abstractmethod
    def sendContactMessage(self, contact, message, group: int=None) -> Message:
        """发送联系人消息（group参数适配mirai）"""
        pass

    @abstractmethod
    def replyContactMessage(self, sender: Contact, message) -> Message:
        """回复联系人消息"""
        pass

    @abstractmethod
    def recall(self, messageId: int) -> None:
        """撤回消息"""
        pass

    @abstractmethod
    def sendWebImage(self, urls: List[str], contactId: int=None, groupId: int=None) -> Message:
        """发送URL图片"""
        pass

    @abstractmethod
    def getContactList(self) -> List[Contact]:
        """获得联系人列表 *联系人模型还没有设计完"""
        pass

    @abstractmethod
    def getGroupList(self) -> List[Group]:
        """获取群列表"""
        pass

    @abstractmethod
    def getMemberList(self, group: int) -> List[Member]:
        """获取群成员列表（Member模型还未验证）"""
        pass

    @abstractmethod
    def getMemberInfo(self, group: int, target: int) -> Member:
        """获取群成员信息"""
        pass

    @abstractmethod
    def kick(self, group: int, target: int, msg: str) -> None:
        """踢出成员，需要权限，注意异常处理（异常还未设计）"""
        pass

    @abstractmethod
    def quit(self, group: int) -> None:
        """退群，群主不能退群，注意异常处理（异常还未设计）"""
        pass
