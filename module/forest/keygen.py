import uuid
import pydblite

from core.extern.data import Data


def genKeys(num: int, effecct: float):
    dataPath = Data('forest').getfo()
    db = pydblite.Base(f'{dataPath}/keys.db')
    if db.exists():
        db.open()
    else:
        db.create('key', 'effect')
        db.create_index('uuid')
        db.commit()

    for i in range(0, num):
        key = uuid.uuid4()
        db.insert(key=key, effect=effecct)
    db.commit()
