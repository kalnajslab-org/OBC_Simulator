#!/usr/bin/env python3
"""
This module provides functions to handle and process messages from instruments
connected via serial ports. It includes functions to handle log messages, Zephyr
messages, and to write telemetry files. The main function `ReadInstrument` runs
as a thread to continuously read from the serial ports and process the incoming
messages.
Functions:
    GetDateTime() -> tuple:
        Returns the current date and time in various string formats.
    HandleStratoLogMessage(message: str) -> None:
        Processes and logs a Strato log message.
    HandleZephyrMessage(first_line: str) -> None:
        Processes and logs a Zephyr message, and handles specific message types.
    WriteTMFile(message: str, binary: bytes) -> None:
        Writes a telemetry message and its binary payload to a file.
    ReadInstrument(
        Continuously reads from the serial ports and processes incoming messages.
"""
# -*- coding: utf-8 -*-

import serial
import queue
import datetime
import xmltodict
import time

# globals
zephyr_port = None
log_port = None
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

def HandleZephyrMessage(first_line: str) -> None:
    message = first_line + str(zephyr_port.read_until(b'</CRC>\n'), 'ascii')
    # The message is not correct XML, since it doesn't have opening/closing
    # tokens. Add some tokens so that it can be parsed.
    msg_dict = xmltodict.parse(f'<MSG>{message}</MSG>')
    msg_type = list(msg_dict["MSG"].keys())[0]
    display = f'{msg_type:7s} {" ".join([key+":"+value+" " for (key,value) in msg_dict["MSG"][msg_type].items()])}\n'

    # if TM, save payload
    if 'TM' == msg_type:
        binary_section = zephyr_port.read_until(b'END')
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

# This function is run as a thread from OBC_Main.
def ReadInstrument(
    inst_queue_in: queue.Queue,
    xml_queue_in: queue.Queue,
    logport: serial.Serial,
    zephyrport: serial.Serial,
    inst_filename_in: str,
    xml_filename_in: str,
    tm_dir_in: str,
    inst_in: str,
    cmd_queue_in: queue.Queue) -> None:

    global zephyr_port
    global log_port
    global inst_filename
    global xml_filename
    global inst_queue
    global xml_queue
    global tm_dir
    global instrument
    global cmd_queue

    # assign globals
    zephyr_port = zephyrport
    log_port = logport
    inst_filename = inst_filename_in
    xml_filename = xml_filename_in
    inst_queue = inst_queue_in
    xml_queue = xml_queue_in
    tm_dir = tm_dir_in
    instrument = inst_in
    cmd_queue = cmd_queue_in

    while True:
        # The zephyr and log ports are opened in OBC_Gui.
        # They can be opened/closed from the GUI, when
        # the suspend button is pressed. Thus the exception
        # handling is used to detect this.

        new_line = None
        # read a line from either the log port or zephyr port
        try:
            if log_port.is_open: 
                if log_port.in_waiting:
                    new_line = log_port.readline()
            elif zephyr_port.is_open: 
                if zephyr_port.in_waiting:
                    new_line = zephyr_port.readline()
        except OSError as e:
            time.sleep(0.001)
            continue

        if not new_line:
            time.sleep(0.001)
            continue

        # if the line contains a '<', it is a Zephyr message
        if (-1 != new_line.find(b'<')):
            HandleZephyrMessage(str(new_line,'ascii'))
            pass
        # otherwise, it is a log message
        else:
            HandleStratoLogMessage(str(new_line,'ascii'))
