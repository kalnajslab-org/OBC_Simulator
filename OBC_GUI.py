#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
This file provides a GUI for OBC commands and output

Author: Alex St. Clair
Created: May 2020
'''

''' 
This module provides a GUI for the OBC simulator. 

ConfigWindow() is called to prompt for configuration.

MainWindow() is called to create the main window.
It contains buttons for each type of message that can be sent, 
and two columns for log messages and Zephyr messages. 
The buttons either send a message  directly (e.g. TMAck), 
or open a popup window (e.g. IM) to configure and send a message.

LogAddMsg() and ZephyrAddMsg() are called to add messages to the 
log and Zephyr message columns.

The main window is referenced by the global variable: main_window.

In order to handle UI events and received messages, a polling mechanism is used.
RunCommands() is called by the program main loop, and handles UI activities.
Popup windows are created by ShowIMPopup(), WaitIMPopup(), etc.
The popup windows are all assigned to the global variable: popup_window.

WaitMessageSelection() is called from RunCommands() to check for button presses.
This function calls both main_window.read() and popup_window.read() to check 
for button press events.
'''

# modules
import os
import PySimpleGUIQt as sg
import OBC_Sim_Generic

# message types and instrument modes
ZephyrMessageTypes = ['IM', 'GPS', 'SW', 'TC', 'SAck', 'RAAck', 'TMAck']
ZephyrInstModes = ['SB', 'FL', 'LP', 'SA', 'EF']

# global window objects
popup_window = None
main_window = None
current_message = 'waiting'
new_window = True

# global configuration variables
port = ''
cmd_filename = ''
instrument = ''

# set the overall look of the GUI
sg.theme('SystemDefault')
sg.set_options(font = ("Helvetica", 12))

def ConfigWindow(comm_port: str):

    config_selector = [[sg.Text('Choose an instrument:')],
                       [sg.Radio('RATS',group_id=1,key='RATS',default=True), sg.Radio('LPC',group_id=1,key='LPC'), sg.Radio('RACHUTS',group_id=1,key='RACHUTS'), sg.Radio('FLOATS',group_id=1,key='FLOATS')],
                       [sg.Text('Choose a port:')],
                       [sg.InputText(comm_port, key='COMMPORT', size=(20,1))],
                       [sg.Text('Automatically respond with ACKs?')],
                       [sg.Radio('Yes',group_id=2,key='ACK',default=True), sg.Radio('No',group_id=2,key='NOACK')],
                       [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
                        sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    # GUI configurator
    window = sg.Window('Welcome', config_selector, element_padding = (2,2))
    event, values = window.read()
    window.close()

    # quit the program if the window is closed or Exit selected
    if event in (None, 'Exit'):
        CloseAndExit()

    # assign the outputs
    if values['RATS']:
        inst = 'RATS'
    if values['LPC']:
        inst = 'LPC'
    elif values['RACHUTS']:
        inst = 'RACHUTS'
    elif values['FLOATS']:
        inst = 'FLOATS'

    port = values['COMMPORT']

    if values['ACK']:
        auto_ack = True
    else:
        auto_ack = False

    sg.Print("Instrument:", inst)
    sg.Print("Port:", port)

    return inst, port, auto_ack

def MainWindow():
    '''Create the main window
    
    It has control buttons at the top and two columns for log messages and Zephyr messages
    '''
    global main_window

    # Command buttons at the top of the window
    buttons = [sg.Button(s, size=(6,1)) for s in ZephyrMessageTypes]
    buttons.append(sg.Button('Exit', size=(8,1), button_color=('white','red')))

    # A columns for log messages and Zephyr messages
    widgets = [
        buttons,
        [sg.Column([[sg.Text('StratoCore Log Messages')], [sg.MLine(key='-log-'+sg.WRITE_ONLY_KEY, size=(50,30))]]),
         sg.Column([[sg.Text('Zephyr Messages'           )], [sg.MLine(key='-zephyr-'+sg.WRITE_ONLY_KEY, size=(100,30))]])]
    ]

    main_window = sg.Window(title=instrument, layout=widgets, location=(500, 100), finalize=True)

def AddLogMsg(message):
    global main_window

    if -1 != message.find('ERR: '):
        main_window['-log-'+sg.WRITE_ONLY_KEY].print(message, text_color='red', end="")
    else:
        main_window['-log-'+sg.WRITE_ONLY_KEY].print(message, end="")

def AddZephyrMsg(message):
    global main_window

    if -1 != message.find('TM') and -1 != message.find('CRIT'):
        main_window['-zephyr-'+sg.WRITE_ONLY_KEY].print(message, text_color='red', end="")
    elif -1 != message.find('TM') and -1 != message.find('WARN'):
        main_window['-zephyr-'+sg.WRITE_ONLY_KEY].print(message, text_color='orange', end="")
    elif -1 != message.find('TM'):
        main_window['-zephyr-'+sg.WRITE_ONLY_KEY].print(message, text_color='green', end="")
    else:
        main_window['-zephyr-'+sg.WRITE_ONLY_KEY].print(message, end="")

def DebugPrint(message, error=False):
    if not error:
        sg.Print(message)
    else:
        sg.Print(message, background_color='red')

def PollWindowEvents():
    global popup_window, main_window, current_message, new_window

    input_event = None
    if popup_window:
        input_event, _ = popup_window.read(timeout=10)

    output_event = None
    if main_window:
        output_event, _ = main_window.read(timeout=10)

    if (input_event in ('__TIMEOUT__', None))  and (output_event in ('__TIMEOUT__', None)):
        return

    if output_event in (None, 'Exit'):
        CloseAndExit()

    if input_event: 
        popup_window.close()
        current_message = input_event
        new_window = True
    else:
        current_message = output_event
        new_window = True

    return

def ShowIMPopup():
    global popup_window

    mode_selector = [[sg.Text('Select a mode')],
                     [],
                     [sg.Text('-'  * 110)],
                     [sg.Button('Cancel', size=(8,1), button_color=('white','orange')),
                      sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    for mode in ZephyrInstModes:
        mode_selector[1].append(sg.Button(mode, size=(6,1)))

    # GUI mode selector
    popup_window = sg.Window('Mode Message Configurator', mode_selector)

def WaitIMPopup():
    global popup_window, current_message, new_window

    event, _ = popup_window.read(timeout=10)

    if '__TIMEOUT__' == event:
        return

    popup_window.close()

    # quit the program if the window is closed or Exit selected
    if event in (None, 'Exit'):
        CloseAndExit()

    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    # as long as cancel wasn't selected, set the mode
    if 'Cancel' != event:
        sg.Print(timestring + "Setting mode:", event)
        OBC_Sim_Generic.sendIM(instrument, event, cmd_filename, port)

    # go back to the message selector
    current_message = 'waiting'
    new_window = True

def ShowGPSPopup():
    global popup_window

    gps_selector = [[sg.Text('Select a solar zenith angle (degrees)')],
                    [sg.InputText('120')],
                    [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
                     sg.Button('Cancel', size=(8,1), button_color=('white','orange')),
                     sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    # GUI GPS creator with SZA float validation
    popup_window = sg.Window('GPS Message Configurator', gps_selector)

def WaitGPSPopup():
    global popup_window, current_message, new_window

    event, values = popup_window.read(timeout=10)

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

    popup_window.close()

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

    sg.Print(timestring + "Sending shutdown warning")
    OBC_Sim_Generic.sendSW(instrument, cmd_filename, port)

def ShowTCPopup():
    global popup_window

    tc_selector = [[sg.Text('Input a telecommand:')],
                    [sg.InputText('1;')],
                    [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
                     sg.Button('Cancel', size=(8,1), button_color=('white','orange')),
                     sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    # GUI TC creator
    popup_window = sg.Window('TC Creator', tc_selector)

def WaitTCPopup():
    global popup_window, current_message, new_window

    event, values = popup_window.read(timeout=10)

    if '__TIMEOUT__' == event:
        return

    popup_window.close()

    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    # quit the program if the window is closed or Exit selected
    if event in (None, 'Exit'):
        CloseAndExit()
    elif 'Cancel' != event:
        sg.Print(timestring + "Sending TC:", values[0])
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

    sg.Print(timestring + "Sent RAAck")
    OBC_Sim_Generic.sendRAAck(instrument, 'ACK', cmd_filename, port)

def TMAckMessage():
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sending TM ack")
    OBC_Sim_Generic.sendTMAck(instrument, 'ACK', cmd_filename, port)

def CloseAndExit():
    global main_window, popup_window

    if main_window != None:
        main_window.close()

    if popup_window != None:
        popup_window.close()

    os._exit(0)

def RunCommands():
    global new_window, current_message

    if new_window:
        if 'waiting' == current_message:
            new_window = False

        elif 'IM' == current_message:
            ShowIMPopup()
            new_window = False

        elif 'GPS' == current_message:
            ShowGPSPopup()
            new_window = False

        elif 'SW' == current_message:
            SWMessage()
            current_message = 'waiting'
            new_window = True

        elif 'TC' == current_message:
            ShowTCPopup()
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
            sg.Print("Unknown new window requested: "+str(current_message))
            current_message = 'waiting'
            new_window = True

    else:
        if 'waiting' == current_message:
            PollWindowEvents()

        elif 'IM' == current_message:
            WaitIMPopup()

        elif 'GPS' == current_message:
            WaitGPSPopup()

        elif 'TC' == current_message:
            WaitTCPopup()

        else:
            sg.Print("Bad window to wait on"+str(current_message))
            current_message = 'waiting'
            new_window = True
