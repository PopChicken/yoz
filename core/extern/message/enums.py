from enum import Enum

class MessageType(Enum):
    AtMessage = 'At'
    TextMessage = 'Plain'
    ImageMessage = 'Image'