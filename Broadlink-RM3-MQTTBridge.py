#!/usr/bin/python
#
# I've taken Perrin7's NinjaCape MQTT Bridge code and modified it for the
# Broadlink RM3 and the Blackbean python code.
#
# This retains Perrin7's MIT License

# 1) Read the ini file using configparser
#    a) get the Blackbean information
#        i)   host
#        ii)  port
#        iii) mac
#        iv)  timeout
#    b) get the MQTT information
#        i)   topic
#        ii)  host
#        iii) port
#        iv)  user
#        v)   password

# used to interface the NinjaCape to openHAB via MQTT
# - reads data from serial port and publishes on MQTT client
# - writes data to serial port from MQTT subscriptions
#
# - uses the Python MQTT client from the Mosquitto project http://mosquitto.org (now in Paho)
#
# https://github.com/perrin7/ninjacape-mqtt-bridge
# perrin7

#
import paho.mqtt.client as mqtt
import os
import json
import threading
import time

import broadlink, configparser
import sys, getopt
import time, binascii
import netaddr
# This is a local file (has the BlackBeanControlSetting, config file name)
# Not sure how to pass the config file name to it but we can pass that to
# the configparser.configparser.read('filename.ini')
#import Settings
from os import path
from Crypto.Cipher import AES

myType = 0x2712 # RM2, close enough for the RM3

# from Settings.py
#ApplicationDir = path.dirname(path.abspath(__file__))
#BlackBeanControlSettings = path.join(ApplicationDir, 'BlackBeanControl.ini')
# Hard coded for now, I'll change that later
myConfigFile = os.environ['HOME'] + '/.mqtt-bbeancr.ini'
if os.path.isfile(myConfigFile) != True :
    print >>sys.stderr, "Config file: %s" % (myConfigFile)
    exit(2)
#

Settings = configparser.ConfigParser()
Settings.read(myConfigFile)

IPAddress  = Settings.get('General', 'IPAddress')
#
Port       = Settings.get('General', 'Port')
#
MACAddress = Settings.get('General', 'MACAddress')
#
Timeout    = Settings.get('General', 'Timeout')
#
MQTT_Topic   = Settings.get('MQTT', 'Topic')
MQTT_Host    = Settings.get('MQTT', 'Host')
#
MQTT_Port    = int(Settings.get('MQTT', 'Port'))
#
MQTT_Timeout = int(Settings.get('MQTT', 'Timeout'))

#SettingsFile = configparser.ConfigParser()
#SettingsFile.optionxform = str
#SettingsFile.read(Settings.BlackBeanControlSettings)

print >> sys.stderr, "IPAddress    = %s" % (IPAddress)
print >> sys.stderr, "Port         = %s" % (Port)
print >> sys.stderr, "MACAddress   = %s" % (MACAddress)
print >> sys.stderr, "Timeout      = %s" % (Timeout)
print >> sys.stderr, "Type         = %s" % (myType)

print >> sys.stderr, "MQTT_Topic   = %s" % (MQTT_Topic)
print >> sys.stderr, "MQTT_Host    = %s" % (MQTT_Host)
print >> sys.stderr, "MQTT_Port    = %s" % (MQTT_Port)
print >> sys.stderr, "MQTT_Timeout = %s" % (MQTT_Timeout)

MACAddress = bytearray.fromhex(MACAddress)

SentCommand           = ''
ReKeyCommand          = False
DeviceName            =''
DeviceIPAddress       = ''
DevicePort            = ''
DeviceMACAddres       = ''
DeviceTimeout         = ''
AlternativeIPAddress  = ''
AlternativePort       = ''
AlternativeMACAddress = ''
AlternativeTimeout    = ''

try:
    Options, args = getopt.getopt(sys.argv[1:], 'c:d:r:i:p:m:t:h', ['command=','device=','rekey=','ipaddress=','port=','macaddress=','timeout=','help'])
except getopt.GetoptError:
    print('BlackBeanControl.py -c <Command name> [-d <Device name>] [-i <IP Address>] [-p <Port>] [-m <MAC Address>] [-t <Timeout>] [-r <Re-Key Command>]')
    sys.exit(2)
#

for Option, Argument in Options:
    if Option in ('-h', '--help'):
        print('BlackBeanControl.py -c <Command name> [-d <Device name>] [-i <IP Address>] [-p <Port>] [-m <MAC Address>] [-t <Timeout> [-r <Re-Key Command>]')
        sys.exit()
    elif Option in ('-c', '--command'):
        SentCommand = Argument
    elif Option in ('-d', '--device'):
        DeviceName = Argument
    elif Option in ('-r', '--rekey'):
        ReKeyCommand = True
        SentCommand = Argument
    elif Option in ('-i', '--ipaddress'):
        AlternativeIPAddress = Argument
    elif Option in ('-p', '--port'):
        AlternativePort = Argument
    elif Option in ('-m', '--macaddress'):
        AlternativeMACAddress = Argument
    elif Option in ('-t', '--timeout'):
        AlternativeTimeout = Argument
    #
#

### Settings

broker = "127.0.0.1" # mqtt broker
port   = 1883 # mqtt broker port

debug  = False  ## set this to True for lots of prints

# buffer of data to output to the serial port
outputData = []

#
def lprint(s):
    print time.strftime('%X ') + s
#

####  MQTT callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        #rc 0 successful connect
        print "Connected"
    else:
        raise Exception
    # subscribe to the output MQTT messages
    output_mid = client.subscribe("ninjaCape/output/#")
#
def on_publish(client, userdata, mid):
    if(debug):
        print "Published. mid:", mid
#

def on_subscribe(client, userdata, mid, granted_qos):
    if(debug):
        print "Subscribed. mid:", mid
#

def on_message_output(client, userdata, msg):
    if(debug):
        print "Output Data: ", msg.topic, "data:", msg.payload
    #add to outputData list
    outputData.append(msg)
#

def on_message(client, userdata, message):
    if(debug):
        print "Unhandled Message Received: ", message.topic, message.paylod		
#

#called on exit
#close serial, disconnect MQTT
def cleanup():
    print "Ending and cleaning up"
    #ser.close()
    mqttc.disconnect()
#

def mqtt_to_JSON_output(mqtt_message):
    topics = mqtt_message.topic.split('/');
    ## JSON message in ninjaCape form
    json_data = '{"DEVICE": [{"G":"0","V":0,"D":' + topics[2] + ',"DA":"' + mqtt_message.payload + '"}]})'
    return json_data
#

#thread for reading serial data and publishing to MQTT client
def read_and_publish(dev, mqttc, topic):
    lprint("Learning...")
    # I've found I need to put his thing back into learning mode to get the new
    # data, otherwise I just keep reading the last one.
    while True:
        timeout = 30
        dev.enter_learning()
        data = None

        while (data is None) and (timeout > 0):
            time.sleep(.25)
            timeout -= 2
            data = dev.check_data()

            if data:
                learned = ''.join(format(x, '02x') for x in bytearray(data))
                lprint(learned)
                try:
                    # Format data as needed
                    #mqttc.publish("home/network/device/bbeancr/learned", learned)
                    mqttc.publish(topic, learned)
                except(KeyError):
                    # TODO should probably do something here if the data is malformed
                    lprint("Exception ...")
                    pass
                #
            else:
                #lprint("No data received...")
                pass
            #
        #
    #
#

#thread for reading serial data and publishing to MQTT client
def serial_read_and_publish(ser, mqttc):
    ser.flushInput()

    while True:
        line = ser.readline() # this is blocking
        if(debug):
            print "line to decode:",line
        #
		
        # split the JSON packet up here and publish on MQTT
        json_data = json.loads(line)
        if(debug):
            print "json decoded:",json_data
        #

        try:
            device = str( json_data['DEVICE'][0]['D'] )
            data = str( json_data['DEVICE'][0]['DA'] )
            mqttc.publish("ninjaCape/input/"+device, data)
        except(KeyError):
            # TODO should probably do something here if the data is malformed
            pass
        #
    #
#

# ------------------------------------------------------------------------------
############ MAIN PROGRAM START
if(True):
    print "Connecting ... ", IPAddress
    dev = broadlink.gendevice(myType, (IPAddress, 80), MACAddress)
    dev.auth()
else:
    try:
        print "Connecting... ", IPAddress
        #connect to serial port
        #ser = serial.Serial(serialdev, 9600, timeout=None) #timeout 0 for non-blocking. Set to None for blocking.
        dev = broadlink.gendevice(myType, (IPAddress, 80), MACAddress)
        dev.auth()
    except:
        print "Failed to connect Blackbean"
        #unable to continue with no serial input
        raise SystemExit
    #
#

try:
    #create an mqtt client
    mqttc = mqtt.Client("broadlink")

    #connect to broker
    mqttc.connect(MQTT_Host, MQTT_Port, MQTT_Timeout)
    #mqttc.connect("mozart.uucp", 1883, 60)

    #attach MQTT callbacks
    mqttc.on_connect   = on_connect
    mqttc.on_publish   = on_publish
    mqttc.on_subscribe = on_subscribe
    mqttc.on_message   = on_message
    mqttc.message_callback_add("home/network/device/bbeancr/send", on_message_output)

    # start the mqttc client thread
    mqttc.loop_start()

    dev_thread = threading.Thread(target=read_and_publish, args=(dev, mqttc, MQTT_Topic))
    dev_thread.daemon = True
    dev_thread.start()
		
    while True: # main thread
        # writing to serial port if there is data available
        #if( len(outputData) > 0 ):
        #    #print "***data to OUTPUT:",mqtt_to_JSON_output(outputData[0])
        #    ser.write(mqtt_to_JSON_output(outputData.pop()))
	#
        time.sleep(3600)
    #

    time.sleep(0.5)
#

# handle app closure
except (KeyboardInterrupt):
    print "Interrupt received"
    cleanup()
except (RuntimeError):
    print "uh-oh! time to die"
    cleanup()
# =[ Fini ]=====================================================================

"""
https://github.com/mjg59/python-broadlink/issues/57
   0    1    2    3
0000 0001 0010 0011
   4    5    6    7
0100 0101 0110 0111
   8    9    A    B
1000 1001 1010 1011
   C    D    E    F
1100 1101 1110 1111

Key 2 -
1 2 3   5                                                                                           50  52             59
+ + +   +                                                                                       |   +   +              +
260030001d1a3936391a1d1a1d361d1b381b1d1a1d1a1d3639000acd1d1a3936391a1d1a1d361d1b381b1d1a1d1a1d3639000d050000000000000000
26 00 3000 1d1a  3936 391a 1d1a 1d36 1d1b 381b 1d1a 1d1a 1d36 3900 0acd 1d1a 3936 391a 1d1a 1d36 1d1b 381b 1d1a 1d1a 1d36 3900 0d05 0000000000000000

1d 00011101
1a 00011100

39 00111001
36 00111010

0a 00001010
cd 11001101

1 2 3   5                                               28
| | |   |                                           +   |   |                          |
26001a001d1b1d1a1d1a391a1d1b1d361d1a391a1d1b1c1b1d3638000d050000000000000000000000000000
26 00 1a00 1d1b1d1a1d1a391a1d1b1d361d1a391a1d1b1c1b1d 36 3800 0d05 0000000000000000000000000000

Bytes           Meaning
26              IR
00              No repeat
1a00            26 bytes
1d ...          data
3800            ???
0d05            End of signal
00 ...          Nul padding (???)

260030001f1b3836391a1d1b1d361d1a391a1d1b1c1b1d3639000acc1d1b3836391b1c1b1d361d1a391a1d1b1d1a1d363900 0d05 0000000000000000
260030001d1a3936391a1d1a1d361d1b381b1d1a1d1b1c3639000acd1d1a3936391a1d1a1d361d1b381b1d1a1d1b1c363900 0d05 0000000000000000
26001a001d1b1d1a1d1b381b1c1b1d33201a391a1d1b1d1a1d363900 0d05 0000000000000000000000000000
260034001d1b1d1a1d1a391a1d1b1d361d1a391a1d1b1c1b1d3639000acc1d1b1d1a1d1a391b1c1b1d361d1a391a1d1b1c1b1d363900 0d05 00000000
260030001e1b3836391a1d1b1d361d1a391a1d1a1d1b1d3638000acd1d1b3836391a1d1b1d361d1a391a1d1a1d1b1d363800 0d05 0000000000000000
260030001d1a3936391a1d1a1d361d1b381b1d1a1d1a1d3639000acd1d1a3936391a1d1a1d361d1b381b1d1a1d1a1d363900 0d05 0000000000000000
26001a001d1b1d1a1d1a391b1c1b1d361d1a391a1d1b1c1b1d363900 0d05 0000000000000000000000000000
260034001d1a1d1a1d1b381b1d1a1d361d1b381b1c1b1d1a1d343b000acd1d1a1d1b1c1b381b1d1a1d361d1b381b1d1a1d1a1d363900 0d05 00000000
260038001d1b1d1a1d1b381b1d1a1d361d1a391a1d1b1d1a1d36390006770700044f1d1a1d1a1d1b381b1d1a1d361d1a391a1d1b1d1a1d363900 0d05 
260030001d1a3936381b1d1a1d361d1b381b1c1b1d1a1d3639000acd1d1a3936381b1d1a1d361d1b381b1d1a1d1a1d363900 0d05 0000000000000000
260030001d1a3936381b1d1a1d361d1b381b1c1b1d1a1d3639000acd1d1a3936381b1d1a1d361d1b381b1d1a1d1a1d363900 0d05 0000000000000000

1 2 3   5                                                                                                                                                       80
| | |   |                                                                                                                                                       |
26004e001d1b1c1b1d1a391a1d1b1d361d1a391a1d1a1d1b1d3638000acd1d1b1c1b1d1a391a1d1b1d361d1a391a1d1a1d1b1d3638000acd1d1b1d1a1d1a391a1d1b1d361d1a391a1d1a1d1b1d3638000d05 00000000000000000000
26 00 4e00 1d1b1c1b1d1a391a1d1b1d361d1a391a1d1a1d1b1d 36 3800 0acd1d1b1c1b1d1a391a1d1b1d361d1a391a1d1a1d1b1d 36 3800 0acd1d1b1d1a1d1a391a1d1b1d361d1a391a1d1a1d1b1d 36 3800 0d05 00000000000000000000

0x4e = 78
0d05 @ byte 80 - 2

260048001e1b3837381b1d1a1d361d1a391a1d1b1d1a1d3639000acc1d1b3936381b1d1a1d361d1a391a1d1b1d1a1d3639000acd1d1a3936381b1d1a1d361d1a391a1d1b1d1a1d363900 0d05 
26001a001d1a1d1a1d1b381b1d1a1d361d1a391a1d1b1d1a1d363900 0d05 0000000000000000000000000000
26001a001d1b1d1a1d1a391b1c1b1d361d1a391a1d1b1c1b1d363900 0d05 0000000000000000000000000000
26001a001e1a1d1a1d1b381b1d1a1d361d1a391a1d1b1d1a1d363900 0d05 0000000000000000000000000000
26001a001d1b1d1a1d1b381b1d1a1d361d1a391a1d1b1d1a1d363900 0d05 0000000000000000000000000000
26001a001d1b1d1a1d1a391a1d1b1d361d1a391a1d1a1d1b1d363800 0d05 0000000000000000000000000000
26001a001c1b1d1a1d1b381b1d1a1d361d1a391a1d1b1d1a1d363900 0d05 0000000000000000000000000000
260018001d1b3836391b1c1b1d361d1a391a1d1b1d1a1d363900 0d05 
260018001d1b3837381b1d1a1d361d1a391a1d1b1d1a1d363900 0d05 

Key 3 (with some long hold)
26 00 38001d1a1d1b1d1a 391a1d1a1d 361d1b 381b1d1a1d1b1c 371d1a1d000ab11d1a1d1b1d1a 391a1d1b1c 371c1b 381b1d1a1d1b1d 361d1a1d00 0d05 

26 00 34001d1a 39 36 391a1d1a1d 361d1b 381b1d1a1d1b1c 33201b1d000ab11d1a 39 36 391a1d1a1d 361d1b 381b1d1a1d1b1c 371c1b1d00 0d05 00000000

26003c000e0001431d1b1c1b1d1a391a1d1b1d361d1a391a1d1a1d1b1d361d1a1d000ab11d1b1c1b1d1a391a1d1b1d361d1a391a1d1a1d1b1d361d1a1d00 0d05 000000000000000000000000
260034001d1a3936391a1d1b1c361d1b381b1d1a1d1b1c371c1b1d000ab11d1a3936391a1d1b1c361d1b381b1d1a1d1b1d361d1a1d00 0d05 00000000
260038001d1b1d1a1d1a391a1d1b1d361d1a391a1d1b1c1b1d361d1a1d000ab11d1b1d1a1d1a391b1c1b1d361d1a391a1d1b1c1b1d361d1a1d00 0d05 
26001a001d1b3836391a1d1b1d361d1a391a1d1a1d1b1d361d1a1d00 0d05 0000000000000000000000000000
260038001d1a1d1b1d1a391a1d1b1c361d1b381b1d1a1d1b1d361d1a1d000ab11d1a1d1b1d1a391a1d1b1c371c1b391a1d1a1d1b1d361d1a1d00 0d05 
260038001d1a1d1b1d1a391a1d1a1d361d1b381b1d1a1d1b1c361d1b1d000ab11d1a1d1b1d1a391a1d1a1d361d1b381b1d1a1d1b1c361d1b1d00 0d05 
26003c011d1a3936391a1d1a1d361d1b381b1d1a1d1a1d361d1b1d000ab11d1a3936391a1d1a1d361d1b381b1d1a1d1b1c361d1b1d000ab11d1a3936391a1d1b1c361d1b381b1d1a1d1b1c371d1a1d000ab11d1a3936391a1d1b1c361d1b381b1d1a1d1b1d361d1a1d000ab11d1b3836391a1d1b1d361d1a391a1d1a1d1b1d361d1a1d000ab11d1b3836391a1d1b1d361d1a391a1d1a1d1b1d361d1a1d000ab11d1b3836391a1d1b1d361d1a391a1d1a1d1b1d361d1a1d000ab11d1b3836391a1d1b1d361d1a391a1d1b1c1b1d361d1a1d000ab11d1b3836391b1c1b1d361d1a391a1d1b1d1a1d361d1a1d0006af100003f21d1b3836391b1c1b1d361d1a391a1d1b1d1a1d361d1a1d000ab11d1b3837381b1d1a1d361d1a391a1d1b1d1a1d361d1a1d000ab21d1a3936381b1d1a1d361d1a391a1d1b1d1a1d361d1b1c00 0d05 000000000000000000000000
2600a8001d1a1d1a1d1b381b1d1a1d361d1a391a1d1b1d1a1d361d1b1c000ab21d1a1d1a1d1b381b1d1a1d361d1a391b1c1b1d1a1d361d1b1c000ab21d1a1d1a1d1b381b1d1a1d361d1b381b1c1b1d1a1d361d1b1d000ab11d1a1d1a1d1b381b1d1a1d361d1b381b1d1a1d1a1d361d1b1d000ab11d1a1d1b1c1b381b1d1a1d361d1b381b1d1a1d1a1d361d1b1d000ab11d1a1d1b1c1b391a1d1a1d361d1b381b1d1a1d1a1d361d1b1d00 0d05 

"""
