#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
This file provides a parser for instrument serial output

Author: Alex St. Clair
Created: June 2020
'''

import serial
import queue
import datetime
import xmltodict

# globals
port = None
inst_filename = ''
xml_filename = ''
inst_queue = None
xml_queue = None
cmd_queue = None
tm_dir = ''
instrument = ''


def GetDateTime() -> tuple:
    # create date and time strings
    current_datetime = datetime.datetime.now()
    date = str(current_datetime.date().strftime("%d-%b-%y"))
    curr_time = str(current_datetime.time().strftime("%H:%M:%S"))
    curr_time_file = str(current_datetime.time().strftime("%H-%M-%S"))
    milliseconds = str(current_datetime.time().strftime("%f"))[:-3]

    return date, curr_time, curr_time_file, milliseconds


def HandleStratoLogMessage(message: str) -> None:
    message = message.rstrip() + '\n'

    # formulate the time
    _, time, _, milliseconds = GetDateTime()
    timestring = '[' + time + '.' + milliseconds + '] '

    # place on the queue to be displayed in the GUI
    message = timestring + message
    inst_queue.put(message)

    # log to the file
    with open(inst_filename, 'a') as inst:
        inst.write(message)

def HandleXMLMessage(first_line: str) -> None:
    message = first_line + str(port.read_until(b'</CRC>\n'), 'ascii')
    # The message is not correct XML, since it doesn't have opening/closing
    # tokens. Add some tokens so that it can be parsed.
    msg_dict = xmltodict.parse(f'<MSG>{message}</MSG>')
    msg_type = list(msg_dict["MSG"].keys())[0]
    display = f'{msg_type:7s} {" ".join([key+":"+value+" " for (key,value) in msg_dict["MSG"][msg_type].items()])}\n'

    # if TM, save payload
    if 'TM' == msg_type:
        binary_section = port.read_until(b'END')
        WriteTMFile(message, binary_section)
        cmd_queue.put('TMAck')
    elif 'S' == msg_type:
        cmd_queue.put('SAck')
    elif 'RA' == msg_type:
        cmd_queue.put('RAAck')

    # formulate the time
    _, time, _, milliseconds = GetDateTime()
    timestring = '[' + time + '.' + milliseconds + '] '

    # place on the queue to be displayed in the GUI
    display = timestring + display
    xml_queue.put(display)

    # log to the file
    with open(xml_filename, 'a') as xml:
        xml.write(display)

def WriteTMFile(message: str, binary: bytes) -> None:
    date, _, time, _ = GetDateTime()

    filename = tm_dir + '/TM_' + date + '_' + time + '.' + instrument + '.dat'

    with open(filename, 'wb') as tm_file:
        tm_file.write(message.encode())
        tm_file.write(binary)

# this function is run as a thread from OBC_Main
def ReadInstrument(inst_queue_in: queue.Queue, xml_queue_in: queue.Queue, port_in: serial.Serial, inst_filename_in: str, xml_filename_in: str, tm_dir_in: str, inst_in: str, cmd_queue_in: queue.Queue) -> None:
    global port, inst_filename, xml_filename, inst_queue, xml_queue, tm_dir, instrument, cmd_queue

    # assign globals
    port = port_in
    inst_filename = inst_filename_in
    xml_filename = xml_filename_in
    inst_queue = inst_queue_in
    xml_queue = xml_queue_in
    tm_dir = tm_dir_in
    instrument = inst_in
    cmd_queue = cmd_queue_in

    # as long as the port is open, parse no messages
    while port:
        new_line = port.readline()

        if (-1 != new_line.find(b'<')):
            HandleXMLMessage(str(new_line,'ascii'))
            pass
        else:
            HandleStratoLogMessage(str(new_line,'ascii'))
