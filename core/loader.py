from typing import Any, Awaitable, Callable, Dict, List
from enum import Enum


class CommandType(Enum):
    Group = 0,
    Contact = 1


class Loader:
    eventsListener: Dict[
        str, List[Callable[[Any], Awaitable]]
    ] = {}

    groupCommands: Dict[
        str, Callable
    ] = {}

    contactCommands: Dict[
        str, Callable
    ] = {}

    @classmethod
    def listen(cls, eventName: str):
        def lis_decorator(func: Callable):
            cls.eventsListener.setdefault(eventName, [])
            cls.eventsListener[eventName].append(func)
            return func
        return lis_decorator
    
    @classmethod
    def command(cls, command: str, base: CommandType):
        def cmd_decorator(func: Callable):
            if base == CommandType.Group:
                if command in cls.groupCommands:
                    raise Exception("指令重复注册")
                cls.groupCommands[command] = func
            elif base == CommandType.Contact:
                if command in cls.contactCommands:
                    raise Exception("指令重复注册")
                cls.contactCommands[command] = func
            return func
        return cmd_decorator
