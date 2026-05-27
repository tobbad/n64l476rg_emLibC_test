#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 31 17:42:53 2025

@author: badi
"""
from GetAttribute import GetAttribute
from Payload import Payload

class AppliFrame(GetAttribute):
    def __init__(self, log, line_nr=0):
        print("Scan in AppliFrame")
        super().__init__(log=log)
        self.log = log        
        self.start = "AppliFrame_t"
        self.end   = "payload_t"
        self._Cmd    = self.getFromLog("Cmd")
        print("Cmd = %s" % str(self._Cmd))
        self._CmdLen = self.getFromLog("CmdLen")
        self._Cmdtag = self.getFromLog("Cmdtag")
        self._CmdType= self.getFromLog("CmdType")
        self._DataLen= self.getFromLog("DataLen")
        self.payload = Payload(self.log)

    def __str__(self):
        res = []
        res.append("Cmd     : %d"%  self.Cmd)        
        res.append("CmdLen  : %d"%  self.CmdLen)
        res.append("Cmdtag  : %d"%  self.Cmdtag)
        res.append("CmdType : %d"%  self.CmdType)
        res.append("DataLen : %d"%  self.DataLen)
        this = "\n".join(res)
        print(this)
        return this+"\n"+str(self.payload)

    @property
    def Cmd(self):
        return int(self._Cmd)

    @property
    def CmdLen(self):
        return int(self._CmdLen)

    @property
    def Cmdtag(self):
        return int(self._Cmdtag)

    @property
    def CmdType(self):
        return int(self._CmdType)

    @property
    def DataLen(self):
        return int(self._DataLen)
