import yaml
import time
import _thread
import random

from queue import Queue
from bisect import bisect_left
from typing import Any, Dict

from core.extern.config import Config
from core.application import App
from core.event import GroupMessageRecvEvent
from core.loader import Loader


class Cooldown:
    def __init__(self, id: int, unlockAt: int) -> None:
        self.groupId: int = id
        self.unlockTime: int = unlockAt


class Info:
    def __init__(self, idle: bool, last: str) -> None:
        self.idle = idle
        self.last = last


groupInfo: Dict[int, Info] = {}
cooldownQueue: "Queue[Cooldown]" = Queue()

config = Config('repeater')

settings = {
    'repeat_prob': 0.4,
    'enabled_groups': [],
    'banned_words': [],
    'cooldown': 5000  # 10s
}


def cooldown_thread():
    t_now = int(time.time())
    while True:
        cd = cooldownQueue.get(True)

        t_later = cd.unlockTime
        time.sleep((t_later - t_now) / 1000.0)
        
        groupInfo[cd.groupId].idle = True
    

def existElem(l: list, elem: Any) -> bool:
    i = bisect_left(l, elem)
    if i != len(l) and l[i] == elem:
        return True
    return False


def checkBan(l: list, raw: str):
    pass


@Loader.listen('Load')
async def onLoad(app: App):
    global settings
    global groupInfo

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
    settings['banned_words'].sort()
    
    conf.close()

    for id in settings['enabled_groups']:
        groupInfo[id] = Info(True, "")
    
    _thread.start_new_thread(cooldown_thread, ())

    print('复读机加载成功')


@Loader.listen('GroupMessage')
async def onRecvGroupMessage(app: App, e: GroupMessageRecvEvent):
    groupId = e.group.id
    message = e.msg

    if not existElem(settings['enabled_groups'], groupId):
        return

    info = groupInfo[groupId]
    new = message.md5()
    last = info.last
    info.last = new

    if new != last:
        return
    # TODO add banned word filter here
    if not info.idle:
        return
    if random.random() > settings['repeat_prob']:
        return
    app.sendGroupMessage(groupId, message)
    info.idle = False

    t = int(time.time()) + settings['cooldown']
    cooldownQueue.put(Cooldown(groupId, t))
