#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan  1 14:38:58 2026

@author: badi
"""
from GetAttribute import GetAttribute

class State(GetAttribute):
    def __init__(self, log):
        super().__init__()
        #print("Constructor of state")
        self.start = "state_t"
        self.end = ">>> SM_STATE_WAIT_FOR_TX_DONE"
        self.log = log
        print("Scan in State")
        self._first  = int(self.getFromLog("first"))
        self._cnt    = int(self.getFromLog("cnt"))
        self._clabel = int(self.getFromLog("clabel"))
        self._label  = self.getFromLog("label", True).split()
        self._state  = self.getFromLog("State", True).split()


    def __str__(self):
        res = []
        res.append("first   : %d" %  self.first)        
        res.append("cnt     : %d" %  self.cnt)
        res.append("clabel  : %d" %  self.clabel)
        res.append("label   : %s" %  self.label)
        res.append("state   : %s "%  self.state)
        return "\n".join(res)
    
    
    @property
    def first(self):
        return self._first

    @property
    def cnt(self):
        return self._cnt

    @property
    def clabel(self):
        return self._clabel

    @property
    def label(self):
        return self._label
    
    @property
    def state(self):
        return self._state

 