#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Dec 28 19:10:05 2025

@author: badi
"""
import codecs
import threading
import serial 
from GetAttribute import *
from  AppliFrame import *
import serial.tools.list_ports

baudRate = 115200

class RadioBellDevice(GetAttribute):
    
    def __init__(self, serName):
        #print("Constructor radio_bell_device with %s" % self._serName)
        super().__init__()
        self._isOk = False
        self._serName = serName
        self._last_log = []
        self._log = []
        self._line_nr = None
        self._las_key_send = -1
        self.reset = self.send_receive(b"R")
        if self.isOk:
            print("my_slot = %d, channel = %d, linecnt = %d" % (self.slot, self.channel, len(self.reset)))
        else:
            print("NOK")
        #self.timer = threading.Timer(0.005, self._update_devices)
        #print("serName %s is on slot %s"% (self._serName, self.slot))

    def _update_devices(self):
       s = serial.Serial(self._serName, baudRate, timeout=1.5)
       responce = self.send_receive(b"R")
       s.close()
   
    def send_receive(self, send):
        s = serial.Serial(self._serName, baudRate, timeout=1.5)
        ret = []
        s.write(send)
        responce = s.readline()
        while len(responce)>0:
            self.isOk = True
            ret.append(responce)
            responce = s.readline()
        s.close()
        ret = self.clean_line(ret)
        if (send != b'R'):
            self._last_key_send = send
            self._last_log = ret
            if len(self._log) == 0:
                self.line_nr = [0]
                self._log = ret
            else:
                self.line_nr.append(len(self._log))
                self._log.extend(ret)
            print("Start of last  at %d" % self.line_nr[-1])
        return ret
    
    @property
    def lastAF(self):
        af = AppliFrame(self._last_log)
        return af
             
    @property
    def isOk(self):
        return self._isOk
    
    @isOk.setter
    def isOk(self, value):
        self._isOk = value
        
    @property
    def reset(self):
        return self._reset
    
    @reset.setter
    def reset(self, value):
        self._reset = value
    
    @property
    def log(self):
        return self._log
   
    @log.setter
    def log(self, value):
        self._log = value

    @property
    def name(self):
        return self._serName.split("/")[-1]
 
    @property
    def slot(self):
        self._slot = int(self.getFromReset("my_slot"))
        return self._slot
    
    @property
    def channel(self):
        self._channel = int(self.getFromReset("my_channel") )          
        return self._channel
    
    @property
    def last_key_send(self):
        return int(self._last_key_send)
    
