from enum import Enum

from core.event import *

class Mirai2CoreEvents(Enum):
    GroupMessage = GroupMessageRecvEvent
    FriendMessage = ContactMessageRecvEvent