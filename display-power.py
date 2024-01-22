from machine import Pin, I2C
from micropython import const

import asyncio
import aioble
import bluetooth

import binascii
import ssd1306

# using default address 0x3C
i2c = I2C(sda=Pin(5), scl=Pin(4))
display = ssd1306.SSD1306_I2C(128, 64, i2c)

#address = "DC:B4:83:07:90:3E"
address = None

_POWER_SENSOR_NAME = "KICKR CORE 3250"
_POWER_SERVICE_UUID = bluetooth.UUID(0x1818)
_POWER_CHARACTERISTIC_UUID = bluetooth.UUID(0x2a63)

def _power_data_handler(data):
    c_data = str(binascii.hexlify(data))
    hr = int(c_data[6:8], 16)
    display.fill(0)
    display.text(str(hr), 0, 0, 1)
    display.show()
    print(hr)


async def find_power_sensor():
    async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
        async for result in scanner:
            if result.name() == _POWER_SENSOR_NAME and _POWER_SERVICE_UUID in result.services():
                return result.device
    return None

_init = True
async def main():
    global _init
    if address:
        device = aioble.Device(aioble.ADDR_RANDOM, address)
    else:
        device = await find_power_sensor()
    if not device:
        print("power sensor not found")
        return

    try:
        if _init:
            print("Connecting to", device)
        connection = await device.connect(timeout_ms=5000)
    except asyncio.TimeoutError:
        if _init:
            print("Timeout during connection")
        return
    _init = False

    async with connection:
        try:
            hr_service = await connection.service(_POWER_SERVICE_UUID)
            hr_characteristic = await hr_service.characteristic(_POWER_CHARACTERISTIC_UUID)
        except asyncio.TimeoutError:
            print("Timeout discovering services/characteristics")
            return

        await hr_characteristic.subscribe(notify=True)
        while True:
            try:
                power_data = await hr_characteristic.notified()
                _power_data_handler(power_data)
                await asyncio.sleep_ms(1000)
            except:
                print("DeviceDisconnected Exit")
                return


asyncio.run(main())

