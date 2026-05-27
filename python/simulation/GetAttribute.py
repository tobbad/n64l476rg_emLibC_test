#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan  5 16:34:37 2026

@author: badi
"""
import re

class GetAttribute(object):
    def __init__(self,log=None, reset=None, start=None, end = None, multi_line=True):
        #print("GetAttribute constructor called")
        self.start = start or "*"
        self.end   = end  or "*"
        self.log   = log or []
        self.reset = reset or []
        self.multi_line = multi_line
        self.search_tpl_a = r'^\d+:\s*(%s)\s*(=|:)\s*(.+)'
        self.search_tpl =  r'^\d+:\s*(%s)\s*(=|:)\s*(\d+)'

    def getFromLog(self, attribut, isArr=False):
        if isArr:
            searchstr =self.search_tpl_a % attribut
        else:
            searchstr =self.search_tpl  % attribut
        doScan = False
        for line in self.log:
            #print("Search %s in %s"% (self.start, line.strip()))
            if re.search(re.escape(self.start), line):
                print("Found start %s in %s" %(self.start, line.strip()))
                doScan = True
            if re.search(re.escape(self.end), line):
                print("Found end %s in %s" %(self.end, line.strip()))
                doScan= False
                return
            if not self.multi_line: doScan= True
            if doScan:
                #print("search line %s, multiline %d" % (line.strip(), self.multi_line))
                m = re.search(searchstr, line)
                if m != None:
                    #print("Found groups '%s'" %( str(m.groups())))
                    return m.groups()[2]
        return None

    def getFromReset(self, attribut):
        for line in self.reset:
            #print("search line %s, multiline %d" % (line.strip(), self.multi_line))
            serchstr = self.search_tpl % attribut
            m = re.search(serchstr, line)
            if m != None:
                #print("Found groups '%s', multiline: %d" %( str(m.groups()), self.multi_line))
                return m.groups()[2]
        return -1
       
    def clean_line(self, lines):
        res =[]
        for l in lines:
            #print(type(l))
            #print(l.decode('ASCII').rstrip('\r\n'))
            #print(type(l.decode('ASCII').rstrip('\r\n')))
            res.append(l.decode('ASCII').rstrip('\r\n'))
        #print("Len of log = %d"% len(res))
        #print("Len of log = %d"% len(res))
        return res
