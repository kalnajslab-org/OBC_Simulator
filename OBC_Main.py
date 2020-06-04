#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
This script provides a console to simulate the OBC over serial

Author: Alex St. Clair
Created: May 2020
'''

# modules
import OBC_GUI, OBC_Parser

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
    output_dir = "sessions/session_" + date + "_" + start_time_file
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


def main():
    global instrument

    # create queues for instrument messages
    inst_queue = queue.Queue()
    xml_queue = queue.Queue()

    # get basic information
    instrument, port_name = OBC_GUI.WelcomeWindow()

    # attempt to open the serial port
    try:
        port = serial.Serial(port_name, 115200)
    except:
        print("Error opening serial port")
        exit()

    # set up the files and structure
    FileSetup()

    # register globals with the GUI module
    OBC_GUI.cmd_filename = cmd_filename
    OBC_GUI.port = port
    OBC_GUI.instrument = instrument

    # start the instrument output window
    OBC_GUI.StartOutputWindow()

    # start listening for instrument messages over serial
    threading.Thread(target=OBC_Parser.ReadInstrument,
        args=(inst_queue,xml_queue,port,inst_filename,xml_filename,tm_dir,instrument,)).start()

    while True:
        # run command GUI
        OBC_GUI.RunCommands()

        # print instrument messages as they arrive
        if not inst_queue.empty():
            OBC_GUI.InstWindowPrint(inst_queue.get())
        if not xml_queue.empty():
            OBC_GUI.XMLWindowPrint(xml_queue.get())


if (__name__ == '__main__'):
    main()