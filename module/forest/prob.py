import random
import yaml

from copy import deepcopy

from core.extern.config import Config

trees: dict = {}

def init(config: Config) -> None:
    global trees
    treef = config.getf('trees.yml')
    trees = yaml.load(treef, Loader=yaml.FullLoader)
    treef.close()


def getQualityDescription(quality: int) -> str:
    return deepcopy(trees['quality'][quality])


def getCongratulations(quality: int) -> str:
    return deepcopy(trees['notification'][quality])


def getItemDetail(id: int) -> dict:
    return deepcopy(trees['item'][int(id/1000)][id])


def lottery(maskProc: float, offset: float=0) -> int:
    global trees
    masks: dict = trees['mask']
    probs: dict = trees['prob']
    for maskNum in masks.keys():
        if maskProc <= maskNum:
            break
    test = random.random() * 100 - offset
    integrate = 0.0
    quals = list(probs.keys())
    quals.sort(reverse=True)
    for quailty in quals:
        prob = probs[quailty] * masks[maskNum][quailty]
        integrate += prob
        if integrate > 0 and test <  integrate:
            break
    itemId = random.choice(list(trees['item'][quailty].keys()))
    return itemId, quailty
