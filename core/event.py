from core.model import Contact
from core.entity.group import Group, Member
from core.extern.event.enums import EventType
from core.message import Message
from pydantic import BaseModel


class BaseEvent:

    def __init__(self, type: EventType) -> None:
        self.type: EventType

        self.type = type


class GroupMessageRecvEvent(BaseEvent):

    def __init__(self, data: dict) -> None:
        self.msg: Message
        self.sender: Member
        self.group: Group

        super().__init__(EventType.GroupMessageEvent)
        senderInfo = data['sender']
        id = senderInfo['id']
        memberName = senderInfo['memberName']
        permission = senderInfo['permission']

        groupInfo = senderInfo['group']
        groupId = groupInfo['id']
        groupName = groupInfo['name']
        groupPermission = groupInfo['permission']

        self.msg = Message(chain=data['messageChain'])
        self.sender = Member(
            id=id,
            memberName=memberName,
            permission=permission
        )
        self.group = Group(
            id=groupId,
            groupName=groupName,
            permission=groupPermission
        )       


class ContactMessageRecvEvent(BaseEvent):

    def __init__(self, data: dict) -> None:
        self.sender: Contact
        self.msg: Message

        super().__init__(EventType.ContactMessageEvent)
        self.msg = Message(chain=data['messageChain'])
