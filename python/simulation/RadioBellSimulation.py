#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 22 18:04:21 2026

@author: badi
"""

from  threading import Thread, Timer
class RadioBellSimulation(object):
    def __init__(self, dev_cnt=8):
        print("Simulate %d RadioBell devices"% int(dev_cnt))
        self._slot_cnt = 16
        self._slotTick = Timer(0.0225,self.slot_update)
        self._cnt = dev_cnt
        self._act = -1

    def slot_update(self):
        self._act = (self._act +1)%self._slot_cnt

if __name__ == '__main__':
    rb = RadioBellSimulation(1)
    rb.print("Test")
   