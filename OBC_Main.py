#!/usr/bin/env python3
"""
OBC_Main.py
This script simulates the Zephyr communications with a StratoCore system. It sets up the necessary file structure, 
opens serial ports for communication, and starts the main output window for the OBC simulator. It also listens for 
instrument messages over serial and handles command queues.
Modules:
    OBC_GUI
    OBC_Parser
    OBC_Sim_Generic
    argparse
    threading
    serial
    queue
    os
Functions:
    FileSetup() -> None:
        Sets up the file structure and creates necessary files for the session.
    parse_args() -> argparse.Namespace:
        Parses command-line arguments.
    main() -> None:
        Main function that initializes the OBC simulator, sets up file structure, opens serial ports, and starts 
        the main output window. It also listens for instrument messages and handles command queues.
"""
# -*- coding: utf-8 -*-

# modules
import OBC_GUI
import OBC_Parser
import OBC_Sim_Generic
import os
import argparse
import xmltodict
import datetime

# libraries
import threading, serial, queue, os

# globals
instrument = ''
inst_filename = ''
xml_filename = ''
cmd_filename = ''
tm_dir = ''

def FileSetup(config:dict) -> None:
    global inst_filename
    global xml_filename
    global cmd_filename
    global tm_dir

    # create date and time strings for file creation
    date, start_time, start_time_file, _ = OBC_Parser.GetDateTime()

    # create the output directory structure for the session
    data_dir = config['DataDirectory']+'/'
    if not os.path.exists(data_dir):
        os.mkdir(data_dir)
    output_dir = data_dir + instrument + "_" + date + "_" + start_time_file
    os.mkdir(output_dir)

    # create a directory for individual TM messages
    tm_dir = output_dir + '/TM'
    os.mkdir(tm_dir)

    # create instrument output and command filenames
    inst_filename = output_dir + "/" + instrument + "_DBG_" + date + "_" + start_time_file + ".txt"
    xml_filename  = output_dir + "/" + instrument + "_XML_" + date + "_" + start_time_file + ".txt"
    cmd_filename  = output_dir + "/" + instrument + "_CMD_" + date + "_" + start_time_file + ".txt"

    # create the files
    with open(inst_filename, "w") as inst:
        inst.write(instrument + " Debug Messages: " + date + " at " + start_time + "\n\n")

    with open(xml_filename, "w") as inst:
        inst.write(instrument + " XML Messages: " + date + " at " + start_time + "\n\n")

    with open(cmd_filename, "w") as inst:
        inst.write(instrument + " Commands: " + date + " at " + start_time + "\n\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='OBC_Simulator',
        description='Simulates the Zephyr communications with a StratoCore system.',
        epilog='The Zephyr and Log ports may be separate or shared, depending on the StratoCore system configuration.')
    args = parser.parse_args()
    return args

def msg_to_queue(q: queue.Queue, timestring: str, msg: str) -> None:
    global xml_queue
    if msg == None:
        return
    # Add tags to make the message XML parsable
    newmsg = '<XMLTOKEN>' + msg + '</XMLTOKEN>'
    dict = xmltodict.parse(newmsg)
    q.put(f'{timestring}  (TO) {dict["XMLTOKEN"]}\n')  

def main() -> None:
    global instrument

    args = parse_args()

    # create queues for instrument messages
    inst_queue = queue.Queue()
    xml_queue = queue.Queue()
    cmd_queue = queue.Queue()

    # get configuration
    config = OBC_GUI.ConfigWindow()

    # set global variables
    instrument = config['Instrument']
    auto_ack = config['AutoAck']

    # set up the files and structure
    FileSetup(config)

    # start the main output window
    OBC_GUI.MainWindow(config, logport=config['LogPort'], zephyrport=config['ZephyrPort'], cmd_fname=cmd_filename, xmlqueue=xml_queue)

    # Set the tm filename
    OBC_GUI.SetTmDir(tm_dir)

    # start listening for instrument messages over serial
    obc_parser_args=(
        inst_queue,
        xml_queue,
        config['LogPort'],
        config['ZephyrPort'],
        inst_filename,
        xml_filename,
        tm_dir,
        instrument,
        cmd_queue,
        config)
    threading.Thread(target=OBC_Parser.ReadInstrument,args=obc_parser_args).start()

    # Wait 10 seconds before sending GPS messages
    last_gps_timestamp = datetime.datetime.now().timestamp() - 50
    # Perhaps this should be a configuration option
    sza = 120

    while True:
        # poll the GUI
        OBC_GUI.PollWindowEvents()

        current_time, millis = OBC_Sim_Generic.GetTime()
        timestring = '[' + current_time + '.' + millis + '] '

        # send GPS messages every 60 seconds
        now_timestamp = datetime.datetime.now().timestamp()
        if config["AutoGPS"] and now_timestamp - last_gps_timestamp >= 60:
            last_gps_timestamp = now_timestamp
            gps_msg = OBC_Sim_Generic.sendGPS(sza, cmd_filename, config['ZephyrPort'])
            msg_to_queue(xml_queue, timestring, gps_msg)

        # handle instrument queues
        if not inst_queue.empty():
            OBC_GUI.AddMsgToLogDisplay(inst_queue.get())
        if not xml_queue.empty():
            OBC_GUI.AddMsgToZephyrDisplay(xml_queue.get())
        if not cmd_queue.empty():
            cmd = cmd_queue.get()
            if auto_ack:
                if 'TMAck' == cmd:
                    msg = OBC_Sim_Generic.sendTMAck(instrument, 'ACK', cmd_filename, config['ZephyrPort'])
                    msg_to_queue(xml_queue, timestring, msg)
                    OBC_GUI.AddDebugMsg(timestring + 'Sent TMAck')
                elif 'SAck' == cmd:
                    msg = OBC_Sim_Generic.sendSAck(config['Instrument'], 'ACK', cmd_filename, config['ZephyrPort'])
                    msg_to_queue(xml_queue, timestring, msg)
                    OBC_GUI.AddDebugMsg(timestring + 'Sent SAck')
                elif 'RAAck' == cmd:
                    msg = OBC_Sim_Generic.sendRAAck(instrument, 'ACK', cmd_filename, config['ZephyrPort'])
                    msg_to_queue(xml_queue, timestring, msg)
                    OBC_GUI.AddDebugMsg(timestring + 'Sent RAAck')
                else:
                    OBC_GUI.AddDebugMsg('Unknown command', True)

if (__name__ == '__main__'):
    main()