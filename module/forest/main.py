from .prob import (
    lottery,
    init,
    getCongratulations,
    getItemDetail,
    getQualityDescription
)

import re
import yaml
import pydblite
import _thread
import time

from bisect import bisect_left
from typing import Any, Dict, Tuple

from core.message import Message
from core.message import RefMsg
from core.loader import CommandType, Loader
from core.extern.config import Config
from core.extern.data import Data
from core.application import App
from core.event import ContactMessageRecvEvent, GroupMessageRecvEvent
from core.entity.group import PermissionType

from util.crontab import Crontab

from module.session import Session, SessionLib



MODULE_NAME = 'forest'

data = Data(MODULE_NAME)
config = Config(MODULE_NAME)
sessions = SessionLib(MODULE_NAME)

db = pydblite.Base(f'{data.getfo()}/{MODULE_NAME}.db')
userdb = pydblite.Base(f'{data.getfo()}/user.db')
crontab = Crontab()

settings = {
    'enabled_groups': [],
    'max_time': 2 * 24 * 60 * 60,  # 单位s
    'min_time': 1 * 1 * 30 * 60,
    'admin': 0
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
    if num > 0.5 and num / round(num) == 1.0:
        num = int(num)
    return f'{num}{unit}'


def dbCommit():
    while True:
        time.sleep(10)
        db.commit()


def plantComplete(app: App, groupId: int, memberId: int, type: str='success'):
    info = db(groupId=groupId, memberId=memberId)[0]
    if type == 'success':
        proc = info['duration'] / settings['max_time'] * 100
        treeId, quality = lottery(proc)
        app.sendGroupMessage(groupId, Message.phrase(
            RefMsg(target=memberId),
            "的树长大啦！\n"
            f"{getCongratulations(quality)}"
            f"你获得了“{getQualityDescription(quality)}”品质的"
            f"{getItemDetail(treeId)['name']}~"
        ))
        record = userdb(userid=memberId)
        if len(record) != 0:
            record = record[0]
            if treeId not in record['bag']:
                record['bag'][treeId] = 1
            else:
                record['bag'][treeId] += 1
            record['accumulate'] += info['duration']
        else:
            userdb.insert(
                userid=memberId,
                bag={ treeId: 1 },
                accumulate=info['duration']
            )
        userdb.commit()
    elif type == 'cancel':
        app.sendGroupMessage(groupId, Message.phrase(
            RefMsg(target=memberId),
            "取消了种树，树枯萎了..."
        ))
        app.unmute(groupId, memberId)
    else:
        return

    del db[info['__id__']]


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

    try:
        init(config)
    except Exception as e:
        print('加载树木信息时出现致命错误: ', e)
        print('模块将无法正常运行，请立即终止进程')
        return

    if userdb.exists():
        userdb.open()
    else:
        userdb.create('userid', 'bag', 'accumulate')
        userdb.create_index('userid')
        userdb.commit()

    if db.exists():
        db.open()
        for record in db:
            groupId = record['groupId']
            memberId = record['memberId']
            endTime = record['endTime']
            crontab.addabs(f'{groupId}.{memberId}',
                           endTime, plantComplete, (app, groupId, memberId))
    else:
        db.create('groupId', 'memberId', 'groupName', 'duration', 'endTime')
        db.create_index('groupId', 'memberId')
        db.commit()

    # 启动数据库自动保存循环
    _thread.start_new_thread(dbCommit, ())

    print('Forest加载成功')


def existElem(l: list, elem: Any) -> bool:
    i = bisect_left(l, elem)
    if i != len(l) and l[i] == elem:
        return True
    return False


@Loader.command("种树", CommandType.Group)
async def plantCommand(app: App, e: GroupMessageRecvEvent):
    groupId = e.group.id
    memberId = e.sender.id
    message = str(e.msg).strip()

    if e.group.permission == PermissionType.Member:
        return

    if not existElem(settings['enabled_groups'], groupId):
        return

    if len(str(message).strip()) == 0:
        app.sendGroupMessage(groupId, Message.phrase(
            RefMsg(target=memberId),
            ("欢迎使用种树功能\n"
             "不 要 挑 战 自 制 力！\n"
             f"如果无法专注忍不住想水群，就让{app.nickname}来帮助你吧！\n"
             "使用\n"
             f"{app.commandHead}种树{{时间}}min\n"
             f"{app.commandHead}种树{{时间}}h\n"
             f"{app.commandHead}种树{{时间}}d\n"
             f"{app.commandHead}种树{{时间}}s\n"
             "给自己安排对应时长的禁言w\n"
             f"时长需要在{formatTime(settings['min_time'])}"
             f"到{formatTime(settings['max_time'])}之间\n"
             f"私聊我，使用“{app.commandHead}放弃种树”指令可以放弃~\n"
             f"私聊或者在群中使用“{app.commandHead}逛树林”可以查看自己拥有的树喔~\n"
             "种树结束会获得一颗树哦，种树时间越久越容易出现珍稀品种~")
        ))
        return

    m = re.match(r'^(\d+(\.\d+)?)\s*(h|d|min|s)$', message)
    if m is None:
        app.sendGroupMessage(groupId, Message.phrase(
            RefMsg(target=memberId),
            (f"格式不对哦，使用 {app.commandHead[0]}种树 查看帮助")
        ))
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
    elif unit == 's':
        sec = int(num)

    if sec > settings['max_time'] or sec < settings['min_time']:
        app.sendGroupMessage(groupId, Message.phrase(
            RefMsg(target=memberId),
            (f"你输入的是{formatTime(sec)}\n"
             "种树时间不可取喔~\n"
             f"需要在{formatTime(settings['min_time'])}"
             f"到{formatTime(settings['max_time'])}之间~")
        ))
        return

    app.mute(groupId, memberId, sec)
    app.sendGroupMessage(groupId, Message.phrase(
        RefMsg(target=memberId),
        (f"要专注哦~{app.nickname}为你加油！")
    ))

    rec = db(groupId=groupId, memberId=memberId)
    if len(rec) != 0:
        del db[rec[0]['__id__']]
    db.insert(groupId=groupId,
              memberId=memberId,
              groupName=e.group.name,
              duration=sec,
              endTime=round(time.time()) + sec)
    crontab.add(f'{groupId}.{memberId}', sec,
                plantComplete, (app, groupId, memberId))


@Loader.command("逛树林", CommandType.Group)
async def groupViewTrees(app: App, e: GroupMessageRecvEvent):
    name = '你'
    msg = e.msg
    msg.chain()
    record = userdb(userid=e.sender.id)
    empty = True
    
    if len(record) > 0:
        reply = "你的树林里有以下树木👇\n"
        bag = record[0]['bag']
        ids = list(bag.keys())
        ids.sort(reverse=True)
        for treeId in bag:
            cnt = bag[treeId]
            if cnt > 0:
                empty = False
                item = getItemDetail(treeId)
                reply += f"  【{getQualityDescription(item['quality'])}】{item['name']}×{cnt}\n"
        reply = reply[:-1]
    if empty:
        app.sendGroupMessage(e.group.id, Message.phrase(
            RefMsg(target=e.sender.id), "哎呀，你的树林空空如也呢，快去种树吧~")
        )
    else:
        app.sendGroupMessage(e.group.id, Message.phrase(
            RefMsg(target=e.sender.id), reply)
        )


@Loader.command("逛树林", CommandType.Contact)
async def contactViewTrees(app: App, e: ContactMessageRecvEvent):
    record = userdb(userid=e.sender.id)
    empty = True
    
    if len(record) > 0:
        reply = "你的树林里有以下树木👇\n"
        bag = record[0]['bag']
        ids = list(bag.keys())
        ids.sort(reverse=True)
        for treeId in ids:
            cnt = bag[treeId]
            if cnt > 0:
                empty = False
                item = getItemDetail(treeId)
                reply += f"  【{getQualityDescription(item['quality'])}】{item['name']}×{cnt}\n"
        reply = reply[:-1]
    if empty:
        app.replyContactMessage(e.sender, "哎呀，你的树林空空如也呢，快去种树吧~")
    else:
        app.replyContactMessage(e.sender, reply)


@Loader.command("加速卡", CommandType.Group)
async def useCard(app: App, e: ContactMessageRecvEvent):
    arg = str(e.msg).strip()
    if len(arg) == 0:
        return
    # m = re.match(r'', arg)

@Loader.command("放弃种树", CommandType.Contact)
async def unplantCommand(app: App, e: ContactMessageRecvEvent):

    async def sessionHandler(app: App, e: ContactMessageRecvEvent):
        sender = e.sender
        contactId = e.sender.id
        message = str(e.msg).strip()
        session = sessions.getSession(contactId)
        step = session.step()

        if step == 1:
            options = session.get('options')
            optionCnt = session.get('optionCnt')
            if str.isdigit(message):
                id = int(message)
                if 1 <= id <= optionCnt:
                    app.replyContactMessage(sender, 
                        ("你确定嘛？\n"
                         "输入“确定”放弃种树，输入其他内容取消操作")
                    )
                    session.set('groupId', options[id])
                    session.next()
                else:
                    app.replyContactMessage(sender, "范围要正确哦~")
            elif message == "取消":
                app.replyContactMessage(sender, "取消啦~")
                sessions.closeSession(contactId)
                app.unredirect(str(contactId))
            else:
                app.replyContactMessage(sender, "输入的内容不正确~")
        elif step == 2:
            if message == "确定":
                app.replyContactMessage(sender, "臭水群怪，给你解除禁言了喔~")
                groupId = session.get('groupId')
                plantComplete(app, groupId, contactId, type='cancel')
                sessions.closeSession(contactId)
                app.unredirect(str(contactId))
                crontab.remove(f'{groupId}.{contactId}')
            else:
                app.replyContactMessage(sender, "未输入确定，操作取消啦~继续专注喔~")
                sessions.closeSession(contactId)
                app.unredirect(str(contactId))

    sender = e.sender
    contactId = e.sender.id
    session = sessions.createSession(contactId)
    records = db(memberId=contactId)

    if len(records) == 0:
        app.replyContactMessage(sender, "你没有在种的树哦~")
        return

    options: Dict[int, int] = {}
    reply = ''
    
    optCnt = 0
    for r in records:
        optCnt += 1
        options[optCnt] = r['groupId']
        reply += f'{optCnt}. {r["groupName"]}\n'
    
    session.set('options', options)
    session.set('optionCnt', optCnt)
    session.next()
    
    app.replyContactMessage(sender, Message.phrase(
        ("你有以下几个正在种树的群\n"
         + reply +
         "请输入序号(仅数字)\n"
         "输入“取消”继续种树")
    ))

    guid = str(contactId)
    app.redirectContact(guid, contactId, sessionHandler)


