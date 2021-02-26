import re
import yaml
import time
import _thread

from bisect import bisect_left
from typing import Any, Dict
from queue import Queue

from core.message import Message
from core.message import RefMsg
from core.loader import CommandType, Loader
from core.extern.config import Config
from core.application import App
from core.event import GroupMessageRecvEvent
from core.entity.group import PermissionType


config = Config('revolver')

settings = {
    'enabled_groups': [],
    'timeout': 10 * 60
}


class Cooldown:
    def __init__(self, id: int, unlockAt: int) -> None:
        self.groupId: int = id
        self.unlockTime: int = unlockAt


class Info:
    def __init__(self, idle: bool, last: str) -> None:
        self.idle = idle


groupInfo: Dict[int, Info] = {}
cooldownQueue: "Queue[Cooldown]" = Queue()


def cooldown_thread():
    t_now = int(time.time())
    while True:
        cd = cooldownQueue.get(True)

        t_later = cd.unlockTime
        time.sleep((t_later - t_now) / 1000.0)
        
        groupInfo[cd.groupId].idle = True


@Loader.listen('Load')
async def onLoad(app: App):
    global settings

    settings_tmp = settings.copy()

    haveError = False

    conf = config.getf('conf.yaml')
    if conf is None:
        conf = config.touch('conf.yaml')
    else:
        newSettings = yaml.load(conf, Loader=yaml.FullLoader)
        try:
            settings_tmp = config.update(settings, newSettings)
        except Exception as e:
            print('配置文件损坏，重置为默认配置，旧文件备份为 conf.yml.bkp')
            try:
                config.backup('conf.yaml')
            except Exception as e:
                print('备份失败，使用默认配置，取消覆写 conf.yml')

    conf.seek(0)
    conf.truncate()

    if not haveError:
        settings = settings_tmp
        yaml.dump(settings_tmp, conf)

    settings['enabled_groups'].sort()
    
    conf.close()

    _thread.start_new_thread(cooldown_thread, ())

    print('Revolver加载成功')


def existElem(l: list, elem: Any) -> bool:
    i = bisect_left(l, elem)
    if i != len(l) and l[i] == elem:
        return True
    return False


@Loader.command('转轮手枪', CommandType.Group)
async def onCommand(app: App, e: GroupMessageRecvEvent):
    groupId = e.group.id
    argument = str(e.msg).strip()

    if e.group.permission == PermissionType.Member:
        return

    if not existElem(settings['enabled_groups'], groupId):
        return
    
    if len(argument) == 0:
        app.sendGroupMessage(groupId, Message.phrase(
            RefMsg(target=e.sender.id),
            ("欢迎来玩转轮手枪~\n"
            "嘎嘎嘎~这是一个恐怖的游戏！\n"
            f"{app.nickname}会为一把六发左轮的弹舱随机装入一发弹药\n"
            f"使用“{app.commandHead}扣扳机”来参加比赛 嘻嘻嘻\n"
            "与赛的各位，依次把枪口调向自己，扣动扳机，直到...砰——子弹出膛！")
        ))
    
    if groupInfo[groupId.id].idle:
        app.sendGroupMessage(groupId, Message.phrase(
            RefMsg(target=e.sender.id),
            "已经重新装填弹药咯！"
        ))
    else:
        app.sendGroupMessage(groupId, Message.phrase(
            RefMsg(target=e.sender.id),
            "本轮比赛还没有结束哟~"
        ))


@Loader.command('扣扳机', CommandType.Group)
async def onCommand(app: App, e: GroupMessageRecvEvent):
    groupId = e.group.id

    if e.group.permission == PermissionType.Member:
        return

    if not existElem(settings['enabled_groups'], groupId):
        return
    
