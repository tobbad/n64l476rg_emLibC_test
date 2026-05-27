#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb 15 17:39:03 2026

@author: badi
"""
    
data ={ "timeing":[
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

def evalTimeing(data):
    print("Received data %s " % data)
    for line in data['timeing']:
        print(line)

if __name__ == '__main__':
    evalTimeing(data)