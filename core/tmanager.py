from core.application import App
import sys
from threading import Thread
from enum import Enum
from queue import Queue
import traceback
from typing import Any, Callable, Dict, Iterable


TASK_TIMEOUT = 1


class InfoClass:

    def __init__(self) -> None:
        self.listener: Callable
        self.app = Any
        self.e = Any


class TaskExecuteResult(Enum):
    Success = 0
    Fail = 1
    Timeout = 2


class ThreadManager:

    def __init__(self) -> None:
        self.__results: "Queue[TaskExecuteResult]" = Queue()
        pass

    def execute(self, func: Callable, args: Iterable):
        def executor(): # 用于执行
            class ExceptionResult:  # 用于储存异常信息
                def __init__(self) -> None:
                    self.exitcode: int = 0
                    self.exception: Exception = None
                    self.exc_traceback: str = ''

            def run(result: ExceptionResult):  # 用于实际执行与捕获异常
                try:
                    func(*args)
                except Exception as ex:
                    result.exitcode = 1
                    result.exception = ex
                    result.exc_traceback = ''.join(traceback.format_exception(*sys.exc_info()))
                    App.logger.warning("Error occurred in plugin\n" + result.exc_traceback)

            res = ExceptionResult()
            t = Thread(target=run, args=(res, ))
            t.setName(f'{func.__module__}-' + t.getName())
            t.setDaemon(True)
            t.start()

            t.join(TASK_TIMEOUT)

            if t.is_alive():
                self.__results.put(TaskExecuteResult.Timeout)
            elif res.exitcode == 1: # 未捕获的异常
                self.__results.put(TaskExecuteResult.Fail)
            else:
                self.__results.put(TaskExecuteResult.Success)

        Thread(target=executor).start()
