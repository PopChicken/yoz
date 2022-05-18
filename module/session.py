from typing import Any, Dict


class Session:

    def __init__(self) -> None:
        self.__stepId: int = 0
        self.cache: dict = {}
        self.keys: list = []

    def next(self) -> None:
        self.__stepId += 1

    def prev(self) -> None:
        if self.__stepId == 0:
            return
        self.__stepId -= 1

    def get(self, key: str) -> Any:
        if key in self.cache:
            return self.cache[key]
        else:
            return None

    def set(self, key: str, value: Any) -> None:
        self.cache[key] = value

    def getall(self) -> dict:
        return self.cache.copy()

    def step(self) -> int:
        return self.__stepId


class SessionLib:

    def __init__(self, moduleName: str) -> None:
        self.moduleName: str = moduleName
        self.contactSessions: Dict[int, Session] = {}
        self.groupSessions: Dict[int, Dict[int, Session]] = {}

    def createSession(self, id: int, groupId: int = None) -> Session:
        session = Session()
        if groupId is not None:
            self.groupSessions[groupId][id] = session
        else:
            self.contactSessions[id] = session
        return session

    def closeSession(self, id: int, groupId: int = None) -> None:
        if groupId is not None:
            if groupId in self.groupSessions and \
               id in self.groupSessions[groupId][id]:
                del self.groupSessions[groupId][id]
        else:
            if id in self.contactSessions:
                del self.contactSessions[id]

    def getSession(self, id: int, groupId: int = None) -> Session:
        if groupId is not None:
            if groupId in self.groupSessions and \
               id in self.groupSessions[groupId][id]:
                return self.groupSessions[groupId][id]
        else:
            if id in self.contactSessions:
                return self.contactSessions[id]
