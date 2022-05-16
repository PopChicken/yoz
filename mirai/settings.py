import os

_host = os.environ.get('YOZ_MIRAI_API_HOST')
_port = os.environ.get('YOZ_MIRAI_API_PORT')


HOST = 'localhost'
PORT = 8089
AUTH_KEY = 'zJdAWmCXz92DAW3vT'

BOT_ID = 1516161873
NICKNAME = '猫猫'

NEED_VERIFY = False
WS_URL = f'ws://{HOST}:{PORT}'
HTTP_URL = f'http://{HOST}:{PORT}'

CMD_HEAD = '.'
ALT_CMD_HEAD = ['。', '#', '/']

BLACK_LIST = [
    1713688770,
    1252361674
]

if _host is not None:
    HOST = _host
if _port is not None:
    PORT = int(_port)