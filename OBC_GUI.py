#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
This script provides a GUI interface to OBC_Sim_Generic.py

Additionally, this script will parse XML and Debug messages from the same stream, if required

Author: Alex St. Clair
Created: May 2020
'''

import PySimpleGUI as sg

# useful globals
ZephyrMessageTypes = ['IM', 'GPS', 'SW', 'TC', 'SAck', 'RAAck', 'TMAck']
ZephyrModes = ['SB', 'FL', 'LP', 'SA', 'EF']
port = ''
instrument = ''

def WelcomeWindow():
    config_selector = [[sg.Text('Choose an instrument:')],
                       [sg.Radio('RACHUTS','inst_radio',True), sg.Radio('FLOATS','inst_radio'), sg.Radio('LPC','inst_radio')],
                       [sg.Text('Choose a port:')],
                       [sg.InputText('/dev/tty.usbserial')],
                       [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
                        sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    # GUI configurator
    window = sg.Window('Configuration', config_selector)
    event, values = window.read()
    window.close()

    # quit the program if the window is closed or Exit selected
    if event in (None, 'Exit'):
        exit()

    # assign the outputs
    if values[0]:
        instrument = 'RACHUTS'
    elif values[1]:
        instrument = 'FLOATS'
    else:
        instrument = 'LPC'
    port = values[3]

    sg.Print("Instrument:", instrument)
    sg.Print("Port:", port)


def SelectMessage():
    message_selector = [[sg.Text('Select a message to send')],
                        [],
                        [sg.Text('-'  * 110)],
                        [sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    for msg_type in ZephyrMessageTypes:
        message_selector[1].append(sg.Button(msg_type, size=(6,1)))

    # GUI message selector
    window = sg.Window('Command Menu', message_selector)
    event, _ = window.read()
    window.close()

    # quit the program if the window is closed or Exit selected
    if event in (None, 'Exit'):
        exit()

    return event


def IMMessage():
    mode_selector = [[sg.Text('Select a mode')],
                     [],
                     [sg.Text('-'  * 110)],
                     [sg.Button('Cancel', size=(8,1), button_color=('white','orange')),
                      sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    for mode in ZephyrModes:
        mode_selector[1].append(sg.Button(mode, size=(6,1)))

    # GUI mode selector
    window = sg.Window('Mode Message Configurator', mode_selector)
    event, _ = window.read()
    window.close()

    # quit the program if the window is closed or Exit selected
    if event in (None, 'Exit'):
        exit()
    elif 'Cancel' == event:
        return

    sg.Print("Setting mode:", event)
    # TODO: send


def GPSMessage():
    gps_selector = [[sg.Text('Select a solar zenith angle (degrees)')],
                    [sg.InputText('120')],
                    [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
                     sg.Button('Cancel', size=(8,1), button_color=('white','orange')),
                     sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    # GUI mode selector with SZA float validation
    window = sg.Window('GPS Message Configurator', gps_selector)
    while True:
        event, values = window.read()

        if 'Submit' != event:
            break

        try:
            sza = float(values[0])
            if sza <= 180 and sza >= 0:
                break
            else:
                sg.popup('SZA must be between 0 and 180')
        except:
            sg.popup('SZA must be a float')

    window.close()

    # quit the program if the window is closed or Exit selected
    if event in (None, 'Exit'):
        exit()
    elif 'Cancel' == event:
        return

    sg.Print("Sending GPS, SZA =", str(sza))
    # TODO: send


def SWMessage():
    sg.Print("Sending shutdown warning")
    # TODO: send


def TCMessage():
    tc_selector = [[sg.Text('Input a telecommand:')],
                    [sg.InputText('1;')],
                    [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
                     sg.Button('Cancel', size=(8,1), button_color=('white','orange')),
                     sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    # GUI mode selector with SZA float validation
    window = sg.Window('TC Creator', tc_selector)
    event, values = window.read()
    window.close()

    # quit the program if the window is closed or Exit selected
    if event in (None, 'Exit'):
        exit()
    elif 'Cancel' == event:
        return

    sg.Print("Sending TC:", values[0])
    # TODO: send


def SAckMessage():
    sg.Print("Sending safety ack")
    # TODO: send


def RAAckMessage():
    sg.Print("Sending RA ack")
    # TODO: send


def TMAckMessage():
    sg.Print("Sending TM ack")
    # TODO: send


def main():
    sg.theme('Dark')

    WelcomeWindow()

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