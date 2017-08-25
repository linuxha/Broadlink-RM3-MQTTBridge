# https://gist.github.com/appden/42d5272bf128125b019c45bc2ed3311f
# 
import binascii
import struct

# Pronto (ex)
# 0000 006E 0022 0002 0156 00AB 0015 003F 0015 0015 0015 003F 0015 0015 0015 0015 0015 0015 0015
# 0015 0015 003F 0015 0015 0015 0015 0015 0015 0015 0015 0015 003F 0015 003F 0015 0015 0015 0015
# 0015 0015 0015 0015 0015 0015 0015 0015 0015 003F 0015 003F 0015 0015 0015 0015 0015 0015 0015
# 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 003F 0015 003F 0015 0719 0156 0055 0015 0E2A
# 4 * 19 = 76
def pronto2lirc(pronto):
    codes = [long(binascii.hexlify(pronto[i:i+2]), 16) for i in xrange(0, len(pronto), 2)]

    if codes[0]:
        raise ValueError('Pronto code should start with 0000')
    if len(codes) != 4 + 2 * (codes[2] + codes[3]):
        raise ValueError('Number of pulse widths does not match the preamble')

    frequency = 1 / (codes[1] * 0.241246)
    return [int(round(code / frequency)) for code in codes[4:]]

# LIRC
# [9076, 4538, 557, 1672, 557, 557, 557, 1672, 557, 557, 557, 557, 557, 557, 557, 557, 557,
# 1672, 557, 557, 557, 557, 557, 557, 557, 557, 557, 1672, 557, 1672, 557, 557, 557, 557,
# 557, 557, 557, 557, 557, 557, 557, 557, 557, 1672, 557, 1672, 557, 557, 557, 557, 557,
# 557, 557, 557, 557, 557, 557, 557, 557, 557, 557, 557, 557, 1672, 557, 1672, 557, 48218,
# 9076, 2256, 557, 96223]
# 72
def lirc2broadlink(pulses):
    array = bytearray()

    for pulse in pulses:
        pulse = pulse * 269 / 8192  # 32.84ms units

        if pulse < 256:
            array += bytearray(struct.pack('>B', pulse))  # big endian (1-byte)
        else:
            array += bytearray([0x00])  # indicate next number is 2-bytes
            array += bytearray(struct.pack('>H', pulse))  # big endian (2-bytes)

    packet = bytearray([0x26, 0x00])  # 0x26 = IR, 0x00 = no repeats
    packet += bytearray(struct.pack('<H', len(array)))  # little endian byte count
    packet += array
    packet += bytearray([0x0d, 0x05])  # IR terminator

    # Add 0s to make ultimate packet size a multiple of 16 for 128-bit AES encryption.
    remainder = (len(packet) + 4) % 16  # rm.send_data() adds 4-byte header (02 00 00 00)
    if remainder:
        packet += bytearray(16 - remainder)

    return packet
#
# Packet:
# 50 00 = 0x0050 = 80 = (80 - 4)/2 = 39 (78 bytes)
# 2600500000012a9512361212123612121212121212121236121212121212121212361236
# 121212121212121212121212123612361212121212121212121212121212121212361236
# 1200062f00012a4a12000c570d05000000000000
# 00012a95123612121236121212121212121212361212121212121212123612361212121212121212121212121236123612121212121212121212121212121212123612361200062f00012a4a1200 0c57
if __name__ == '__main__':
    import sys

    for code in sys.argv[1:]:
        print "Code:"
        print code
        pulses = pronto2lirc(bytearray.fromhex(code))
        print "Pulses:"
        print pulses
        print len(pulses)
        packet = lirc2broadlink(pulses) # Binary format
        print "Broadlink:"
        print binascii.hexlify(packet)
    #
#
