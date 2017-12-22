import serial
import threading
import time

def stripLeadingZeros(num):
    if(len(num) == 0):
        return num
    return str(int(num))

def normalizeSingleAddress(addr):
    result = ''
    latestNumber = ''
    for c in addr:
        if ord(c) >= ord('0') and ord(c) <= ord('9'):
            latestNumber += c
        elif c == '.' or c == ':' or c == '/' or c == '\\' or c == '-':
            result += stripLeadingZeros(latestNumber)+':'
            latestNumber = ''
    return result+stripLeadingZeros(latestNumber)

def normalizeAddress(address):
    if isinstance(address, list):
        return ",".join(list(map(normalizeSingleAddress, address)))
    return normalizeSingleAddress(address)

class LutronRS232(threading.Thread):
    def __init__(self, file, baudrate=115200):
        threading.Thread.__init__(self)
        self.ser = serial.Serial(file, baudrate, timeout=0.5)
        self.serialLock = threading.Lock()
        self.stopEvent = threading.Event()
        self.cachedValues = {}
        self.bufferedRead = ""
        self.writeData("DLMON\r\n") # enable dimmer level monitoring
        self.start()

    def writeData(self, str):
        self.serialLock.acquire()
        try:
            self.ser.write(str.encode('utf-8'))
        finally:
            self.serialLock.release()

    def processLine(self, line):
        parts = list(map(str.strip, line.split(',')))
        if len(parts) > 0:
            if parts[0] == "DL":
                self.cachedValues[normalizeAddress(parts[1])] = int(parts[2])

    def read(self):
        if (self.ser.inWaiting()>0):
            self.bufferedRead += self.ser.read(self.ser.inWaiting()).decode('ascii')
        index = self.bufferedRead.find('\r')
        while index != -1:
            self.processLine(self.bufferedRead[:index])
            self.bufferedRead = self.bufferedRead[index+1:]
            index = self.bufferedRead.find('\r')

    def run(self):
        while not self.stopEvent.isSet():
            self.serialLock.acquire()
            try:
                self.read()
            finally:
                self.serialLock.release()
            

    def setBrightness(self, address, brightness, fadeTime=1, delayTime=0):
        addressNormalized = normalizeAddress(address)
        self.writeData('FADEDIM,'+str(brightness)+','+str(fadeTime)+','+str(delayTime)+','+addressNormalized+'\r\n')
        if isinstance(address, list):
            for a in address:
                self.cachedValues[normalizeAddress(a)] = int(brightness)
        else:
            self.cachedValues[addressNormalized] = int(brightness)

    def forceBrightnessUpdate(self, address, waitTime=0):
        self.writeData('RDL,'+normalizeAddress(address)+'\r\n')
        time.sleep(waitTime)

    def getBrightness(self, address, timeout=2):
        # I think accessing cachedValues is safe, because of this:
        # "Python's built-in data structures (lists, dictionaries, etc.) are thread-safe as a side-effect of having atomic byte-codes for manipulating them"
        # https://pymotw.com/2/threading/#controlling-access-to-resources
        #
        # Also I only ever read in this thread, all writing is done in the other thread
        addressNormalized = normalizeAddress(address)
        if addressNormalized not in self.cachedValues:
            self.serialLock.acquire()
            try:
                self.ser.write(('RDL,'+addressNormalized+'\r\n').encode('utf-8'))
                startTime = time.time()
                while addressNormalized not in self.cachedValues and time.time() < startTime+timeout:
                    self.read()
            finally:
                self.serialLock.release()

            if addressNormalized not in self.cachedValues:
                raise RuntimeError("Couldn't get brightness for address "+addressNormalized)
        return self.cachedValues[addressNormalized]

    def stop(self):
        self.stopEvent.set()

if __name__ == "__main__":
    lutron = LutronRS232('/dev/tty.usbserial')
    time.sleep(2)
    lutron.setBrightness('1.4.2.7.3', 0)
    time.sleep(2)
    lutron.setBrightness('1.4.2.7.3', 50)
    lutron.stop()
