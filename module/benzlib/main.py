import re
import requests
import yaml

from urllib.parse import urlparse
from bisect import bisect_left
from typing import Any, List, Tuple
from enum import Enum
from requests.exceptions import ConnectionError

from core.extern.config import Config
from core.application import App
from core.loader import CommandType, Loader
from core.message import Message, RefMsg
from core.event import GroupMessageRecvEvent
from util.crontab import Crontab
from core.extern.message.enums import MessageType

from pyparsing import Combine, Regex, ParseException, White, \
    Word, delimitedList, lineEnd, Suppress, nums, Optional


config = Config('benzlib')

settings = {
    'enabled_groups': [],
    'admin': [
        1035522103,
        1921277934
    ],
    'ymdb_host': '127.0.0.1',
    'ymdb_ssl': False,
    'ymdb_port': 8000,
    'imgbed_token': '',
    'secret_key': ''
}

website = 'https://ymdb.jnn.icu'
imgbed_manager = 'https://m.pic.jnn.icu'
imgbed = 'https://pic.jnn.icu'
netloc = ''

crontab = Crontab()

service_online = True

quote = Suppress('"')
content_no_space = Regex(r'[^\s"]+')
content_no_space_semicolon = Regex(r'[^\s;"]+')
content_quoted = quote + Regex(r'[^"]+') + quote
content = content_quoted | content_no_space
number = Combine(Word(nums) + '.' + Word(nums)) | Word(nums)
any_no_quote = Regex(r'[^"]*')
integer = Word(nums)


class RespStatus(Enum):
    Success = 0
    Offline = 1
    Error = 2


def test_service() -> None:
    global service_online
    try:
        resp_body = requests.get(f'{netloc}/test')
        resp = resp_body.json()
    except ValueError:
        App.logger.error("the YMDB service is broken")
        crontab.add('service_tester', 5, test_service)
        return
    except ConnectionError:
        service_online = False
        crontab.add('service_tester', 5, test_service)
        return

    if resp.get('code') == 0:
        service_online = True
        App.logger.info("re-connected with YMDB service")
    else:
        crontab.add('service_tester', 5, test_service)
    

def make_req(path: str, json: dict=None) -> Tuple[RespStatus, dict | Any]:
    global service_online
    if service_online is False:
        return RespStatus.Offline, None
    try:
        if json is None:
            resp_body = requests.get(f'{netloc}/{path}')
        else:
            resp_body = requests.post(f'{netloc}/{path}', json=json)
        resp = resp_body.json()
    except ValueError:
        App.logger.warn("error response from the YMDB service")
        return RespStatus.Offline, None
    except ConnectionError:
        App.logger.warn("connection lost with the YMDB service")
        service_online = False
        test_service()
        return RespStatus.Offline, None

    if resp.get('code') == 0:
        return RespStatus.Success, resp.get('response')

    return RespStatus.Error, resp.get('msg')


def upload_img():
    pass


def existElem(l: list, elem: Any) -> bool:
    i = bisect_left(l, elem)
    if i != len(l) and l[i] == elem:
        return True
    return False


@Loader.listen('Load')
def onLoad(app: App):
    global settings
    global netloc

    settings_tmp = settings.copy()

    haveError = False

    conf = config.getf('conf.yml')
    if conf is None:
        conf = config.touch('conf.yml')
    else:
        newSettings = yaml.load(conf, Loader=yaml.FullLoader)
        try:
            settings_tmp = config.update(settings, newSettings)
        except Exception as e:
            app.logger.info('配置文件损坏，重置为默认配置，旧文件备份为 conf.yml.bkp')
            try:
                config.backup('conf.yml')
            except Exception as e:
                app.logger.info('备份失败，使用默认配置，取消覆写 conf.yml')

    conf.seek(0)
    conf.truncate()

    if not haveError:
        settings = settings_tmp
        yaml.dump(settings_tmp, conf)

    settings['enabled_groups'].sort()
    settings['admin'].sort()

    schema = 'http'
    if settings['ymdb_ssl']:
        schema = 'https'
    netloc = f'{schema}://{settings["ymdb_host"]}:{settings["ymdb_port"]}'
    
    conf.close()

    app.logger.info('BenzLib loaded successfully')


@Loader.command('新本子', CommandType.Group)
def addBenz(app: App, e: GroupMessageRecvEvent):
    if not existElem(settings['enabled_groups'], e.group.id):
        return

    if not existElem(settings['admin'], e.sender.id):
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 只有被授权的绅士才可以执行该指令哦~"
        ))
        return

    arguments = str(e.msg).strip()

    if len(arguments) == 0:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 使用方法是:\n"
             "#新本子 <标题> <作者> <简介> <评分>\n"
             "注意: 含空格的内容需要用引号包裹起来~")
        ))
        return

    pattern = content + content + content + number + lineEnd
    try:
        comp = pattern.parseString(arguments)
    except ParseException:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            f" 格式不对喔~"
        ))
        return

    title: str = comp[0]
    author: str = comp[1]
    brief: str = comp[2]
    rating: float = float(comp[3])

    if len(title) > 64:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 标题太长了啦~"
        ))
        return

    if len(title) < 4:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 标题太短了啦~"
        ))
        return

    if len(author) > 38:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 作者名称太长了啦~"
        ))
        return

    if len(author) < 2:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 作者名称太短了啦~"
        ))
        return

    if rating > 10:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 评分最高为10哦~"
        ))
        return
    
    stat, resp = make_req('manga/add', {
        'title': title,
        'author': author,
        'brief': brief,
        'rating': rating
    })

    if stat == RespStatus.Offline:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " YMDB服务已离线，请稍后再试~"
        ))
        return

    if stat == RespStatus.Error:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 操作失败...YMDB服务提示信息:\n"
             f"{resp}")
        ))
        return
    
    app.sendGroupMessage(e.group.id, Message.parse(
        RefMsg(target=e.sender.id),
        (" 操作成功~\n"
         f"新本子的ID是: {resp['manga_id']}")
    ))


@Loader.command('删本子', CommandType.Group)
def delBenz(app: App, e: GroupMessageRecvEvent):
    if not existElem(settings['enabled_groups'], e.group.id):
        return

    arguments = str(e.msg).strip()

    if len(arguments) == 0:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 使用方法是:\n"
             "#删本子 <本子ID>\n"
             "注意: 本子从数据库中删除后不会从精华消息中移除喔~")
        ))
        return


@Loader.command('新标签', CommandType.Group)
def addTag(app: App, e: GroupMessageRecvEvent):
    if not existElem(settings['enabled_groups'], e.group.id):
        return

    if not existElem(settings['admin'], e.sender.id):
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 只有被授权的绅士才可以执行该指令哦~"
        ))
        return

    argument = str(e.msg).strip()

    if len(argument) == 0:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 使用方法是:\n"
             "#新标签 <名称>\n"
             "注意: 标签不能包含空格喔~")
        ))
        return

    if argument.find(' ') != -1:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 格式不对喔~"
        ))
        return

    if len(argument) > 38:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 标签太长了啦~"
        ))
        return

    if len(argument) < 2:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 标签太短了啦~"
        ))
        return

    stat, resp = make_req('tag/add', {
        'name': argument
    })

    if stat == RespStatus.Offline:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " YMDB服务已离线，请稍后再试~"
        ))
        return

    if stat == RespStatus.Error:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 操作失败...YMDB服务提示信息:\n"
             f"{resp}")
        ))
        return

    app.sendGroupMessage(e.group.id, Message.parse(
        RefMsg(target=e.sender.id),
        " 操作成功~"
    ))


@Loader.command('新合集', CommandType.Group)
def addGallery(app: App, e: GroupMessageRecvEvent):
    if not existElem(settings['enabled_groups'], e.group.id):
        return

    if not existElem(settings['admin'], e.sender.id):
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 只有被授权的绅士才可以执行该指令哦~"
        ))
        return

    arguments = str(e.msg).strip()

    if len(arguments) == 0:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 使用方法是:\n"
             "#新合集 <名称> <描述>\n"
             "注意: 合集名称不可以包含空格，含空格的描述需要用引号包裹起来~")
        ))
        return

    pattern = content_no_space + content + lineEnd

    try:
        comp = pattern.parseString(arguments)
    except ParseException:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            f" 格式不对喔~"
        ))
        return

    name: str = comp[0]
    description: str = comp[1]

    if len(name) > 38:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 合集名称太长了啦~"
        ))
        return

    if len(name) < 2:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 合集名称太短了啦~"
        ))
        return

    stat, resp = make_req('gallery/add', {
        'name': name,
        'owner': f'{e.sender.id}',
        'description': description
    })

    if stat == RespStatus.Offline:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " YMDB服务已离线，请稍后再试~"
        ))
        return

    if stat == RespStatus.Error:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 操作失败...YMDB服务提示信息:\n"
             f"{resp}")
        ))
        return
    
    app.sendGroupMessage(e.group.id, Message.parse(
        RefMsg(target=e.sender.id),
        " 操作成功~"
    ))


@Loader.command('搜本子', CommandType.Group)
def searchBenz(app: App, e: GroupMessageRecvEvent):
    if not existElem(settings['enabled_groups'], e.group.id):
        return

    argument = str(e.msg).strip()

    if len(argument) == 0:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 使用方法是:\n"
             "#搜本子 <合集>; <标题>; <作者>; <最低评分>; <标签1> <标签2> ...\n"
             "注意:\n\t合集、标签名称不能包含空格喔~\n"
             "\t标题、作者中的';'和空格可以包裹在引号中~\n"
             "\t所有参数都是可选参数，某个参数不需要时只加分号即可~\n"
             "\t分号前后的空格也是可选的~\n"
             "\t标签支持任意多个，但是必须用空格分开喔~")
        ))
        return
    
    semicolon = Suppress(';')
    pattern = Optional(content_no_space_semicolon, '') + semicolon \
        + Optional(content_quoted | content_no_space_semicolon, '') + semicolon \
        + Optional(content_quoted | content_no_space_semicolon, '') + semicolon \
        + Optional(number, '') + semicolon + any_no_quote
    
    try:
        comp: List[str] = pattern.parseString(argument)
    except ParseException:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 格式不对喔~"
        ))
        return
    
    # App.logger.info(comp)

    tags_pattern = Optional(delimitedList(content_no_space, delim=White(' ')))

    try:
        tags_comp = tags_pattern.parseString(comp[4])
    except ParseException as e:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 格式不对喔~"
        ))
        return

    # App.logger.info(tags_comp)

    gallery: str = comp[0].strip()
    title: str = comp[1].strip()
    author: str = comp[2].strip()
    rating: str = comp[3].strip()
    tags: List[str] = tags_comp.asList()

    req = {}

    no_filter = True

    if len(gallery) > 0:
        no_filter = False
        req['gallery'] = gallery
    if len(title) > 0:
        no_filter = False
        req['title'] = title
    if len(author) > 0:
        no_filter = False
        req['author'] = author
    if len(rating) > 0:
        no_filter = False
        req['minRating'] = float(rating)
    if len(tags) > 0:
        no_filter = False
        req['tag'] = tags
    
    if no_filter:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 请至少填写一个约束条件喔~"
        ))
        return

    stat, resp = make_req('token/gen', req)

    if stat == RespStatus.Offline:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " YMDB服务已离线，请稍后再试~"
        ))
        return

    if stat == RespStatus.Error:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 操作失败...YMDB服务提示信息:\n"
             f"{resp}")
        ))
        return

    app.sendGroupMessage(e.group.id, Message.parse(
        RefMsg(target=e.sender.id),
        (" 这是你的搜索结果~\n"
         f"{website}/search/{resp.get('token')}")
    ))
    """
    manga_list: List[dict] = resp['manga_list']
    if len(manga_list) == 0:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 没有搜到喔~"
        ))
    else:
        result = ""
        for manga in manga_list:
            result += f"\n{manga['manga_id']} | {manga['title']} | {manga['author']}" \
                + f" | {manga['brief']} | {manga['rating']}"
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 本子搜索结果:\n"
             f"本子ID | 标题 | 作者 | 简介 | 评分"
             f"{result}")
        ))
    """

@Loader.command('全部标签', CommandType.Group)
def addTag(app: App, e: GroupMessageRecvEvent):
    if not existElem(settings['enabled_groups'], e.group.id):
        return

    argument = str(e.msg).strip()

    if len(argument) > 0:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 格式不对喔~\n这个指令不需要参数~"
        ))

    stat, resp = make_req('tag/all')

    if stat == RespStatus.Offline:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " YMDB服务已离线，请稍后再试~"
        ))
        return

    if stat == RespStatus.Error:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 操作失败...YMDB服务提示信息:\n"
             f"{resp}")
        ))
        return

    tag_list: list = resp['tag_list']
    app.sendGroupMessage(e.group.id, Message.parse(
        RefMsg(target=e.sender.id),
        (" 标签列表:\n"
         f"{' '.join(tag_list)}")
    ))


@Loader.command('搜标签', CommandType.Group)
def searchTag(app: App, e: GroupMessageRecvEvent):
    if not existElem(settings['enabled_groups'], e.group.id):
        return

    argument = str(e.msg).strip()

    if len(argument) == 0:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 使用方法是:\n"
             "#搜标签 <名称>\n"
             "注意: 标签不能包含空格喔~")
        ))
        return

    if argument.find(' ') != -1:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 格式不对喔~"
        ))
        return

    if len(argument) > 38:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 标签太长了啦~"
        ))
        return

    stat, resp = make_req('tag/search', {
        'text': argument
    })

    if stat == RespStatus.Offline:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " YMDB服务已离线，请稍后再试~"
        ))
        return

    if stat == RespStatus.Error:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 操作失败...YMDB服务提示信息:\n"
             f"{resp}")
        ))
        return

    tag_list: list = resp['tag_list']
    if len(tag_list) == 0:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 没有搜到喔~"
        ))
    else:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 标签搜索结果:\n"
             f"{' '.join(tag_list)}")
        ))


@Loader.command('贴标签', CommandType.Group)
def setTag(app: App, e: GroupMessageRecvEvent):
    if not existElem(settings['enabled_groups'], e.group.id):
        return

    argument = str(e.msg).strip()

    if len(argument) == 0:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 使用方法是:\n"
             "#贴标签 <本子ID> <标签>\n"
             "注意: 标签不能包含空格且需要已经创建喔~")
        ))
        return
    
    pattern = integer + content_no_space
    
    try:
        comp = pattern.parseString(argument)
    except ParseException:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 格式不对喔~"
        ))
        return
    
    manga_id: int = int(comp[0])
    tag: str = comp[1]

    stat, resp = make_req('manga/setTag', {
        'manga_id': manga_id,
        'tag': tag
    })

    if stat == RespStatus.Offline:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " YMDB服务已离线，请稍后再试~"
        ))
        return

    if stat == RespStatus.Error:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 操作失败...YMDB服务提示信息:\n"
             f"{resp}")
        ))
        return

    app.sendGroupMessage(e.group.id, Message.parse(
        RefMsg(target=e.sender.id),
        " 操作成功~"
    ))


@Loader.command('本子', CommandType.Group)
def getManga(app: App, e: GroupMessageRecvEvent):
    if not existElem(settings['enabled_groups'], e.group.id):
        return

    argument = str(e.msg).strip()

    if len(argument) == 0:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 使用方法是:\n"
             "#贴标签 <本子ID> <标签>\n"
             "注意: 标签不能包含空格且需要已经创建喔~")
        ))
        return

    pattern = integer

    try:
        comp = pattern.parseString(argument)
    except ParseException:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 格式不对喔~"
        ))
        return
    
    manga_id: int = int(comp[0])
    stat, resp = make_req('manga/get', {
        'manga_id': manga_id
    })

    if stat == RespStatus.Offline:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " YMDB服务已离线，请稍后再试~"
        ))
        return

    if stat == RespStatus.Error:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 操作失败...YMDB服务提示信息:\n"
             f"{resp}")
        ))
        return

    stat, resp = make_req('token/gen', {
        'manga_id': manga_id
    })

    if stat == RespStatus.Offline:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " YMDB服务已离线，请稍后再试~"
        ))
        return

    if stat == RespStatus.Error:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 操作失败...YMDB服务提示信息:\n"
             f"{resp}")
        ))
        return
    
    app.sendGroupMessage(e.group.id, Message.parse(
        RefMsg(target=e.sender.id),
        (" 这是你要的本子~\n"
         f"{website}/manga/detail/{resp.get('token')}")
    ))


@Loader.command('缩略图', CommandType.Group)
def setThunmbnail(app: App, e: GroupMessageRecvEvent):
    if not existElem(settings['enabled_groups'], e.group.id):
        return

    argument = str(e.msg).strip()

    if len(argument) == 0:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 使用方法是:\n"
             "#缩略图 <本子ID> <图片>\n"
             "注意: 图片不能超过5MB喔~")
        ))
        return
    
    if len(e.msg.msgChain) != 2 or \
       e.msg.msgChain[0].type != MessageType.TextMessage or \
       e.msg.msgChain[1].type != MessageType.ImageMessage:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 格式不对喔~"
        ))
        return
    
    argument = str(e.msg.msgChain[0]).strip()

    pattern = integer

    try:
        comp = pattern.parseString(argument)
    except ParseException:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 格式不对喔~"
        ))
        return
    
    manga_id: int = int(comp[0])
    img_url: str = e.msg.msgChain[1].url

    img_resp = requests.get(img_url)

    pattern = r'^http://gchat.qpic.cn/gchatpic_new/\d+/\d+\-\d+\-([0-9A-Z]+)/.*'
    img_name = re.match(pattern, img_url).group(1) + '.jpg'
    headers={'token': settings['imgbed_token']}
    files = [
        ('image', (img_name, img_resp.content, 'image/jpeg'))
    ]

    stat, resp = make_req('manga/get', {
        'manga_id': manga_id
    })

    if stat == RespStatus.Offline:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " YMDB服务已离线，请稍后再试~"
        ))
        return

    if stat == RespStatus.Error:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 操作失败...YMDB服务提示信息:\n"
             f"{resp}")
        ))
        return

    if resp['thumbnail_id'] != -1:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 已存在缩略图记录，尝试清除..."
        ))
        try:
            data = {'id': resp['thumbnail_id']}
            upload_resp = requests.post(f'{imgbed_manager}/api/delete', headers=headers, data=data).json()
        except ConnectionError:
            App.logger.warn("lost connection to image bed service")
            app.sendGroupMessage(e.group.id, Message.parse(
                RefMsg(target=e.sender.id),
                " 服务器异常，上传失败..."
            ))
            return
        except ValueError:
            App.logger.warn("service returns bad json response")
            app.sendGroupMessage(e.group.id, Message.parse(
                RefMsg(target=e.sender.id),
                " 服务器异常，上传失败..."
            ))
            return

    try:
        upload_resp = requests.post(f'{imgbed_manager}/api/upload', headers=headers, files=files).json()
    except ConnectionError:
        App.logger.warn("lost connection to image bed service")
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 服务器异常，上传失败..."
        ))
        return
    except ValueError:
        App.logger.warn("service returns bad json response")
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 服务器异常，上传失败..."
        ))
        return

    if upload_resp['code'] != 200:
        App.logger.info(f"'{img_name}' upload failed: {upload_resp['msg']}")
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " 服务器异常，上传失败..."
        ))
        return

    url = urlparse(upload_resp['data']['url'])
    thumbnail_id = int(upload_resp['data']['id'])
    thumbnail = f'{imgbed}{url.path}'
    
    App.logger.info(f"'{img_name}' uploaded successfully with id '{thumbnail_id}' and url '{thumbnail}'")

    stat, resp = make_req('manga/setThumbnail', {
        'manga_id': manga_id,
        'thumbnail': thumbnail,
        'thumbnail_id': thumbnail_id
    })

    if stat == RespStatus.Offline:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            " YMDB服务已离线，请稍后再试~"
        ))
        return

    if stat == RespStatus.Error:
        app.sendGroupMessage(e.group.id, Message.parse(
            RefMsg(target=e.sender.id),
            (" 操作失败...YMDB服务提示信息:\n"
             f"{resp}")
        ))
        return
    
    app.sendGroupMessage(e.group.id, Message.parse(
        RefMsg(target=e.sender.id),
        " 操作成功~"
    ))