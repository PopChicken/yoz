import websockets
import asyncio
import json
import requests
import pydblite
import copy

import mirai.settings as s
import mirai.unify as unify

from typing import Callable, List, Dict

from mirai.mapping import Mirai2CoreEvents

from core.application import App
from core.loader import Loader
from core.event import BaseEvent, ContactMessageRecvEvent, GroupMessageRecvEvent
from core.message import Message
from core.entity.group import Group, Member
from core.entity.contact import Contact


class Mirai(App):

    def __init__(self) -> None:
        self.commandHead: str = s.CMD_HEAD
        self.sessionKey: str = ''
        self.redirectors: Dict[str, (str, Callable)] = {}
        self.memberRedirectors = pydblite.Base(':memory:')
        self.contactRedirectors = pydblite.Base(':memory:')
        self.nickname: str = s.NICKNAME

        self.memberRedirectors.create('guid', 'groupId', 'memberId', 'hook')
        self.contactRedirectors.create('guid', 'contactId', 'hook')

        self.memberRedirectors.create_index('guid', 'groupId', 'memberId')
        self.contactRedirectors.create_index('guid', 'contactId')

    # 过滤满足filter的消息，并将其完全重定向至hook
    def redirect(self, guid: str, filter: dict,
                 hook: Callable[[App, BaseEvent], None]):
        # 待实现
        self.redirectors[guid] = (filter, hook)

    # 过滤满足特定群与QQ号的消息，并将其完全重定向至hook
    def redirectMember(self, guid: str, groupId: int, memberId: int,
                       hook: Callable[[App, GroupMessageRecvEvent], None]):
        self.memberRedirectors.insert(
            guid=guid,
            groupId=groupId,
            memberId=memberId,
            hook=hook
        )

    # 过滤满足特定QQ号的消息，并将其完全重定向至hook
    def redirectContact(self, guid: str, contactId: int,
                        hook: Callable[[App, ContactMessageRecvEvent], None]):
        self.contactRedirectors.insert(
            guid=guid,
            contactId=contactId,
            hook=hook
        )

    # 卸载hook
    def unredirect(self, guid: str) -> None:
        if guid in self.redirectors:
            del self.redirectors[guid]
        else:
            recs = self.contactRedirectors(guid=guid)
            if len(recs) != 0:
                del self.contactRedirectors[recs[0]['__id__']]
            else:
                recs = self.memberRedirectors(guid=guid)
                if len(recs) != 0:
                    del self.memberRedirectors[recs[0]['__id__']]

    async def _message_event_socket(self):
        try:
            receiver = await websockets.connect(f'{s.WS_URL}/all?sessionKey={self.sessionKey}')
        except Exception as e:
            print('Websocket 连接出错:', e)
        while True:
            try:
                response = await receiver.recv()
                response = json.loads(response)
            except Exception as e:
                print('Websocket 通讯中出错:', e)

            eventName = response['type']

            # 检查是否满足redirector
            if eventName == 'GroupMessage':
                groupId = response['sender']['group']['id']
                memberId = response['sender']['id']
                rec = self.memberRedirectors(groupId=groupId, memberId=memberId)
                if len(rec) != 0:
                    rec = rec[0]
                    e = GroupMessageRecvEvent(
                        unify.unify_event_dict(response))
                    rec['hook'](self, e)
                    continue
                
            elif eventName == 'FriendMessage':
                contactId = response['sender']['id']
                rec = self.contactRedirectors(contactId=contactId)
                if len(rec) != 0:
                    rec = rec[0]
                    e = ContactMessageRecvEvent(
                        unify.unify_event_dict(response))
                    rec['hook'](self, e)
                    continue
            
            # 尝试匹配指令
            if eventName == 'GroupMessage' or eventName == 'FriendMessage':
                # TODO use Trie tree to optimize command match
                try:
                    activeCommand: Callable = None
                    mostMatch = ''
                    section1 = response['messageChain'][1]
                    if section1['type'] == 'Plain' \
                            and section1['text'][0] in s.CMD_HEAD:
                        text = section1['text'][1:]
                        if eventName == 'GroupMessage':
                            for cmdStr in Loader.groupCommands.keys():
                                if text[:len(cmdStr)] == cmdStr and len(cmdStr) > len(mostMatch):
                                    mostMatch = cmdStr
                            section1['text'] = section1['text'][len(mostMatch)+1:]
                            e = GroupMessageRecvEvent(
                                unify.unify_event_dict(response))
                            if len(mostMatch) != 0:
                                activeCommand = Loader.groupCommands[mostMatch]
                        else:
                            for cmdStr in Loader.contactCommands.keys():
                                if text[:len(cmdStr)] == cmdStr and len(cmdStr) > len(mostMatch):
                                    mostMatch = cmdStr
                            section1['text'] = section1['text'][len(mostMatch)+1:]
                            e = ContactMessageRecvEvent(
                                unify.unify_event_dict(response))
                            if len(mostMatch) != 0:
                                activeCommand = Loader.contactCommands[mostMatch]
                    if activeCommand is not None:
                        await activeCommand(self, e)
                        continue
                except Exception as e:
                    print("指令识别出错: ", e)
                    continue

            if hasattr(Mirai2CoreEvents, eventName):
                e = Mirai2CoreEvents[eventName].value(
                    unify.unify_event_dict(response))
                listeners = Loader.eventsListener.get(eventName)

                if listeners is not None:
                    await asyncio.gather(*(listener(self, e) for listener in listeners))

    async def _init_modules(self) -> None:
        listeners = Loader.eventsListener.get('Load')
        await asyncio.gather(*(listener(self) for listener in listeners))

    def run(self):
        # init modules
        asyncio.get_event_loop().run_until_complete(self._init_modules())

        auth = {
            'authKey': s.AUTH_KEY
        }
        try:
            resp = requests.post(f'{s.HTTP_URL}/auth', json=auth).json()
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

        asyncio.get_event_loop().run_until_complete(self._message_event_socket())

    def setCommandHead(self, head: str) -> None:
        self.commandHead = head

    def sendGroupMessage(self, group: int, message):
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

    # mirai-http-api 有/sendFriendMessage 与 /sendTempMessage 分别对应好友与临时消息.
    # TODO 临时消息尚无模型，建议tg接口中的临时消息接口直接调用sendContactMessage，mirai接口中分别实现。
    def sendContactMessage(self, contact, message) -> Message:
        if not isinstance(message, Message):
            message = Message(raw=message)
        message: Message
        fMsg = {
            "sessionKey": self.sessionKey,
            "target": contact,
            "messageChain": message.chain()
        }
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

    def sendWebImage(self, urls: List[str], contactId: int=None, groupId: int=None) -> None:
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

    def getContactList(self) -> List[Contact]:
        pass

    def getGroupList(self) -> List[Group]:
        pass

    def getMemberList(self, group: int) -> List[Member]:
        pass

    def kick(self, group: int, target: int, msg: str) -> None:
        pass

    def quit(self, group: int) -> None:
        pass