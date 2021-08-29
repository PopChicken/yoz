from enum import Enum, unique

@unique
class EventType(Enum):
    GroupMessageEvent = 'GroupMessageEvent'
    ContactMessageEvent = 'ContactMessageEvent'
    GroupRecallEvent = 'GroupRecallEvent'
