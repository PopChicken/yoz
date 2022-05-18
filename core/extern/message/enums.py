from enum import Enum, unique


@unique
class MessageType(Enum):
    AtMessage = 'At'
    TextMessage = 'Plain'
    ImageMessage = 'Image'
