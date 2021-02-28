import os

class Data:
    __dataPath = './data'
    
    def __init__(self, moduleName) -> None:
        self.moduleName = moduleName

        moduleFolder = f'{Data.__dataPath}/{self.moduleName}'
        if not os.path.exists(moduleFolder):
            os.makedirs(moduleFolder)

    def getfo(self) -> str:
        return f'{Data.__dataPath}/{self.moduleName}'