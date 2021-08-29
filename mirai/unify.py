
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
    operator = 'operator'
    if operator not in event_dict:
        operator = 'sender'
    if operator in event_dict:
        sender = event_dict[operator]
        if 'permission' in sender:
            event_dict[operator]['permission'] = \
                __PERMISSION_MAP[sender['permission'].upper()]
        if 'group' in sender:
            group = sender['group']
            if 'permission' in group:
                event_dict[operator]['group']['permission'] = \
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
    return event_dict
