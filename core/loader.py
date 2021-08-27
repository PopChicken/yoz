import importlib
import os
import json
import sys

from typing import Any, Awaitable, Callable, Dict, List, Tuple
from enum import Enum


class CommandType(Enum):
    Group = 0,
    Contact = 1


class ModuleMatcher:
    class Node:
        def __init__(self) -> None:
            self.children: Dict[str, ModuleMatcher.Node] = {}
            self.data: Any = None

        def set(self, data: Any):
            self.data = data

        def clearData(self):
            self.data = None

    def __init__(self) -> None:
        self.root: ModuleMatcher.Node = ModuleMatcher.Node()
        self.__cache = {}
        self.outdate = True

    def search(self, s: str) -> Tuple[str, Any]:
        components = s.split('.')
        node = self.root
        head = ''
        for component in components:    # 遍历时删除无数据叶子节点
            terminate = True
            delList = []
            father = node
            for index, cnode in node.children.items():
                if len(cnode.children) == 0 and cnode.data is None:
                    delList.append(index)
                    continue
                if index != component:
                    continue
                node = cnode
                terminate = False
                break
            for index in delList:
                del father.children[index]
            if terminate:
                break
            if len(head) > 0:
                head += '.'
            head += component
        return head, node.data

    def get(self, module: str) -> Any:
        components = module.split('.')
        components.reverse()
        node = self.root
        while len(components) > 0:    # 遍历时删除无数据叶子节点
            component = components.pop()
            terminate = True
            delList = []
            father = node
            for index, cnode in node.children.items():
                if len(cnode.children) == 0 and cnode.data is None:
                    delList.append(index)
                    continue
                if index != component:
                    continue
                node = cnode
                terminate = False
                break
            for index in delList:
                del father.children[index]
            if terminate and len(component > 0):
                return
        return node.data

    def delete(self, module: str) -> None:
        components = module.split('.')
        components.reverse()
        node = self.root
        while len(components) > 0:    # 遍历时删除无数据叶子节点
            component = components.pop()
            terminate = True
            delList = []
            father = node
            for index, cnode in node.children.items():
                if len(cnode.children) == 0 and cnode.data is None:
                    delList.append(index)
                    continue
                if index != component:
                    continue
                node = cnode
                terminate = False
                break
            for index in delList:
                del father.children[index]
            if terminate and len(component > 0):
                return
        self.outdate = True
        node.clearData()

    def set(self, module: str, data: Any) -> None:
        self.outdate = True
        components = module.split('.')
        node = self.root
        cur = 0
        for component in components:    # 遍历时删除无数据叶子节点
            terminate = True
            delList = []
            father = node
            for index, cnode in node.children.items():
                if len(cnode.children) == 0 and cnode.data is None:
                    delList.append(index)
                    continue
                if index != component:
                    continue
                node = cnode
                terminate = False
                break
            for index in delList:
                del father.children[index]
            if terminate:
                break
            cur += 1
        for component in components[cur:]:
            cnode = ModuleMatcher.Node()
            node.children[component] = cnode
            node = cnode
        node.data = data

    def __dfs(self, node, prefix: str, dict: dict):
        for index, cnode in node.children.items():
            if len(prefix) > 0:
                cprefix = prefix + '.' + index
            else:
                cprefix = index
            if cnode.data is not None:
                dict[cprefix] = cnode.data
            self.__dfs(cnode, cprefix, dict)

    def cache(self) -> dict:
        if not self.outdate:
            return self.__cache
        node = self.root
        self.__dfs(node, '', self.__cache)
        return self.__cache


class PluginMaster:
    def __init__(self, name: str, altername: str, version: str,
                 author: str, description: str, website: str, module: str) -> None:

        if name is None or len(name) == 0:
            raise Exception("name field cannot be null")

        self.name: str = name
        self.altername: str = altername
        self.version: str = version
        self.author: str = author
        self.description: str = description
        self.website: str = website
        self.module: str = module

        self.groupCommands: List[str] = []
        self.contactCommands: List[str] = []
        self.events: List[str] = []

    def install(self) -> None:
        if self.module in sys.modules:
            importlib.reload(sys.modules[self.module])
        else:
            importlib.import_module(self.module)

    def unhook(self) -> None:
        for cmd in self.groupCommands:
            del Loader.groupCommands[cmd]
        for cmd in self.contactCommands:
            del Loader.contactCommands[cmd]
        for event in self.events:
            del Loader.eventsListener[event][self.name]


class Loader:
    lib: ModuleMatcher = ModuleMatcher()

    eventsListener: Dict[
        str, Dict[
            str, List[Callable[[Any], Awaitable]]
        ]
    ] = {}

    groupCommands: Dict[
        str, Callable
    ] = {}

    contactCommands: Dict[
        str, Callable
    ] = {}

    @classmethod
    def getLegal(cls, func: Callable) -> bool:
        result, _ = cls.lib.search(func.__module__)
        return result

    @classmethod
    def listen(cls, eventName: str):
        def lis_decorator(func: Callable):
            module = cls.getLegal(func)
            if len(module) == 0:
                raise Exception('illegal event listener registration attempt')
            cls.eventsListener.setdefault(eventName, {})
            cls.eventsListener[eventName].setdefault(module, [])
            cls.eventsListener[eventName][module].append(func)
            return func
        return lis_decorator

    @classmethod
    def command(cls, command: str, base: CommandType):
        def cmd_decorator(func: Callable):
            if base == CommandType.Group:
                if command in cls.groupCommands:
                    raise Exception("指令重复注册")
                cls.groupCommands[command] = func
            elif base == CommandType.Contact:
                if command in cls.contactCommands:
                    raise Exception("指令重复注册")
                cls.contactCommands[command] = func
            return func
        return cmd_decorator

    # TODO 添加 load after 选项，构造依赖树，自顶向下按顺序加载
    @classmethod
    def loadPlugins(cls, root: str) -> None:
        for dir in os.listdir(root):
            if os.path.isdir(f'{root}/{dir}'):
                manifest = f'{root}/{dir}/yozifest.json'
                if not os.path.exists(manifest) or not os.path.isfile(manifest):
                    continue
                with open(manifest, 'r') as manifest:
                    manifest: dict = json.load(manifest)

                module = f'{root}.{dir}'

                if not 'name' in manifest:
                    raise Exception(
                        f"load {dir} fails with a bad manifest file")

                name = manifest['name']
                if module in cls.lib.cache():
                    # TODO 打印日志告知重新加载
                    plugin: PluginMaster = cls.lib.get(module)
                    if plugin is not None:
                        plugin.unhook()
                        cls.lib.delete(module)
                altername: str = ''
                version: str = ''
                author: str = ''
                description: str = ''
                website: str = ''

                if 'altername' in manifest:
                    altername = manifest['altername']
                if 'version' in manifest:
                    version = manifest['version']
                if 'author' in manifest:
                    author = manifest['author']
                if 'description' in manifest:
                    description = manifest['description']
                if 'website' in manifest:
                    website = manifest['website']

                plugin = PluginMaster(
                    name, altername, version, author, description, website, module)

                cls.lib.set(module, plugin)
                plugin.install()
