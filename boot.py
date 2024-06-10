import sys

sys.path.append("")

from micropython import const
from machine import Pin, ADC, I2C, deepsleep
from hx711 import HX711
import machine
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
        #print("battery: {}".format(battery_level))

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
    def __init__(self, pin_adc, indication_pin):
        self.level = 60
        self.indication = indication_pin
        self.adc = ADC(Pin(pin_adc, mode=Pin.IN), atten=ADC.ATTN_11DB)
        #self.adc.atten(ADC.ATTN_6DB)
        self.power_down = False
  

    def get_level(self):
        return self.level
    
    def set_power_down(self):
        self.power_down = True

    async def level_task(self):
        clamp = lambda n, minn, maxn: max(min(maxn, n), minn)
        while True:
            voltage = 0
            for i in range(16):
                voltage += self.adc.read_uv()
            #TODO clean
            self.level = clamp(int((2 * voltage / 16 / 1000 * (3.3 / 4095)) / 3.3 * 100), 1, 99)
            await asyncio.sleep(1)
    
    async def management(self):
        while True:
            #  power on indication
            self.indication.value(1)
            time.sleep(0.5*------)
            self.indication.value(0)
            if (self.power_down) :
                print("zzzzz.....")
                self.indication.value(1)
                time.sleep(5)
                deepsleep()
            await asyncio.sleep(10)

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
        if (not self.weight):
            self.weight = 1
        return self.weight

    def get_samples(self):
        if (not self.samples):
            self.samples = 1
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

    def __init__(self, pin_hall):
        self.revolutions = 0
        self.lastRevTime = 0
        self.lastRevolutions = 0
        pin_hall.irq(trigger=Pin.IRQ_FALLING, handler=self.hall_sensor_task)
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

'''

Controller

'''

class Controller:
    
    def __init__(self):
        hall_sensor_pin = Pin(2, Pin.IN) #TODO doesn't wake up on hall
        pin_awake = Pin(4, Pin.IN)
        esp32.wake_on_ext1((pin_awake, hall_sensor_pin), esp32.WAKEUP_ANY_HIGH)
        indication_pin = Pin(10, Pin.OUT)
        
         # initializing indication
        for i in range(6):
            indication_pin.value(1)
            time.sleep(0.3)
            indication_pin.value(0)
            time.sleep(0.3)
        
        self.cycling_power = BLE_Cycling_Power()
        self.weight = Weight(9, 8, 57.5) # 2, 4 s3
        self.battery = Battery(3, indication_pin)
        self.cadance = Cadance(hall_sensor_pin)
        self.no_connection_counter = 0
        

        


    async def check_activity(self):
        inactivity_time = 50000
        while True:
            print(self.no_connection_counter)
            # TODO check
            lpt = self.cycling_power.last_published_time
            if ((time.time_ns() - lpt) > inactivity_time and not lpt == 0) or self.no_connection_counter == 2:
                self.battery.set_power_down()
            if lpt == 0 :
                # need to go to sleep if there is no connection
                self.no_connection_counter += 1
            await asyncio.sleep(1)
         
    async def tasks(self):
        t0 = asyncio.create_task(self.battery.level_task())
        t1 = asyncio.create_task(self.battery.management())
        t2 = asyncio.create_task(self.cycling_power.connection_task())
        t3 = asyncio.create_task(self.check_activity())
        t4 = asyncio.create_task(self.weight.load_sensor_task())
        await asyncio.gather(t0, t1, t2, t3, t4)
        
# main        
controller = Controller()
def handle_revolution_update():
    controller.cycling_power.publish_task(controller.cadance.get_revolutions(),
                               controller.cadance.get_lastRevTime(), 
                               abs(controller.weight.get_weight())/controller.weight.get_samples(), 
                               controller.battery.get_level(),
                               controller.weight.reset)
controller.cadance.set_callback(handle_revolution_update)

asyncio.run(controller.tasks())






