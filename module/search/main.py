import re
import yaml

from bisect import bisect_left
from typing import Any

from core.message import Message
from core.message import RefMsg
from core.loader import CommandType, Loader
from core.extern.config import Config
from core.application import App
from core.event import GroupMessageRecvEvent
from core.entity.group import PermissionType


config = Config('search')

settings = {
    'enabled_groups': []
}

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

    print('Search加载成功')

def genMsg(search_str: str, search_engine: str) -> str:
    prefix = {
        'google': 'https://www.google.com/search?q=',
        'baidu': 'https://www.baidu.com/s?wd=',
        'github': 'https://github.com/search?q=',
        'bilibili': 'https://search.bilibili.com/all?keyword=',
    }
    msg = f'正在从 {search_engine} 中搜索...\n'
    return msg+prefix[search_engine]+search_str

def existElem(l: list, elem: Any) -> bool:
    i = bisect_left(l, elem)
    if i != len(l) and l[i] == elem:
        return True
    return False

def common(func):
    async def wrapper(app: App, e: GroupMessageRecvEvent):
        groupId = e.group.id
        if not existElem(settings['enabled_groups'], groupId):
            return

        if not await func(app, e):
            app.sendGroupMessage(groupId, Message.phrase(
                RefMsg(target=e.sender.id),
                ("使用方法： .(google | baidu | github | bilibili) search_string")
            ))
    return wrapper


@Loader.command("google", CommandType.Group)
@common
async def google_search(app: App, e: GroupMessageRecvEvent):
    groupId = e.group.id
    message = str(e.msg).strip()
    
    if message: 
        app.sendGroupMessage(groupId, genMsg(message, 'google'))
        return True
    else:
        return False
    
@Loader.command("baidu", CommandType.Group)
@common
async def baidu_search(app: App, e: GroupMessageRecvEvent):
    groupId = e.group.id
    message = str(e.msg).strip()
    
    if message: 
        app.sendGroupMessage(groupId, genMsg(message, 'baidu'))
        return True
    else:
        return False
    
@Loader.command("github", CommandType.Group)
@common
async def github_search(app: App, e: GroupMessageRecvEvent):
    groupId = e.group.id
    message = str(e.msg).strip()
    
    if message: 
        app.sendGroupMessage(groupId, genMsg(message, 'github'))
        return True
    else:
        return False
    
@Loader.command("bilibili", CommandType.Group)
@common
async def bilibili_search(app: App, e: GroupMessageRecvEvent):
    groupId = e.group.id
    message = str(e.msg).strip()
    
    if message: 
        app.sendGroupMessage(groupId, genMsg(message, 'bilibili'))
        return True
    else:
        return False
    

