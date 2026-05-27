#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Dec 28 19:10:05 2025

@author: badi
"""
import os
import glob
import threading
from GetAttribute import *
from RadioBellDevice import *

class RadioBell(GetAttribute):
    _LOG_FOLDER = "/log/"
    def __init__(self, *ports):
        print("Constructor with ports %s" % ports)
        super().__init__()
        self._radio_dev={}
        self._ready = False
        self.sRadioPort = ports[0]
        self._slot2dev={}
        self._cdir = os.path.dirname(os.path.realpath(__file__))+RadioBell._LOG_FOLDER
        self.timer = threading.Timer(0.005, self._update_devices)
        self.timer.start()
    
    def _update_devices(self):
        #print("cmdlineports %s is type %s" % (self.sRadioPort))
        cexports = []
        for ip in self.sRadioPort:
            cexports.extend(glob.glob(ip))
        #print("Existing command line ports %s" % cexports)
        for s in cexports:
            print("Check serial %s: "% s, end='')
            self._radio_dev[s] = RadioBellDevice(s)
            if self._radio_dev[s].isOk:
                slot = self._radio_dev[s].slot
                self._slot2dev[self._radio_dev[s].slot] = s
                print("Map dev %s to slot %d"% (s, slot ))
        self._ready = True
        return  

    def send_key(self, key, slot):
        print("Send key %s to slot %d"% (key, slot))
        dev = self._slot2dev[slot]
        res = self._radio_dev[dev].send_receive(key)
        
    def clear_slot(self, slot):
        print("Clear all log of slot %d" % (slot))
        self._radio_dev[dev].log   = []
        self._radio_dev[dev].reset = []
    
    def clear_log(self):
        print("Clear all logs in %s " % self._cdir)
        for filename in os.listdir(self._cdir):
            file_path = os.path.join(self._cdir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))    
                
    def print_log(self, slot):
        dev = self._slot2dev[slot]
        for line in self._radio_dev[dev].log:
            print("%s" % line)
    
    def get_appli_frame(self, slot):
        dev = self._slot2dev[slot]
        af  = self._radio_dev[dev].lastAF
        return af
    
    def save_log(self, slot):
        dev = self._slot2dev[slot]
        lk  = self._radio_dev[dev].last_key_send
        fname =  self._cdir+("slot_%d_key_%d" % (slot, lk))+".log"
        print("Save log %s " % fname)
        with open(fname, 'w') as file:
            file.writelines(f"%s\n" % i for i in self._radio_dev[dev].log)
 
    def save_reset(self, slot):
        dev = self._slot2dev[slot]
        fname =  self._cdir+("reset_slot_%d" % (slot))+".log"
        print("Save reset %s " % fname)
        with open(fname, 'w') as file:
            file.writelines(f"%s\n" % i for i in self._radio_dev[dev].reset)
    
    def get_appli_frame(self, slot):
        dev = self._slot2dev[slot]
        return self._radio_dev[dev].lastAF

        
    @property
    def ready(self):
        return self._ready
