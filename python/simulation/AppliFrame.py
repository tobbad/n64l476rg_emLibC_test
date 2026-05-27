#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 31 17:42:53 2025

@author: badi
"""
from Payload import Payload

class AppliFrame(object):
    def __init__(self):
        self._Cmd    = 0
        self._CmdLen = 0
        self._Cmdtag = 0
        self._CmdType= 0
        self._DataLen= 0
        self.payload = Payload()

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
 
    @property
    def bytearray(self):
        ba = bytearray(6)
        idx=0
        ba[idx]=self.Cmd
        idx+=1
        ba[idx]=self.CmdLen
        idx+=1
        ba[idx]=self.Cmdtag
        idx+=1
        ba[idx]=self._CmdType
        idx+=1
        ba[idx]=self._DataLen
        ba += self.payload.bytearray
        return ba



if __name__ == '__main__':
    appli = AppliFrame()
    print(appli.bytearray)
    print(len(appli.bytearray))
