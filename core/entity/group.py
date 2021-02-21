from enum import Enum


class PermissionType(Enum):
    Owner = 1
    Admin = 2
    Member = 3
    

class Member:

    def __init__(self, id: int, memberName: str, permission: str) -> None:
        self.id: int
        self.inGroupName: str
        self.permission: PermissionType

        self.id = id
        self.inGroupName = memberName
        self.permission = PermissionType[permission]


class Group:

    def __init__(self, id: int, groupName: str, permission: str) -> None:
        self.id: int
        self.name: str
        self.permission: PermissionType

        self.id = id
        self.name = groupName
        self.permission = PermissionType[permission]
