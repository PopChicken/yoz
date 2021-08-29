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


config = Config('title')

settings = {
    'enabled_groups': [],
    'master': 0,
}

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

    app.logger.info('Title加载成功')


def existElem(l: list, elem: Any) -> bool:
    i = bisect_left(l, elem)
    if i != len(l) and l[i] == elem:
        return True
    return False


@Loader.command("赐名", CommandType.Group)
def plantCommand(app: App, e: GroupMessageRecvEvent):
    groupId = e.group.id
    masterId = settings['master']

    if not existElem(settings['enabled_groups'], groupId):
        return

    if e.group.permission == PermissionType.Member:
        app.sendGroupMessage(groupId, Message.phrase(
            RefMsg(target=e.sender.id),
            " 需要管理员权限才能执行该指令嗷~"
        ))
        return

    if (masterId == 0 and e.sender.permission == PermissionType.Member) \
        or (masterId != 0 and masterId != e.sender.id):
        app.sendGroupMessage(groupId, Message.phrase(
            RefMsg(target=e.sender.id),
            " 你没有权限哟~"
        ))
        return
    
    if len(e.msg.msgChain) == 0:
        app.sendGroupMessage(groupId, Message.phrase(
            RefMsg(target=e.sender.id),
            " 格式是\"赐名 @成员 头衔\"哦~"
        ))
        return

    atCodes = e.msg.getAtCodes()
    if (len(atCodes) != 1):
        app.sendGroupMessage(groupId, Message.phrase(
            RefMsg(target=e.sender.id),
            " 格式不对喔~"
        ))
        return

    app.setSpecialTitle(groupId, atCodes[0].target, str(e.msg.msgChain[2]).strip())
    app.sendGroupMessage(groupId, Message.phrase(
        RefMsg(target=e.sender.id),
        " 操作成功~"
    ))
