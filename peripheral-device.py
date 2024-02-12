import sys

sys.path.append("")

from micropython import const

import asyncio
import aioble
import bluetooth

import random
import struct
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
        self.measurement_characteristic = aioble.Characteristic(self.power_service, bluetooth.UUID(0x2a63), read=True, notify=True)
        self.manufacturer_characteristic = aioble.Characteristic(self.device_information_service, bluetooth.UUID(0x2A29), read=True, notify=False)
        self.software_rev_characteristic = aioble.Characteristic(self.device_information_service, bluetooth.UUID(0x2A28), read=True, notify=False)
        self.battery_level_characteristic = aioble.Characteristic(self.battery_service, bluetooth.UUID(0x2A19), read=True, notify=True)
        # register services
        aioble.register_services(self.power_service, self.device_information_service, self.battery_service)

    async def publish_task(self, connection):
        while True:

            power = int(weight.get_weight())*2 #todo
            battery_level =  struct.pack('<B', int(battery.get_level()))
            print(connection)

            print(cadance.get_revolutions())
            print(cadance.get_lastRevTime())

            power_data =  struct.pack('<8B',
                0x20, 
                0x00, 
                power & 0xff, 
                power >> 8, 
                cadance.get_revolutions() & 0xff, 
                cadance.get_revolutions() >> 8,
                cadance.get_lastRevTime() & 0xff, 
                cadance.get_lastRevTime() >> 8)
            self.battery_level_characteristic.notify(connection, battery_level)
            self.battery_level_characteristic.write(battery_level)
            self.measurement_characteristic.notify(connection, power_data)
            self.measurement_characteristic.write(power_data)
            await asyncio.sleep_ms(1000)

    async def connection_task(self):
        while True:
            async with await aioble.advertise(
                250_000,
                name="open-kinetic-pwr",
                services=[self.power_service_uuid, self.device_information_service_uuid],
                appearance=1156
            ) as connection:
                # write power specific information
                self.location_characteristic.write(struct.pack('<B',0x05)) # left crunk
                self.feature_characteristic.write(struct.pack('<4B', 0x00, 0x10, 0x00, 0x08)) # non distribution and crank revolution
                # write device information
                self.manufacturer_characteristic.write(struct.pack('<12s', b'open-kinetic'))
                self.software_rev_characteristic.write(struct.pack('<6s', b'v0.1.1'))
                print("Connection from", connection.device)
                while connection.is_connected():
                    await cycling_power.publish_task(connection)

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
        self.weight = 100

    def get_weight(self):
        return self.weight

    async def load_sensor_task(self):
        while True:
            self.weight += random.uniform(-5, 5)
            await asyncio.sleep_ms(500)

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
            await asyncio.sleep_ms(800)

# Run tasks.
async def main():
    t1 = asyncio.create_task(battery.level_task())
    t2 = asyncio.create_task(cycling_power.connection_task())
    t3 = asyncio.create_task(cadance.hall_sensor_task())
    t4 = asyncio.create_task(weight.load_sensor_task())
    await asyncio.gather(t1, t2, t3, t4)

cadance = Cadance()
weight = Weight()
battery = Battery()
cycling_power = BLE_Cycling_Power()
asyncio.run(main())
