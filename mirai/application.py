import websockets
import asyncio
import json
import requests
import pydblite
import copy
import inspect
import time
import os

import mirai.settings as s
import mirai.unify as unify
import core.tmanager as t

from typing import Callable, List, Dict

from mirai.mapping import Mirai2CoreEvents

from core.application import App
from core.loader import Loader
from core.event import BaseEvent, ContactMessageRecvEvent, GroupMessageRecvEvent
from core.message import Message
from core.entity.group import Group, Member
from core.entity.contact import Contact

os.environ['no_proxy'] = '*'


class Mirai(App):

    def __init__(self) -> None:
        super(Mirai, self).__init__()

        self.commandHead: str = s.CMD_HEAD
        self.sessionKey: str = ''
        self.redirections: Dict[str, (str, Callable)] = {}
        self.memberRedirections = pydblite.Base(':memory:')
        self.contactRedirections = pydblite.Base(':memory:')
        self.nickname: str = s.NICKNAME

        self.threadManager = t.ThreadManager()

        self.memberRedirections.create('guid', 'groupId', 'memberId', 'hook')
        self.contactRedirections.create('guid', 'contactId', 'hook')

        self.memberRedirections.create_index('guid', 'groupId', 'memberId')
        self.contactRedirections.create_index('guid', 'contactId')

    # 过滤满足filter的消息，并将其完全重定向至hook
    def redirect(self, guid: str, filter: dict,
                 hook: Callable[[App, BaseEvent], None]):
        # 待实现
        self.redirections[guid] = (filter, hook)

    # 过滤满足特定群与QQ号的消息，并将其完全重定向至hook
    def redirectMember(self, guid: str, groupId: int, memberId: int,
                       hook: Callable[[App, GroupMessageRecvEvent], None]):
        self.memberRedirections.insert(
            guid=guid,
            groupId=groupId,
            memberId=memberId,
            hook=hook
        )

    # 过滤满足特定QQ号的消息，并将其完全重定向至hook
    def redirectContact(self, guid: str, contactId: int,
                        hook: Callable[[App, ContactMessageRecvEvent], None]):
        self.contactRedirections.insert(
            guid=guid,
            contactId=contactId,
            hook=hook
        )

    # 卸载hook
    def unredirect(self, guid: str) -> None:
        if guid in self.redirections:
            del self.redirections[guid]
        else:
            recs = self.contactRedirections(guid=guid)
            if len(recs) != 0:
                del self.contactRedirections[recs[0]['__id__']]
            else:
                recs = self.memberRedirections(guid=guid)
                if len(recs) != 0:
                    del self.memberRedirections[recs[0]['__id__']]

    async def __message_event_socket(self):
        async def connect(app: Mirai):
            while True:
                App.logger.info("connecting mirai-http service...")
                try:
                    if s.NEED_VERIFY:
                        receiver = await asyncio.wait_for(websockets.connect(f'{s.WS_URL}/all?verifyKey={s.AUTH_KEY}&qq={s.BOT_ID}'), 5)
                    else:
                        receiver = await asyncio.wait_for(websockets.connect(f'{s.WS_URL}/all?qq={s.BOT_ID}'), 5)
                    response = await asyncio.wait_for(receiver.recv(), 5)
                    response = json.loads(response)
                    app.sessionKey = response['data']['session']
                    break
                except TimeoutError:
                    App.logger.error("websocket connecting attemption timeout, retrying")
                except:
                    App.logger.error("websocket connecting attemption failed, retrying")
                    time.sleep(10.0)
            App.logger.info("mirai-http service connected")
            return receiver

        receiver = await connect(self)
        self.__init_modules()
        App.logger.info("event loop started")
        while True:
            try:
                response = await receiver.recv()
                response = json.loads(response)['data']
            except Exception as e:
                print("websocket communication error, retrying:", e)
                receiver = await connect(self)
                continue

            # 初始化 data
            data: dict = {}

            if response['type'][-7:] == 'Message':
                if response['sender']['id'] in s.BLACK_LIST:
                    continue

            # Middleware: temp message filter here
            if response['type'] == 'TempMessage':
                data['originGroupId'] = response['sender']['group']['id']
                response = unify.unifyTemp2FriendEvent(response)

            eventName = response['type']

            # 检查是否满足redirector
            if eventName == 'GroupMessage':
                groupId = response['sender']['group']['id']
                memberId = response['sender']['id']
                rec = self.memberRedirections(groupId=groupId, memberId=memberId)
                if len(rec) != 0:
                    rec = rec[0]
                    e = GroupMessageRecvEvent(
                        unify.unifyEventDict(response))
                    self.threadManager.execute(rec['hook'], (self, e,))
                    continue

            elif eventName == 'FriendMessage':
                contactId = response['sender']['id']
                rec = self.contactRedirections(contactId=contactId)
                if len(rec) != 0:
                    rec = rec[0]
                    e = ContactMessageRecvEvent(
                        unify.unifyEventDict(response))
                    self.threadManager.execute(rec['hook'], (self, e,))
                    continue

            # 尝试匹配指令
            if eventName == 'GroupMessage' or eventName == 'FriendMessage':
                # TODO use Trie tree to optimize command match
                activeCommand: Callable = None
                try:
                    mostMatch = ''
                    section1 = response['messageChain'][1]
                    if section1['type'] == 'Plain' \
                            and (section1['text'][0] == s.CMD_HEAD or section1['text'][0] in s.ALT_CMD_HEAD):
                        text = section1['text'][1:]
                        if eventName == 'GroupMessage':
                            for cmdStr in Loader.groupCommands.keys():
                                if text[:len(cmdStr)] == cmdStr and len(cmdStr) > len(mostMatch):
                                    mostMatch = cmdStr
                            section1['text'] = section1['text'][len(mostMatch) + 1:]
                            e = GroupMessageRecvEvent(
                                unify.unifyEventDict(response))
                            if len(mostMatch) != 0:
                                activeCommand = Loader.groupCommands[mostMatch]
                        else:
                            for cmdStr in Loader.contactCommands.keys():
                                if text[:len(cmdStr)] == cmdStr and len(cmdStr) > len(mostMatch):
                                    mostMatch = cmdStr
                            section1['text'] = section1['text'][len(mostMatch) + 1:]
                            e = ContactMessageRecvEvent(
                                unify.unifyEventDict(response))
                            if len(mostMatch) != 0:
                                activeCommand = Loader.contactCommands[mostMatch]
                except Exception as e:
                    print("指令识别出错: ", e)
                    continue
                if activeCommand is not None:
                    self.threadManager.execute(activeCommand, (self, e,))
                    continue

            if hasattr(Mirai2CoreEvents, eventName):
                e = Mirai2CoreEvents[eventName].value(
                    unify.unifyEventDict(response))
                modules = Loader.eventsListener.get(eventName)
                if modules is not None:
                    for _, listeners in modules.items():
                        for listener in listeners:
                            self.threadManager.execute(listener, (self, e,))

    def __init_modules(self) -> None:
        Loader.loadPlugins('module')
        
        App.logger.info("initializing plugins...")
        modules = Loader.eventsListener.get('Load')
        if modules is not None:
            for _, listeners in modules.items():
                for listener in listeners:
                    self.threadManager.execute(listener, (self,))

    def run(self):
        """
        auth = {
            'verifyKey': s.AUTH_KEY
        }
        try:
            resp = requests.post(f'{s.HTTP_URL}/verify', json=auth).json()
            if resp['code'] != 0:
                raise Exception(resp['msg'])
            self.sessionKey = resp['session']
        except Exception as e:
            print("申请 session 时发生错误: ", e)

        verify = {
            'sessionKey': self.sessionKey,
            'qq': s.BOT_ID
        }
        try:
            resp = requests.post(f'{s.HTTP_URL}/verify', json=verify).json()
            if resp['code'] != 0:
                raise Exception(resp['msg'])
        except Exception as e:
            print("认证 session 时发生错误: ", e)
        """

        # init modules
        App.logger.info("starting yozbot console...")
        asyncio.run(self.__message_event_socket())

    def setCommandHead(self, head: str) -> None:
        self.commandHead = head

    def sendGroupMessage(self, group: int, message) -> Message:
        if not isinstance(message, Message):
            message = Message(raw=message)
        message: Message
        fMsg = {
            "sessionKey": self.sessionKey,
            "target": group,
            "messageChain": message.chain()
        }
        resp = requests.post(f'{s.HTTP_URL}/sendGroupMessage', json=fMsg).json()
        message = copy.deepcopy(message)
        message.uid = resp['messageId']
        return message

    def setSpecialTitle(self, group: int, id: int, title: str) -> None:
        fMsg = {
            "sessionKey": self.sessionKey,
            "target": group,
            "memberId": id,
            "info": {
                "specialTitle": title
            }
        }
        requests.post(f'{s.HTTP_URL}/memberInfo', json=fMsg)

    def mute(self, group: int, id: int, time: int) -> None:
        fMsg = {
            "sessionKey": self.sessionKey,
            "target": group,
            "memberId": id,
            "time": time
        }
        requests.post(f'{s.HTTP_URL}/mute', json=fMsg)

    def unmute(self, group: int, id: int) -> None:
        fMsg = {
            "sessionKey": self.sessionKey,
            "target": group,
            "memberId": id
        }
        requests.post(f'{s.HTTP_URL}/unmute', json=fMsg)

    def muteAll(self, group: int) -> None:
        fMsg = {
            "sessionKey": self.sessionKey,
            "target": group
        }
        requests.post(f'{s.HTTP_URL}/muteAll', json=fMsg)

    def unmuteAll(self, group: int) -> None:
        fMsg = {
            "sessionKey": self.sessionKey,
            "target": group
        }
        requests.post(f'{s.HTTP_URL}/unmuteAll', json=fMsg)

    # TODO 临时消息尚无模型，建议tg接口中的临时消息接口直接调用sendContactMessage，mirai接口中分别实现。
    def sendContactMessage(self, contact: int, message, group: int = None) -> Message:
        if not isinstance(message, Message):
            message = Message(raw=message)
        message: Message
        fMsg = {
            "sessionKey": self.sessionKey,
            "messageChain": message.chain()
        }

        if group is not None:
            fMsg['group'] = group
            fMsg['qq'] = contact
            resp = requests.post(f'{s.HTTP_URL}/sendTempMessage', json=fMsg).json()
        else:
            temp = False
            for frameInfo in inspect.stack(0):
                if frameInfo.function == self.__message_event_socket.__name__ \
                        and isinstance(frameInfo.frame.f_locals['self'], Mirai):
                    data = frameInfo.frame.f_locals['data']
                    if 'originGroupId' in data:
                        groupId = data['originGroupId']
                        temp = True
                    break
            if temp:
                fMsg['group'] = groupId
                fMsg['qq'] = contact
                resp = requests.post(f'{s.HTTP_URL}/sendTempMessage', json=fMsg).json()
            else:
                fMsg['target'] = contact
                resp = requests.post(f'{s.HTTP_URL}/sendFriendMessage', json=fMsg).json()
        message = copy.deepcopy(message)
        message.uid = resp['messageId']
        return message

    def replyContactMessage(self, sender: Contact, message) -> Message:
        if not isinstance(message, Message):
            message = Message(raw=message)
        message: Message
        fMsg = {
            "sessionKey": self.sessionKey,
            "messageChain": message.chain()
        }
        if sender.fromGroup is not None:
            fMsg['group'] = sender.fromGroup
            fMsg['qq'] = sender.id
            resp = requests.post(f'{s.HTTP_URL}/sendTempMessage', json=fMsg).json()
        else:
            fMsg['target'] = sender.id
            resp = requests.post(f'{s.HTTP_URL}/sendFriendMessage', json=fMsg).json()
        message = copy.deepcopy(message)
        message.uid = resp['messageId']
        return message

    def recall(self, messageId: int) -> None:
        """撤回消息"""
        fMsg = {
            "sessionKey": self.sessionKey,
            "target": messageId
        }
        requests.post(f'{s.HTTP_URL}/recall', json=fMsg)

    # /sendImageMessage 不返回信息id
    def sendWebImage(self, urls: List[str], contactId: int = None, groupId: int = None) -> None:
        """
        发送URL图片 
        仅传入contantId:    好友消息
        仅传入groupId:      群聊消息
        都传入:             临时消息
        """
        # TODO tg EFB接口的临时消息同好友消息处理。
        if contactId is None and groupId is not None:
            fMsg = {
                "sessionKey": self.sessionKey,
                "target": groupId,
                "group": groupId,
                "urls": urls
            }
        elif contactId is not None and groupId is None:
            fMsg = {
                "sessionKey": self.sessionKey,
                "target": contactId,
                "qq": contactId,
                "urls": urls
            }
        elif contactId is not None and groupId is not None:
            fMsg = {
                "sessionKey": self.sessionKey,
                "target": contactId,
                "qq": contactId,
                "group": groupId,
                "urls": urls
            }
        requests.post(f'{s.HTTP_URL}/sendImageMessage', json=fMsg)

    def getMemberInfo(self, group: int, target: int) -> Member:
        fMsg = {
            "sessionKey": self.sessionKey,
            "target": group,
            "memberId": target
        }
        resp = requests.get(
            f'{s.HTTP_URL}/memberInfo?sessionKey={self.sessionKey}&target={group}&memberId={target}').json()
        member = Member(target, resp['memberName'], unify.unifyPermission(resp['permission']),
                        resp['joinTimestamp'], resp['lastSpeakTimestamp'], resp['muteTimeRemaining'])
        return member

    def getContactList(self) -> List[Contact]:
        pass

    def getGroupList(self) -> List[Group]:
        pass

    def getMemberList(self, group: int) -> List[Member]:
        resp = requests.get(f'{s.HTTP_URL}/memberList?sessionKey={self.sessionKey}&target={group}').json()
        members = []
        for m in resp['data']:
            member = Member(m['id'], m['memberName'], unify.unifyPermission(m['permission']),
                            m['joinTimestamp'], m['lastSpeakTimestamp'], m['muteTimeRemaining'])
            members.append(member)
        return members

    def kick(self, group: int, target: int, msg: str) -> None:
        pass

    def quit(self, group: int) -> None:
        pass
