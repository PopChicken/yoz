from core.message import Message, RefMsg
import yaml
import time
import _thread
import random

from bisect import bisect_left
from typing import Any, Dict
from collections import OrderedDict

from core.extern.config import Config
from core.application import App
from core.event import GroupMessageRecvEvent, GroupRecallEvent
from core.loader import Loader


class Cooldown:
    def __init__(self, id: int, unlockAt: int) -> None:
        self.groupId: int = id
        self.unlockTime: int = unlockAt


msgDB: "OrderedDict[int, Message]" = OrderedDict()

config = Config('norecall')

settings = {
    'enabled_groups': []
}
    

def existElem(l: list, elem: Any) -> bool:
    i = bisect_left(l, elem)
    if i != len(l) and l[i] == elem:
        return True
    return False


@Loader.listen('Load')
def onLoad(app: App):
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
            app.logger.info('配置文件损坏，重置为默认配置，旧文件备份为 conf.yml.bkp')
            try:
                config.backup('conf.yml')
            except Exception as e:
                app.logger.info('备份失败，使用默认配置，取消覆写 conf.yml')

    conf.seek(0)
    conf.truncate()

    if not haveError:
        settings = settings_tmp
        yaml.dump(settings_tmp, conf)

    settings['enabled_groups'].sort()
    
    conf.close()

    app.logger.info('NoRecall loaded successfully')


def updateCache(msg: Message):
    global msgDB
    
    msgDB[msg.uid] = msg
    popTime = 0
    for _, v in msgDB.items():
        if msg.time - v.time > 120:
            popTime += 1
    for i in range(popTime):
        msgDB.popitem(False)


@Loader.listen('GroupMessage')
def onRecvGroupMessage(app: App, e: GroupMessageRecvEvent):
    groupId = e.group.id
    message = e.msg

    if not existElem(settings['enabled_groups'], groupId):
        return
    
    updateCache(message)


@Loader.listen('GroupRecallEvent')
def onGroupRecallEvent(app: App, e: GroupRecallEvent):
    global msgDB
    
    groupId = e.group.id
    msgId = e.msgId

    if not existElem(settings['enabled_groups'], groupId):
        return

    if msgId not in msgDB:
        app.sendGroupMessage(groupId, Message.phrase(
            RefMsg(target=e.operator.id),
            (" 好可惜呀！没记住说了啥~嘻嘻")
        ))
        return
    
    reply = Message.phrase(
        RefMsg(target=e.operator.id)
        ,(": ")
    )
    reply.append(msgDB[msgId])
    app.sendGroupMessage(groupId, reply)

