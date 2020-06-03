#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
This file provides a parser for instrument serial output

Author: Alex St. Clair
Created: June 2020
'''

import serial, queue, parse

# globals
port = None
inst_filename = ''
inst_queue = None
xml_queue = None


def HandleDebugMessage(message):
    message = message.rstrip() + '\n'

    inst_queue.put(message)

    with open(inst_filename, 'a') as inst:
        inst.write(message)


def HandleXMLMessage(first_line):
    message = first_line + str(port.read_until(b'</CRC>\n'), 'ascii')

    # check for and parse a binary section if necessary
    xml_top = parse.parse('<{}>', first_line)
    if 'TM' == xml_top[0]:
        binary_section = port.read_until(b'END')
        message += str(binary_section)

    message += '\n'
    xml_queue.put(message)


# this function is run as a thread from OBC_Main
def ReadInstrument(inst_queue_in, xml_queue_in, port_in, inst_filename_in):
    global port, inst_filename, inst_queue, xml_queue

    # assign globals
    port = port_in
    inst_filename = inst_filename_in
    inst_queue = inst_queue_in
    xml_queue = xml_queue_in

    # as long as the port is open, parse no messages
    while port:
        new_line = port.readline()

        if (-1 != new_line.find(b'<')):
            HandleXMLMessage(str(new_line,'ascii'))
            pass
        else:
            HandleDebugMessage(str(new_line,'ascii'))
