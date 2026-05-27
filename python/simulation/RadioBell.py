#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Dec 28 19:10:05 2025

@author: badi
"""
import os
import sys
import glob
import threading
sys.path.insert(0, "..")
from PyAppliFrame import PyState, PyPayload, PyAppliFrame, EmMsg, KeyState

from RadioBellDevice import *
import AppliFrame

class RadioBell(object):
    _LOG_FOLDER = "/log/"
    def __init__(self, slot_nr):
        print("RadioBell Constructor with slot %s" % slot_nr)
        self._slot_nr     = slot_nr
        self._appli_frame = AppliFrame.AppliFrame()
        self._appli_frame.payload.slot = slot_nr
    
    def run(self):
        pass
        return  
        return self._radio_dev[dev].lastAF

        
if __name__ == '__main__':
     rb = RadioBell(1)
     rb.print("Test")
