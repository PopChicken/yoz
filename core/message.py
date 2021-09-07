import re
import hashlib
import copy

from typing import List

from core.extern.message.enums import MessageType
from core.extern.message.enums import *


class BaseMsg:

    def __init__(self, type: MessageType) -> None:
        self.type: MessageType = None

        self.type = type
    
    def getType(self) -> MessageType:
        return copy.copy(self.type)
    
    def dict() -> dict:
        pass


class TextMsg(BaseMsg):

    def __init__(self, data: dict = None, text: str = None) -> None:
        self.text: str = None

        super().__init__(MessageType.TextMessage)
        if data is not None and text is None:
            try:
                self.text = data['text']
            except:
                raise Exception("Text 消息初始化错误 输入: ", data)
        elif data is None and text is not None:
            self.text = text

    def __str__(self) -> str:
        return self.text
    
    def dict(self):
        return {
            'text': self.text
        }


class RefMsg(BaseMsg):
    #target: Member

    def __init__(self, data: dict = None, target: int = None) -> None:
        self.target: int = None
        self.display: str = None

        super().__init__(MessageType.AtMessage)
        if data is not None and target is None:
            try:
                self.target = int(data['target'])
                # self.display = data['display']
            except:
                raise Exception("At 消息初始化错误 输入: ", data)
        elif data is None and target is not None:
            self.target = int(target)

    def __str__(self) -> str:
        return f'[YOZ:At,target={self.target}]'
    
    def dict(self):
        return {
            'target': self.target
        }


class ImgMsg(BaseMsg):
    
    def __init__(self, data: dict) -> None:
        self.imageId: str = None
        self.online: bool = None
        self.url: str = None

        super().__init__(MessageType.ImageMessage)

        self.online = False
        self.imageId = data['imageId']
    
    def __str__(self) -> str:
        return f'[YOZ:Image,imageId={self.imageId}]'
    
    def dict(self):
        if self.online:
            return {
                'url': self.url
            }
        else:
            return {
                'imageId': self.imageId
            }


class Message:

    # TODO 在外部实现转换器类 以兼容 Telegram
    # TODO 建议构造输入 mirai 对象的方式，同时将 enums 类移入 mirai 模块

    __TYPE_SOURCE = 'Source'

    __CONVERTOR = {
        'At': RefMsg,
        'Plain': TextMsg,
        'Image': ImgMsg
    }

    def __init__(self, chain: List[dict] = None, raw: str = None) -> None:
        self.msgChain: List[BaseMsg] = []
        self.uid: int = None
        self.time: int = None

        if chain is not None and raw is None:
            self.uid = chain[0]['id']
            self.time = chain[0]['time']
            for msgDict in chain:
                try:
                    type = msgDict['type']
                    if type == Message.__TYPE_SOURCE:
                        continue
                    if type in Message.__CONVERTOR.keys():
                        self.msgChain.append(
                            Message.__CONVERTOR[type](data=msgDict))
                except Exception as e:
                    print('解析消息链时出现问题:\n\t', e)

        elif chain is None and raw is not None:
            self.parseAppend(raw)

    def __str__(self) -> str:
        msgStr = ''
        for msg in self.msgChain:
            msgStr += str(msg)
        return msgStr

    def __getitem__(self, val):
        if isinstance(val, int):
            return copy.deepcopy(self.msgChain[val])
        elif isinstance(val, slice):
            start = val.start
            stop = val.stop
            step = val.step
            msg = copy.deepcopy(self)
            msg.msgChain = msg.msgChain[start:stop:step]
            return msg

    def strip(self) -> "Message":
        msg = copy.deepcopy(self)
        if len(msg.msgChain) == 0:
            return msg
        if msg.msgChain[0].type == MessageType.TextMessage:
            if len(str(msg.msgChain[0]).strip()) == 0:
                del msg.msgChain[0]
        if len(msg.msgChain) == 0:
            return msg
        if msg.msgChain[-1].type == MessageType.TextMessage:
            if len(str(msg.msgChain[-1]).strip()) == 0:
                del msg.msgChain[-1]
        return msg


    def md5(self) -> str:
        hl = hashlib.md5()
        hl.update(str(self).encode(encoding='utf-8'))
        return hl.hexdigest()
    
    def chain(self) -> List[dict]:
        chain = []
        for msg in self.msgChain:
            msgDict = {}
            msgDict['type'] = msg.getType().value
            msgDict.update(msg.dict())
            chain.append(msgDict)
        return chain

    def join(self, msg: "Message") -> "Message":
        _msg = copy.deepcopy(self)
        _msg.msgChain += msg.msgChain
        return _msg
    
    def append(self, msg: "Message") -> None:
        self.msgChain += msg.msgChain

    def parseAppend(self, raw: str) -> None:
        typeMatch = '|'.join(list(Message.__CONVERTOR.keys()))
        components = re.split(rf'(\[YOZ:({typeMatch})((?!\]).)*\])', raw)

        skip = 0

        for component in components:
            if len(component) == 0:
                continue
            if skip > 0:
                skip -= 1
                continue
            m = re.match(rf'\[YOZ:({typeMatch}).*\]', component)
            if m is None:
                self.msgChain.append(TextMsg(text=component))
            else:
                skip = 2
                typeName = m.group(1)
                properties = dict(re.findall(
                    r',\s*([^,]+)\s*=\s*([^,\]]+)\s*', component))
                self.msgChain.append(
                    Message.__CONVERTOR[typeName](properties))

    def getAtCodes(self) -> List[RefMsg]:
        codes = []
        for msg in self.msgChain:
            if isinstance(msg, RefMsg):
                codes.append(msg)
        return codes

    @classmethod
    def parse(cls, *obj) -> "Message":
        msg = cls()
        for partMsg in obj:
            if isinstance(partMsg, BaseMsg):
                msg.msgChain.append(partMsg)
            elif isinstance(partMsg, str):
                msg.parseAppend(partMsg)
        return msg
