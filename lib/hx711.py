# hx711.py
# Modul und Klasse zur bedienung des 24-Bit ADC HX711
# Datenblatt: https://datasheetspdf.com/pdf-file/842201/Aviasemiconductor/HX711/1
# 
from time import sleep_us, ticks_ms

class DeviceNotReady(Exception):
    def __init__(self):
        print("Fehler\nHX711 antwortet nicht")


class HX711(DeviceNotReady):
    KselA128 = const(1)
    KselB32 = const(2)
    KselA64 = const(3)
    Dbits =const(24)
    MaxVal = const(0x7FFFFF)
    MinVal = const(0x800000)
    Frame = const(1<<Dbits)
    ReadyDelay = const(3000) # ms
    WaitSleep =const(60) # us
    ChannelAndGain={
        1:("A",128),
        2:("B",32),
        3:("A",64),
        }
    KalibrierFaktor=1104
    
    def __init__(self, dOut, pdSck, ch=KselA128):
        self.data=dOut
        self.data.init(mode=self.data.IN)
        self.clk=pdSck
        self.clk.init(mode=self.clk.OUT, value=0)
        self.channel=ch
        self.tare=0
        self.cal=HX711.KalibrierFaktor
        self.waitReady()
        k,g=HX711.ChannelAndGain[ch]
        print("HX711 bereit auf Kanal {} mit Gain {}".\
              format(k,g))
        
    def TimeOut(self,t):
        start=ticks_ms()
        def compare():
            return int(ticks_ms()-start) >= t
        return compare
    
    def isDeviceReady(self):
        return self.data.value() == 0
    
    def waitReady(self):
        delayOver = self.TimeOut(ReadyDelay)
        while not self.isDeviceReady():
            if delayOver():
                raise DeviceNotReady()
    
    def convertResult(self,val):
        if val & MinVal:
            val -= Frame
        return val
    
    def clock(self):
        self.clk.value(1)
        self.clk.value(0)
    
    def kanal(self, ch=None):
        if ch is None:
            ch,gain=HX711.ChannelAndGain[self.channel]
            return ch,gain
        else:
            assert ch in [1,2,3], "Falsche Kanalnummer: {}\nKorrekt ist 1,2 3".format(ch)
            self.channel=ch
            if not self.isDeviceReady():
                self.waitReady()
            for n in range(Dbits + ch):
                self.clock()
                
    def getRaw(self, conv=True):
        if not self.isDeviceReady():
            self.waitReady()
        raw = 0
        for b in range(Dbits-1):
            self.clock()
            raw=(raw | self.data.value())<< 1 
        self.clock()
        raw=raw | self.data.value()
        for b in range(self.channel):
            self.clock()
        if conv:
            return self.convertResult(raw)

        else:
            return raw
    
    def mean(self, n):
        s=0
        for i in range(n):
            s += self.getRaw()
        return int(s/n) 
    
    def tara(self, n):
        self.tare = self.mean(n)
        return self.tare
        
    def masse(self,n):
        g=(self.mean(n)-self.tare) / self.cal
        return g
        
    def calFaktor(self, f=None):
        if f is not None:
            self.cal = f
        else:
            return self.cal
        
    def wakeUp(self):
        self.clk.value(0)
        self.kanal(self.channel)

    def toSleep(self):
        self.clk.value(0)
        self.clk.value(1)
        sleep_us(WaitSleep)
            
    
    
