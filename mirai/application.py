from typing import overload
from core.message import Message
from core.entity.group import Group
from core.model import Contact
import websockets
import asyncio
import json
import requests

import mirai.settings as s
import mirai.unify as unify
from mirai.mapping import Mirai2CoreEvents

from core.application import App
from core.loader import Loader


class Mirai(App):

    def __init__(self) -> None:
        self.commandHead: str = s.CMD_HEAD
        self.sessionKey: str

    def setCommandHead(self, head: str) -> None:
        self.commandHead = head

    def sendGroupMessage(self, target: Group, message):
        if not isinstance(message, Message):
            message = Message(raw=message)
        message: Message
        fMsg = {
            "sessionKey": self.sessionKey,
            "target": target.id,
            "messageChain": message.chain()
        }
        requests.post(f'{s.HTTP_URL}/sendGroupMessage', json=fMsg)
    
    def mute(self, group: Group, id: int, time: int):
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
                continue

            if hasattr(Mirai2CoreEvents, eventName):
                e = Mirai2CoreEvents[eventName].value[0](unify.unify_event_dict(response))
                listeners = Loader.eventsListener.get(eventName)

                if listeners is not None:
                    await asyncio.gather(*(listener(self, e) for listener in listeners))

    async def _init_modules(self):
        listeners = Loader.eventsListener.get('Load')
        await asyncio.gather(*(listener(self) for listener in listeners))

    def run(self):

        asyncio.get_event_loop().run_until_complete(self._init_modules())   # init modules

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
