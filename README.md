# Kinetic-pwr an open cycling power meter

This project aims to provide a simple open cycling power meter to extend, learn and being independently creative. It uses an easy-to-learn programming language ([micropython](https://micropython.org/)) and runs on widely available and inexpensive hardware like HX711 and ESP32 to be accessible to a broad audience. For compatibility reasons it uses an open specification, the Bluetooth cycling power profile. Al code is open and licences under a [free software license](https://raw.githubusercontent.com/btotr/cycling-power-meter/main/LICENSE)

## instructions
coming soon

## notes
Currently tested with [Rouvy](https://rouvy.com/), [Garmin forerunner 935](https://www.garmin.com/en-US/p/564291) and [Wahoo elements bold v2](https://eu.wahoofitness.com/devices/bike-computers/elemnt-bolt-buy). Garmin and Rouvy are running fine however Wahoo isn't finding the device. 

Addition [files for calibration could be find here](https://github.com/btotr/force-calibration) and a [case](https://github.com/btotr/kinetic-pw-case) is in development. A bare minimal micropython [client implementation](https://gist.github.com/btotr/462ab281c35927629a8f70ec4f23cb6f) is available as gist



## based on the following work
- [in depth instructions for strain gauges on power meters](https://www.youtube.com/@kwakeham) from Keith Wakeman
- [HX711 library and calibration instructions](https://www.azdelivery.de/blogs/azdelivery-blog-fur-arduino-und-raspberry-pi/digitalwaage-mit-hx711-und-esp8266-esp32-in-micropython) from Jürgen Grzesina
- [Simple Peripheral bluetooth example in micropython](https://github.com/jcardenal/BLEexample/tree/master/Peripheral/py) from Jesús Cardenal Escribano
- [Similair project in C++ with step by step instructions](https://gitlab.com/tbressers/power/-/wikis/home?version_id=5ca1941095dd4ada6b218e4f30f58e189ba50af5) by Thijs Bressers
