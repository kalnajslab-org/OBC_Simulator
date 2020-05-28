#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
This file provides a GUI for OBC commands and output

Author: Alex St. Clair
Created: May 2020
'''

import PySimpleGUI as sg

# useful globals
ZephyrMessageTypes = ['IM', 'GPS', 'SW', 'TC', 'SAck', 'RAAck', 'TMAck']
ZephyrModes = ['SB', 'FL', 'LP', 'SA', 'EF']

# global window objects
input_window = None
output_window = None
current_message = 'waiting'
new_window = True

def WelcomeWindow():
    sg.theme('Dark')

    config_selector = [[sg.Text('Choose an instrument:')],
                       [sg.Radio('RACHUTS','inst_radio',True), sg.Radio('FLOATS','inst_radio'), sg.Radio('LPC','inst_radio')],
                       [sg.Text('Choose a port:')],
                       [sg.InputText('COM3')],
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

    return instrument, port


def StartOutputWindow():
    global output_window

    instrument_output = [[sg.MLine(key='-output-'+sg.WRITE_ONLY_KEY, size=(80,10))]]

    output_window = sg.Window('Instrument Output', instrument_output, finalize=True)


def OutputWindowPrint(message):
    global output_window

    output_window['-output-'+sg.WRITE_ONLY_KEY].print(message)


def DisplaySelectMessage():
    global input_window, new_window

    message_selector = [[sg.Text('Select a message to send')],
                        [],
                        [sg.Text('-'  * 110)],
                        [sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    for msg_type in ZephyrMessageTypes:
        message_selector[1].append(sg.Button(msg_type, size=(6,1)))

    # GUI message selector
    input_window = sg.Window('Command Menu', message_selector)


def WaitSelectMessage():
    global input_window, current_message, new_window

    event, _ = input_window.read(timeout=10)

    if event == '__TIMEOUT__':
        return

    else:
        input_window.close()

        # quit the program if the window is closed or Exit selected
        if event in (None, 'Exit'):
            exit()
        else:
            current_message = event
            new_window = True


def DisplayIMMessage():
    global input_window, new_window

    mode_selector = [[sg.Text('Select a mode')],
                     [],
                     [sg.Text('-'  * 110)],
                     [sg.Button('Cancel', size=(8,1), button_color=('white','orange')),
                      sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    for mode in ZephyrModes:
        mode_selector[1].append(sg.Button(mode, size=(6,1)))

    # GUI mode selector
    input_window = sg.Window('Mode Message Configurator', mode_selector)


def WaitIMMessage():
    global input_window, current_message, new_window

    event, _ = input_window.read(timeout=10)

    if event == '__TIMEOUT__':
        return
    else:
        input_window.close()

        # quit the program if the window is closed or Exit selected
        if event in (None, 'Exit'):
            exit()

        # as long as cancel wasn't selected, set the mode
        if 'Cancel' != event:
            sg.Print("Setting mode:", event, background_color='blue')
            # TODO: send

        # go back to the message selector
        current_message = 'waiting'
        new_window = True


# def GPSMessage():
#     gps_selector = [[sg.Text('Select a solar zenith angle (degrees)')],
#                     [sg.InputText('120')],
#                     [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
#                      sg.Button('Cancel', size=(8,1), button_color=('white','orange')),
#                      sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

#     # GUI mode selector with SZA float validation
#     window = sg.Window('GPS Message Configurator', gps_selector)
#     while True:
#         event, values = window.read()

#         if 'Submit' != event:
#             break

#         try:
#             sza = float(values[0])
#             if sza <= 180 and sza >= 0:
#                 break
#             else:
#                 sg.popup('SZA must be between 0 and 180')
#         except:
#             sg.popup('SZA must be a float')

#     window.close()

#     # quit the program if the window is closed or Exit selected
#     if event in (None, 'Exit'):
#         exit()
#     elif 'Cancel' == event:
#         return

#     sg.Print("Sending GPS, SZA =", str(sza))
#     # TODO: send


def SWMessage():
    sg.Print("Sending shutdown warning", background_color='red')
    # TODO: send


# def TCMessage():
#     tc_selector = [[sg.Text('Input a telecommand:')],
#                     [sg.InputText('1;')],
#                     [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
#                      sg.Button('Cancel', size=(8,1), button_color=('white','orange')),
#                      sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

#     # GUI mode selector with SZA float validation
#     window = sg.Window('TC Creator', tc_selector)
#     event, values = window.read()
#     window.close()

#     # quit the program if the window is closed or Exit selected
#     if event in (None, 'Exit'):
#         exit()
#     elif 'Cancel' == event:
#         return

#     sg.Print("Sending TC:", values[0], background_color='green')
#     # TODO: send


def SAckMessage():
    sg.Print("Sending safety ack")
    # TODO: send


def RAAckMessage():
    sg.Print("Sending RA ack")
    # TODO: send

def TMAckMessage():
    sg.Print("Sending TM ack")
    # TODO: send


def RunCommands():
    global new_window, current_message

    if new_window:
        if 'waiting' == current_message:
            DisplaySelectMessage()
            new_window = False

        elif 'IM' == current_message:
            DisplayIMMessage()
            new_window = False

        elif 'GPS' == current_message:
            #GPSMessage()
            sg.Print("Unimplemented")
            current_message = 'waiting'
            new_window = True

        elif 'SW' == current_message:
            SWMessage()
            current_message = 'waiting'
            new_window = True

        elif 'TC' == current_message:
            #TCMessage()
            sg.Print("Unimplemented")
            current_message = 'waiting'
            new_window = True

        elif 'SAck' == current_message:
            SAckMessage()
            current_message = 'waiting'
            new_window = True

        elif 'RAAck' == current_message:
            RAAckMessage()
            current_message = 'waiting'
            new_window = True

        elif 'TMAck' == current_message:
            TMAckMessage()
            current_message = 'waiting'
            new_window = True

        else:
            sg.Print("Unknown new window requested")
            current_message = 'waiting'
            new_window = True

    else:
        if 'waiting' == current_message:
            WaitSelectMessage()

        elif 'IM' == current_message:
            WaitIMMessage()

        elif 'GPS' == current_message:
            #WaitGPSMessage()
            sg.Print("Unimplemented")

        elif 'TC' == current_message:
            #TCMessage()
            sg.Print("Unimplemented")

        else:
            sg.Print("Bad window to wait on")
            current_message = 'waiting'
            new_window = True



if (__name__ == '__main__'):
    RunCommands()