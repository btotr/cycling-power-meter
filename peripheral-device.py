import sys

sys.path.append("")

from machine import Pin, I2C
from micropython import const
from esp32 import *

import asyncio
import aioble
import bluetooth

import random
import struct
import binascii
import time

'''

BLE_Cycling_Power

'''
class BLE_Cycling_Power:

    def __init__(self):
        # Services
        self.power_service_uuid = bluetooth.UUID(0x1818)
        self.device_information_service_uuid = bluetooth.UUID(0x180A)
        self.battery_service_uuid = bluetooth.UUID(0x180F)
        self.power_service = aioble.Service(self.power_service_uuid)
        self.device_information_service = aioble.Service(self.device_information_service_uuid)
        self.battery_service = aioble.Service(self.battery_service_uuid)
        # Characteristics
        self.feature_characteristic = aioble.Characteristic(self.power_service, bluetooth.UUID(0x2a65), read=True, notify=False)
        self.location_characteristic = aioble.Characteristic(self.power_service, bluetooth.UUID(0x2a5d), read=True, notify=False)
        self.measurement_characteristic = aioble.Characteristic(self.power_service, bluetooth.UUID(0x2a63), read=False, notify=True)
        self.manufacturer_characteristic = aioble.Characteristic(self.device_information_service, bluetooth.UUID(0x2A29), read=True, notify=False)
        self.software_rev_characteristic = aioble.Characteristic(self.device_information_service, bluetooth.UUID(0x2A28), read=True, notify=False)
        self.battery_level_characteristic = aioble.Characteristic(self.battery_service, bluetooth.UUID(0x2A19), read=False, notify=True)
        # register services
        aioble.register_services(self.power_service, self.device_information_service, self.battery_service)
        # initialise buffers
        self.bleBuffer = bytearray(8)
        self.slBuffer = bytearray(1)
        self.fBuffer = bytearray(4)
        self.slBuffer[0] = 0x05
        self.fBuffer[0] = 0x00
        self.fBuffer[1] = 0x10 # non distribution 
        self.fBuffer[2] = 0x00
        self.fBuffer[3] = 0x08 # crank revolution
        # write device information
        self.manufacturer_characteristic.write(struct.pack('5s', b'btotr'))
        self.software_rev_characteristic.write(struct.pack('4s', b'v0.1'))

    async def publish_task(self, connection):
        while True:

            power = int(weight.get_weight())*2 #todo

            #print(cadance.get_revolutions())
            #print(cadance.get_lastRevTime())

            self.bleBuffer[0] = 0x20 # 00100000
            self.bleBuffer[1] = 0x00
            self.bleBuffer[2] = power & 0xff
            self.bleBuffer[3] = power >> 8
            self.bleBuffer[4] = cadance.get_revolutions() & 0xff
            self.bleBuffer[5] = cadance.get_revolutions() >> 8
            self.bleBuffer[6] = cadance.get_lastRevTime() & 0xff
            self.bleBuffer[7] = cadance.get_lastRevTime() >> 8

            #binary_string = binascii.hexlify(self.bleBuffer).decode('utf-8')
            #print(binary_string)

            self.location_characteristic.write(self.slBuffer)
            self.feature_characteristic.write(self.fBuffer)
            self.measurement_characteristic.notify(connection, self.bleBuffer)
            self.battery_level_characteristic.notify(connection, struct.pack('h', int(battery.get_level())))
            await asyncio.sleep_ms(1000)

    async def connection_task(self):
        while True:
            async with await aioble.advertise(
                250_000,
                name="open-kinetic",
                services=[self.power_service_uuid, self.device_information_service_uuid],
                appearance=1156
            ) as connection:
                asyncio.create_task(cycling_power.publish_task(connection))
                print("Connection from", connection.device)
                while connection.is_connected():
                    await asyncio.sleep_ms(5000)

'''

battery

'''

class Battery:

    def __init__(self):
        self.level = 60

    def get_level(self):
        return self.level

    async def level_task(self):
        while True:
            self.level += random.uniform(-0.5, 0.5)
            await asyncio.sleep_ms(1000)

'''

weight

'''

class Weight:

    def __init__(self):
        self.weight = 200

    def get_weight(self):
        return self.weight

    async def load_sensor_task(self):
        while True:
            self.weight += random.uniform(-0.5, 0.5)
            await asyncio.sleep_ms(1000)

'''

cadance

'''

class Cadance:

    def __init__(self):
        self.revolutions = 0
        self.lastRevTime = 0

    def get_revolutions(self):
        return self.revolutions

    def get_lastRevTime(self):
        return self.lastRevTime

    async def hall_sensor_task(self):
        while True:
            self.revolutions += 1
            self.lastRevTime = time.ticks_diff(time.ticks_ms(), self.lastRevTime)
            await asyncio.sleep_ms(1000)

# Run tasks.
async def main():
    t1 = asyncio.create_task(battery.level_task())
    t2 = asyncio.create_task(cycling_power.connection_task())
    t3 = asyncio.create_task(cadance.hall_sensor_task())
    t4 = asyncio.create_task(weight.load_sensor_task())
    await asyncio.gather(t2, t3, t4)

cadance = Cadance()
weight = Weight()
battery = Battery()
cycling_power = BLE_Cycling_Power()
asyncio.run(main())
