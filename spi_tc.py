#!/usr/bin/python
# encoding: utf-8

###########################
# COPYRIGHT NOTICE GOES HERE
###########################


import argparse
from time import sleep
import sys
import hal
from spidev import SpiDev as SPI


class TC_AMP:
    """SPI thermocouple amplifier
        """
    def __init__(self, configstring):
        # bus.dev:device_type

        # split configstring into bus/dev and device_type
        bus, device = (configstring.split(':'))
        # split bus/dev
        try:
            self.bus, self.dev = (int(i) for i in bus.split('.'))
        except ValueError:
            raise ValueError('invalid device specifier: %s' % configstring.split(':')[0])

        device = device.lower()

        if device == 'max6675':
            self.error_mask = 0b100
            self.move_len = 3
            self.msg_len = 2
        elif device == 'max31855':
            self.error_mask = 0b1
            self.move_len = 2
            self.msg_len = 2
        else:
            raise ValueError('unknown device type: %s' % device)

        # initialize SPI configuration
        self.spi = SPI(self.bus, self.dev)
        # SPI mode
        self.spi.mode = 1
        # max speed in Hz
        self.spi.max_speed_hz = 4 * 10 ** 6
        # bits per word
        self.spi.bits_per_word = 8
        # MSB first
        self.spi.lsbfirst = False
        # CS low
        self.spi.cshigh = False



    def read(self):
        """
            """
        t = self.spi.readbytes(self.msg_len)
        # convert temp from a list of bytes to a single number
        temp = 0
        while t:
            temp <<= 8
            temp |= t.pop(0)

        # check error mask, raise if necessary
        if temp & self.error_mask:
            raise IOError('error during SPI read: %s' % self)

        # return raw data and temperature (in deg C)
        return [temp, (temp >> self.move_len) * 0.25]

    def __str__(self):
        return 'ch-%1d:%1d' % (self.bus, self.dev)

    """
        http://datasheets.maximintegrated.com/en/ds/MAX6675.pdf
        http://datasheets.maximintegrated.com/en/ds/MAX31855.pdf
        """


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HAL component to read thermocouple data via SPI")
    parser.add_argument('-n', '--name', help='HAL component name', required=True)
    parser.add_argument('-i', '--interval', help='Update interval', default=0.5)
    parser.add_argument('-d', '--devices', help='Comma-separated list of SPI devices and TC amp types, e.g. 1.1:MAX6675', required=True)
    args = parser.parse_args()

    devices = []



    # sanitize arguments and initialize devices
    if not args.devices.strip():
        print('No devices specified, exiting')
        sys.exit(1)

    h = hal.component(args.name)

    # loop through all specified devices
    for device in args.devices.lower().split(','):
        # initialize device based on config string
        try:
            d = TC_AMP(device)
            devices.append(d)
        except ValueError:
            continue
        # add HAL pins to device
        d.halRawPin = h.newpin('%s.raw' % d, hal.HAL_U32, hal.HAL_OUT)
        d.halValuePin = h.newpin('%s.value' % d, hal.HAL_FLOAT, hal.HAL_OUT)

    if not devices:
        print('No devices successfully parsed. Exiting')
        h.exit()
        sys.exit(1)

    # find the maximum required update delay
    update = 1#max([d.delay for d in devices])


    # add error and watchdog pins
    halErrorPin = h.newpin('error', hal.HAL_BIT, hal.HAL_OUT)
    halNoErrorPin = h.newpin('no-error', hal.HAL_BIT, hal.HAL_OUT)
    halWatchdogPin = h.newpin('watchdog', hal.HAL_BIT, hal.HAL_OUT)
    h.ready()


    try:
        sleep(update)
        while(True):
            try:
                for d in devices:
                    # read data from device
                    d.halRawPin.value, d.halValuePin.value = d.read()

                error = False
            except IOError as e:
                error = True

            sleep(update)
    except:
        print('terminating SPI connections')
        for d in devices:
            d.spi.close()
        print('exiting HAL component ' + args.name)
        h.exit()

