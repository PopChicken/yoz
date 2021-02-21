
from typing import List
from core.message import Message


__PERMISSION_MAP = {
    'OWNER': 'Owner',
    'ADMINISTRATOR': 'Admin',
    'MEMBER': 'Member'
}


def unify_event_dict(event_dict: dict) -> dict:
    event_dict = event_dict.copy()
    if 'sender' in event_dict:
        sender = event_dict['sender']
        event_dict['sender']['permission'] = \
            __PERMISSION_MAP[sender['permission']]
        event_dict
        if 'group' in sender:
            group = sender['group']
            event_dict['sender']['group']['permission'] = \
                __PERMISSION_MAP[group['permission']]
    return event_dict

def unify_message2chain(message: Message) -> List[dict]:
    pass
