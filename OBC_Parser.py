#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
This file provides a parser for instrument serial output

Author: Alex St. Clair
Created: June 2020
'''

import serial, queue, parse, datetime

# globals
port = None
inst_filename = ''
xml_filename = ''
inst_queue = None
xml_queue = None
cmd_queue = None
tm_dir = ''
instrument = ''


def GetDateTime():
    # create date and time strings
    current_datetime = datetime.datetime.now()
    date = str(current_datetime.date().strftime("%d-%b-%y"))
    curr_time = str(current_datetime.time().strftime("%H:%M:%S"))
    curr_time_file = str(current_datetime.time().strftime("%H-%M-%S"))
    milliseconds = str(current_datetime.time().strftime("%f"))[:-3]

    return date, curr_time, curr_time_file, milliseconds


def HandleDebugMessage(message):
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


def HandleXMLMessage(first_line):
    message = first_line + str(port.read_until(b'</CRC>\n'), 'ascii')

    # parse out the message type
    xml_top = parse.parse('<{}>', first_line.strip())

    # if TM, get all the info
    if 'TM' == xml_top[0]:
        binary_section = port.read_until(b'END')
        state_flag = parse.search('<StateFlag1>{}</StateFlag1>', message)
        state_mess = parse.search('<StateMess1>{}</StateMess1>', message)
        tm_length = parse.search('<Length>{}</Length>', message)
        display = 'TM (' + state_flag[0] + ', len=' + tm_length[0] + '): ' + state_mess[0] + '\n'
        WriteTMFile(message, binary_section)
        cmd_queue.put('TMAck')
    elif 'S' == xml_top[0]:
        cmd_queue.put('SAck')
        display = xml_top[0] + '\n'
    elif 'RA' == xml_top[0]:
        cmd_queue.put('RAAck')
        display = xml_top[0] + '\n'
    else:
        display = xml_top[0] + '\n'

    # formulate the time
    _, time, _, milliseconds = GetDateTime()
    timestring = '[' + time + '.' + milliseconds + '] '

    # place on the queue to be displayed in the GUI
    display = timestring + display
    xml_queue.put(display)

    # log to the file
    with open(xml_filename, 'a') as xml:
        xml.write(display)


def WriteTMFile(message, binary):
    date, _, time, _ = GetDateTime()

    filename = tm_dir + '/TM_' + date + '_' + time + '.' + instrument + '.dat'

    with open(filename, 'wb') as tm_file:
        tm_file.write(message.encode())
        tm_file.write(binary)


# this function is run as a thread from OBC_Main
def ReadInstrument(inst_queue_in, xml_queue_in, port_in, inst_filename_in, xml_filename_in, tm_dir_in, inst_in, cmd_queue_in):
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
        print(f'*{new_line}*')

        if (-1 != new_line.find(b'<')):
            HandleXMLMessage(str(new_line,'ascii'))
            pass
        else:
            HandleDebugMessage(str(new_line,'ascii'))
