#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan  6 15:37:50 2026

@author: badi
"""
from GetAttribute import *
import unittest

class RegExp_test(unittest.TestCase):
        
    def setUp(self):
        pass
    
    def testCmd(self):
        test_str = ["0000011074: Cmd     = 1",]
        ga = GetAttribute(test_str, multi_line=False)
        a = int(ga.getFromLog("Cmd"))
        print("test Cmd  %d"  % a)
        self.assertEqual(a, 1)
        
    def testhubCnt(self):
        test_str = ["0000009174: hubCnt= 0",]
        ga = GetAttribute(test_str, multi_line=False)
        a = int(ga.getFromLog("hubCnt"))
        print("test hubCnt  %d"  % a)
        self.assertEqual(a, 0)
  
    def testSlot(self):
        test_str = ["0000001095: my_slot      =    1",]
        ga = GetAttribute(test_str, multi_line=False)
        a = int(ga.getFromLog("my_slot"))
        print("test my_slot = %s" % a)
        self.assertEqual(a, 1)
  
    def testVector_int(self):
        test_str = ["0000009184: label =  0   1   2   3   4   5   6   7   8   9   A   B   C   D   E   F",]
        ga = GetAttribute(test_str, multi_line=False)
        a = ga.getFromLog("label", True)
        print("testVector_int label = %s" % a)
        self.assertEqual(a, 1)
  
    def testVector_str(self):
        test_str = ["0000009192: State = OFF BLI ON  OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF ",]
        ga = GetAttribute(test_str, multi_line = False)
        a = ga.getFromLog("State", True)
        print("testVector_str State = %s" % a)
        self.assertEqual(a, 1)
  
    def testVector_file(self):
        print("testVector_file")
        fname = "./key_sample_nok.txt"
        lines=[]
        with open(fname, 'r') as file:
            lines = file.readlines()
        ga = GetAttribute(log=lines, start="AppliFrame_t", end=">>> SM_STATE_WAIT_FOR_TX_DONE")
        a = ga.getFromLog("State", True)
        print("testVector_file %s" % a)
        a = ga.getFromLog("Cmd", False)
        print("testVector_file Cmd %s" % a)
        self.assertEqual(len(lines), 73)



if __name__ == "__main__":
    unittest.main()