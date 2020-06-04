#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
This file provides a GUI for OBC commands and output

Author: Alex St. Clair
Created: May 2020
'''

import PySimpleGUI as sg
import os, threading
import OBC_Sim_Generic

# message type globals
ZephyrMessageTypes = ['IM', 'GPS', 'SW', 'TC', 'SAck', 'RAAck', 'TMAck']
ZephyrModes = ['SB', 'FL', 'LP', 'SA', 'EF']

# global window objects
input_window = None
output_window = None
current_message = 'waiting'
new_window = True

# string globals
port = ''
cmd_filename = ''
instrument = ''


def WelcomeWindow():
    sg.theme('Dark')

    config_selector = [[sg.Text('Choose an instrument:')],
                       [sg.Radio('RACHUTS','inst_radio',True), sg.Radio('FLOATS','inst_radio'), sg.Radio('LPC','inst_radio')],
                       [sg.Text('Choose a port:')],
                       [sg.InputText('COM3')],
                       [sg.Text('Automatically respond with ACKs?')],
                       [sg.Radio('Yes','ack_radio',True), sg.Radio('No','ack_radio')],
                       [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
                        sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    # GUI configurator
    window = sg.Window('Welcome', config_selector)
    event, values = window.read()
    window.close()

    # quit the program if the window is closed or Exit selected
    if event in (None, 'Exit'):
        CloseAndExit()

    # assign the outputs
    if values[0]:
        inst = 'RACHUTS'
    elif values[1]:
        inst = 'FLOATS'
    else:
        inst = 'LPC'
    port = values[3]
    if values[4]:
        auto_ack = True
    else:
        auto_ack = False

    sg.Print("Instrument:", inst)
    sg.Print("Port:", port)

    return inst, port, auto_ack


def StartOutputWindow():
    global output_window

    instrument_output = [[sg.Text('Debug Output:'), sg.Text('XML Output:')],
                         [sg.MLine(key='-inst-'+sg.WRITE_ONLY_KEY, size=(80,25)),
                          sg.MLine(key='-xml-'+sg.WRITE_ONLY_KEY, size=(80,25))]]

    output_window = sg.Window('Instrument Output', instrument_output, finalize=True)


def InstWindowPrint(message):
    global output_window

    if -1 != message.find('ERR: '):
        output_window['-inst-'+sg.WRITE_ONLY_KEY].print(message, background_color='red', end="")
    else:
        output_window['-inst-'+sg.WRITE_ONLY_KEY].print(message, end="")


def XMLWindowPrint(message):
    global output_window

    if -1 != message.find('TM') and -1 != message.find('CRIT'):
        output_window['-xml-'+sg.WRITE_ONLY_KEY].print(message, background_color='red', end="")
    elif -1 != message.find('TM') and -1 != message.find('WARN'):
        output_window['-xml-'+sg.WRITE_ONLY_KEY].print(message, background_color='orange', end="")
    else:
        output_window['-xml-'+sg.WRITE_ONLY_KEY].print(message, end="")


def DebugPrint(message, error=False):
    if not error:
        sg.Print(message)
    else:
        sg.Print(message, background_color='red')


def DisplayMessageSelection():
    global input_window

    message_selector = [[sg.Text('Select a message to send')],
                        [],
                        [sg.Text('-'  * 110)],
                        [sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    for msg_type in ZephyrMessageTypes:
        message_selector[1].append(sg.Button(msg_type, size=(6,1)))

    # GUI message selector
    input_window = sg.Window('Command Menu', message_selector)


def WaitMessageSelection():
    global input_window, current_message, new_window

    event, _ = input_window.read(timeout=10)

    if '__TIMEOUT__' == event:
        return

    input_window.close()

    # quit the program if the window is closed or Exit selected
    if event in (None, 'Exit'):
        CloseAndExit()
    else:
        current_message = event
        new_window = True


def DisplayIMSelection():
    global input_window

    mode_selector = [[sg.Text('Select a mode')],
                     [],
                     [sg.Text('-'  * 110)],
                     [sg.Button('Cancel', size=(8,1), button_color=('white','orange')),
                      sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    for mode in ZephyrModes:
        mode_selector[1].append(sg.Button(mode, size=(6,1)))

    # GUI mode selector
    input_window = sg.Window('Mode Message Configurator', mode_selector)


def WaitIMSelection():
    global input_window, current_message, new_window

    event, _ = input_window.read(timeout=10)

    if '__TIMEOUT__' == event:
        return

    input_window.close()

    # quit the program if the window is closed or Exit selected
    if event in (None, 'Exit'):
        CloseAndExit()

    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    # as long as cancel wasn't selected, set the mode
    if 'Cancel' != event:
        sg.Print(timestring + "Setting mode:", event, background_color='blue')
        OBC_Sim_Generic.sendIM(instrument, event, cmd_filename, port)

    # go back to the message selector
    current_message = 'waiting'
    new_window = True


def DisplayGPSSelection():
    global input_window

    gps_selector = [[sg.Text('Select a solar zenith angle (degrees)')],
                    [sg.InputText('120')],
                    [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
                     sg.Button('Cancel', size=(8,1), button_color=('white','orange')),
                     sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    # GUI GPS creator with SZA float validation
    input_window = sg.Window('GPS Message Configurator', gps_selector)


def WaitGPSSelection():
    global input_window, current_message, new_window

    event, values = input_window.read(timeout=10)

    if '__TIMEOUT__' == event:
        return

    if 'Submit' == event:
        try:
            sza = float(values[0])
            if sza > 180 or sza < 0:
                sg.popup('SZA must be between 0 and 180')
                return
        except:
            sg.popup('SZA must be a float')
            return

    input_window.close()

    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    # quit the program if the window is closed or Exit selected
    if event in (None, 'Exit'):
        CloseAndExit()
    elif 'Cancel' != event:
        sg.Print(timestring + "Sending GPS, SZA =", str(sza))
        OBC_Sim_Generic.sendGPS(sza, cmd_filename, port)

    # go back to the message selector
    current_message = 'waiting'
    new_window = True


def SWMessage():
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sending shutdown warning", background_color='red')
    OBC_Sim_Generic.sendSW(instrument, cmd_filename, port)


def DisplayTCSelection():
    global input_window

    tc_selector = [[sg.Text('Input a telecommand:')],
                    [sg.InputText('1;')],
                    [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
                     sg.Button('Cancel', size=(8,1), button_color=('white','orange')),
                     sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    # GUI TC creator
    input_window = sg.Window('TC Creator', tc_selector)


def WaitTCSelection():
    global input_window, current_message, new_window

    event, values = input_window.read(timeout=10)

    if '__TIMEOUT__' == event:
        return

    input_window.close()

    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    # quit the program if the window is closed or Exit selected
    if event in (None, 'Exit'):
        CloseAndExit()
    elif 'Cancel' != event:
        sg.Print(timestring + "Sending TC:", values[0], background_color='green')
        OBC_Sim_Generic.sendTC(instrument, values[0], cmd_filename, port)

    # go back to the message selector
    current_message = 'waiting'
    new_window = True


def SAckMessage():
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sending safety ack")
    OBC_Sim_Generic.sendSAck(instrument, 'ACK', cmd_filename, port)


def RAAckMessage():
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sending RA ack")
    OBC_Sim_Generic.sendRAAck('ACK', cmd_filename, port)


def TMAckMessage():
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sending TM ack")
    OBC_Sim_Generic.sendTMAck(instrument, 'ACK', cmd_filename, port)


def CloseAndExit():
    global output_window, input_window

    if output_window != None:
        output_window.close()

    if input_window != None:
        input_window.close()

    os._exit(0)


def RunCommands():
    global new_window, current_message

    if new_window:
        if 'waiting' == current_message:
            DisplayMessageSelection()
            new_window = False

        elif 'IM' == current_message:
            DisplayIMSelection()
            new_window = False

        elif 'GPS' == current_message:
            DisplayGPSSelection()
            new_window = False

        elif 'SW' == current_message:
            SWMessage()
            current_message = 'waiting'
            new_window = True

        elif 'TC' == current_message:
            DisplayTCSelection()
            new_window = False

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
            sg.Print("Unknown new window requested", background_color='orange')
            current_message = 'waiting'
            new_window = True

    else:
        if 'waiting' == current_message:
            WaitMessageSelection()

        elif 'IM' == current_message:
            WaitIMSelection()

        elif 'GPS' == current_message:
            WaitGPSSelection()

        elif 'TC' == current_message:
            WaitTCSelection()

        else:
            sg.Print("Bad window to wait on", background_color='orange')
            current_message = 'waiting'
            new_window = True
