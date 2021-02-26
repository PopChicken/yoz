import websockets
import asyncio
import json
import requests

import mirai.settings as s
import mirai.unify as unify

from typing import Callable, List, overload

from mirai.mapping import Mirai2CoreEvents

from core.application import App
from core.loader import Loader
from core.event import ContactMessageRecvEvent, GroupMessageRecvEvent
from core.message import Message
from core.entity.group import Group, Member
from core.entity.contact import Contact


class Mirai(App):

    def __init__(self) -> None:
        self.commandHead: str = s.CMD_HEAD
        self.sessionKey: str

        self.nickname = s.NICKNAME

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
        requests.post(f'{s.HTTP_URL}/sendGroupMessage', json=fMsg)

    def mute(self, group: int, id: int, time: int):
        fMsg = {
            "sessionKey": self.sessionKey,
            "target": group,
            "memberId": id,
            "time": time
        }
        requests.post(f'{s.HTTP_URL}/mute', json=fMsg)

    def unmute(self, group: int, id: int, time: int):
        pass

    def muteAll(self, group: int):
        pass

    def unmuteAll(self, group: int):
        pass

    def sendContactMessage(self, contact, message) -> None:
        pass

    def recall(self, messageId: int) -> None:
        pass

    def sendWebImage(self, urls: List[str], contactId: int=None, groupId: int=None) -> None:
        pass

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

            if eventName == 'GroupMessage' or eventName == 'FriendMessage':
                # TODO use Trie tree to optimize command match
                try:
                    activeCommand: Callable
                    mostMatch = ''
                    section1 = response['messageChain'][1]
                    if section1['type'] == 'Plain' \
                            and section1['text'][0] == s.CMD_HEAD:
                        text = section1['text'][1:]
                        if eventName == 'GroupMessage':
                            for cmdStr in Loader.groupCommands.keys():
                                if text[:len(cmdStr)] == cmdStr and len(cmdStr) > len(mostMatch):
                                    mostMatch = cmdStr
                            section1['text'] = section1['text'][len(mostMatch)+1:]
                            e = GroupMessageRecvEvent(
                                unify.unify_event_dict(response))
                            activeCommand = Loader.groupCommands[mostMatch]
                        else:
                            for cmdStr in Loader.contactCommands.keys():
                                if text[:len(cmdStr)] == cmdStr and len(cmdStr) > len(mostMatch):
                                    mostMatch = cmdStr
                            section1['text'] = section1['text'][len(mostMatch)+1:]
                            e = ContactMessageRecvEvent(
                                unify.unify_event_dict(response))
                            activeCommand = Loader.contactCommands[mostMatch]
                    if activeCommand is not None:
                        await activeCommand(self, e)
                        continue
                except Exception as e:
                    print("指令识别出错: ", e)
                    continue

            if hasattr(Mirai2CoreEvents, eventName):
                e = Mirai2CoreEvents[eventName].value[0](
                    unify.unify_event_dict(response))
                listeners = Loader.eventsListener.get(eventName)

                if listeners is not None:
                    await asyncio.gather(*(listener(self, e) for listener in listeners))

    async def _init_modules(self):
        listeners = Loader.eventsListener.get('Load')
        await asyncio.gather(*(listener(self) for listener in listeners))

    def run(self):

        asyncio.get_event_loop().run_until_complete(
            self._init_modules())   # init modules

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
