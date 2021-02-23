import re
import yaml

from bisect import bisect_left
from typing import Any

from core.loader import CommandType, Loader
from core.extern.config import Config
from core.application import App
from core.event import GroupMessageRecvEvent
from core.entity.group import PermissionType


config = Config('forest')

settings = {
    'enabled_groups': [],
    'max_time': 2 * 24 * 60 * 60, # 单位s
    'min_time': 1 * 1 * 30 * 60
}

def hourToSec(hour: float) -> int:
    return int(hour * 3600)

def dayToSec(day: float) -> int:
    return int(day * 24 * 3600)

def minToSec(min: float) -> int:
    return int(min * 60)

def formatTime(sec: int):
    num: float
    unit: str
    if sec < 60:
        num = sec
        unit = '秒'
    elif sec < 60 * 60:
        num = sec / 60
        unit = '分钟'
    elif sec < 24 * 60 * 60:
        num = sec / 60 / 60
        unit = '小时'
    else:
        num = sec / 24 / 60 / 60
        unit = '天'
    num = round(num, 1)
    if num / int(num) == 1.0:
        num = int(num)
    return f'{num}{unit}'

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

    print('Forest加载成功')


def existElem(l: list, elem: Any) -> bool:
    i = bisect_left(l, elem)
    if i != len(l) and l[i] == elem:
        return True
    return False


@Loader.command("种树", CommandType.Group)
async def plantCommand(app: App, e: GroupMessageRecvEvent):
    group = e.group
    message = str(e.msg).strip()

    if group.permission == PermissionType.Member:
        return

    if not existElem(settings['enabled_groups'], group.id):
        return
    
    if len(str(message).strip()) == 0:
        app.sendGroupMessage(e.group,
            ("欢迎使用种树功能\n"
            "不 要 挑 战 自 制 力！\n"
            f"如果无法专注忍不住想水群，就让{app.nickname}来帮助你吧！\n"
            "使用\n"
            f"{app.commandHead}种树{{时间}}min\n"
            f"{app.commandHead}种树{{时间}}h\n"
            f"{app.commandHead}种树{{时间}}d\n"
            "给自己安排对应时长的禁言w\n"
            f"时长需要在{formatTime(settings['min_time'])}"
            f"到{formatTime(settings['max_time'])}之间\n"
            "未来会在种树结束获得一颗树哦~"))
        return

    m = re.match(r'^(\d+(\.\d+)?)\s*(h|d|min)', message)
    if m is None:
        app.sendGroupMessage(e.group, 
            (f"格式不对哦，使用 {app.commandHead}种树 查看帮助"))
        return
    
    num = float(m.group(1))
    unit = str(m.group(3))
    sec: int

    if unit == 'min':
        sec = minToSec(num)
    elif unit == 'h':
        sec = hourToSec(num)
    elif unit == 'd':
        sec = dayToSec(num)
    
    if sec > settings['max_time'] or sec < settings['min_time']:
        app.sendGroupMessage(e.group, 
            ("种树时间不可取喔~\n"
            f"需要在{formatTime(settings['min_time'])}"
            f"到{formatTime(settings['max_time'])}之间~"))
        return
    
    app.mute(e.group, e.sender.id, sec)
    app.sendGroupMessage(e.group,
        (f"要专注哦~{app.nickname}为你加油！"))

