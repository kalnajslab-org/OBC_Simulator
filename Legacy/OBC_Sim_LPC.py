#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 14 15:14:45 2019

Quick program to simulate the Zephyr OBC for repetative testing.

The test cycle is defined in main.  All comms are logged to the log file. 

Command line usage:
    python3 OBC_sim.py /dev/tty.usbserial OBC_Sim_Log.txt

@author: kalnajs
"""
LogFile = 'OBC_LPC_test.txt'


import time
import serial # import Serial Library
import xml.etree.ElementTree as ET #import XML library
from xml.dom import minidom
from datetime import datetime
from time import sleep


#Define the serial port
#port = /dev/tty.usbserial
#
#s = serial.Serial(port)
#s.reset_input_buffer()

def crc16_ccitt(crc, data):
    msb = crc >> 8
    lsb = crc & 255

    for c in data:
        x = c ^ msb
        x ^= (x >> 4)
        msb = (lsb ^ (x >> 3) ^ (x << 4)) & 255
        lsb = (x ^ (x << 5)) & 255
    return (msb << 8) + lsb

def AddCRC(InputXMLString):
    crc = crc16_ccitt(0x1021,InputXMLString.encode("ASCII"))
    
    return InputXMLString + '<CRC>' + str(crc) + '</CRC>\n'

def prettify(xmlStr):
    INDENT = "\t"
    rough_string = ET.tostring(xmlStr)
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent=INDENT)


def sendIM(Instrument,Mode, port):
    XML_IM = ET.Element('IM')
    
    msg_id = ET.SubElement(XML_IM,'Msg')
    msg_id.text = '123'
    
    inst_id = ET.SubElement(XML_IM,'Inst')
    inst_id.text = Instrument
    
    mode = ET.SubElement(XML_IM,'Mode')
    mode.text = Mode

    pretty_string = prettify(XML_IM)
    without_first_line = pretty_string.split("\n",1)[1];
    
    output = AddCRC(without_first_line)
    
    print(output)
   
    port.write(output.encode()) 
    	
    with open(LogFile, mode='a') as output_file:
        output_file.write("Sending IM\n")
    
    print("Sending IM")
    return output

def sendGPS(zenith, time_in, port):
    
    XML_GPS = ET.Element('GPS')
    msg_id = ET.SubElement(XML_GPS,'Msg')
    msg_id.text = '123'
    
    date = ET.SubElement(XML_GPS,'Date')
    date.text = datetime.today().strftime('%Y/%m/%d')
    

    time = ET.SubElement(XML_GPS,'Time')
    
    if time_in == 'clock':
        time.text = datetime.today().strftime('%H:%M:%S')
    else:
        time.text = time_in
    
    lon = ET.SubElement(XML_GPS,'Lon')
    lon.text = '-105.000000'
    
    lat = ET.SubElement(XML_GPS,'Lat')
    lat.text = '40.000000'
    
    alt = ET.SubElement(XML_GPS,'Alt')
    alt.text = '1620.3'

    sza = ET.SubElement(XML_GPS,'SZA')
    sza.text = str(zenith)   
    
    quality = ET.SubElement(XML_GPS,'Quality')
    quality.text = '3'
    
    pretty_string = prettify(XML_GPS)
    without_first_line = pretty_string.split("\n",1)[1];
    output = AddCRC(without_first_line)
    
    port.write(output.encode()) 
    	
    with open(LogFile, mode='a') as output_file:
        output_file.write("Sending GPS, SZA = " + str(zenith) + "\n")
    
    print(output)
    return output

def sendTC(instrument, command, port):

    XML_TC = ET.Element('TC')
    
    msg_id = ET.SubElement(XML_TC,'Msg')
    msg_id.text = '123'
    
    inst_id = ET.SubElement(XML_TC,'Inst')
    inst_id.text = instrument
    
    length = ET.SubElement(XML_TC,'Length')
    length.text = str(len(command))
    
    pretty_string = prettify(XML_TC)
    without_first_line = pretty_string.split("\n",1)[1];
    
    crc = crc16_ccitt(0x1021,command.encode("ASCII"))
    
    command = 'START' + command
    output = AddCRC(without_first_line)
    output = output + command
    

    port.write(output.encode()) 
    port.write(crc.to_bytes(2,byteorder='big',signed=False))
    port.write(b'END')

    	
    with open(LogFile, mode='a') as output_file:
        output_file.write("Sending TC: " + command + "\n")
    
    print("Sending TC: " + command)
    return output
    
def sendRAAck(ACK, port):
    
    XML_RAAck = ET.Element('RAAck')
    
    msg_id = ET.SubElement(XML_RAAck,'Msg')
    msg_id.text = '123'
    
    inst_id = ET.SubElement(XML_RAAck,'Inst')
    inst_id.text = 'RACHUTS'
    
    ack = ET.SubElement(XML_RAAck, 'Ack')
    ack.text = ACK
    
    pretty_string = prettify(XML_RAAck)
    without_first_line = pretty_string.split("\n",1)[1];
    output = AddCRC(without_first_line)

    port.write(output.encode()) 
    	
    with open(LogFile, mode='a') as output_file:
        output_file.write("Sending RAAck\n")
    
    print("Seding RAAck")
    return output

def sendTMAck(instrument,ACK, port):
    XML_TMAck = ET.Element('TMAck')
    
    msg_id = ET.SubElement(XML_TMAck,'Msg')
    msg_id.text = '123'
    
    inst_id = ET.SubElement(XML_TMAck,'Inst')
    inst_id.text = instrument
    
    ack = ET.SubElement(XML_TMAck, 'Ack')
    ack.text = ACK
    
    pretty_string = prettify(XML_TMAck)
    without_first_line = pretty_string.split("\n",1)[1];
    output = AddCRC(without_first_line)
   
    port.write(output.encode()) 
    
    print("Sending TM Ack")
    
    return output

def listenFor(instrument,port):
    
    print('Listening')
    inBytes = port.read_until(b'</CRC>', 9000) #get the XML part
    inStr = inBytes.decode('utf-8',errors='ignore')
    
    if 'TM' in inStr:
        TMBytes = port.read_until(b'END', 9000) #if it is a TM listen for binary
        filename = instrument + time.strftime("%Y%m%d-%H%M%S") + '.TM'
        print('Received TM, Saving to '+filename)
        with open(filename, mode='ab') as output_file:
             output_file.write(inBytes)
             output_file.write(TMBytes)
        
        sendTMAck(instrument,'ACK',port)
        return 'TM'
        
    if 'RA' in inStr:
        return 'RA'
    
    if 'TCAck' in inStr:
        return 'TCAck'
    
    if 'IMR' in inStr:
        sendIM('LPC','FL',port)
        return 'IMR'
    
    if 'IMAck' in inStr:
        return 'IMAck'

    else:
        return False

def main():
    
    
    port = '/dev/tty.usbserial'
    ser = serial.Serial(port,115200,timeout=60)
    
    sleep(3)
    
    sendGPS(40,'11:59:00', ser)
    
    for i in range(10000):
        response = listenFor('LPC',ser)
        print(response)
        #sendGPS(40,'clock',ser)
        
    
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    
    sleep(1)
    ser.close()
    
    
    
    
        
if (__name__ == '__main__'): 
    main()          

        

  


        