#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" 
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

SimplePyGUIQt.UserSettings is used to persist the configuration parameters.
These are stored in a JSON file in the user's home directory. The config
parameters are returned to the main program as a dictionary.
"""

# modules
import os
import queue
import serial
import serial.tools.list_ports
import glob
import xmltodict
import PySimpleGUIQt as sg
import OBC_Sim_Generic

# message types and instrument modes
ZephyrMessageTypes = ['IM', 'GPS', 'SW', 'TC', 'SAck', 'RAAck', 'TMAck']
ZephyrInstModes = ['SB', 'FL', 'LP', 'SA', 'EF']

# global window objects
popup_window = None
main_window = None
xml_queue = None
current_action = 'waiting'
new_window = True

# global variables
log_port = None
zephyr_port = None
cmd_filename = ''
instrument = ''
serial_suspended = False

# set the overall look of the GUI
sg.theme('SystemDefault')
sg.set_options(font = ("Monaco", 11))

def ConfigWindow() -> dict:
    '''Configuration window for the OBC simulator

    Persistent settings are loaded from a JSON file in the user's home directory.
    The user can change the settings. The selected settings are saved to the JSON file,
    and returned as a dictionary. There is not a one-to-one correspondence between the
    settings and the returned dictionary.

    The settings contains the following:    
    'ZephyrPort': the serial port object for the Zephyr port
    'LogPort': the serial port object for the log port, or None if shared with Zephyr port
    'SharedPorts': whether the Zephyr and log ports are shared
    'Instrument': the instrument type
    'AutoAck': whether to automatically respond with ACKs
    'WindowSize': the size of the window (Small, Medium, Large)
    'DataDirectory': the directory for data storage

    The returned dictionary contains the following:
    ZephyrPort(serial.Serial): the serial port object for the Zephyr port
    LogPort(serial.Serial or None): the serial port object for the log port, or None if shared with Zephyr port
    SharedPorts(bool): whether the Zephyr and log ports are shared
    Instrument(str): the instrument type
    AutoAck(bool): whether to automatically respond with ACKs
    WindowParams(dict): parameters for the window size (font_size, width, height)
    DataDirectory(str): the directory for data storage
    '''

    # Load the saved settings from the settings file.
    settings = sg.UserSettings(filename='OBC_Simulator.json', path=os.path.abspath(os.path.expanduser("~/")));
    zephyr_port = settings.get('ZephyrPort', 'None')
    log_port = settings.get('LogPort', 'None')
    auto_ack = settings.get('AutoAck', True)

    instruments = ['RATS', 'LPC', 'RACHUTS', 'FLOATS']
    window_sizes = ['Small', 'Medium', 'Large']
    window_params = {'Small': {'font_size': 8, 'width': 100, 'height': 20},
                     'Medium': {'font_size': 10, 'width': 120, 'height': 30},
                     'Large': {'font_size': 12, 'width': 160, 'height': 40}} 

    # Find all of the appropriate serial ports.
    ports = [port.device for port in serial.tools.list_ports.comports()]
    # delete ports with Bluetooth in the name
    ports = [port for port in ports if 'Bluetooth' not in port]
    
    # Loop until all parameters are specified
    config = {}
    config_values_validated = False
    while not config_values_validated:

        # Create radio buttons for instruments and set the default to the saved instrument (if it exists).
        radio_instruments = [sg.Radio(i, group_id="radio_instruments", key=i, default=(settings.get('Instrument', False)==i)) for i in instruments]
        radio_instruments.insert(0, sg.Text('Instrument:'))

        # Create radio buttons for the overall window size and set the default to the saved size (if it exists).
        radio_window_size = [sg.Radio(s, group_id="radio_window_size", key=s, default=(s==settings.get('WindowSize', 'Medium'))) for s in window_sizes]
        radio_window_size.insert(0, sg.Text('Window size:'))

        # Create radio buttons for zephyr ports and set the default to the saved port (if it exists). 
        # The key is prefixed with 'zephyr_' to differentiate it from the log ports.
        radio_zephyr_ports = [[sg.Radio(p, group_id="radio_zephyr_ports", key="zephyr_"+p, default=(p==zephyr_port))] for p in ports]
        radio_zephyr_ports.insert(0, [sg.Text('Zephyr port:')])

        # Create radio buttons for log ports and set the default to the saved port (if it exists).
        # The key is prefixed with 'log_' to differentiate it from the zephyr ports.
        radio_log_ports = [[sg.Radio(p, group_id="radio_log_ports", key="log_"+p, default=(p==log_port))] for p in ports]
        radio_log_ports.insert(0, [sg.Text('Log port:')])

        # Create the layout for the configuration window
        layout = [
            [sg.Text('Settings file: ' + settings.full_filename)],
            [sg.Text(" ")],
            [sg.Text("Data Directory:"),
             sg.Text(settings.get('DataDirectory', os.getcwd()+'/')), 
             sg.Button('Select', button_color=('white','blue'))],
            radio_window_size,
            [sg.Text(" ")],
            radio_instruments,
            [sg.Text(" "), sg.Text(" "), sg.Text(" ")],
            [sg.Text('Automatically respond with ACKs?'), 
             sg.Radio('Yes',group_id=2,key='ACK',default=auto_ack), 
             sg.Radio('No',group_id=2,key='NOACK',default=not auto_ack)],
            [sg.Text(" ")],
            [sg.Text("- Select the same Log and Zephyr ports when StratoCore<INST> is")],
            [sg.Text("  compiled for port sharing or when the log port is not used. -")],
            [sg.Column(radio_zephyr_ports), sg.Column(radio_log_ports)],
            [sg.Text(" ")],
            [sg.Button('Continue', size=(8,1), button_color=('white','blue')),
             sg.Button('Exit', size=(8,1), button_color=('white','red'))
            ]
        ]

        window = sg.Window('Configure', layout)
        event, values = window.read()
        window.close()
        if event in ('Select'):
            settings['DataDirectory'] = sg.popup_get_folder('Select the data directory')
            continue

        # quit the program if the window is closed or Exit selected
        if event in (None, 'Exit'):
            CloseAndExit()

        # Extract the selected values from the radio buttons.
        zephyr_port = [i for i in values if i.startswith('zephyr_') and values[i] == True]
        log_port = [i for i in values if i.startswith('log_') and values[i] == True]
        instrument = [i for i in instruments if values[i] == True]
        if instrument:
            instrument = instrument[0]
        window_size = [i for i in window_sizes if values[i] == True]
        if window_size:
            window_size = window_size[0]

        # Verify the selections.
        if zephyr_port and log_port and instrument:
            zephyr_port_name = zephyr_port[0].replace('zephyr_','')
            log_port_name = log_port[0].replace('log_','')
            # Verify that the zephyr and log ports are both accessible
            try:
                config['ZephyrPort'] = serial.Serial(port=zephyr_port_name, baudrate=115200, timeout=0.001)
                config['ZephyrPort'].reset_input_buffer()
                if log_port_name != zephyr_port_name:
                    config['LogPort'] = serial.Serial(port=log_port_name, baudrate=115200, timeout=0.001)
                    config['LogPort'].reset_input_buffer()
                    config['SharedPorts'] = False
                else:
                    config['LogPort'] = None
                    config['SharedPorts'] = True
            except Exception as e:
                sg.popup('Error opening serial port: ' + str(e), title='Error')
                continue
            config_values_validated = True
        else:
            sg.popup('Please select an Instrument, Zephyr port, and Log port', title='Error')

    # Save the selected parameters to the settings file.
    settings['ZephyrPort'] = zephyr_port[0].replace('zephyr_','')
    settings['LogPort'] = log_port[0].replace('log_','')
    settings['Instrument'] = instrument
    settings['AutoAck'] = values['ACK']
    settings['WindowSize'] = window_size

    # Return the selected parameters as a dictionary.
    config['Instrument'] = settings['Instrument']
    config['AutoAck'] = settings['AutoAck']
    config['WindowParams'] = window_params[window_size]
    config['DataDirectory'] = settings['DataDirectory']

    # Print the selected parameters to the debug window.
    sg.Print("Instrument:", config['Instrument'])
    sg.Print("Zephyr Port:", config['ZephyrPort'])
    sg.Print("Log Port:", config['LogPort'])
    sg.Print("AutoAck:", config['AutoAck'])

    return config

def MainWindow(config: dict, logport: serial.Serial, zephyrport: serial.Serial, cmd_fname: str, xmlqueue: queue.Queue) -> None:
    '''Main window for the OBC simulator
    
    It has control buttons at the top and two columns for log messages and Zephyr messages
    '''
    global main_window
    global log_port
    global zephyr_port
    global instrument
    global cmd_filename
    global xml_queue

    instrument = config['Instrument']
    log_port = logport
    zephyr_port = zephyrport
    cmd_filename = cmd_fname
    xml_queue = xmlqueue

    # Command buttons and config values at the top of the window
    button_row = [sg.Button(s, size=(6,1)) for s in ZephyrMessageTypes]
    button_row.append(sg.Button('Suspend', size=(8,1), button_color=('white','orange')))
    button_row.append(sg.Button('Exit', size=(8,1), button_color=('white','red')))

    if config['SharedPorts']:
        log_port_text = sg.Text("Log port: " + zephyr_port.name)
    else:
        log_port_text = sg.Text("Log port: " + config['LogPort'].name)
    zephyr_port_text = sg.Text("Zephyr port: " + config['ZephyrPort'].name)
    auto_ack_text = sg.Text("AutoAck: " + str(config['AutoAck']))
    config_row = []
    config_row.append(log_port_text)
    config_row.append(zephyr_port_text)
    config_row.append(auto_ack_text)
    files_row = []
    files_row.append(sg.Text("TM directory:"))
    files_row.append(sg.InputText(' ', key='-tm_directory-', readonly=True, size=(80,1)))

    # Main window layout
    sg.set_options(font = ("Monaco", config['WindowParams']['font_size']))
    w = config['WindowParams']['width']
    h = config['WindowParams']['height']
    widgets = [
        button_row,
        [sg.Column([[sg.Text('StratoCore Log Messages')], [sg.MLine(key='-log_window-'+sg.WRITE_ONLY_KEY, size=(w/4,h))]]),
         sg.Column([[sg.Text(f'Messages TO/FROM {instrument}')], [sg.MLine(key='-zephyr_window-'+sg.WRITE_ONLY_KEY, size=(3*w/4,h))]])],
        config_row,
        files_row
    ]

    main_window = sg.Window(title=instrument, layout=widgets, location=(10, 10), finalize=True)

def AddLogMsg(message: str) -> None:
    '''Add a message to the log window
    
    if the message contains 'ERR: ', the text color is red
    '''

    global main_window

    if -1 != message.find('ERR: '):
        main_window['-log_window-'+sg.WRITE_ONLY_KEY].print(message, text_color='red', end="")
    else:
        main_window['-log_window-'+sg.WRITE_ONLY_KEY].print(message, end="")

def AddZephyrMsg(message: str) -> None:
    '''Add a message to the Zephyr window
    
    The message color is determined by the message type.
    '''

    global main_window

    if -1 != message.find('(TO)'):
        main_window['-zephyr_window-'+sg.WRITE_ONLY_KEY].print(message, text_color='blue', end="")
    elif -1 != message.find('TM') and -1 != message.find('CRIT'):
        main_window['-zephyr_window-'+sg.WRITE_ONLY_KEY].print(message, text_color='red', end="")
    elif -1 != message.find('TM') and -1 != message.find('WARN'):
        main_window['-zephyr_window-'+sg.WRITE_ONLY_KEY].print(message, text_color='orange', end="")
    elif -1 != message.find('TM'):
        main_window['-zephyr_window-'+sg.WRITE_ONLY_KEY].print(message, text_color='green', end="")
    else:
        main_window['-zephyr_window-'+sg.WRITE_ONLY_KEY].print(message, end="")

def AddDebugMsg(message: str, error: bool = False) -> None:
    '''Print a message to the debug window

    If error is True, the message background is red
    '''
    if not error:
        sg.Print(message)
    else:
        sg.Print(message, background_color='red')

def PollWindowEvents() -> None:
    '''Poll the main and popup windows for events
    
    When an event is detected, current_action is set to the event name,
    and new_window is set to True to indicate that the event should be handled.
    '''

    global popup_window, main_window, current_action, new_window

    popup_window_event = None
    if popup_window:
        popup_window_event, _ = popup_window.read(timeout=10)

    main_window_event, _ = main_window.read(timeout=10)

    if main_window_event in (None, 'Exit'):
        CloseAndExit()

    if main_window_event in ('Suspend', 'Resume'):
        # toggle the suspend state
        SerialSuspend()
        if serial_suspended:
            main_window["Suspend"].update('Resume', button_color=('white','blue'))
        else:
            main_window["Suspend"].update('Suspend', button_color=('white','orange'))

    if serial_suspended:
        return

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

def ShowIMPopup() -> None:
    global popup_window

    mode_selector = [[sg.Text('Select a mode')],
                     [],
                     [sg.Text('-'  * 110)],
                     [sg.Button('Cancel', size=(8,1), button_color=('white','orange'))]]

    for mode in ZephyrInstModes:
        mode_selector[1].append(sg.Button(mode, size=(6,1)))

    # GUI mode selector
    popup_window = sg.Window('Mode Message Configurator', mode_selector)

def WaitIMPopup() -> None:
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
        im_msg = OBC_Sim_Generic.sendIM(instrument, event, cmd_filename, zephyr_port)
        msg_to_queue(im_msg)

    # go back to the message selector
    current_action = 'waiting'
    new_window = True

def ShowGPSPopup() -> None:
    global popup_window

    gps_selector = [[sg.Text('Select a solar zenith angle (degrees)')],
                    [sg.InputText('120')],
                    [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
                     sg.Button('Cancel', size=(8,1), button_color=('white','orange'))]]

    # GUI GPS creator with SZA float validation
    popup_window = sg.Window('GPS Message Configurator', gps_selector)

def WaitGPSPopup() -> None:
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
        msg = OBC_Sim_Generic.sendGPS(sza, cmd_filename, zephyr_port)
        msg_to_queue(msg)

    # go back to the message selector
    current_action = 'waiting'
    new_window = True

def SWMessage() -> None:
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sending shutdown warning")
    OBC_Sim_Generic.sendSW(instrument, cmd_filename, zephyr_port)

def ShowTCPopup() -> None:
    global popup_window

    tc_selector = [[sg.Text('Input a telecommand:')],
                    [sg.InputText('1;')],
                    [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
                     sg.Button('Cancel', size=(8,1), button_color=('white','orange'))]]

    # GUI TC creator
    popup_window = sg.Window('TC Creator', tc_selector)

def WaitTCPopup() -> None:
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
        msg = OBC_Sim_Generic.sendTC(instrument, values[0], cmd_filename, zephyr_port)
        msg_to_queue(msg)

    # go back to the message selector
    current_action = 'waiting'
    new_window = True

def SAckMessage() -> None:
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sending safety ack")
    msg = OBC_Sim_Generic.sendSAck(instrument, 'ACK', cmd_filename, zephyr_port)
    msg_to_queue(msg)

def RAAckMessage() -> None:
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sent RAAck")
    msg = OBC_Sim_Generic.sendRAAck(instrument, 'ACK', cmd_filename, zephyr_port)
    msg_to_queue(msg)

def TMAckMessage() -> None:
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sending TM ack")
    msg = OBC_Sim_Generic.sendTMAck(instrument, 'ACK', cmd_filename, zephyr_port)
    msg_to_queue(msg)

def CloseAndExit() -> None:
    global main_window, popup_window

    if main_window != None:
        main_window.close()

    if popup_window != None:
        popup_window.close()
        popup_window = None

    os._exit(0)

def RunCommands() -> None:
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

def msg_to_queue(msg: str) -> None:
    global xml_queue
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    # Add tags to make the message XML parsable
    newmsg = '<XMLTOKEN>' + msg + '</XMLTOKEN>'
    dict = xmltodict.parse(newmsg)
    xml_queue.put(f'{timestring}  (TO) {dict["XMLTOKEN"]}\n')  

def SerialSuspend() -> None:
    '''Suspend the serial ports until suspend button is pressed again'''

    global serial_suspended
    global log_port
    global zephyr_port

    if not serial_suspended:
        zephyr_port.close()
        if log_port and zephyr_port.name != log_port.name:
            log_port.close()
        serial_suspended = True
    else:
        zephyr_port.open()
        if log_port and zephyr_port.name != log_port.name:
            log_port.open()
        serial_suspended = False

def SetTmDir(filename: str) -> None:
    global main_window
    main_window['-tm_directory-'].update(filename)