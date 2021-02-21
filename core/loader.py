from typing import Any, Awaitable, Callable, Dict, List

from pydantic.errors import ClassError


class Loader:
    eventsListener: Dict[
        str, List[Callable[[Any], Awaitable]]
    ] = {}

    groupCommands: Dict[
        str, Callable
    ] = {}

    allCommands: Dict[
        str, Callable
    ]

    @classmethod
    def listen(cls, eventName: str):
        def lis_decorator(func: Callable):
            cls.eventsListener.setdefault(eventName, [])
            cls.eventsListener[eventName].append(func)
            return func
        return lis_decorator
    
    @classmethod
    def command(cls, command: str, baseEvent: str = None):
        def cmd_decorator(func: Callable):
            if baseEvent == 'GroupMessage':
                cls.groupCommands[command, func]
            elif baseEvent == 'ContactMessage':
                cls.contactCommands[command, func]
            return func
        return cmd_decorator
