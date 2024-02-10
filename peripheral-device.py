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
        # BLE UUIDs.
        self.power_service_uuid = bluetooth.UUID(0x1818)
        self.feature_uuid = bluetooth.UUID(0x2a65)
        self.location_uuid = bluetooth.UUID(0x2a5d)
        self.measurement_uuid = bluetooth.UUID(0x2a63)
        # Register GATT server.
        self.power_service = aioble.Service(self.power_service_uuid)
        self.feature_characteristic = aioble.Characteristic(self.power_service, self.feature_uuid, read=True, notify=False)
        self.location_characteristic = aioble.Characteristic(self.power_service, self.location_uuid, read=True, notify=False)
        self.measurement_characteristic = aioble.Characteristic(self.power_service, self.measurement_uuid, read=False, notify=True)
        aioble.register_services(self.power_service)
        # initialise buffers
        self.bleBuffer = bytearray(8)
        self.slBuffer = bytearray(1)
        self.fBuffer = bytearray(4)
        self.slBuffer[0] = 0x05
        self.fBuffer[0] = 0x00
        self.fBuffer[1] = 0x10 # non distribution 
        self.fBuffer[2] = 0x00
        self.fBuffer[3] = 0x08 # crank revolution


    def publish_task(self, connection):
        while True:

            power = int(weight.get_weight())*2 #todo

            self.bleBuffer[0] = 0x20 # 00100000
            self.bleBuffer[1] = 0x00
            self.bleBuffer[2] = power & 0xff
            self.bleBuffer[3] = power >> 8
            self.bleBuffer[4] = cadans.get_revolutions() & 0xff
            self.bleBuffer[5] = cadans.get_revolutions() >> 8
            self.bleBuffer[6] = cadans.get_lastRevTime() & 0xff
            self.bleBuffer[7] = cadans.get_lastRevTime() >> 8

            binary_string = binascii.hexlify(self.bleBuffer).decode('utf-8')
            print(binary_string)

            self.location_characteristic.write(self.slBuffer)
            self.feature_characteristic.write(self.fBuffer)
            self.measurement_characteristic.notify(connection,self.bleBuffer)
            await asyncio.sleep_ms(1000)

    async def connection_task(self):
        while True:
            async with await aioble.advertise(
                250_000,
                name="open-power",
                services=[self.power_service_uuid]
            ) as connection:
                asyncio.create_task(cycling_power.publish_task(connection))
                print("Connection from", connection.device)
                await connection.disconnected()

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

cadans

'''

class Cadans:

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

    t2 = asyncio.create_task(cycling_power.connection_task())
    t3 = asyncio.create_task(cadans.hall_sensor_task())
    t4 = asyncio.create_task(weight.load_sensor_task())
    await asyncio.gather(t2, t3, t4)

cadans = Cadans()
weight = Weight()
cycling_power = BLE_Cycling_Power()
asyncio.run(main())
