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
        # Connections
        self.connections = []
        self.last_published_time = 0

    def publish_task(self, revolutions, lastRevTime, force, battery_level, callback):
        # power calculation
        mp = 1 # rouvy=2 garmin=1 TODO sniff brand
        newton_ratio = 0.00980665 # 1 gram
        meter_per_revolution = 1.09956 #2PI*0.175 need to use bluetooth opcode to set the crunk size
        now = time.time_ns()
        diff_time = (now - self.last_published_time)/1e9
        power = int(force*newton_ratio*mp*(meter_per_revolution/diff_time))
      
        

        # debugging 
        rpm = 60 / diff_time
        print("force: {:0.2f}".format(force))
        #print("last rev: {}".format(lastRevTime))
        print("power: {}".format(power))
        #print("revolutions: {}".format(revolutions))
        print("rpm: {}".format(rpm))
        print("time: {}".format(diff_time))

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
            self.weight += self.hx.masse(1)
            self.samples += 1
            #print(self.weight)
            #print(abs(self.weight)/self.samples)
            await asyncio.sleep_ms(100)

'''

cadance

'''

class Cadance:

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

    def hall_sensor_task(self, pin):
        self.revolutions += 1
        now = time.ticks_ms()
        now_1024 = now % 65536 # rollover 64000 sec / 1000 * 1024
        self.lastRevTime =  now_1024
        self.callback()


class Fake_cadance:
    
    def __init__(self, weight):
        self.e = 0
        self.weight = weight;
        self.run()
    
    def run(self):
        print("run fake cadance")
        while True:
            self.e += 1
            lastRevTime = int(time.ticks_ms() % 65536)
            cycling_power.publish_task(self.e,
                                   lastRevTime, 
                                   abs(self.weight.get_weight())/(self.weight.get_samples()+1), 
                                   10,
                                   self.weight.reset)
            time.sleep_ms(1000) # i.e. 60 rpm


# Run tasks
async def tasks():
    t1 = asyncio.create_task(battery.level_task())
    t2 = asyncio.create_task(cycling_power.connection_task())
    t4 = asyncio.create_task(weight.load_sensor_task())
    await asyncio.gather(t1, t2, t4)

# main 
cycling_power = BLE_Cycling_Power()
weight = Weight(2, 3, 30)
#cadance = Cadance(7)
cadance = Fake_cadance(weight)


battery = Battery(5)



def handle_revolution_update_b():
    cycling_power.publish_task(cadance.get_revolutions(),
                               cadance.get_lastRevTime(), 
                               abs(weight.get_weight())/weight.get_samples(), 
                               battery.get_level(),
                               weight.reset)

#cadance.set_callback(handle_revolution_update)
asyncio.run(tasks())


