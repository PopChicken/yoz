import re
import yaml

from pydantic.dataclasses import dataclass
from bisect import bisect_left
from typing import Any, Dict
from queue import Queue
from enum import Enum, unique

from core.message import Message
from core.message import RefMsg
from core.loader import CommandType, Loader
from core.extern.config import Config
from core.application import App
from core.event import GroupMessageRecvEvent


config = Config('solo')

settings = {
    'enabled_groups': [],
    'valid_span': 10 * 60, # 单位秒
    'max_stack': 10
}


@unique
class CommandType(Enum):
    Solo = 0,
    Refuse = 1,
    Abandon = 2,
    Check = 3,
    SoloEnhanced = 4


class Command:
    def __init__(self) -> None:
        self.type: CommandType
        self.arg: str


class Challenge:
    def __init__(self) -> None:
        self.bigPin: bool
        self.toId: int
        self.timeLeft: int
        self.stack: int


@dataclass
class Database:
    groupId: int
    commandQueue: "Queue[Command]" = Queue()

challenges: Dict[int, Dict[int, Challenge]]


def existElem(l: list, elem: Any) -> bool:
    i = bisect_left(l, elem)
    if i != len(l) and l[i] == elem:
        return True
    return False


@Loader.listen('Load')
async def onLoad(app: App):
    global settings

    settings_tmp = settings.copy()

    haveError = False

    conf = config.getf('conf.yml')
    if conf is None:
        conf = config.touch('conf.yml')
    else:
        newSettings = yaml.load(conf, Loader=yaml.FullLoader)
        try:
            settings_tmp = config.update(settings, newSettings)
        except Exception as e:
            print('配置文件损坏，重置为默认配置，旧文件备份为 conf.yml.bkp')
            try:
                config.backup('conf.yml')
            except Exception as e:
                print('备份失败，使用默认配置，取消覆写 conf.yml')

    conf.seek(0)
    conf.truncate()

    if not haveError:
        settings = settings_tmp
        yaml.dump(settings_tmp, conf)

    settings['enabled_groups'].sort()
    
    conf.close()

    print('Solo加载成功')


@Loader.command('拼点', CommandType.Group)
async def Solo(app: App, e: GroupMessageRecvEvent):
    arguments = str(e.msg).strip()

    if len(arguments) == 0:
        app.sendGroupMessage(e.group, Message.phrase(
            RefMsg(target=e.sender.id),
            ("欢迎来玩拼点~\n"
            "“拼点@对方”可以下达战书或者应战\n"
            "“不拼@对方”可以拒绝对方的挑战\n"
            "“弃拼”可以放弃挑战\n"
            "“查战书”可以查看有谁向你发起了挑战\n"
            "“大拼点n倍@对方”可以向对方发起赌上尊严的挑战（倍率为n哦）！\n"
            "【注意】已经有等待对方接受的战书后，就不能再发战书了哦~\n"
            "【注意】大拼点会占用拼点的战书槽，且要用“大拼点@对方”进行应战")
        ))

@Loader.command('不拼', CommandType.Group)
async def Solo(app: App, e: GroupMessageRecvEvent):
    arguments = str(e.msg).strip()

    if len(arguments) == 0:
        app.sendGroupMessage(e.group, Message.phrase(
            RefMsg(target=e.sender.id),
            "你没有at你的对手喔~"
        ))
    pass

@Loader.command('弃拼', CommandType.Group)
async def Solo(app: App, e: GroupMessageRecvEvent):
    arguments = str(e.msg).strip()

    if len(arguments) == 0:
        app.sendGroupMessage(e.group, Message.phrase(
            RefMsg(target=e.sender.id),
            ("已放弃挑战~")
        ))

@Loader.command('查战书', CommandType.Group)
async def Solo(app: App, e: GroupMessageRecvEvent):
    arguments = str(e.msg).strip()

    if len(arguments) == 0:
        app.sendGroupMessage(e.group, Message.phrase(
            RefMsg(target=e.sender.id),
            (""
            "")
        ))

@Loader.command('大拼点', CommandType.Group)
async def Solo(app: App, e: GroupMessageRecvEvent):
    arguments = str(e.msg).strip()

    if len(arguments) == 0:
        app.sendGroupMessage(e.group, Message.phrase(
            RefMsg(target=e.sender.id),
            ("请at你的对手喔~")
        ))