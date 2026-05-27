#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 31 17:43:23 2025
""+
@author: badi
"""
from State import State

class Payload(object):
    _log = None
    def __init__(self):
        #print("Constructor of payload" )
        self._slot  = 0
        self._hubCnt= 0
        self._init  = 1
        self._conf  = 0
        self._clabel  = [0,0,0,0]
        self._state = State(1,8)

    def __str__(self):
        res = []
        res.append("slot    : %d"%  self._slot)        
        res.append("hubCnt  : %d"%  self._hubCnt)
        res.append("init    : %d"%  self._init)
        this = "\n".join(res)
        return this+"\n"+str(self._state)

    @property
    def slot(self):
        return self._slot

    @property
    def hubCnt(self):
        return self._hubCnt

    @property
    def init(self):
        return self._init

    @property
    def conf(self):
        return self._conf

    @property
    def state(self):
        return self._state
    
    @property
    def bytearray(self):
        ba = bytearray(6)
        idx=0
        ba[idx]=self.slot
        idx+=1
        ba[idx]=self.hubCnt
        idx+=1
        ba[idx]=self.init
        idx+=1
        ba[idx]=self.conf
        ba += self.state.bytearray
        return ba


if __name__ == '__main__':
    pl = Payload()
    print(pl.bytearray)
    print(len(pl.bytearray))
