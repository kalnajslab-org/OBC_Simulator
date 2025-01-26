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
import OBC_GUI, OBC_Parser, OBC_Sim_Generic
import argparse

# libraries
import threading, serial, queue, os

# globals
instrument = ''
inst_filename = ''
xml_filename = ''
cmd_filename = ''
tm_dir = ''

def FileSetup() -> None:
    global inst_filename, xml_filename, cmd_filename, tm_dir

    # create date and time strings for file creation
    date, start_time, start_time_file, _ = OBC_Parser.GetDateTime()

    # create the output directory structure for the session
    if not os.path.exists("sessions"):
        os.mkdir("sessions")
    output_dir = "sessions/" + instrument + "_" + date + "_" + start_time_file
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
    FileSetup()

    # start the main output window
    OBC_GUI.MainWindow(config, logport=config['LogPort'], zephyrport=config['ZephyrPort'], cmd_fname=cmd_filename)

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
        cmd_queue)
    threading.Thread(target=OBC_Parser.ReadInstrument,args=obc_parser_args).start()

    while True:
        # run command GUI
        OBC_GUI.RunCommands()

        # handle instrument queues
        if not inst_queue.empty():
            OBC_GUI.AddLogMsg(inst_queue.get())
        if not xml_queue.empty():
            OBC_GUI.AddZephyrMsg(xml_queue.get())
        if not cmd_queue.empty():
            cmd = cmd_queue.get()
            if auto_ack:
                time, millis = OBC_Sim_Generic.GetTime()
                timestring = '[' + time + '.' + millis + '] '
                if 'TMAck' == cmd:
                    OBC_Sim_Generic.sendTMAck(instrument, 'ACK', cmd_filename, config['ZephyrPort'])
                    OBC_GUI.AddDebugMsg(timestring + 'Sent TMAck')
                elif 'SAck' == cmd:
                    OBC_Sim_Generic.sendSAck(config['inst'], 'ACK', cmd_filename, config['ZephyrPort'])
                    OBC_GUI.AddDebugMsg(timestring + 'Sent SAck')
                elif 'RAAck' == cmd:
                    OBC_Sim_Generic.sendRAAck(instrument, 'ACK', cmd_filename, config['ZephyrPort'])
                    OBC_GUI.AddDebugMsg(timestring + 'Sent RAAck')
                else:
                    OBC_GUI.AddDebugMsg('Unknown command', True)

if (__name__ == '__main__'):
    main()