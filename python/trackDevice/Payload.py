#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 31 17:43:23 2025
""+
@author: badi
"""
from GetAttribute import *
from State import State

class Payload(GetAttribute):
    _log = None
    def __init__(self, log):
        super().__init__(log=log)
        #print("Constructor of payload" )
        self.start = "payload_t"
        self.end = "state_t"
        self.log = log
        print("Scan in Payload")
        self._slot  = int(self.getFromLog("slot"))
        self._hubCnt= int(self.getFromLog("hubCnt"))
        self._init  = int(self.getFromLog("init"))
        self._conf  = int(self.getFromLog("conf"))
        self._state = State(self.log)

    def __str__(self):
        res = []
        res.append("slot    : %d"%  self.slot)        
        res.append("hubCnt  : %d"%  self.hubCnt)
        res.append("init    : %d"%  self.init)
        res.append("conf    : %d"%  self.conf)
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
    