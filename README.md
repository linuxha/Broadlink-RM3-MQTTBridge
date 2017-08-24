# Broadlink-RM3-MQTTBridge Readme

## Introduction
A simple daemon to recieve IR commands from a user and post them to a MQTT topic

## Version
Version 0.0.1

## Usage

## ToDo

This is a work in progress and a lot of things are still hard coded
and a lot of testing is going on. The should be considered pre-Alpha
at this time.

I haven't figured out what the IR Controller is sending. The same key
hit twice (once, pause, twice) returns 2 different strings. I'll need
to figure out how to interpret the data in a consistent manner.

## Notes:
https://github.com/mjg59/python-broadlink/issues/57
From the previous URL
Data for sending an IR/RF command (payload for the send command)

Offset          Meaning
0x00            0x26 = IR, 0xb2 for RF 433Mhz, 0xd7 for RF 315Mhz
0x01            repeat count, (0 = no repeat, 1 send twice, .....)
0x02, 0x03      Length of the following data in little endian (*1)
0x04 ....       Pulse lengths in 32,84ms units (ms * 269 / 8192 works very well)
....            ....
....            0x0d 0x05 at the end for IR only

1) Little endian - 0x1234 mem[0] = 0x34, mem[1] = 0x12 (LSB first)
   Big endian    - 0x1234 mem[0] = 0x12, mem[1] = 0x34 (MSB first)
   So 3000 is a byte count of 0x30 or 48 bytes

Each value is represented by one byte. If the length exceeds one byte
then it is stored big endian with a leading 0.

Note to self: 32.84 ms? (xtal 32768Hz?)
Example: The header for my Optoma projector is 8920 4450
8920 * 269 / 8192 = 0x124
4450 * 269 / 8192 = 0x92

So the data starts with 0x00 0x01 0x24 0x92 ....

### Eample (Key 2 on my Streamzap IR remote - factory programming?)
26 00 1a00 1d1b1d1a1d1a391a1d1b1d361d1a391a1d1b1c1b1d36 3800 0d05 0000000000000000000000000000

Bytes           Meaning
26              IR
00              No repeat
1a00            26 bytes
1d ...          data
3800            ???
0d05            End of signal
00 ...          Null padding (why ???)

If you use LIRC as a template then you have just to continue with
pre-data and then command, where you would use the "zero" pulse
lengths for 0 and the "one" pulse lengths for 1

It seems that infrared commands need to be terminated always with 0x0d
0x05 in addition, whereas this is not required for RF. I didn't figure
out the meaning of this so far.

So far I was able to produce all IR commands for my devices as well as
for all RF devices. I have quite a bunch of RF devices, like remote
controllable sockets and switches and a projection screen. For most of
them I was not able to learn the RF code with the RM2 PRo, but as I
knew the timings already generating the codes works perfectly well.