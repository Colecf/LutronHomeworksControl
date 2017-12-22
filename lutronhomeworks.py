import serial
import threading
import time
import queue

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
        self.txQueue = queue.Queue()
        self.stopEvent = threading.Event()
        self.cachedValues = {}
        self.bufferedRead = ""

        # set this to be notified when a light changes
        # note that it will call in a seperate thread, so
        # any communication with your main code must be thread-safe
        self.brightnessChangedCallback = None

        self.writeData("DLMON\r\n") # enable dimmer level monitoring
        self.start()

    def writeData(self, str):
        self.txQueue.put(str)

    def setCachedBrightness(self, address, brightness):
        if isinstance(address, list):
            for a in address:
                self.cachedValues[normalizeAddress(a)] = int(brightness)
                if callable(self.brightnessChangedCallback):
                    self.brightnessChangedCallback(normalizeAddress(a), int(brightness))
        else:
            self.cachedValues[normalizeAddress(address)] = int(brightness)
            if callable(self.brightnessChangedCallback):
                self.brightnessChangedCallback(normalizeAddress(address), int(brightness))

    def processLine(self, line):
        parts = list(map(str.strip, line.split(',')))
        if len(parts) > 0:
            if parts[0] == "DL":
                self.setCachedBrightness(parts[1], parts[2])

    def run(self):
        while not self.stopEvent.isSet():
            while self.ser.inWaiting()>0:
                self.bufferedRead += self.ser.read(self.ser.inWaiting()).decode('ascii')
            index = self.bufferedRead.find('\r')
            while index != -1:
                self.processLine(self.bufferedRead[:index])
                self.bufferedRead = self.bufferedRead[index+1:]
                index = self.bufferedRead.find('\r')

            while not self.txQueue.empty():
                self.ser.write(self.txQueue.get().encode('utf-8'))
            
    def setBrightness(self, address, brightness, fadeTime=1, delayTime=0):
        addressNormalized = normalizeAddress(address)
        self.writeData('FADEDIM,'+str(brightness)+','+str(fadeTime)+','+str(delayTime)+','+addressNormalized+'\r\n')
        self.setCachedBrightness(address, brightness)

    def forceBrightnessUpdate(self, address):
        self.writeData('RDL,'+normalizeAddress(address)+'\r\n')

    def getBrightness(self, address, timeout=2):
        addressNormalized = normalizeAddress(address)
        if addressNormalized not in self.cachedValues:
            self.forceBrightnessUpdate(address)
            startTime = time.time()
            while addressNormalized not in self.cachedValues and time.time() < startTime+timeout:
                time.sleep(0.01)

            if addressNormalized not in self.cachedValues:
                raise RuntimeError("Couldn't get brightness for address "+addressNormalized)
        return self.cachedValues[addressNormalized]

    def stop(self):
        self.stopEvent.set()
        self.join()

if __name__ == "__main__":
    lutron = LutronRS232('/dev/tty.usbserial')
    lutron.brightnessChangedCallback = lambda address, brightness: print(address+": "+str(brightness))
    lutron.setBrightness('1.4.2.7.3', 0)
    time.sleep(2)
    lutron.setBrightness('1.4.2.7.3', 50)
    time.sleep(1)
    lutron.stop()
