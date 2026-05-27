#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb 15 17:33:49 2026

@author: badi
"""
import sys
import os
import inspect
import time
import git
from evalTimeing import *
repo = git.Repo(search_parent_directories=True)
sha = repo.head.object.hexsha


thisModule = sys.modules[__name__]
pythonVersion=sys.version_info[0:3]
exportPrefix='ex_'
#######################################
#
# script functions
#
############################
###########   


#######################################
#
# Collect all commands in this script.
#
#######################################   
def getModuleInfo():
    #print("Items in the current context:")
    exPrefixlen=len(exportPrefix)
    cmds={}
    moduleDoc=""
    for name, item in inspect.getmembers(thisModule):
        if inspect.isfunction(item):
            if exportPrefix == item.__name__[0:exPrefixlen]:
                cmds[item.__name__]=item
        if inspect.ismodule(item):
            moduleDoc=item.__doc__
    return cmds, moduleDoc

def cleanUpTextList(tList):
    '''
    Remove empty lines in a \n separated test list
    '''
    text=[]
    for i in tList:
        i=i.strip()
        if len(i)>0:
            text.append(i)
    return text
#######################################
#
# Usage and main entrance of skript
#
#######################################   
def Usage(error=None):
    skriptname=sys.argv[0].split(os.sep)[-1]
    CnCDict, moduleDoc =getModuleInfo()
    sCList  =  list(k for k in  CnCDict.keys() )
    sCList.sort()
    text=cleanUpTextList(moduleDoc.split("\n"))
    cmdStr="command"
    maxCmdLen=len(cmdStr)
    for cmd in sCList:
        maxCmdLen = maxCmdLen if len(cmd)<maxCmdLen else len(cmd)
    commentPos=12
    text.extend([
          "GitHash: %s" % (sha),
          "",
          "Comand line:",
          "  %s cmd parameter" % skriptname,
          " "*commentPos+"'cmd' and 'parameter' according to the following list:",
          " "*commentPos+"(Parameters in [xxx] are optional and should - if used - entered without [])",
          ])
    cmdHeader="    command      parameter"
    if pythonVersion[1]>5:
        cmdHeader="    {cmd:{cwidth}} {b}".format(cmd=cmdStr,b="Parameter(s)",cwidth=maxCmdLen+1)
    #text.append(cmdHeader)
    for idx, cmdName in enumerate(sCList):
        if CnCDict[cmdName].__doc__!=None:
            print("__doc__ %s " % CnCDict[cmdName].__doc__.split("\n"))
            cmdInfo=cleanUpTextList(CnCDict[cmdName].__doc__.split("\n"))        
            cmdName=cmdInfo[0].split()[0].strip()
            para=" ".join(cmdInfo[0].split()[1:])
            print("idx %d: cmd: %s para: %s" %(idx, cmdName, para))
            if pythonVersion[1]>5:
                text.append("    {a:{cwidth}} {b}".format(a=cmdName,b=para,cwidth=maxCmdLen+1))
            else:
                text.append("    %s %s" % (cmdInfo[0].strip(),cmdInfo[1].strip()))
            if len(cmdInfo)>1:
                for line in cmdInfo[1:]:
                    text.append(" "*commentPos+line.strip())
    res="\n".join(text)
    etext=[]
    if error != None:
        error.insert(0,"ERROR:")
        maxlen=max([len(i) for i in error])
        etext.append("*"*(maxlen+4))
        etext.append("*"*(maxlen+4))
        for i in error:
            etext.append("* "+i+"%s *" % (" "*(maxlen-len(i))))
        etext.append("*"*(maxlen+4))
        etext.append("*"*(maxlen+4))
        print("\n".join(etext))    
    print(res)
    sys.exit()
##############################################
#  list ports
#############################################
 
   
data ={ "timing":[
    [ 63434,   73,   73 ],
    [ 7043,    8,    8 ],
    [ 24389,   28,   28 ],
    [ 23529,   27,   27 ],
    [ 24397,   28,   28 ],
    [ 24391,   28,   28 ],
    [ 24393,   28,   28 ],
    [ 24445,   28,   28 ],
    [ 24394,   28,   28 ],
    [ 24389,   28,   28 ],
]}

def ex_eval(*cnt):
    '''
    eval 
    eval  array
    '''
    print("eval serial send data transfer")
    print(cnt)
    evalTiming(data)

if __name__ == '__main__':
    if len(sys.argv)<2:
        Usage(["No Command given",])
    cmd  =sys.argv[1]
    para = sys.argv[2:]
    cmds, moduleDoc = getModuleInfo()
    iCmd='ex_'+cmd
    if iCmd not in cmds:
        Usage()
    cmds[iCmd](data)
