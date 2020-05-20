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
LogFile = 'OBC_RACHuTS_Auto_test_2.txt'


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
    
    print("Sending GPS, SZA = " + str(zenith) + " time =  "+ time.text+ "\n")	
    with open(LogFile, mode='a') as output_file:
        output_file.write("Sending GPS, SZA = " + str(zenith) + " time =  "+ time.text+ "\n")
    

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
    
    print("Sending RAAck")
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
    
    if '<TM>' in inStr:
        print(inStr)
        TMBytes = port.read_until(b'END', 9000) #if it is a TM listen for binary
        if 'TSEN:' in inStr:
            filename = 'RACHUTS_TSEN_TM/' + instrument + time.strftime("%Y%m%d-%H%M%S") + '.TM'
        if 'PU Profile Record:' in inStr:
            filename = 'RACHUTS_Profile_TM/' + instrument + time.strftime("%Y%m%d-%H%M%S") + '.TM'
        else:
            filename = 'RACHUTS_TM/' + instrument + time.strftime("%Y%m%d-%H%M%S") + '.TM'
            
        print('Received TM, Saving to '+filename)
        with open(filename, mode='ab') as output_file:
             output_file.write(inBytes)
             output_file.write(TMBytes)
        
        sendTMAck(instrument,'ACK',port)
        return 'TM'
        
    if '<RA>' in inStr:
        sendRAAck('ACK',port)
        return 'RA'
    
    if '<TCAck>' in inStr:
        return 'TCAck'
    
    if '<IMR>' in inStr:
        sendIM('RACHUTS','FL',port) #go flight mode
        reply = listenFor('RACHUTS',port)
        print(reply)
        return 'IMR'
    
    if '<IMAck>' in inStr:
        return 'IMAck'

    else:
        return False
            
                
            
def main():
    
    port = '/dev/tty.usbserial'
    ser = serial.Serial(port,115200,timeout=30)

    
    
#    sendGPS(30,'clock',ser)
#    
#    sendIM('RACHUTS','FL',ser) #go flight mode
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    sendGPS(30,'clock',ser)
    
    sendTC('RACHUTS','147;',ser)
    reply = listenFor('RACHUTS',ser)
    print(reply)
    
    
#    sendTC('RACHUTS','143;',ser)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    
    for i in range(1000):
        reply = listenFor('RACHUTS',ser)
        print(reply)
        
#    
#    sendTC('RACHUTS','130;',ser)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    sleep(1)
    
#    sendGPS(30,'clock',ser)
#    
#    sendTC('RACHUTS','180,-20,0,0,0,1;',ser)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    sleep(1)
#    

#    sendTC('RACHUTS','133,1250;',ser)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    sleep(1)
#    
#    sendTC('RACHUTS','132,105;',ser)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    sleep(1)
#    
#    sendTC('RACHUTS','134,80;',ser)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    sleep(1)
#    
#    sendTC('RACHUTS','135,600;',ser)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    sleep(1)
#    
#    sendTC('RACHUTS','136,7200;',ser)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    sleep(1)
#    
#    sendTC('RACHUTS','137,4;',ser)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    sleep(1)
#    
#    sendTC('RACHUTS','141,40;',ser)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    sleep(1)
#    
#    sendTC('RACHUTS','148,60;',ser)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    sleep(1)
#    
#    sendTC('RACHUTS','149,60;',ser)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    sleep(1)

    

    
#    sendGPS(40,'clock',ser)
#    sleep(3)
#    
#    sendIM('RACHUTS','FL',ser) #go flight mode
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    sendTC('RACHUTS','1,0.1;',ser) # Use SZA Trigger
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    for i in range(20): #down profile MCB TM
#        reply = listenFor('RACHUTS',ser)
#        print(reply)
#        sendGPS(106+i,'clock',ser)
#  






    
#    sendTC('RACHUTS','143;',ser)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    sleep(10)
#    
#    sendTC('RACHUTS','181,1,10,1,1,1;',ser) #Set Porfile Parameters
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    
#    sendTC('RACHUTS','138;',ser) # Use SZA Trigger
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    sendTC('RACHUTS','132,105;',ser) #SZA to profile is 105
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    sendTC('RACHUTS','148,30;',ser) #Set Preprofile to 30 seconds
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    sendTC('RACHUTS','149,10;',ser) #Set PU Warm up to 10 seconds
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    sendTC('RACHUTS','133,250;',ser) #profile 2500 revs
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    sendTC('RACHUTS','134,5;',ser) #dock 5 revs
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    sendTC('RACHUTS','141,5;',ser) #dock overshoot 5 revs
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#
#    sendTC('RACHUTS','135,60;',ser) #dwell 60 seconds
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    sendTC('RACHUTS','136,7200;',ser) #full profile period (down+dwell+up+dock)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    sendTC('RACHUTS','137,4;',ser) #number of profiles
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    sendIM('RACHUTS','FL',ser) #go flight mode
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    sendTC('RACHUTS','130;',ser) #go to auto mode
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#
#    
#    sleep(5)
#    sendGPS(30,'clock',ser)
#    sleep(3)
#    sendGPS(105,'clock',ser)
#    sleep(3)
#    sendGPS(106,'clock',ser)
#    sleep(3)
#        
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#
#    for i in range(1000): #down profile MCB TM
#        reply = listenFor('RACHUTS',ser)
#        print(reply)
#        sendGPS(106+i,'clock',ser)
#   
#   
    
#    sendTC('RACHUTS','13,80,-15,60,-15,80,-40;',ser) #Set temp limit, MTR 1 High, MTR1 LOw, MTR2 High, MTR2 LOw, MC1 High, MC1 Low
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    sendTC('RACHUTS','14,500,-500;',ser) #Set reel torque, high limit, low limit (internal units)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    
#    sendTC('RACHUTS','15,13.75,-10;',ser) #Set MTR1 current limit High, Low (amps)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
# 
    
#    sendTC('RACHUTS','182;',ser) #PU Reset
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
#    reply = listenFor('RACHUTS',ser)
#    print(reply)
       
        
    ser.close()        
if (__name__ == '__main__'): 
    main()          

        

  


        