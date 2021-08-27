from mirai.application import Mirai
from core.loader import Loader

Loader.loadPlugins('module')
Loader.loadPlugins('module')


appMirai = Mirai()
appMirai.run()

# TODO 模块优先级