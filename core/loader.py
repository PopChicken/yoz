import importlib
import os
import json
import sys

from typing import Any, Awaitable, Callable, Dict, List, Tuple
from enum import Enum

from core.application import App


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
        self.outdated = True

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
            if terminate and len(component) > 0:
                return
        return node.data

    def delete(self, module: str) -> None:
        components = module.split('.')
        components.reverse()
        node = self.root
        while len(components) > 0:    # 遍历时删除无数据叶子节点
            component: str = components.pop()
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
            if terminate and len(component) > 0:
                return
        self.outdated = True
        node.clearData()

    def set(self, module: str, data: Any) -> None:
        self.outdated = True
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
        if not self.outdated:
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

        self.groupCommands: List[Tuple[str, Callable]] = []
        self.contactCommands: List[Tuple[str, Callable]] = []
        self.events: Dict[str, List[Callable]] = {}

        self.__hooked = False

    def install(self) -> None:
        if self.module in sys.modules:
            importlib.reload(sys.modules[self.module])
        else:
            importlib.import_module(self.module)
        self.__hooked = True
        App.logger.info(f"plugin '{self.name}' installed successfully")

    def unhook(self) -> None:
        for cmd, _ in self.groupCommands:
            del Loader.groupCommands[cmd]
        for cmd, _ in self.contactCommands:
            del Loader.contactCommands[cmd]
        for event, _ in self.events.items():
            del Loader.eventsListener[event][self.module]
        self.__hooked = False
        App.logger.info(
            f"observers of plugin '{self.name}' have been unhooked")

    def hook(self) -> None:
        if self.__hooked:
            raise Exception(f"observers of '{self.name}' have already hooked")
        for cmd, func in self.groupCommands:
            if cmd in Loader.groupCommands:
                raise Exception(
                    f"the command '{cmd}' for groups' conversation has been registered")
            Loader.groupCommands[cmd] = func
        for cmd, func in self.contactCommands:
            if cmd in Loader.contactCommands:
                raise Exception(
                    f"the command '{cmd}' for contacts' conversation has been registered")
            Loader.contactCommands[cmd] = func
        for event, funcs in self.events.items():
            Loader.eventsListener.setdefault(event, {})
            Loader.eventsListener[event].setdefault(self.module, [])
            Loader.eventsListener[event][self.module] += funcs
        self.__hooked = True
        App.logger.info(f"observers of plugin '{self.name}' have been hooked")


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
    def getLegal(cls, func: Callable) -> str:
        result, _ = cls.lib.search(func.__module__)
        return result

    @classmethod
    def listen(cls, eventName: str):
        def lis_decorator(func: Callable):
            module = cls.getLegal(func)
            if len(module) == 0:
                raise Exception("illegal event listener registration attempt")
            cls.eventsListener.setdefault(eventName, {})
            cls.eventsListener[eventName].setdefault(module, [])
            cls.eventsListener[eventName][module].append(func)
            master: PluginMaster = cls.lib.get(module)
            master.events.setdefault(eventName, [])
            master.events[eventName].append(func)
            return func
        return lis_decorator

    @classmethod
    def command(cls, command: str, base: CommandType):
        def cmd_decorator(func: Callable):
            module = cls.getLegal(func)
            if len(module) == 0:
                raise Exception("illegal event command registration attempt")
            if base == CommandType.Group:
                if command in cls.groupCommands:
                    raise Exception(
                        f"the command '{command}' for groups' conversation has been registered")
                cls.groupCommands[command] = func
                master: PluginMaster = cls.lib.get(module)
                master.groupCommands.append((command, func))
            elif base == CommandType.Contact:
                if command in cls.contactCommands:
                    raise Exception(
                        f"the command '{command}' for contacts' conversation has been registered")
                cls.contactCommands[command] = func
                master: PluginMaster = cls.lib.get(module)
                master.contactCommands.append((command, func))
            return func
        return cmd_decorator

    # TODO 添加 load after 选项，构造依赖树，自顶向下按顺序加载
    @classmethod
    def loadPlugins(cls, root: str) -> None:
        App.logger.info(f"start to load plugins in '{root}' dynamically")
        for directory in os.listdir(root):
            if os.path.isdir(f'{root}/{directory}'):
                manifest: str = f'{root}/{directory}/yozifest.json'
                if not os.path.exists(manifest) or not os.path.isfile(manifest):
                    continue
                with open(manifest, 'r') as manifestFile:
                    manifest: dict = json.load(manifestFile)

                module = f'{root}.{directory}'

                if 'name' not in manifest:
                    raise Exception(
                        f"load '{directory}' fails with a bad manifest file")

                name = manifest['name']
                App.logger.info(f"'{name}' discovered in '{root}'")
                if module in cls.lib.cache():
                    App.logger.warn(
                        f"'{name}' has already been installed. start to reload it")
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
