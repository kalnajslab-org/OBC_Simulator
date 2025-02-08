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
import sys
import queue
import serial
import serial.tools.list_ports
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
    ConfigSet(str): the name of the configuration set
    '''

    settings = sg.UserSettings(filename='OBC_Simulator.ini', use_config_file=True, autosave=True, path=os.path.abspath(os.path.expanduser("~/")))
    if not settings['-Main-']['SelectedConfig']:
        settings['-Main-']['SelectedConfig'] = 'NewSet' # default to the first configuration set

    # Create a list of settings keys. This will need to be updated if new settings are added.
    settings_keys = ['ZephyrPort', 'LogPort', 'Instrument', 'AutoAck', 'WindowSize', 'DataDirectory']

    # Loop until all parameters are specified
    config = {}
    config_values_validated = False
    while not config_values_validated:
        settings = sg.UserSettings(filename='OBC_Simulator.ini', use_config_file=True, path=os.path.abspath(os.path.expanduser("~/")))
        config_set = settings['-Main-'].get('SelectedConfig', '1')
        zephyr_port = settings[config_set].get('ZephyrPort', 'None')
        log_port = settings[config_set].get('LogPort', 'None')
        auto_ack = settings[config_set].get('AutoAck', True)

        instruments = ['RATS', 'LPC', 'RACHUTS', 'FLOATS']
        window_sizes = ['Small', 'Medium', 'Large']
        window_params = {'Small': {'font_size': 8, 'width': 100, 'height': 20},
                        'Medium': {'font_size': 10, 'width': 120, 'height': 30},
                        'Large': {'font_size': 12, 'width': 160, 'height': 40}} 

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

        # Create the layout for the configuration window
        layout = [
            [sg.Text('Settings file: ' + settings.full_filename)],
            [sg.Text(" ")],
            [sg.Text("Data Directory:"),
              sg.Text(settings[config_set].get('DataDirectory', os.getcwd()+'/')), 
              sg.Button('Select', key='-select-data-dir-', button_color=('white','blue'))],
            [sg.Text(" ")],
            [sg.Text("Configuration set:"), sg.Text(config_set),
              sg.Button('Select', key='-popup-select-config-', button_color=('white','blue')),
              sg.Button('Delete', key='-popup-delete-config-', button_color=('white','blue')),
              sg.Button('New', key='-popup-new-config-', button_color=('white','blue'))],
            [sg.Text(" ")],
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
                settings[new_config_set][key] = settings[config_set][key]
            continue

        # Process close and exit events
        if event in (None, '-exit-'):
            CloseAndExit()

        # Save settings which don't get saved automagically
        instrument = [i for i in instruments if values[i] == True]
        if instrument:
            instrument = instrument[0]
            settings[config_set]['Instrument'] = instrument

        settings[config_set]['AutoAck'] = values['ACK']

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
                if log_port_name != zephyr_port_name:
                    config['LogPort'] = serial.Serial(port=log_port_name, baudrate=115200, timeout=0.001)
                    config['LogPort'].reset_input_buffer()
                    config['SharedPorts'] = False
                    settings[config_set]['LogPort'] = log_port[0].replace('log_','')
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
    config['WindowParams'] = window_params[window_size]
    config['DataDirectory'] = settings[config_set]['DataDirectory']
    config['ConfigSet'] = config_set

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

    instrument = config['Instrument']
    log_port = logport
    zephyr_port = zephyrport
    cmd_filename = cmd_fname
    xml_queue = xmlqueue

    # Command buttons and config values at the top of the window
    button_row = [sg.Button(s, size=(6,1)) for s in ZephyrMessageTypes]
    button_row.append(sg.Button('Suspend', key='-suspend-', size=(8,1), button_color=('white','orange')))
    button_row.append(sg.Button('Exit', key='-exit-', size=(8,1), button_color=('white','red')))

    config_set_text = sg.Text("Configuration set: " + config['ConfigSet'])
    if config['SharedPorts']:
        log_port_text = sg.Text("Log port: " + zephyr_port.name)
    else:
        log_port_text = sg.Text("Log port: " + config['LogPort'].name)
    zephyr_port_text = sg.Text("Zephyr port: " + config['ZephyrPort'].name)
    auto_ack_text = sg.Text("AutoAck: " + str(config['AutoAck']))
    config_row = []
    config_row.append(config_set_text)
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
    """
    Add a message to the log window.
    If the message contains 'ERR: ', the text color is set to red.
    Args:
        message (str): The message to be added to the log window.
    Returns:
        None
    """

    global main_window

    if -1 != message.find('ERR: '):
        main_window['-log_window-'+sg.WRITE_ONLY_KEY].print(message, text_color='red', end="")
    else:
        main_window['-log_window-'+sg.WRITE_ONLY_KEY].print(message, end="")

def AddZephyrMsg(message: str) -> None:
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
    Poll the main and popup windows for events.
    This function checks for events in the main and popup windows. When an event is detected,
    it updates the global variables `current_action` and `new_window` to indicate the event
    and that it should be handled. If the main window event is 'Exit', the application will
    close. If the event is 'Suspend' or 'Resume', it toggles the suspend state of the serial
    connection and updates the button text and color accordingly.
    Global Variables:
    - popup_window: The popup window object.
    - main_window: The main window object.
    - current_action: The name of the detected event.
    - new_window: A boolean indicating if a new event should be handled.
    - serial_suspended: A boolean indicating if the serial connection is suspended.
    Returns:
    None
    """

    global popup_window, main_window, current_action, new_window

    popup_window_event = None
    if popup_window:
        popup_window_event, _ = popup_window.read(timeout=10)

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
    """
    Displays a popup window for selecting a mode from the available Zephyr instrument modes.
    This function creates a graphical user interface (GUI) popup window using the PySimpleGUI library.
    The window contains a list of buttons representing different modes and a cancel button.
    Global Variables:
    - popup_window: The window object for the popup.
    The function does not take any parameters and does not return any value.
    """

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
    """
    Handles the popup window for setting the mode of an instrument.
    This function reads events from the popup window with a timeout of 10 milliseconds.
    If the event is a timeout, it returns immediately. Otherwise, it closes the popup window,
    retrieves the current time, and logs the event. If the 'Cancel' event is not selected,
    it sends an instrument mode (IM) message and queues the message. Finally, it sets the
    current action to 'waiting' and flags that a new window should be created.
    Globals:
        popup_window: The current popup window instance.
        current_action: The current action being performed.
        new_window: Flag indicating whether a new window should be created.
    Events:
        '__TIMEOUT__': Indicates that the read operation timed out.
        'Cancel': Indicates that the cancel button was selected.
    Returns:
        None
    """


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
    """
    Displays a popup window for configuring GPS messages to the instrument.
    This function creates and shows a popup window using the PySimpleGUI library.
    The popup window allows the user to input a solar zenith angle (SZA) in degrees.
    It includes a text input field pre-filled with '120' and two buttons: 'Submit' and 'Cancel'.
    The 'Submit' button is styled with a blue background and white text, while the 'Cancel' button
    is styled with an orange background and white text.
    Returns:
        None
    """

    global popup_window

    gps_selector = [[sg.Text('Select a solar zenith angle (degrees)')],
                    [sg.InputText('120')],
                    [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
                     sg.Button('Cancel', size=(8,1), button_color=('white','orange'))]]

    # GUI GPS creator with SZA float validation
    popup_window = sg.Window('GPS Message Configurator', gps_selector)

def WaitGPSPopup() -> None:
    """
    Handles the GPS popup window interaction.
    This function reads events from the popup window with a timeout of 10 milliseconds.
    If the event is a timeout, it returns immediately. If the event is 'Submit', it
    validates the Solar Zenith Angle (SZA) input, ensuring it is a float between 0 and 180.
    If the validation fails, it shows an appropriate popup message and returns.
    Upon successful validation, it closes the popup window, retrieves the current time,
    and sends the GPS data with the specified SZA. It then prints a message indicating
    the GPS data has been sent and updates the current action to 'waiting'.
    Globals:
        popup_window: The current popup window instance.
        current_action: The current action state of the application.
        new_window: A flag indicating if a new window should be created.
    Raises:
        ValueError: If the SZA is not a float or is out of the valid range (0-180).
    """

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

def ShowTCPopup() -> None:
    """
    Display a popup window for telecommand input.
    This function creates and shows a popup window using the PySimpleGUI library.
    The popup window contains a text prompt, an input field for entering a telecommand,
    and two buttons: 'Submit' and 'Cancel'.
    The global variable 'popup_window' is used to store the reference to the created window.
    Returns:
        None
    """

    global popup_window

    tc_selector = [[sg.Text('Input a telecommand:')],
                    [sg.InputText('1;')],
                    [sg.Button('Submit', size=(8,1), button_color=('white','blue')),
                     sg.Button('Cancel', size=(8,1), button_color=('white','orange'))]]

    # GUI TC creator
    popup_window = sg.Window('TC Creator', tc_selector)

def WaitTCPopup() -> None:
    """
    Handles the TCP popup window events and processes the user input.
    This function reads events from the TCP popup window with a timeout of 10 milliseconds.
    If a timeout event occurs, the function returns immediately. Otherwise, it closes the
    popup window and processes the user input.
    The function performs the following actions:
    - Reads the current time and formats it as a string.
    - If the 'Submit' event is triggered, it sends a TC (telecommand) using the provided
      instrument, command filename, and zephyr port, and prints the action to the console.
    - Updates the current action to 'waiting' and sets the new_window flag to True.
    Global Variables:
    - popup_window: The current popup window instance.
    - current_action: The current action being performed.
    - new_window: A flag indicating if a new window should be created.
    Returns:
    - None
    """

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
    msg_to_queue(msg)

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
    msg_to_queue(msg)

def TMAckMessage() -> None:
    """
    Sends a telemetry acknowledgment message.
    This function retrieves the current time and formats it into a string.
    It then prints a message indicating that a telemetry acknowledgment is being sent.
    Finally, it sends the acknowledgment message using the OBC_Sim_Generic.sendTMAck function
    and queues the message for further processing.
    Returns:
        None
    """

    time, millis = OBC_Sim_Generic.GetTime()
    timestring = '[' + time + '.' + millis + '] '

    sg.Print(timestring + "Sending TM ack")
    msg = OBC_Sim_Generic.sendTMAck(instrument, 'ACK', cmd_filename, zephyr_port)
    msg_to_queue(msg)

def CloseAndExit() -> None:
    """
    Closes the main and popup windows if they are open, and then exits the application.
    This function checks if the global variables `main_window` and `popup_window` are not None.
    If they are not None, it closes them. Finally, it terminates the program with an exit code of 0.
    Returns:
        None
    """

    global main_window, popup_window

    if main_window != None:
        main_window.close()

    if popup_window != None:
        popup_window.close()
        popup_window = None

    os._exit(0)

def RunCommands() -> None:
    """
    Executes commands based on the current action and window state.
    This function checks the state of the `new_window` flag and the `current_action` variable
    to determine which command to execute. It handles different actions such as showing popups,
    sending messages, and polling window events.
    Global Variables:
    - new_window (bool): Indicates whether a new window should be created.
    - current_action (str): The current action to be executed.
    Actions:
    - 'waiting': Polls window events or sets the state to waiting.
    - 'IM': Shows or waits for the IM popup.
    - 'GPS': Shows or waits for the GPS popup.
    - 'SW': Sends the SW message and sets the state to waiting.
    - 'TC': Shows or waits for the TC popup.
    - 'SAck': Sends the SAck message and sets the state to waiting.
    - 'RAAck': Sends the RAAck message and sets the state to waiting.
    - 'TMAck': Sends the TMAck message and sets the state to waiting.
    - Any other action: Prints an unknown window request message and sets the state to waiting.
    Returns:
    None
    """

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

def SetTmDir(filename: str) -> None:
    global main_window
    main_window['-tm_directory-'].update(filename)