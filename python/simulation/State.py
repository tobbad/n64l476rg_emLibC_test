#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan  1 14:38:58 2026

@author: badi
"""
from enum import Enum

class bState(Enum):
    OFF = 0
    BLI = 1
    ON  = 2   
    CNT = 3

class kstate(object):
    
    def __init__(self, label):
        self._label = label
        self._kstate = bState.OFF
        
    def propagate(self):
        self._kstate = bState((self._kstate.value+1)%bState.CNT.value)

    @property
    def label(self):
        return self._label
    
    @property
    def kstate(self):
        return self._kstate
        
    def __str__(self):
        res = "%s: %s\n"% (self._label, self._kstate)
        return res
                   

class State(object):
    maxCnt = 16
    def __init__(self, first=0, cnt=15):
        #print("Constructor of state")
        self._first  = first
        self._cnt    = cnt
        self._dirty    = False         
        self._clabel  = [0,0,0,0]
        self._state  = {"%x"%i:kstate("%x"%i) for i in range(0, State.maxCnt)}

    def __str__(self):
        res = []
        res.append("first   : %d" %  self._first)        
        res.append("cnt     : %d" %  self._cnt)
        res.append("dirty   : %d" %  self._dirty)
        res.append("State   :\n %s "%  " ".join("%s"%self._state["%x"%i] for i in range(0, State.maxCnt)))
        return "\n".join(res)
    
    def propagate(self, key):
        if ((key>=self._first) and (key<self._first+self._cnt)):
            self._state["%x"%key].propagate()
            self._dirty = True
    
    @property
    def first(self):
        return self._first

    @property
    def cnt(self):
        return self._cnt

    @property
    def state(self):
        return self._state

    @property
    def dirty(self):
        return self._dirty

    @property
    def clabel(self):
        return self._clabel

    @property
    def bytearray(self):
        ba = bytearray(40)
        idx=0
        ba[idx]=self._first
        idx+=1
        ba[idx]=self._cnt
        idx+=1
        ba[idx]=self._dirty
        idx+=1
        ba[idx]=0xff
        idx+=1
        for i in self.clabel:
            ba[idx]=i
            idx+=1
        for i in range(0, State.maxCnt):
            ba[idx] = self._state["%x"%i].kstate.value
            idx+=1
        for i in range(0, State.maxCnt):
            ba[idx] = ord(self._state["%x"%i].label[0])
            idx+=1
        return ba

 
if __name__ == '__main__':
    s = State(1,8)
    for i in range(0, State.maxCnt):
        s.propagate(i)
    print(s.bytearray)
    print(len(s.bytearray))
    
