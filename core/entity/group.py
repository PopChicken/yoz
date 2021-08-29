from enum import Enum, unique


@unique
class PermissionType(Enum):
    Owner = 1
    Admin = 2
    Member = 3


class Member:

    def __init__(self, id: int, memberName: str, permission: str, joinTimestamp: int,
                 lastSpeakTimestamp: int, muteTimeRemaining: int) -> None:
        self.id: int = id
        self.inGroupName: str = memberName
        self.permission: PermissionType = PermissionType[permission]
        self.joinTimestamp: int = joinTimestamp
        self.lastSpeakTimestamp: int = lastSpeakTimestamp
        self.muteTimeRemaining: int = muteTimeRemaining


class Group:

    def __init__(self, id: int, groupName: str, permission: str) -> None:
        self.id: int = id
        self.name: str = groupName
        self.permission: PermissionType = PermissionType[permission]
