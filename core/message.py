import re
import hashlib
import copy

from typing import List, overload

from core.extern.message.enums import MessageType
from core.extern.message.enums import *


class BaseMsg:

    def __init__(self, type: MessageType) -> None:
        self.type: MessageType

        self.type = type
    
    def getType(self) -> MessageType:
        return copy.copy(self.type)
    
    def dict() -> dict:
        pass


class TextMsg(BaseMsg):

    def __init__(self, data: dict = None, text: str = None) -> None:
        self.text: str

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
        self.target: int
        self.display: str

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
        self.imageId: str
        self.online: bool
        self.url: str

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
        self.uid: int

        if chain is not None and raw is None:
            self.uid = chain[0]['id']
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
            self.phraseAppend(raw)

    def __str__(self) -> str:
        msgStr = ''
        for msg in self.msgChain:
            msgStr += str(msg)
        return msgStr

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
    
    def phraseAppend(self, raw: str) -> None:
        typeMatch = '|'.join(list(Message.__CONVERTOR.keys()))
        components = re.split(rf'(\[YOZ:({typeMatch}).*\])', raw)

        skip = False

        for component in components:
            if len(component) == 0:
                continue
            if skip:
                skip = False
                continue
            m = re.match(rf'\[YOZ:({typeMatch}).*\]', component)
            if m is None:
                self.msgChain.append(TextMsg(text=component))
            else:
                skip = True
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
    def phrase(cls, *obj):
        msg = cls()
        for partMsg in obj:
            if isinstance(partMsg, BaseMsg):
                msg.msgChain.append(partMsg)
            elif isinstance(partMsg, str):
                msg.phraseAppend(partMsg)
        return msg
