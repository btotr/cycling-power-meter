import sys

sys.path.append("")

from micropython import const
from machine import Pin, ADC
from hx711 import HX711
import esp32
import asyncio
import math
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

    def publish_task(self, connection):
        power = 0
        last_time = 0
        diff_time = 0
        while True:
            '''
            TODO power calculation and update and frequency is based on the revolutions.
            Need to use something like a MPU-6050 accelerometer
            '''
            revolutions = cadance.get_revolutions()-cadance.get_lastRevolutions()
            if revolutions == 0:
                return

            # power calculation
            meter_per_revolution = 1.09956 #2PI*0.175 need to use bluetooth opcode to set the crunk size
            now = time.time_ns()
            diff_time = (now - last_time)/1e9
            power = int(abs(weight.get_weight()*2)*abs(revolutions*meter_per_revolution)/diff_time)
            
            # reset weight, time and cadance
            weight.set_weight(0)
            cadance.set_lastRevolutions(cadance.get_revolutions())
            last_time = now

            # debugging 
            rpm = 60*revolutions/diff_time
            #print("force: {:0.2f}".format(weight.get_weight()))
            #print("time: {:0.2f}".format(diff_time))
            print("last rev: {:0.2f}".format(cadance.get_lastRevTime()))
            #print("power: {}".format(power))
            print("revolutions: {}".format(cadance.get_revolutions()))
            print("rpm: {}".format(rpm))

            # bluetooth packets
            battery_level =  struct.pack('<B', int(battery.get_level()))
            power_data =  struct.pack('<8B',
                0x20, 
                0x00, 
                power & 0xff, 
                power >> 8, 
                cadance.get_revolutions() & 0xff, 
                cadance.get_revolutions() >> 8,
                cadance.get_lastRevTime() & 0xff, 
                cadance.get_lastRevTime() >> 8)
            # publish packets
            self.battery_level_characteristic.notify(connection, battery_level)
            self.battery_level_characteristic.write(battery_level)
            self.measurement_characteristic.notify(connection, power_data)
            self.measurement_characteristic.write(power_data)
            await asyncio.sleep_ms(1000)

    async def server_task(self, connection):
        # write power specific information
        self.location_characteristic.write(struct.pack('<B',0x05)) # left crunk
        self.feature_characteristic.write(struct.pack('<4B', 0x00, 0x10, 0x00, 0x08)) # non distribution and crank revolution
        # write device information
        self.manufacturer_characteristic.write(struct.pack('<12s', b'open-kinetic'))
        self.software_rev_characteristic.write(struct.pack('<6s', b'v0.1.1'))
        print("Connection from", connection.device)
        while connection.is_connected():
            await cycling_power.publish_task(connection)

    async def connection_task(self):
        while True:
            connection =  await aioble.advertise (
                250_000,
                name="open-kinetic-pwr",
                services=[self.power_service_uuid, self.device_information_service_uuid],
                appearance=1156)
            asyncio.create_task(self.server_task(connection))

'''

battery

'''

class Battery:

    def __init__(self, pin_adc=5):
        self.level = 60
        self.adc = ADC(Pin(pin_adc)) 
        self.adc.atten(ADC.ATTN_11DB)
        # self.adc.width(ADC.WIDTH_9BIT)  

    def get_level(self):
        return self.level

    async def level_task(self):
        while True:
            self.level = self.adc.read()/511*100
            await asyncio.sleep(120)

'''

weight

'''

class Weight:

    def __init__(self, pin_out=2, pin_clk=3, cf=35):
        self.taste=Pin(1,Pin.IN,Pin.PULL_UP)
        self.weight = 0
        self.hx = HX711(Pin(pin_out),Pin(pin_clk),1)
        self.hx.wakeUp()
        self.hx.tara(25)
        self.hx.calFaktor(cf)

    def get_weight(self):
        return self.weight

    def set_weight(self, weight):
        self.weight = weight

    async def load_sensor_task(self):
        while True:
            if self.taste.value() == 0:
                self.hx.tara(25)
            self.weight += self.hx.masse(10)
            await asyncio.sleep_ms(100)

'''

cadance

'''

class Cadance:

    def __init__(self, pin_hall=7):
        self.revolutions = 0
        self.lastRevTime = 0
        self.lastRevolutions = 0
        self.hall_sensor = Pin(pin_hall,Pin.IN)
        self.hall_sensor.irq(trigger=Pin.IRQ_FALLING, handler=self.hall_sensor_task)
        self.last_time = time.time_ns()

    def get_revolutions(self):
        return self.revolutions
    
    def set_lastRevolutions(self, revolutions):
        self.lastRevolutions = revolutions
    
    def get_lastRevolutions(self):
        return self.lastRevolutions

    def get_lastRevTime(self):
        return self.lastRevTime

    def hall_sensor_task(self, pin):
        self.revolutions += 1
        now = time.time_ns()
        #diff_time = (now - self.last_time)
        #diff_1024 = int(diff_time*(1000/1024)/1e6)
        # TODO now blijft constant!
        self.lastRevTime =  int((now-1)/1e6 % 65536) # 64000 sec / 1000 * 1024  
        #self.last_time = now

# Run tasks.
async def main():
    t1 = asyncio.create_task(battery.level_task())
    t2 = asyncio.create_task(cycling_power.connection_task())
    t4 = asyncio.create_task(weight.load_sensor_task())
    await asyncio.gather(t1, t2, t4)

cadance = Cadance()
weight = Weight(2,3,225)
battery = Battery()
cycling_power = BLE_Cycling_Power()
asyncio.run(main())


