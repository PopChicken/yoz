import uuid
import threading
import _thread
import time

from typing import Callable, Type
from llist import dllist


class Crontab:

    def __init__(self) -> None:
        self.__tasks = dllist()
        self.uuids = set()
        self.__timeline: Timeline

        self.__timeline = Timeline(str(uuid.uuid4()), self, self.__tasks)
        self.__timeline.setDaemon(True)
        self.__timeline.start()

    def add(self, uuid: str, delay: float, callback: Callable, args: tuple = None):
        if args is None:
            args = tuple()
        timeNow = time.time()
        self.__insert((uuid, timeNow + delay, callback, args))

    def addabs(self, uuid: str, timestamp: float, callback: Callable, args: tuple = None):
        if args is None:
            args = tuple()
        self.__insert((uuid, timestamp, callback, args))

    def remove(self, uuid):
        if uuid not in self.uuids:
            # TODO raise exception
            pass
        self.uuids.remove(uuid)

    def __insert(self, v: tuple):
        with self.__timeline.lock:
            self.uuids.add(v[0])
            if self.__tasks.size == 0:
                self.__tasks.append(v)
            else:
                node = self.__tasks.first
                while node is not None:
                    if v[1] < node.value[1]:
                        break
                    node = node.next
                self.__tasks.insert(v, node)

            self.__timeline.act.set()


class Timeline(threading.Thread):

    def __init__(self, name, crontab: Crontab, tasks: Type[dllist]):
        threading.Thread.__init__(self)
        self.name = name
        self.tasks = tasks
        self.lock = threading.RLock()
        self.crontab = crontab
        self.act = threading.Event()

    def run(self):
        while True:
            if self.tasks.size == 0:
                self.act.wait()

            with self.lock:
                node = self.tasks.first

                empty = False
                while node.value[0] not in self.crontab.uuids:
                    self.tasks.popleft()
                    node = self.tasks.first
                    if node is None:
                        empty = True
                        break
                if empty:
                    continue
                task = node.value
                duration = task[1] - time.time()
            if duration > 0:
                self.act.wait(duration)
            if self.act.is_set():
                self.act.clear()
                continue
            with self.lock:
                self.act.clear()
                func = task[2]
                args = task[3]
                _thread.start_new_thread(func, args)
                self.crontab.uuids.remove(task[0])
                self.tasks.popleft()
