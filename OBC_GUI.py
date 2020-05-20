#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import PySimpleGUI as sg

# useful globals
ZephyrMessageTypes = ['IM', 'GPS', 'SW', 'TC', 'SAck', 'RAAck', 'TMAck']
ZephyrModes = ['SB', 'FL', 'LP', 'SA', 'EF']

def SelectMessage():
    message_selector = [[sg.Text('Select a message to send')],
                        [],
                        [sg.Text('-'  * 110)],
                        [sg.Button('Exit', size=(6,1), button_color=('white','red'))]]

    for msg_type in ZephyrMessageTypes:
        message_selector[1].append(sg.Button(msg_type, size=(6,1)))

    # GUI message selector
    window = sg.Window('Command Menu', message_selector)
    event, _ = window.read()
    window.close()

    if event in (None, 'Exit'):
        exit()

    return event

def IMMessage():
    mode_selector = [[sg.Text('Select a mode')],
                        [],
                        [sg.Text('-'  * 110)],
                        [sg.Button('Exit', size=(6,1), button_color=('white','red')), sg.Button('Back')]]

    for mode in ZephyrModes:
        mode_selector[1].append(sg.Button(mode, size=(6,1)))

    # GUI mode selector
    window = sg.Window('Command Menu', mode_selector)
    event, _ = window.read()
    window.close()

    # quit the program if the window is close or Exit
    if event in (None, 'Exit'):
        exit()
    elif 'Back' == event:
        return

    sg.Print("Setting mode:", event)
    # TODO: send IM


def GPSMessage():
    sg.Print("Sending GPS message")


def SWMessage():
    sg.Print("Sending shutdown warning")


def TCMessage():
    sg.Print("Sending telecommand")


def SAckMessage():
    sg.Print("Sending safety ack")


def RAAckMessage():
    sg.Print("Sending RA ack")


def TMAckMessage():
    sg.Print("Sending TM ack")


def main():
    sg.theme('Dark')

    while True:
        message_type = SelectMessage()

        if 'IM' == message_type:
            IMMessage()

        elif 'GPS' == message_type:
            GPSMessage()

        elif 'SW' == message_type:
            SWMessage()

        elif 'TC' == message_type:
            TCMessage()

        elif 'SAck' == message_type:
            SAckMessage()

        elif 'RAAck' == message_type:
            RAAckMessage()

        elif 'TMAck' == message_type:
            TMAckMessage()


if (__name__ == '__main__'):
    main()