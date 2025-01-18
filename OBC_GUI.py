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
import serial
import glob
import datetime
import PySimpleGUIQt as sg
import OBC_Sim_Generic

# message types and instrument modes
ZephyrMessageTypes = ['IM', 'GPS', 'SW', 'TC', 'SAck', 'RAAck', 'TMAck']
ZephyrInstModes = ['SB', 'FL', 'LP', 'SA', 'EF']

# global window objects
popup_window = None
main_window = None
current_action = 'waiting'
new_window = True

# global configuration variables
serial_port = None
cmd_filename = ''
instrument = ''

# set the overall look of the GUI
sg.theme('SystemDefault')
sg.set_options(font = ("Helvetica", 12))

def ConfigWindow(comm_port: str)->dict:
    '''Configuration window for the OBC simulator

    A dictionary is returned with the following keys:
    inst(str): the instrument type
    serial(str): the serial port name connected to the instrument log port
    auto_ack(bool): whether to automatically respond with ACKs
    '''

    settings = sg.UserSettings()
    zephyr_port = settings.get('ZephyrPort', 'None')
    log_port = settings.get('LogPort', 'None')
    auto_ack = settings.get('AutoAck', True)

    instruments = ['RATS', 'LPC', 'RACHUTS', 'FLOATS']
    radio_instruments = [sg.Radio(i, group_id="radio_instruments", key=i, default=(settings.get('Instrument', False)==i)) for i in instruments]
    radio_instruments.insert(0, sg.Text('Instrument:'))

    ports = glob.glob('/dev/cu.*')
    ports.remove('/dev/cu.Bluetooth-Incoming-Port')
    radio_zephyr_ports = [[sg.Radio(p, group_id="radio_zephyr_ports", key="zephyr_"+p, default=(p==zephyr_port))] for p in ports]
    radio_zephyr_ports.insert(0, [sg.Text('Zephyr port:')])

    radio_log_ports = [[sg.Radio(p, group_id="radio_log_ports", key="log_"+p, default=(p==log_port))] for p in ports]
    radio_log_ports.insert(0, [sg.Text('Log port:')])

    config_selector = [
        [sg.Text('Settings file: ' + settings.full_filename)],
        [sg.Text(" "), sg.Text(" "), sg.Text(" ")],
        radio_instruments,
        [sg.Text(" "), sg.Text(" "), sg.Text(" ")],
        [sg.Text('Automatically respond with ACKs?'), sg.Radio('Yes',group_id=2,key='ACK',default=settings.get('AutoAck')), sg.Radio('No',group_id=2,key='NOACK',default=(not settings.get('AutoAck')))],
        [sg.Column(radio_log_ports), sg.Column(radio_zephyr_ports)],
        [sg.Button('Continue', size=(8,1), button_color=('white','blue')),
        sg.Button('Exit', size=(8,1), button_color=('white','red'))]]

    # GUI configurator
    window = sg.Window('Configure', config_selector)
    event, values = window.read()
    window.close()

    zephyr_port = [i for i in values if i.startswith('zephyr_') and values[i] == True]
    log_port = [i for i in values if i.startswith('log_') and values[i] == True]
    instrument = [i for i in instruments if values[i] == True]
    settings['ZephyrPort'] = zephyr_port[0].replace('zephyr_','')
    settings['LogPort'] = log_port[0].replace('log_','')
    settings['Instrument'] = instrument[0]
    settings['LastRun'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    settings['AutoAck'] = values['ACK']

    config = {}
    config['LogPort'] = settings['LogPort'] 
    config['Instrument'] = settings['Instrument']
    config['AutoAck'] = settings['AutoAck']

    sg.Print("Instrument:", config['Instrument'])
    sg.Print("Port:", config['LogPort'])
    sg.Print("AutoAck:", config['AutoAck'])    

    # quit the program if the window is closed or Exit selected
    if event in (None, 'Exit'):
        CloseAndExit()

    return config

def MainWindow(config:dict, sport:serial, cmd_fname:str)->None:
    '''Create the main window
    
    It has control buttons at the top and two columns for log messages and Zephyr messages
    '''
    global main_window
    global serial_port
    global instrument
    global cmd_filename

    instrument = config['Instrument']
    serial_port = sport
    cmd_filename = cmd_fname

    # Command buttons at the top of the window
    buttons = [sg.Button(s, size=(6,1)) for s in ZephyrMessageTypes]
    buttons.append(sg.Button('Exit', size=(8,1), button_color=('white','red')))
    buttons.append(sg.Stretch())
    buttons.append(sg.Text("Log port: " + config['LogPort'], size=(30,1), justification='right'))
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
    global popup_window, main_window, current_action, new_window

    popup_window_event = None
    if popup_window:
        popup_window_event, _ = popup_window.read(timeout=10)

    main_window_event, _ = main_window.read(timeout=10)

    if main_window_event in (None, 'Exit'):
        CloseAndExit()

    if (popup_window_event in ('__TIMEOUT__', None))  and (main_window_event == '__TIMEOUT__'):
        return

    if popup_window_event: 
        popup_window.close()
        popup_window = None
        current_action = popup_window_event
        new_window = True
    else:
        current_action = main_window_event
        new_window = True

    return

def ShowIMPopup():
    global popup_window

    mode_selector = [[sg.Text('Select a mode')],
                     [],
                     [sg.Text('-'  * 110)],
                     [sg.Button('Cancel', size=(8,1), button_color=('white','orange'))]]

    for mode in ZephyrInstModes:
        mode_selector[1].append(sg.Button(mode, size=(6,1)))

    # GUI mode selector
    popup_window = sg.Window('Mode Message Configurator', mode_selector)

def WaitIMPopup():
    global popup_window, current_action, new_window

    event, _ = popup_window.read(timeout=10)

    if '__TIMEOUT__' == event:
        return

    popup_window.close()
    popup_window = None

    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    # as long as cancel wasn't selected, set the mode
    if 'Cancel' != event:
        sg.Print(timestring + "Setting mode:", event)
        OBC_Sim_Generic.sendIM(instrument, event, cmd_filename, serial_port)

    # go back to the message selector
    current_action = 'waiting'
    new_window = True

def ShowGPSPopup():
    global popup_window

    gps_selector = [[sg.Text('Select a solar zenith angle (degrees)')],
                    [sg.InputText('120')],
                    [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
                     sg.Button('Cancel', size=(8,1), button_color=('white','orange'))]]

    # GUI GPS creator with SZA float validation
    popup_window = sg.Window('GPS Message Configurator', gps_selector)

def WaitGPSPopup():
    global popup_window, current_action, new_window

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
    popup_window = None

    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    if 'Submit' == event:
        sg.Print(timestring + "Sending GPS, SZA =", str(sza))
        OBC_Sim_Generic.sendGPS(sza, cmd_filename, serial_port)

    # go back to the message selector
    current_action = 'waiting'
    new_window = True

def SWMessage():
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sending shutdown warning")
    OBC_Sim_Generic.sendSW(instrument, cmd_filename, serial_port)

def ShowTCPopup():
    global popup_window

    tc_selector = [[sg.Text('Input a telecommand:')],
                    [sg.InputText('1;')],
                    [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
                     sg.Button('Cancel', size=(8,1), button_color=('white','orange'))]]

    # GUI TC creator
    popup_window = sg.Window('TC Creator', tc_selector)

def WaitTCPopup():
    global popup_window, current_action, new_window

    event, values = popup_window.read(timeout=10)

    if '__TIMEOUT__' == event:
        return

    popup_window.close()
    popup_window = None

    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    if 'Submit' == event:
        sg.Print(timestring + "Sending TC:", values[0])
        OBC_Sim_Generic.sendTC(instrument, values[0], cmd_filename, serial_port)

    # go back to the message selector
    current_action = 'waiting'
    new_window = True

def SAckMessage():
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sending safety ack")
    OBC_Sim_Generic.sendSAck(instrument, 'ACK', cmd_filename, serial_port)

def RAAckMessage():
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sent RAAck")
    OBC_Sim_Generic.sendRAAck(instrument, 'ACK', cmd_filename, serial_port)

def TMAckMessage():
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sending TM ack")
    OBC_Sim_Generic.sendTMAck(instrument, 'ACK', cmd_filename, serial_port)

def CloseAndExit():
    global main_window, popup_window

    if main_window != None:
        main_window.close()

    if popup_window != None:
        popup_window.close()
        popup_window = None

    os._exit(0)

def RunCommands():
    global new_window, current_action

    if new_window:
        if 'waiting' == current_action:
            new_window = False

        elif 'IM' == current_action:
            ShowIMPopup()
            new_window = False

        elif 'GPS' == current_action:
            ShowGPSPopup()
            new_window = False

        elif 'SW' == current_action:
            SWMessage()
            current_action = 'waiting'
            new_window = True

        elif 'TC' == current_action:
            ShowTCPopup()
            new_window = False

        elif 'SAck' == current_action:
            SAckMessage()
            current_action = 'waiting'
            new_window = True

        elif 'RAAck' == current_action:
            RAAckMessage()
            current_action = 'waiting'
            new_window = True

        elif 'TMAck' == current_action:
            TMAckMessage()
            current_action = 'waiting'
            new_window = True

        else:
            sg.Print("Unknown new window requested: "+str(current_action))
            current_action = 'waiting'
            new_window = True

    else:
        if 'waiting' == current_action:
            PollWindowEvents()

        elif 'IM' == current_action:
            WaitIMPopup()

        elif 'GPS' == current_action:
            WaitGPSPopup()

        elif 'TC' == current_action:
            WaitTCPopup()

        else:
            sg.Print("Bad window to wait on"+str(current_action))
            current_action = 'waiting'
            new_window = True
