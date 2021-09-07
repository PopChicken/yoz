import re
from util.crontab import Crontab
import yaml
import time
import random

from threading import Lock
from core.extern.message.enums import MessageType

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
    def __init__(self, app: App, group: int, initiator: int, target: int,
                 enhanced: bool, ratio: int) -> None:
        self.app: App = app
        self.group: int = group
        self.enhanced: bool = enhanced
        self.initiator: int = initiator
        self.target: int = target
        self.ratio: int = ratio
        self.timestamp: int = time.time()
    
    def getValidTimeStr(self) -> str:
        validSec = round(settings['valid_span'] - time.time() + self.timestamp)
        if validSec >= 60:
            return f"{int(validSec / 60)}分{validSec % 60}秒"
        return f"{int(validSec)}秒"
    
    def getValidTimeSec(self) -> int:
        return round(settings['valid_span'] - time.time() + self.timestamp)


lockDB: Dict[int, Dict[int, Lock]] = {}
statusDB: Dict[int, set[SoloStatus]] = {}
requestsDB: Dict[int, Dict[int, Dict[int, Challenge]]] = {}
challengerDB: Dict[int, Dict[int, Challenge]] = {}

crontab = Crontab()


class Command:
    def __init__(self) -> None:
        self.type: CommandType
        self.arg: str


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
    if status.Idle and id in statusDB[group]:
        statusDB[group].remove(id)
    else:
        statusDB[group].add(id)


def getLock(group: int, id: int) -> Lock:
    global lockDB

    locks = lockDB[group]
    lock = locks.get(id)
    if lock is not None:
        return lock
    lock = Lock()
    locks[id] = lock
    return lock


def handleTimeout(challenge: Challenge) -> None:
    with (getLock(challenge.group, challenge.initiator), getLock(challenge.group, challenge.target)):
        transit(challenge.app, challenge.group, challenge.initiator, SoloCommandType.Timeout)


def getChallengeFrom(group: int, sender: int) -> Challenge | None:
    global challengerDB
    groupChallenges = challengerDB[group]
    senderChallenge = groupChallenges.get(sender)
    return senderChallenge


def getChallengesOn(group: int, target: int) -> Dict[int, Challenge] | None:
    global requestsDB
    groupRequests = requestsDB[group]
    targetChallenges = groupRequests.get(target)
    return targetChallenges


def removeChallengeFrom(group: int, sender: int) -> None:
    ch = getChallengeFrom(group, sender)
    if ch is None:
        return
    try:
        del requestsDB[group][ch.target][sender]
    finally:
        pass
    try:
        del challengerDB[group][sender]
    finally:
        pass


def initiateChallenge(app: App, group: int, sender: int, acceptor: int,
                      enhanced: bool = False, ratio: int = 1) -> None:
    challenge = Challenge(app, group, sender, acceptor, enhanced, ratio)
    requestsDB[group].setdefault(acceptor, {})
    requestsDB[group][acceptor][sender] = challenge
    challengerDB[group][sender] = challenge

    crontab.add(f'{str(group)}-{str(sender)}', settings['valid_span'], handleTimeout, (challenge, ))


def versus(app: App, group: int, challenge: Challenge, attacker: int, defender: int):
    roundMsg = Message()
    if challenge.enhanced:
        roundMsg.parseAppend(
            f"{RefMsg(target=attacker)} 与{RefMsg(target=defender)} 赌上尊严的对决开始了！\n"
        )
    else:
        roundMsg.parseAppend(
            f"{RefMsg(target=attacker)} 与{RefMsg(target=defender)} 的对决开始了！\n"
        )
    attack = random.randint(1, 6)
    defend = random.randint(1, 6)
    draw = False
    winner = None
    loser = None
    roundMsg.parseAppend(
        f"挑战者{RefMsg(target=attacker)} 掷出了{attack}点！\n" +
        f"应战者{RefMsg(target=defender)} 掷出了{defend}点！\n"
    )
    if attack > defend:
        winner = attacker
        loser = defender
        roundMsg.parseAppend(
            f"挑战者{RefMsg(target=attacker)} 击败了应战者{RefMsg(target=defender)}\n"
        )
    elif attack == defend:
        draw = True
        roundMsg.parseAppend(
            f"挑战者{RefMsg(target=attacker)} 与应战者{RefMsg(target=defender)} 和局~\n"
        )
    else:
        winner = defender
        loser = attacker
        roundMsg.parseAppend(
            f"应战者{RefMsg(target=defender)} 击败了挑战者{RefMsg(target=attacker)}\n"
        )
    
    if challenge.enhanced:
        if draw:
            roundMsg.parseAppend(
                f"和局~没有人会被惩罚w\n"
            )
        else:
            roundMsg.parseAppend(
                f"{RefMsg(target=loser)} 在大拼点中被击败了！接受处罚吧！\n"
            )
            app.mute(group, loser, int(challenge.ratio * abs(attack - defend) * 60))
    
    removeChallengeFrom(group, attacker)
    app.sendGroupMessage(group, roundMsg)


def transit(app: App, group: int, initiator: int, type: SoloCommandType,
            target: int=None, ratio: int=None) -> None:
    initiatorStatus: SoloStatus = getStatus(group, initiator)
    targetStatus: SoloStatus = getStatus(group, target)
    if initiator == target:
        app.sendGroupMessage(group, Message.parse(
            RefMsg(target=initiator),
            " 不可以自雷的哦~"
        ))
        return

    match initiatorStatus:
        case SoloStatus.Idle:
            match type:
                case SoloCommandType.Solo | SoloCommandType.SoloEnhanced:
                    enhanced = False
                    if type == SoloCommandType.SoloEnhanced:
                        enhanced = True
                    if targetStatus == SoloStatus.Waiting:
                        challenge: Challenge = getChallengeFrom(group, target)
                        if challenge is not None and challenge.target == initiator:
                            if challenge.enhanced != enhanced:
                                app.sendGroupMessage(group, Message.parse(
                                    RefMsg(target=initiator),
                                    " 要使用相同类型的指令进行应战喔~"
                                ))
                                return
                            versus(app, group, challenge, target, initiator)
                            setStatus(group, target, SoloStatus.Idle)
                            return
                    initiateChallenge(app, group, initiator, target, enhanced, ratio)
                    setStatus(group, initiator, SoloStatus.Waiting)
                    app.sendGroupMessage(group, Message.parse(
                        RefMsg(target=initiator),
                        " 成功向",
                        RefMsg(target=target),
                        " 发起挑战~"
                    ))
                case SoloCommandType.Abandon:
                    app.sendGroupMessage(group, Message.parse(
                        RefMsg(target=initiator),
                        " 你还没有发起挑战~"
                    ))
                case SoloCommandType.Refuse:
                    challenge = getChallengeFrom(group, target)
                    if challenge is None:
                        app.sendGroupMessage(group, Message.parse(
                            RefMsg(target=initiator),
                            " 对方并没有挑战你哦~"
                        ))
                    else:
                        removeChallengeFrom(group, target)
                        setStatus(group, target, SoloStatus.Idle)
                        app.sendGroupMessage(group, Message.parse(
                            RefMsg(target=initiator),
                            " 你拒绝了对方的挑战！"
                        ))
        case SoloStatus.Waiting:
            match type:
                case SoloCommandType.Solo | SoloCommandType.SoloEnhanced:
                    enhanced = False
                    if type == SoloCommandType.SoloEnhanced:
                        enhanced = True
                    if targetStatus == SoloStatus.Waiting:
                        challenge: Challenge = getChallengeFrom(group, target)
                        if challenge is not None and challenge.target == initiator:
                            if challenge.enhanced != enhanced:
                                app.sendGroupMessage(group, Message.parse(
                                    RefMsg(target=initiator),
                                    " 要使用相同类型的指令进行应战喔~"
                                ))
                                return
                            versus(app, group, challenge, target, initiator)
                            setStatus(group, target, SoloStatus.Idle)
                            return
                    app.sendGroupMessage(group, Message.parse(
                        RefMsg(target=initiator),
                        " 你已经发起了一个挑战~"
                    ))
                case SoloCommandType.Abandon:
                    removeChallengeFrom(group, initiator)
                    setStatus(group, initiator, SoloStatus.Idle)
                    app.sendGroupMessage(group, Message.parse(
                        RefMsg(target=initiator),
                        " 成功放弃挑战~"
                    ))
                case SoloCommandType.Refuse:
                    challenge = getChallengeFrom(group, target)
                    if challenge is None:
                        app.sendGroupMessage(group, Message.parse(
                            RefMsg(target=initiator),
                            " 对方并没有挑战你哦~"
                        ))
                    else:
                        removeChallengeFrom(group, target)
                        setStatus(group, target, SoloStatus.Idle)
                        app.sendGroupMessage(group, Message.parse(
                            RefMsg(target=initiator),
                            " 你拒绝了对方的挑战！"
                        ))
                case SoloCommandType.Timeout:   # 系统发起，无需校验
                    if getChallengeFrom(group, initiator) is not None:
                        removeChallengeFrom(group, initiator)


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
        statusDB[int(group)] = set()
        challengerDB[int(group)] = {}
        requestsDB[int(group)] = {}
        lockDB[int(group)] = {}

    App.logger.info('Solo加载成功')


def handleSolo(app: App, e: GroupMessageRecvEvent, enhanced: bool = False):
    msg = e.msg.strip()
    arguments = str(msg).strip()
    senderId = e.sender.id
    groupId = e.group.id

    if len(arguments) == 0:
        app.sendGroupMessage(groupId, Message.parse(
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
        if msg[0].type == MessageType.TextMessage:
            match = re.match(pattern, str(msg[0]))
            if match is None or len(msg.msgChain) < 2:
                app.sendGroupMessage(groupId, Message.parse(
                    RefMsg(target=e.sender.id),
                    " 格式不对喔~"
                ))
                return
            ratioStr = match.group(2)
            if ratioStr is not None:
                ratio = int(ratioStr)
            msg = msg[1:]
        if msg[0].type != MessageType.AtMessage:
            app.sendGroupMessage(groupId, Message.parse(
                RefMsg(target=e.sender.id),
                " 格式不对喔~"
            ))
            return
    else:
        if msg[0].type != MessageType.AtMessage:
            app.sendGroupMessage(groupId, Message.parse(
                RefMsg(target=e.sender.id),
                " 格式不对喔~"
            ))
            return

    if not 1 <= ratio <= settings['max_stack']:
        app.sendGroupMessage(groupId, Message.parse(
            RefMsg(target=e.sender.id),
            f" 倍率只可以是2到{settings['max_stack']}范围内的整数哦~"
        ))
        return

    targetId = msg[0].target

    type = SoloCommandType.Solo
    if enhanced:
        type = SoloCommandType.SoloEnhanced
    
    if targetId == senderId:
        with getLock(groupId, senderId):
            transit(app, groupId, senderId, type, targetId, ratio)
    else:
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
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 你没有at你的拒绝对象喔~"
        ))
    
    msg = e.msg.strip()
    if len(msg.msgChain) == 0 or msg[0].type != MessageType.AtMessage:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 格式不对喔~"
        ))
    target = msg[0].target

    with (getLock(e.group.id, e.sender.id), getLock(e.group.id, target)):
        transit(app, e.group.id, e.sender.id, SoloCommandType.Refuse, target)


@Loader.command('弃拼', CommandType.Group)
def Solo(app: App, e: GroupMessageRecvEvent):
    arguments = str(e.msg).strip()
    senderId = e.sender.id
    groupId = e.group.id

    senderStatus: SoloStatus = getStatus(groupId, senderId)
    if senderStatus == SoloStatus.Idle:
        app.sendGroupMessage(groupId, Message.parse(
            RefMsg(target=e.sender.id),
            " 你还没有向别人发起挑战喔~"
        ))
        return

    if len(arguments) > 0:
        app.sendGroupMessage(groupId, Message.parse(
            RefMsg(target=e.sender.id),
            " 格式不对喔~"
        ))
    with getLock(groupId, senderId):
        transit(app, groupId, senderId, SoloCommandType.Abandon)


@Loader.command('查战书', CommandType.Group)
def Solo(app: App, e: GroupMessageRecvEvent):
    arguments = str(e.msg).strip()

    if len(arguments) > 0:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 格式不对喔~"
        ))
    
    with getLock(e.group.id, e.sender.id):
        requests = getChallengesOn(e.group.id, e.sender.id)
        if requests is None or len(requests) == 0:
            app.sendGroupMessage(e.group.id, Message.parse(
                RefMsg(target=e.sender.id),
                " 你还没有收到挑战喔~"
            ))
        else:
            reply = Message(raw="目前你收到的战书有：\n挑战者  类型  有效时间\n")
            for _, req in requests.items():
                member = app.getMemberInfo(req.group, req.initiator)
                type = ""
                if req.enhanced:
                    type = "大"
                reply.parseAppend(
                    f"{member.inGroupName} {type}拼点 {req.getValidTimeStr()}\n")
            app.sendGroupMessage(e.group.id, reply)

