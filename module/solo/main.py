import re
import yaml
import time

from threading import Lock
from core.extern.message.enums import MessageType

from pydantic.dataclasses import dataclass
from bisect import bisect_left
from typing import Any, Dict, List, Tuple
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
    'valid_span': 10 * 60,  # 单位秒
    'max_stack': 10
}


@unique
class SoloStatus(Enum):
    Idle = 0
    Waiting = 1


@unique
class SoloCommandType(Enum):
    Solo = 0
    Refuse = 1
    Abandon = 2
    Check = 3
    SoloEnhanced = 4
    Timeout = 5


class Challenge:
    def __init__(self, target: int, enhanced: bool, ratio: int) -> None:
        self.enhanced: bool = enhanced
        self.target: int = target
        self.ratio: int = ratio
        self.timestamp: int = time.time()


lockDB: Dict[int, Dict[int, Lock]] = {}
statusDB: Dict[int, set[SoloStatus]] = {}
requestsDB: Dict[int, Dict[int, Dict[int, Challenge]]] = {}
challengerDB: Dict[int, Dict[int, Challenge]] = {}


class Command:
    def __init__(self) -> None:
        self.type: CommandType
        self.arg: str


@dataclass
class Database:
    groupId: int
    commandQueue: "Queue[Command]" = Queue()


def existElem(l: list, elem: Any) -> bool:
    i = bisect_left(l, elem)
    if i != len(l) and l[i] == elem:
        return True
    return False


def getStatus(group: int, id: int) -> SoloStatus:
    global statusDB
    if id in statusDB[group]:
        return SoloStatus.Waiting
    return SoloStatus.Idle


def setStatus(group: int, id: int, status: SoloStatus) -> None:
    global statusDB
    statusDB[group][id] = status


def getLock(group: int, id: int) -> Lock:
    global lockDB

    locks = lockDB[group]
    lock = locks.get(id)
    if lock is not None:
        return lock
    lock = Lock()
    locks[id] = lock
    return lock


def getChallenge(group: int, sender: int, acceptor: int) -> Challenge | None:
    groupRequests = requestsDB[group]
    acceptorRequests = groupRequests.get(acceptor)
    if acceptorRequests is None:
        groupRequests[acceptor] = {}
        return None
    return groupRequests[acceptor].get(sender)


def cancelChallenge(group: int, sender: int, acceptor: int) -> None:
    try:
        del requestsDB[group][acceptor][sender]
        del challengerDB[group][sender]
    finally:
        pass

def initiateChallenge(group: int, sender: int, acceptor: int,
                      enhanced: bool = False, ratio: int = 1) -> None:
    challenge = Challenge(acceptor, enhanced, ratio)
    requestsDB[group][acceptor][sender] = challenge
    challengerDB[group][sender] = challenge


def versus(group: int, attacker: int, defender: int):
    pass


def transit(app: App, group: int, initiator: int, type: SoloCommandType,
            target: int=None, ratio: int=None) -> None:
    initiatorStatus: SoloStatus = getStatus(group, initiator)
    targetStatus: SoloStatus = getStatus(group, target)
    if initiator == target:
        app.sendGroupMessage(group, Message.phrase(
            RefMsg(target=initiator),
            "不可以自雷的哦~"
        ))
        return

    match initiatorStatus:
        case SoloStatus.Idle:
            match type:
                case SoloCommandType.Solo, SoloCommandType.SoloEnhanced:
                    enhanced = False
                    if type == SoloCommandType.SoloEnhanced:
                        enhanced = True
                    if targetStatus == SoloStatus.Waiting:
                        challenge = getChallenge(group, initiator, target)
                        if challenge is not None:
                            # 应战
                            setStatus(group, target, SoloStatus.Idle)
                            return
                    initiateChallenge(group, initiator, target, enhanced, ratio)
                    app.sendGroupMessage(group, Message.phrase(
                        RefMsg(target=initiator),
                        " 成功向",
                        RefMsg(target=target),
                        " 发起挑战~"
                    ))
                case SoloCommandType.Abandon:
                    app.sendGroupMessage(group, Message.phrase(
                        RefMsg(target=initiator),
                        " 你还没有发起挑战~"
                    ))
        case SoloStatus.Waiting:
            match type:
                case SoloCommandType.Solo, SoloCommandType.SoloEnhanced:
                    app.sendGroupMessage(group, Message.phrase(
                        RefMsg(target=initiator),
                        "你已经发起了一个挑战~"
                    ))
                case SoloCommandType.Abandon:
                    setStatus(group, initiator, SoloStatus.Idle)
                    app.sendGroupMessage(group, Message.phrase(
                        RefMsg(target=initiator),
                        "成功放弃挑战~"
                    ))
                case SoloCommandType.Timeout:   # 系统发起，无需校验
                    pass


@Loader.listen('Load')
def onLoad(app: App):
    global settings
    global statusDB

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

    for group in settings['enabled_groups']:
        statusDB[int(group)] = {}

    App.logger.info('Solo加载成功')


def handleSolo(app: App, e: GroupMessageRecvEvent, enhanced: bool = False):
    msg = e.msg.trim()
    arguments = str(msg).strip()
    senderId = e.sender.id
    groupId = e.group.id

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
        return

    ratio = 1.0

    if enhanced:
        pattern = r'^((\d+)倍|)\s*'
        ref = None
        if msg[0].type == MessageType.TextMessage:
            match = re.match(pattern, str(msg[0]))
            if match is None or len(msg.msgChain) < 2:
                app.sendGroupMessage(e.group, Message.phrase(
                    RefMsg(target=e.sender.id),
                    "格式不对喔~"
                ))
                return
            ratioStr = match.group(2)
            if ratioStr is not None:
                ratio = int(ratioStr)
            msg = msg[1:]
        if msg[0] != MessageType.AtMessage:
            app.sendGroupMessage(e.group, Message.phrase(
                RefMsg(target=e.sender.id),
                "格式不对喔~"
            ))
            return
    else:
        if msg[0].type != MessageType.AtMessage:
            app.sendGroupMessage(e.group, Message.phrase(
                RefMsg(target=e.sender.id),
                "格式不对喔~"
            ))
            return

    targetId = msg[0].target

    type = SoloCommandType.Solo
    if enhanced:
        type = SoloCommandType.SoloEnhanced
    with (getLock(groupId, senderId), getLock(groupId, targetId)):
        transit(app, groupId, senderId, type, targetId, ratio)


@Loader.command('拼点', CommandType.Group)
def Solo(app: App, e: GroupMessageRecvEvent):
    handleSolo(app, e)


@Loader.command('大拼点', CommandType.Group)
def Solo(app: App, e: GroupMessageRecvEvent):
    handleSolo(app, e, True)


@Loader.command('不拼', CommandType.Group)
def Solo(app: App, e: GroupMessageRecvEvent):
    arguments = str(e.msg).strip()

    if len(arguments) == 0:
        app.sendGroupMessage(e.group, Message.phrase(
            RefMsg(target=e.sender.id),
            "你没有at你的对手喔~"
        ))
    pass


@Loader.command('弃拼', CommandType.Group)
def Solo(app: App, e: GroupMessageRecvEvent):
    arguments = str(e.msg).strip()
    senderId = e.sender.id
    groupId = e.group.id

    senderStatus: SoloStatus = getStatus(groupId, senderId)
    if senderStatus == SoloStatus.Idle:
        app.sendGroupMessage(e.group, Message.phrase(
            RefMsg(target=e.sender.id),
            "你还没有向别人发起挑战喔~"
        ))
        return


@Loader.command('查战书', CommandType.Group)
def Solo(app: App, e: GroupMessageRecvEvent):
    arguments = str(e.msg).strip()

    if len(arguments) == 0:
        app.sendGroupMessage(e.group, Message.phrase(
            RefMsg(target=e.sender.id),
            (""
             "")
        ))
