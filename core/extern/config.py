import io
import copy
import shutil
import os

from pathlib import Path

class Config:
    __configPath = './config'
    
    @classmethod
    def update(cls, default: dict, loaded: dict) -> dict:
        new = copy.deepcopy(default)
        for key in loaded.keys():
            if key not in new:
                continue
            if isinstance(loaded[key], dict):
                new[key] = cls.update(new[key], loaded[key])
            else:
                new[key] = loaded[key]
        return new

    def __init__(self, moduleName: str) -> None:
        self.moduleName = moduleName

        moduleFolder = f'{Config.__configPath}/{self.moduleName}'
        if not os.path.exists(moduleFolder):
            os.makedirs(moduleFolder)

    def getf(self, fileName: str) -> io.TextIOWrapper:
        path = f'{Config.__configPath}/{self.moduleName}/{fileName}'
        if os.path.exists(path):
            return open(path, 'r+', encoding='utf-8')
        else:
            return None
    
    def touch(self, fileName: str) -> io.TextIOWrapper:
        path = f'{Config.__configPath}/{self.moduleName}/{fileName}'
        Path(path).touch()
        return open(path, 'r+', encoding='utf-8')
    
    def backup(self, fileName: str) -> None:
        path = f'{Config.__configPath}/{self.moduleName}/{fileName}'
        shutil.copyfile(path, f'{path}.bkp')
