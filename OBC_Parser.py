#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
This file provides a parser for instrument serial output

Author: Alex St. Clair
Created: June 2020
'''

import serial, queue

# globals
port = None
inst_filename = ''


def ReadInstrument(inst_queue, port_in, inst_filename_in):
    global port, inst_filename

    port = port_in
    inst_filename = inst_filename_in

    while True:
        new_line = str(port.readline())

        new_line = new_line.rstrip() + '\n'
        inst_queue.put(new_line)

        with open(inst_filename, "a") as inst:
            inst.write(new_line)