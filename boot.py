import sys

sys.path.append("")

from micropython import const
from machine import Pin, ADC, I2C
from hx711 import HX711
import esp32
import asyncio
import math
import aioble
import bluetooth
import random
import struct
import ustruct
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
        # Connections
        self.connections = []
        self.last_published_time = 0

    def publish_task(self, revolutions, lastRevTime, force, battery_level, callback):
        # power calculation
        mp = 2 # rouvy=2 garmin=1 TODO sniff brand
        newton_ratio = 0.00980665 #= 1 gram
        meter_per_revolution = 1.09956 #2PI*0.175 need to use bluetooth opcode to set the crunk size
        now = time.time_ns()
        diff_time = (now - self.last_published_time)/1e9
        power = int((force*newton_ratio)*mp*(meter_per_revolution/diff_time))
      
        

        # debugging 
        rpm = 60 / diff_time
        #print("force: {:0.2f}".format(force))
        #print("last rev: {}".format(lastRevTime))
        #print("power: {}".format(power))
        print("revolutions: {}".format(revolutions))
        #print("rpm: {}".format(rpm))
        #print("time: {}".format(diff_time))

        # bluetooth packets
        battery_level_data =  struct.pack('<B', int(battery_level))
        power_data =  struct.pack('<8B',
            0x20, 
            0x00, 
            power & 0xff, 
            power >> 8, 
            revolutions & 0xff, 
            revolutions >> 8,
            lastRevTime & 0xff, 
            lastRevTime >> 8)
        # publish packets
        for c in self.connections:
            self.battery_level_characteristic.notify(c, battery_level_data)
            self.battery_level_characteristic.write(battery_level_data)
            self.measurement_characteristic.notify(c, power_data)
            self.measurement_characteristic.write(power_data)
        
        # save time 
        self.last_published_time = now
        callback()
        

    async def server_task(self, connection):
        # write power specific information
        self.location_characteristic.write(struct.pack('<B',0x05)) # left crunk
        self.feature_characteristic.write(struct.pack('<4B', 0x00, 0x10, 0x00, 0x08)) # non distribution and crank revolution
        # write device information
        self.manufacturer_characteristic.write(struct.pack('<12s', b'open-kinetic'))
        self.software_rev_characteristic.write(struct.pack('<6s', b'v0.1.1'))
        print("Connection from", connection.device)
        self.connections.append(connection)
        while connection.is_connected():
            # TODO handeling opcode
            await asyncio.sleep(60)

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

    def __init__(self, pin_adc):
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

    def __init__(self, pin_out, pin_clk, cf=35):
        
        self.taste=Pin(1,Pin.IN,Pin.PULL_UP)
        self.weight = 0
        self.hx = HX711(Pin(pin_out),Pin(pin_clk),1)
        self.hx.wakeUp()
        self.hx.tara(25)
        self.samples = 0
        self.hx.calFaktor(cf)

       
    def get_weight(self):
        return self.weight

    def get_samples(self):
        return self.samples

    def reset(self):
        self.weight = 0
        self.samples = 0


    async def load_sensor_task(self):
        while True:
            self.samples += 1
            g = self.hx.masse(1)
            self.weight += abs(g)
            # print(g)
            # print(abs(self.weight)/self.samples)
            await asyncio.sleep_ms(50)

'''

cadance

'''

class Cadance:

    def __init__(self, pin_sda, pin_scl):
        self.i2c = I2C(0, sda=Pin(pin_sda), scl=Pin(pin_scl), freq=400000)
        self.i2c.writeto_mem(0x53, 0x2D, bytearray([0x08]))  # Set bit 3 to 1 to enable measurement mode
        self.i2c.writeto_mem(0x53,  0x31, bytearray([0x0B]))  # Set data format to full resolution, +/- 16g
        self.revolutions = 0
        self.lastRevTime = 0
        self.lastRevolutions = 0
        self.c = 0
        self.callback = None

    def read_accel_data(self):
        data = self.i2c.readfrom_mem(0x53, 0x32, 6)
        x, y, z = ustruct.unpack('<3h', data)
        return x

    def get_revolutions(self):
        return self.revolutions
    
    def set_callback(self, callback):
        self.callback = callback

    def get_lastRevTime(self):
        return self.lastRevTime

    async def task(self):
        while True:
            x = self.read_accel_data()
            if x > 50 and self.c == 1:
                self.c = 2
            if x > 50 and self.c == 2:
                self.c = 0
            if x > -50 and x < 50 and self.c == 0:
                self.revolutions += 1
                now = time.ticks_ms()
                now_1024 = now % 65536 # rollover 64000 sec / 1000 * 1024
                self.lastRevTime = now_1024
                self.callback()
                self.c = 1
            await asyncio.sleep_ms(100)


class Cadance_hall:

    def __init__(self, pin_hall):
        self.revolutions = 0
        self.lastRevTime = 0
        self.lastRevolutions = 0
        self.hall_sensor = Pin(pin_hall,Pin.IN)
        self.hall_sensor.irq(trigger=Pin.IRQ_FALLING, handler=self.hall_sensor_task)
        self.callback = None

    def get_revolutions(self):
        return self.revolutions
    
    def set_callback(self, callback):
        self.callback = callback

    def get_lastRevTime(self):
        return self.lastRevTime

    def task(self, pin):
        while True:
            self.revolutions += 1
            now = time.ticks_ms()
            now_1024 = now % 65536 # rollover 64000 sec / 1000 * 1024
            self.lastRevTime =  now_1024
            self.callback()
            


class Cadance_fake:
    
    def __init__(self, weight):
        self.e = 0
        self.weight = weight;
    
    async def task(self):
        print("run fake cadance")
        while True:
            self.e += 1
            lastRevTime = int(time.ticks_ms() % 65536)
            cycling_power.publish_task(self.e,
                                   lastRevTime, 
                                   abs(self.weight.get_weight())/(self.weight.get_samples()+1), 
                                   10,
                                   self.weight.reset)
            await asyncio.sleep_ms(1000) # i.e. 60 rpm


# Run tasks
async def tasks():
    t1 = asyncio.create_task(battery.level_task())
    t2 = asyncio.create_task(cycling_power.connection_task())
    t4 = asyncio.create_task(weight.load_sensor_task())
    t5 = asyncio.create_task(cadance.task()) 
    await asyncio.gather(t1, t2, t4, t5)

# main 
cycling_power = BLE_Cycling_Power()
weight = Weight(2, 3, 57.5)
battery = Battery(5)
cadance = Cadance(6, 7)


def handle_revolution_update():
    cycling_power.publish_task(cadance.get_revolutions(),
                               cadance.get_lastRevTime(), 
                               abs(weight.get_weight())/weight.get_samples(), 
                               battery.get_level(),
                               weight.reset)

cadance.set_callback(handle_revolution_update)
asyncio.run(tasks())