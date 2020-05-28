#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
This script provides a console to simulate the OBC over serial

Author: Alex St. Clair
Created: May 2020
'''

import OBC_GUI
import threading
import time

instrument = ''
port = ''

def main():
    global instrument, port

    # get basic information
    instrument, port = OBC_GUI.WelcomeWindow()

    # start the instrument output window
    OBC_GUI.StartOutputWindow()

    while True:
        # run command GUI
        OBC_GUI.RunCommands()


if (__name__ == '__main__'):
    main()