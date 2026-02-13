#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" 
This module provides the GUI for the OBC simulator. 

ConfigWindow() is called to prompt for configuration.

MainWindow() is called to create the main window.

LogAddMsg() and ZephyrAddMsg() are called to add messages to the log and Zephyr message displays.

PollWindowEvents() is called from the main program loop to poll the main window for events.

SimplePyGUIQt.UserSettings is used to persist the configuration parameters.
These are stored in a JSON file in the user's home directory. The config
parameters are returned to the main program as a dictionary.
"""

# modules
import os
import sys
import ast
import json
import queue
import serial
import serial.tools.list_ports
import xmltodict
import pyperclip
import PySimpleGUIQt as sg
import OBC_Sim_Generic

# Zephyr messages with no parameters, and their tooltips
ZephyrMessagesNoParams = [
    ('SW',   'Send a Shutdown Warning'), 
    ('SAck', 'Send a Safety Ack'), 
    ('RAAck', 'Send a RAA Ack'), 
    ('TMAck', 'Send a TM Ack')
]

# Instrument modes, and their tooltips
ZephyrInstModes = [
    ('SB','Standby Mode'),
    ('FL','Flight Mode'), 
    ('LP', 'Low Power Mode'),
    ('SA','Safety Mode'),
    ('EF','End of Flight Mode')]

# set global variables
main_window = None
xml_queue = None
new_window = True
log_port = None
zephyr_port = None
cmd_filename = ''
instrument = ''
serial_suspended = False
active_config_set = None

# set the maximum number of lines in the log window,
# and the number of lines to keep when the maximum is reached
MAXLOGLINES = 2000
KEEPLOGLINES = 1600

log_line_count = 0
message_display_types = ['GPS', 'TM', 'TC', 'IM', 'TMAck', 'TCAck', 'IMAck', 'IMR']
message_display_filters = {msg_type: True for msg_type in message_display_types}
display_toggle_keys = {msg_type: f'-display-{msg_type}-' for msg_type in message_display_types}
display_all_toggle_key = '-display-all-'

# set the overall look of the GUI
sg.theme('SystemDefault')
sg.set_options(font = ("Monaco", 11))
window_sizes = ['Small', 'Medium', 'Large']
window_params = {'Small': {'font_size': 8, 'width': 100, 'height': 20},
                'Medium': {'font_size': 10, 'width': 140, 'height': 30},
                'Large': {'font_size': 12, 'width': 180, 'height': 40}} 
button_sizes = {'Small': (4,1), 'Medium': (6,1), 'Large': (8,1)}
window_size = 'Medium'

def NormalizeMessageDisplayFilters(filters: dict) -> dict:
    parsed_filters = {}
    if isinstance(filters, dict):
        parsed_filters = filters
    elif isinstance(filters, str):
        # UserSettings may deserialize nested structures as strings for older entries.
        try:
            json_filters = json.loads(filters)
            if isinstance(json_filters, dict):
                parsed_filters = json_filters
        except Exception:
            try:
                literal_filters = ast.literal_eval(filters)
                if isinstance(literal_filters, dict):
                    parsed_filters = literal_filters
            except Exception:
                parsed_filters = {}

    normalized = {}
    for msg_type in message_display_types:
        normalized[msg_type] = bool(parsed_filters.get(msg_type, True))
    return normalized

def ConfigWindow() -> dict:
    '''Configuration window for the OBC simulator

    Persistent settings are loaded from a JSON file in the user's home directory.
    The user can change the settings. The selected settings are saved to the JSON file,
    and returned as a dictionary. There is not a one-to-one correspondence between the
    settings and the returned dictionary.

    The settings contains the following:    
    'ZephyrPort': the serial port object for the Zephyr port
    'LogPort': the serial port object for the log port, or None if shared with Zephyr port
    'Instrument': the instrument type
    'AutoAck': whether to automatically respond with ACKs
    'AutoGPS': whether to automatically send GPS
    'WindowSize': the size of the window (Small, Medium, Large)
    'DataDirectory': the directory for data storage

    The returned dictionary contains the following:
    ZephyrPort(serial.Serial): the serial port object for the Zephyr port
    LogPort(serial.Serial or None): the serial port object for the log port, or None if shared with Zephyr port
    SharedPorts(bool): whether the Zephyr and log ports are shared
    Instrument(str): the instrument type
    AutoAck(bool): whether to automatically respond with ACKs
    AutoGPS(bool): whether to automatically send GPS
    WindowParams(dict): parameters for the window size (font_size, width, height)
    DataDirectory(str): the directory for data storage
    ConfigSet(str): the name of the configuration set
    '''

    global window_size

    settings = sg.UserSettings(filename='OBC_Simulator.ini', use_config_file=True, autosave=True, path=os.path.abspath(os.path.expanduser("~/")))
    if not settings['-Main-']['SelectedConfig']:
        settings['-Main-']['SelectedConfig'] = 'NewSet' # default to the first configuration set

    # Create a list of settings keys. This will need to be updated if new settings are added.
    settings_keys = ['ZephyrPort', 'LogPort', 'Instrument', 'AutoAck', 'AutoGPS', 'WindowSize', 'DataDirectory', 'MessageDisplayFilters']

    instruments = ['RATS', 'LPC', 'RACHUTS', 'FLOATS']

    # Loop until all parameters are specified
    config = {}
    config_values_validated = False
    while not config_values_validated:
        # Get the current settings. Default values are used if the setting is not found.
        settings = sg.UserSettings(filename='OBC_Simulator.ini', use_config_file=True, path=os.path.abspath(os.path.expanduser("~/")))
        config_set = settings['-Main-'].get('SelectedConfig', 'NewSet')
        data_dir = settings[config_set].get('DataDirectory', None)
        auto_ack = settings[config_set].get('AutoAck', True)
        auto_gps = settings[config_set].get('AutoGPS', True)
        window_size = settings[config_set].get('WindowSize', 'Medium')
        zephyr_port = settings[config_set].get('ZephyrPort', 'None')
        log_port = settings[config_set].get('LogPort', 'None')
        msg_display_filters = NormalizeMessageDisplayFilters(settings[config_set].get('MessageDisplayFilters', {}))
        settings[config_set]['MessageDisplayFilters'] = msg_display_filters

        # Find all of the appropriate serial ports.
        ports = [port.device for port in serial.tools.list_ports.comports()]
        # delete ports with Bluetooth in the name
        ports = [port for port in ports if 'Bluetooth' not in port]
    
        # Create radio buttons for instruments and set the default to the saved instrument (if it exists).
        radio_instruments = [sg.Radio(i, group_id="radio_instruments", key=i, default=(settings[config_set].get('Instrument', False)==i)) for i in instruments]
        radio_instruments.insert(0, sg.Text('Instrument:'))

        # Create radio buttons for the overall window size and set the default to the saved size (if it exists).
        radio_window_size = [sg.Radio(s, group_id="radio_window_size", key=s, default=(s==settings[config_set].get('WindowSize', 'Medium'))) for s in window_sizes]
        radio_window_size.insert(0, sg.Text('Window size:'))

        # Create radio buttons for zephyr ports and set the default to the saved port (if it exists). 
        # The key is prefixed with 'zephyr_' to differentiate it from the log ports.
        radio_zephyr_ports = [[sg.Radio(p, group_id="radio_zephyr_ports", key="zephyr_"+p, default=(p==zephyr_port))] for p in ports]
        radio_zephyr_ports.insert(0, [sg.Text('Zephyr port:')])

        # Create radio buttons for log ports and set the default to the saved port (if it exists).
        # The key is prefixed with 'log_' to differentiate it from the zephyr ports.
        radio_log_ports = [[sg.Radio(p, group_id="radio_log_ports", key="log_"+p, default=(p==log_port))] for p in ports]
        radio_log_ports.insert(0, [sg.Text('Log port:')])

        config_manage = [sg.Text("Configuration set:"), sg.Text(config_set),
            sg.Button('Select', key='-popup-select-config-', button_color=('white','blue')),
            sg.Button('Rename', key='-popup-rename-config-', button_color=('white','blue')),
            sg.Button('New',    key='-popup-new-config-',    button_color=('white','blue')),
            sg.Button('Delete', key='-popup-delete-config-', button_color=('white','blue'))]

        # Create the layout for the configuration window
        layout = [
            config_manage,
            radio_instruments,
            [sg.Text('Settings file: ' + settings.full_filename)],
            [sg.Text("Data Directory:"),
              sg.Text(data_dir), 
              sg.Button('Select', key='-select-data-dir-', button_color=('white','blue'))],
            radio_window_size,
            [sg.Text('Automatically respond with ACKs?'), 
              sg.Radio('Yes', group_id='-ack-group-',key='-auto-ack-',default=auto_ack), 
              sg.Radio('No', group_id='-ack-group-',key='-no-auto-ack-',default=not auto_ack)],
            [sg.Text('Automatically send GPS?'), 
              sg.Radio('Yes',group_id='-gps-group-',key='-auto-gps-',default=auto_gps), 
              sg.Radio('No',group_id='-gps-group-',key='-no-auto-gps',default=not auto_gps)],
            [sg.Text(" ")],
            [sg.Text("  Select the same Log and Zephyr ports when StratoCore<INST> is")],
            [sg.Text("  compiled for port sharing or when the log port is not used.  ")],
            [sg.Column(radio_zephyr_ports), sg.Column(radio_log_ports)],
            [sg.Text(" ")],
            [sg.Button('Continue', key='-continue-', size=(8,1), button_color=('white','blue')),
             sg.Button('Exit', key='-exit-', size=(8,1), button_color=('white','red'))
            ]
        ]

        config_window = sg.Window('Configure', layout)
        event, values = config_window.read()

        config_window.close()

        if event in ('-select-data-dir-'):
            settings[config_set]['DataDirectory'] = sg.popup_get_folder('Select the data directory')
            continue

        if event in ('--popup-select-config--'):
            configs = [key for key in settings.get_dict().keys() if key != '-Main-']
            config_set_layout = [[sg.Text("Select Configuration Set:")],
                                 [sg.Combo(configs, default_value=config_set, key='-config_set-')],
                                 [sg.Button('Select', key='-select-config-', button_color=('white','blue'))]
                                ]
            popup_window = sg.Window('Select', config_set_layout)
            config_events, config_values = popup_window.read()
            popup_window.close()
            settings['-Main-']['SelectedConfig'] = config_values['-config_set-']
            continue

        if event in ('-popup-rename-config-'):
            new_set_name = sg.popup_get_text('Enter the  new name of the new configuration set')
            if new_set_name in (None, ''):
                continue
            if not new_set_name.isprintable():
                sg.popup('Configuration set name must be printable', title='Error')
                continue
            # Copy current settings to a new config set
            for key in settings_keys:
                if key == 'MessageDisplayFilters':
                    settings[new_set_name][key] = NormalizeMessageDisplayFilters(settings[config_set].get(key, {}))
                else:
                    settings[new_set_name][key] = settings[config_set].get(key, None)
            # delete the old config set
            try:
                settings.delete_section(config_set)
            except KeyError:
                pass
            settings['-Main-']['SelectedConfig'] = new_set_name
            continue

        if event in ('-popup-new-config-'):
            new_config_set = sg.popup_get_text('Enter the name of the new configuration set')
            if new_config_set in (None, ''):
                continue
            if not new_config_set.isprintable():
                sg.popup('Configuration set name must be printable', title='Error')
                continue
            settings['-Main-']['SelectedConfig'] = new_config_set
            # Copy current settings to new config set
            for key in settings_keys:
                if key == 'MessageDisplayFilters':
                    settings[new_config_set][key] = NormalizeMessageDisplayFilters(settings[config_set].get(key, {}))
                else:
                    settings[new_config_set][key] = settings[config_set].get(key, None)
            continue

        if event in ('-popup-delete-config-'):
            popup_layout = [[sg.Text("Do you want to delete the configuration set: " + config_set + "?")],
                                 [sg.Button('Yes', key='-delete-yes-', button_color=('white','blue')),
                                  sg.Button('No', key='-delete-no-', button_color=('white','red'))]
                                ]
            popup_window = sg.Window('Select', popup_layout)
            config_events, config_values = popup_window.read()
            popup_window.close()
            if config_events == '-delete-yes-':
                configs = [key for key in settings.get_dict().keys() if key != '-Main-']
                if len(configs) > 1:
                    try:
                        settings.delete_section(config_set)
                    except KeyError:
                        pass
                    settings['-Main-']['SelectedConfig'] = configs[0]
                else:
                    sg.popup('Cannot delete the last configuration set', title='Error')
            continue

        # Process close and exit events
        if event in (None, '-exit-'):
            CloseAndExit()

        # Save settings which don't get saved automagically
        instrument = [i for i in instruments if values[i] == True]
        if instrument:
            instrument = instrument[0]
            settings[config_set]['Instrument'] = instrument

        settings[config_set]['AutoAck'] = values['-auto-ack-']
        settings[config_set]['AutoGPS'] = values['-auto-gps-']

        window_size = [i for i in window_sizes if values[i] == True]
        if window_size:
            window_size = window_size[0]
            settings[config_set]['WindowSize'] = window_size

        zephyr_port = [i for i in values if i.startswith('zephyr_') and values[i] == True]
        log_port = [i for i in values if i.startswith('log_') and values[i] == True]
        if zephyr_port and log_port and instrument and settings[config_set]['DataDirectory'] and settings[config_set]['WindowSize'] and settings[config_set]['AutoAck']:
            zephyr_port_name = zephyr_port[0].replace('zephyr_','')
            log_port_name = log_port[0].replace('log_','')
            # Verify that the zephyr and log ports are both accessible
            try:
                config['ZephyrPort'] = serial.Serial(port=zephyr_port_name, baudrate=115200, timeout=0.001)
                config['ZephyrPort'].reset_input_buffer()
                settings[config_set]['ZephyrPort'] = zephyr_port[0].replace('zephyr_','')
                settings[config_set]['LogPort'] = log_port[0].replace('log_','')
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
            sg.popup('Please specify all items', title='Error')

    # Return the selected parameters as a dictionary.
    config['Instrument'] = settings[config_set]['Instrument']
    config['AutoAck'] = settings[config_set]['AutoAck']
    config['AutoGPS'] = settings[config_set]['AutoGPS']
    config['WindowParams'] = window_params[window_size]
    config['DataDirectory'] = settings[config_set]['DataDirectory']
    config['ConfigSet'] = config_set
    config['MessageDisplayFilters'] = msg_display_filters

    # Print the selected parameters to the debug window.
    sg.Print("Instrument:", config['Instrument'])
    sg.Print("Zephyr Port:", config['ZephyrPort'])
    sg.Print("Log Port:", config['LogPort'])
    sg.Print("AutoAck:", config['AutoAck'])

    return config

def MainWindow(
    config: dict, 
    logport: serial.Serial, 
    zephyrport: serial.Serial, 
    cmd_fname: str, 
    xmlqueue: queue.Queue
) -> None:
    """
    Main window for the OBC simulator.
    This function creates the main window for the OBC simulator application. The window includes 
    control buttons at the top, two columns for displaying log messages and Zephyr messages,
    and a row at the bottom for displaying configuration settings and file paths.

    Args:
        config (dict): Configuration dictionary containing various settings for the simulator.
        logport (serial.Serial): Serial port object for logging messages.
        zephyrport (serial.Serial): Serial port object for Zephyr messages.
        cmd_fname (str): Filename for command file.
        xmlqueue (queue.Queue): Queue for XML messages.
    Returns:
        None
    """

    global main_window
    global log_port
    global zephyr_port
    global instrument
    global cmd_filename
    global xml_queue
    global message_display_filters
    global active_config_set

    instrument = config['Instrument']
    log_port = logport
    zephyr_port = zephyrport
    cmd_filename = cmd_fname
    xml_queue = xmlqueue
    active_config_set = config['ConfigSet']
    message_display_filters = NormalizeMessageDisplayFilters(config.get('MessageDisplayFilters', {}))

    sg.set_options(font = ("Monaco", config['WindowParams']['font_size']))
    w = config['WindowParams']['width']
    h = config['WindowParams']['height']
    b_size = button_sizes[window_size]
    # Command buttons and config values at the top of the window
    button_row = []

    # Instrument modes
    for b,t in ZephyrInstModes:
        button_row.append(sg.Button(b, size=b_size, button_color=('black','lightblue'),tooltip=t))

    # Zephyr msgs which carry parameters
    button_row.append(sg.Text(' '))
    button_row.append(sg.Button('TC', key='TC', size=b_size, button_color=('black','green'), tooltip='Send Telecommand', bind_return_key=True))
    button_row.append(sg.InputText('', key='-tc-text-', size=b_size, text_color='black', background_color='white', tooltip='TC Text, semicolon will be appended'))

    button_row.append(sg.Text(' '))
    button_row.append(sg.Button('GPS', key='GPS', size=b_size, button_color=('black','green'), tooltip='Send GPS'))
    button_row.append(sg.InputText('120.0', key='-gps-text-', size=b_size, text_color='black', background_color='white', tooltip='GPS SZA value'))

    # Zephyr msgs with no parameters
    button_row.append(sg.Text(' '))
    for b, t in ZephyrMessagesNoParams:
        button_row.append(sg.Button(b, size=b_size, tooltip=t))

    # Suspend and Exit buttons
    button_row.append(sg.Text(' '))
    button_row.append(sg.Button('Suspend', key='-suspend-', size=(8,1), button_color=('white','orange'), tooltip='Suspend/Resume serial ports'))
    button_row.append(sg.Button('Exit', key='-exit-', size=(8,1), button_color=('white','red'), tooltip='Exit the application'))

    # Configuration settings and file paths
    config_set_text = sg.Text("Configuration set:" + config['ConfigSet'])
    if config['SharedPorts']:
        log_port_text = sg.Text("Log port:" + zephyr_port.name)
    else:
        log_port_text = sg.Text("Log port:" + config['LogPort'].name)
    zephyr_port_text = sg.Text("Zephyr port:" + config['ZephyrPort'].name)
    auto_ack_text = sg.Text("AutoAck:" + str(config['AutoAck']))
    auto_gps_text = sg.Text("AutoGPS:" + str(config['AutoGPS']))

    config_row = []
    config_row.append(config_set_text)
    config_row.append(log_port_text)
    config_row.append(zephyr_port_text)
    config_row.append(auto_ack_text)
    config_row.append(auto_gps_text)
    files_row = []
    files_row.append(sg.Text("TM directory"))
    files_row.append(sg.InputText(' ', key='-tm_directory-', readonly=True, size=(80,1)))
    files_row.append(sg.Button('Copy', key='-copy-tm-dir-', size=b_size, button_color=('white','blue'), tooltip='Copy TM directory to clipboard'))

    display_filter_row = [sg.Button('All', key=display_all_toggle_key, size=b_size, button_color=('black', 'lightgray'), tooltip='Toggle all message display filters')]
    for msg_type in message_display_types:
        if msg_type in ('IMAck', 'IMR', 'TMAck', 'TCAck'):
            display_filter_row.append(sg.Button(msg_type, key=display_toggle_keys[msg_type], size=b_size, button_color=('white', 'black')))
        elif msg_type in ('GPS', 'TC', 'IM'):
            display_filter_row.append(sg.Button(msg_type, key=display_toggle_keys[msg_type], size=b_size, button_color=('white', 'blue')))
        else:
            display_filter_row.append(sg.Button(msg_type, key=display_toggle_keys[msg_type], size=b_size, button_color=('black', 'green')))

    display_filter_box = [
        sg.Column(
            [
                [sg.Text('Messages to Display')],
                display_filter_row
            ],
            pad=((6, 6), (4, 6))
        )
    ]

    widgets = [
        button_row,
        display_filter_box,
        [sg.Column([[sg.Text('StratoCore Log Messages')], [sg.MLine(key='-log_window-'+sg.WRITE_ONLY_KEY, size=(w/4,h))]]),
         sg.Column([[sg.Text(f'Messages TO/FROM {instrument}')], [sg.MLine(key='-zephyr_window-'+sg.WRITE_ONLY_KEY, size=(3*w/4,h))]])],
        config_row,
        files_row
    ]
    # Create the main window with the specified layout
    # If an icon file exists, use it; otherwise, create the window without an icon
    if os.path.exists('./icon.ico'):
        main_window = sg.Window(title=instrument, layout=widgets, icon=r'./icon.ico', finalize=True)
    else:
        main_window = sg.Window(title=instrument, layout=widgets, finalize=True)
    UpdateDisplayFilterButtons()

def AddMsgToLogDisplay(message: str) -> None:
    """
    Add a message to the log window.
    If the message contains 'ERR: ', the text color is set to red.
    Args:
        message (str): The message to be added to the log window.
    Returns:
        None
    """
    global main_window
    global log_line_count

    if log_line_count > MAXLOGLINES:
        log_lines = main_window['-log_window-'+sg.WRITE_ONLY_KEY].get().split('\n')
        log_lines = log_lines[-KEEPLOGLINES:]
        main_window['-log_window-'+sg.WRITE_ONLY_KEY].update(value='\n'.join(log_lines))
        log_line_count = KEEPLOGLINES

    log_line_count += 1

    message = message.strip()

    if -1 != message.find('ERR: '):
        main_window['-log_window-'+sg.WRITE_ONLY_KEY].print(message, text_color='red', end="\n")
    else:
        main_window['-log_window-'+sg.WRITE_ONLY_KEY].print(message, end="\n")

def AddMsgToZephyrDisplay(message: str) -> None:
    """
    Add a message to the Zephyr window with color coding based on message type.
    Parameters:
    message (str): The message to be added to the Zephyr window. The color of the message
                   is determined by its content:
                   - Blue for messages containing '(TO)'
                   - Red for messages containing 'TM' and 'CRIT'
                   - Orange for messages containing 'TM' and 'WARN'
                   - Green for messages containing 'TM'
                   - Default color for all other messages
    Returns:
    None
    """
    global main_window

    if not ShouldDisplayMessage(message):
        return

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
    """
    Adds a debug message to the output.
    Parameters:
    message (str): The debug message to be printed.
    error (bool): If True, the message is printed with a red background to indicate an error. Defaults to False.
    Returns:
    None
    """
    if not error:
        sg.Print(message)
    else:
        sg.Print(message, background_color='red')

def PollWindowEvents() -> None:
    """
    Poll the main window for events.
    Global Variables:
    - main_window: The main window object.
    - serial_suspended: A boolean indicating if the serial connection is suspended.
    Returns: None
    """
    global main_window, serial_suspended

    main_window_event, _ = main_window.read(timeout=10)

    if main_window_event in (None, '-exit-'):
        CloseAndExit()

    if main_window_event in ('-suspend-'):
        # toggle the suspend state
        SerialSuspend()
        if serial_suspended:
            main_window["-suspend-"].update('Resume', button_color=('white','blue'))
        else:
            main_window["-suspend-"].update('Suspend', button_color=('white','orange'))

    if serial_suspended:
        return
    
    if main_window_event in ['-copy-tm-dir-']:
        pyperclip.copy(main_window['-tm_directory-'].get())

    if main_window_event == display_all_toggle_key:
        ToggleAllMessageDisplayFilters()
        return

    if main_window_event in display_toggle_keys.values():
        for msg_type, key in display_toggle_keys.items():
            if main_window_event == key:
                ToggleMessageDisplayFilter(msg_type)
                return

    if main_window_event in [mode[0] for mode in ZephyrInstModes]:
        im_msg = OBC_Sim_Generic.sendIM(instrument, main_window_event, cmd_filename, zephyr_port)
        AddMsgToXmlQueue(im_msg)

    if main_window_event == 'TC':
        TCMessage()

    if main_window_event == 'GPS':
        GPSMessage()

    if main_window_event == 'SW':
        SWMessage()
    
    if main_window_event == 'SAck':
        SAckMessage()

    if main_window_event == 'RAAck':
        RAAckMessage()

    if main_window_event == 'TMAck':
        TMAckMessage()

    return

def TCMessage() -> None:
    global main_window
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '
    tc_text = main_window['-tc-text-'].get() + ';'
    if tc_text == ';':
        sg.popup('TC text must not be empty', non_blocking=True)
    else:
        sg.Print(timestring + "Sending TC:", tc_text)
        msg = OBC_Sim_Generic.sendTC(instrument, tc_text, cmd_filename, zephyr_port)
        AddMsgToXmlQueue(msg)

def GPSMessage() -> None:
    global main_window
    sza_text = main_window['-gps-text-'].get()
    sza = None
    try:
        sza = float(sza_text)
        if sza > 180 or sza < 0:
            sg.popup('SZA must be between 0 and 180', non_blocking=True)
    except:
        sg.popup('SZA must be a float', non_blocking=True)
    if sza != None:  
        time, millis = OBC_Sim_Generic.GetTime()
        timestring = '[' + time + '.' + millis + '] '
        sg.Print(timestring + "Sending GPS, SZA =", str(sza))
        msg = OBC_Sim_Generic.sendGPS(sza, cmd_filename, zephyr_port)
        AddMsgToXmlQueue(msg)

def SWMessage() -> None:
    """
    Sends a shutdown warning message.
    This function retrieves the current time and formats it into a string.
    It then prints a message indicating that a shutdown warning is being sent,
    and sends the shutdown warning using the OBC_Sim_Generic module.
    Returns:
        None
    """

    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sending shutdown warning")
    OBC_Sim_Generic.sendSW(instrument, cmd_filename, zephyr_port)

def SAckMessage() -> None:
    """
    Sends a safety acknowledgment message.
    This function retrieves the current time and formats it into a string. It then prints
    a message indicating that a safety acknowledgment is being sent. The function sends 
    the safety acknowledgment message using the `OBC_Sim_Generic.sendSAck` method and adds the message to a queue.
    Returns:
        None
    """
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sending safety ack")
    msg = OBC_Sim_Generic.sendSAck(instrument, 'ACK', cmd_filename, zephyr_port)
    AddMsgToXmlQueue(msg)

def RAAckMessage() -> None:
    """
    Sends an RA acknowledgment message and logs the event with a timestamp.
    This function retrieves the current time, formats it into a string, and logs
    the sending of an RA acknowledgment message. It then sends the RA acknowledgment
    message using the `OBC_Sim_Generic.sendRAAck` function and places the message
    into a queue.
    Returns:
        None
    """
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sent RAAck")
    msg = OBC_Sim_Generic.sendRAAck(instrument, 'ACK', cmd_filename, zephyr_port)
    AddMsgToXmlQueue(msg)

def TMAckMessage() -> None:
    """
    Sends a telemetry acknowledgment message.
    Returns:
        None
    """
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sending TM ack")
    msg = OBC_Sim_Generic.sendTMAck(instrument, 'ACK', cmd_filename, zephyr_port)
    AddMsgToXmlQueue(msg)

def CloseAndExit() -> None:
    """
    """
    global main_window
    if main_window != None:
        main_window.close()
    os._exit(0)

def SerialSuspend() -> None:
    """
    Suspend or resume the serial ports based on the current state.
    This function toggles the state of the serial ports. If the serial ports
    are currently active, it will close them and set the `serial_suspended`
    flag to True. If the serial ports are currently suspended, it will open
    them and set the `serial_suspended` flag to False.
    Globals:
        serial_suspended (bool): A flag indicating whether the serial ports
                                 are currently suspended.
        log_port (serial.Serial): The serial port used for logging.
        zephyr_port (serial.Serial): The main serial port used for communication.
    Returns:
        None
    """
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

def AddMsgToXmlQueue(msg: str) -> None:
    """
    Adds a message to the global XML queue with a timestamp.
    This function takes a string message, adds XML tags to it to make it XML parsable,
    and then puts it into the global `xml_queue` with a timestamp.
    Args:
        msg (str): The message to be added to the queue.
    Returns:
        None
    """
    global xml_queue
    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    # Add tags to make the message XML parsable
    newmsg = '<XMLTOKEN>' + msg + '</XMLTOKEN>'
    dict = xmltodict.parse(newmsg)
    xml_queue.put(f'{timestring}  (TO) {dict["XMLTOKEN"]}\n')  

def SetTmDir(filename: str) -> None:
    global main_window
    main_window['-tm_directory-'].update(filename)

def MessageMatchesType(message: str, msg_type: str) -> bool:
    if f"'{msg_type}':" in message:
        return True
    if f'"{msg_type}":' in message:
        return True
    if f'<{msg_type}>' in message:
        return True
    return False

def ShouldDisplayMessage(message: str) -> bool:
    matched_type = False
    for msg_type in message_display_types:
        if MessageMatchesType(message, msg_type):
            matched_type = True
            if not message_display_filters[msg_type]:
                return False
    if matched_type:
        return True
    return True

def GetDisplayButtonColor(msg_type: str, enabled: bool) -> tuple:
    if not enabled:
        return ('white', 'gray')
    if msg_type in ('IMAck', 'IMR', 'TMAck', 'TCAck'):
        return ('white', 'black')
    if msg_type in ('GPS', 'TC', 'IM'):
        return ('white', 'blue')
    return ('black', 'green')

def UpdateDisplayFilterButtons() -> None:
    global main_window
    if not main_window:
        return
    for msg_type in message_display_types:
        main_window[display_toggle_keys[msg_type]].update(button_color=GetDisplayButtonColor(msg_type, message_display_filters[msg_type]))
    if all(message_display_filters.values()):
        main_window[display_all_toggle_key].update(button_color=('black', 'green'))
    elif any(message_display_filters.values()):
        main_window[display_all_toggle_key].update(button_color=('black', 'orange'))
    else:
        main_window[display_all_toggle_key].update(button_color=('white', 'gray'))

def ToggleMessageDisplayFilter(msg_type: str) -> None:
    message_display_filters[msg_type] = not message_display_filters[msg_type]
    SaveMessageDisplayFiltersToSettings()
    UpdateDisplayFilterButtons()

def ToggleAllMessageDisplayFilters() -> None:
    target_state = not all(message_display_filters.values())
    for msg_type in message_display_types:
        message_display_filters[msg_type] = target_state
    SaveMessageDisplayFiltersToSettings()
    UpdateDisplayFilterButtons()

def SaveMessageDisplayFiltersToSettings() -> None:
    global active_config_set
    if not active_config_set:
        return
    settings = sg.UserSettings(filename='OBC_Simulator.ini', use_config_file=True, autosave=True, path=os.path.abspath(os.path.expanduser("~/")))
    settings[active_config_set]['MessageDisplayFilters'] = NormalizeMessageDisplayFilters(message_display_filters)
