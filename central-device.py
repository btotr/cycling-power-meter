from machine import Pin, I2C
from micropython import const

import asyncio
import aioble
import bluetooth

import binascii
import ssd1306



'''

BLE_cycling_power_client

'''
class BLE_cycling_power_client:

    def __init__(self, callback):
        self.callback = callback
        self.sensor_name  = "open-kinetic-pwr"
        self.power_service_uuid = bluetooth.UUID(0x1818)
    
    async def connection_task(self):

        self.device = await self.find_power_sensor()
        self.connection = await self.device.connect(timeout_ms=10000)
        async with self.connection:
            print("trying to connect")
            power_service = await self.connection.service(self.power_service_uuid)
            power_characteristic = await power_service.characteristic(bluetooth.UUID(0x2a63))
            await power_characteristic.subscribe(notify=True)
            while True:
                power_data = await power_characteristic.notified()
                self.power_data_handler(power_data)
                await asyncio.sleep_ms(1000)
 
    def power_data_handler(self, data):
        c_data = str(binascii.hexlify(data))
        pwr = int(c_data[6:8], 16)
        print("power data", pwr)
        self.callback(pwr)

    async def find_power_sensor(self):
        print("find power meter", self.sensor_name)
        async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
            async for result in scanner:
                if result.name() == self.sensor_name and self.power_service_uuid in result.services():
                    return result.device
        return None

'''

Display

'''

class OLED_output:

    def __init__(self):
        self.i2c = I2C(sda=Pin(5), scl=Pin(4))
        self.screen = ssd1306.SSD1306_I2C(128, 64, self.i2c)

    def update(self, data):
        self.screen.fill(0)
        self.screen.text(str(data),0,0,1)
        self.screen.show()

async def main():
    await asyncio.create_task(cycling_power.connection_task())


output = OLED_output()
cycling_power = BLE_cycling_power_client(output.update)

asyncio.run(main())

