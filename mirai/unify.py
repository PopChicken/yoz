
from typing import Any, Callable, List
from core.message import Message
from copy import deepcopy


__PERMISSION_MAP = {
    'OWNER': 'Owner',
    'ADMINISTRATOR': 'Admin',
    'ADMIN': 'Admin',
    'MEMBER': 'Member'
}


def unifyEventDict(event_dict: dict) -> dict:
    event_dict = deepcopy(event_dict)
    if 'sender' in event_dict:
        sender = event_dict['sender']
        if 'permission' in sender:
            event_dict['sender']['permission'] = \
                __PERMISSION_MAP[sender['permission'].upper()]
        if 'group' in sender:
            group = sender['group']
            if 'permission' in group:
                event_dict['sender']['group']['permission'] = \
                    __PERMISSION_MAP[group['permission'].upper()]
    return event_dict


def unifyMessage2Chain(message: Message) -> List[dict]:
    pass


def unifyTemp2FriendEvent(event_dict: dict) -> dict:
    event_dict = deepcopy(event_dict)
    event_dict['type'] = 'FriendMessage'
    event_dict['sender']['nickname'] = event_dict['sender']['memberName']
    event_dict['sender']['remark'] = ''
    del event_dict['sender']['memberName']
    del event_dict['sender']['permission']
    del event_dict['sender']['group']
    return event_dict
