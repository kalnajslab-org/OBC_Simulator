#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
This script provides a console to simulate the OBC over serial

Author: Alex St. Clair
Created: May 2020
'''

# modules
import OBC_GUI

# libraries
import threading, serial, queue, time

# globals
instrument = ''
port = ''


def ReadInstrument(inst_queue):
    while True:
        with serial.Serial(port) as inst_serial:
            inst_queue.put(inst_serial.readline().decode('utf-8'))


def main():
    global instrument, port

    # create a queue for instrument serial messages
    inst_queue = queue.Queue()

    # get basic information
    instrument, port = OBC_GUI.WelcomeWindow()

    # start the instrument output window
    OBC_GUI.StartOutputWindow()

    # start listening for instrument messages over serial
    threading.Thread(target=ReadInstrument, args=(inst_queue,)).start()

    while True:
        # run command GUI
        OBC_GUI.RunCommands()

        # print instrument messages as they arrive
        if not inst_queue.empty():
            OBC_GUI.OutputWindowPrint(inst_queue.get())


if (__name__ == '__main__'):
    main()