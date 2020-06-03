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
cmd_filename = ''


def FileSetup():
    global inst_filename, cmd_filename

    # create dat and time strings
    current_datetime = datetime.datetime.now()
    date = str(current_datetime.date().strftime("%d-%b-%y"))
    start_time_file = str(current_datetime.time().strftime("%H-%M-%S"))
    start_time = str(current_datetime.time().strftime("%H:%M:%S"))

    # create the output directory for the session
    if not os.path.exists("sessions"):
        os.mkdir("sessions")
    output_dir = "sessions/session_" + date + "_" + start_time_file
    os.mkdir(output_dir)

    # create instrument and command filenames
    inst_filename = output_dir + "/" + instrument + "_" + date + "_" + start_time_file + ".txt"
    cmd_filename = output_dir + "/" + "Commands_" + date + "_" + start_time_file + ".txt"

    # create the files
    with open(inst_filename, "w") as inst:
        inst.write(instrument + " Output: " + date + " at " + start_time + "\n\n")

    with open(cmd_filename, "w") as inst:
        inst.write(instrument + " Commands: " + date + " at " + start_time + "\n\n")


def main():
    global instrument

    # create a queue for instrument serial messages
    inst_queue = queue.Queue()

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
    threading.Thread(target=OBC_Parser.ReadInstrument, args=(inst_queue,port,inst_filename)).start()

    while True:
        # run command GUI
        OBC_GUI.RunCommands()

        # print instrument messages as they arrive
        if not inst_queue.empty():
            OBC_GUI.OutputWindowPrint(inst_queue.get())


if (__name__ == '__main__'):
    main()