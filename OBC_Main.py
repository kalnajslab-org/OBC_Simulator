#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
This script provides a console to simulate the OBC over serial

Author: Alex St. Clair
Created: May 2020
'''

# modules
import OBC_GUI, OBC_Parser, OBC_Sim_Generic
import argparse

# libraries
import threading, serial, queue, time, datetime, os

# globals
instrument = ''
inst_filename = ''
xml_filename = ''
cmd_filename = ''
tm_dir = ''


def FileSetup():
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


def parse_args():
    parser = argparse.ArgumentParser(
        prog='OBC_Simulator',
        description='Simulates the Zephyr communications with a StratoCore system.',
        epilog='The Zephyr and Log ports may be separate or shared, depending on the StratoCore system configuration.')
    args = parser.parse_args()
    return args

def main():
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
    port_name = config['LogPort']
    auto_ack = config['AutoAck']

    # attempt to open the serial port
    try:
        port = serial.Serial(port_name, 115200)
    except Exception as e:
        print("Error opening serial port", e)
        exit()

    # set up the files and structure
    FileSetup()

    # start the instrument output window
    OBC_GUI.MainWindow(config, sport=port, cmd_fname=cmd_filename)

    # start listening for instrument messages over serial
    threading.Thread(target=OBC_Parser.ReadInstrument,
        args=(inst_queue,xml_queue,port,inst_filename,xml_filename,tm_dir,instrument,cmd_queue)).start()

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
                    OBC_Sim_Generic.sendTMAck(instrument, 'ACK', cmd_filename, port)
                    OBC_GUI.AddDebugMsg(timestring + 'Sent TMAck')
                elif 'SAck' == cmd:
                    OBC_Sim_Generic.sendSAck(config['inst'], 'ACK', cmd_filename, port)
                    OBC_GUI.AddDebugMsg(timestring + 'Sent SAck')
                elif 'RAAck' == cmd:
                    OBC_Sim_Generic.sendRAAck(instrument, 'ACK', cmd_filename, port)
                    OBC_GUI.AddDebugMsg(timestring + 'Sent RAAck')
                else:
                    OBC_GUI.AddDebugMsg('Unknown command', True)



if (__name__ == '__main__'):
    main()