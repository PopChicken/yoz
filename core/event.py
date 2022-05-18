from core.entity.contact import Contact
from core.entity.group import Group, Member
from core.extern.event.enums import EventType
from core.message import Message


class BaseEvent:

    def __init__(self, type: EventType) -> None:
        self.type: EventType = type
        self.time: int = None


class GroupMessageRecvEvent(BaseEvent):

    def __init__(self, data: dict) -> None:
        self.msg: Message = None
        self.sender: Member = None
        self.group: Group = None

        super().__init__(EventType.GroupMessageEvent)
        senderInfo = data['sender']
        id = senderInfo['id']
        memberName = senderInfo['memberName']
        permission = senderInfo['permission']
        joinTimestamp = senderInfo['joinTimestamp']
        lastSpeakTimestamp = senderInfo['lastSpeakTimestamp']
        muteTimeRemaining = senderInfo['muteTimeRemaining']

        groupInfo = senderInfo['group']
        groupId = groupInfo['id']
        groupName = groupInfo['name']
        groupPermission = groupInfo['permission']

        self.msg = Message(chain=data['messageChain'])
        self.sender = Member(
            id=id,
            memberName=memberName,
            permission=permission,
            joinTimestamp=joinTimestamp,
            lastSpeakTimestamp=lastSpeakTimestamp,
            muteTimeRemaining=muteTimeRemaining
        )
        self.group = Group(
            id=groupId,
            groupName=groupName,
            permission=groupPermission
        )


class ContactMessageRecvEvent(BaseEvent):

    def __init__(self, data: dict) -> None:
        self.sender: Contact = None
        self.msg: Message = None

        super().__init__(EventType.ContactMessageEvent)

        senderInfo = data['sender']
        id = senderInfo['id']
        nickname = senderInfo['nickname']
        remark = senderInfo['remark']
        fromGroup = None
        if 'group' in senderInfo:
            fromGroup = senderInfo['group']['id']

        self.msg = Message(chain=data['messageChain'])
        self.sender = Contact(
            id=id,
            nickname=nickname,
            remark=remark,
            fromGroup=fromGroup
        )


class GroupRecallEvent(BaseEvent):
    def __init__(self, data: dict) -> None:
        self.msgId: Message = None
        self.operator: Member = None

        super().__init__(EventType.GroupRecallEvent)
        operatorInfo = data['operator']
        id = operatorInfo['id']
        memberName = operatorInfo['memberName']
        permission = operatorInfo['permission']
        joinTimestamp = operatorInfo['joinTimestamp']
        lastSpeakTimestamp = operatorInfo['lastSpeakTimestamp']
        muteTimeRemaining = operatorInfo['muteTimeRemaining']

        groupInfo = operatorInfo['group']
        groupId = groupInfo['id']
        groupName = groupInfo['name']
        groupPermission = groupInfo['permission']

        self.msgId = data['messageId']
        self.time = data['time']
        self.operator = Member(
            id=id,
            memberName=memberName,
            permission=permission,
            joinTimestamp=joinTimestamp,
            lastSpeakTimestamp=lastSpeakTimestamp,
            muteTimeRemaining=muteTimeRemaining
        )
        self.group = Group(
            id=groupId,
            groupName=groupName,
            permission=groupPermission
        )
