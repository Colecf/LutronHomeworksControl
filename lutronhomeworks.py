import serial
import threading

def normalizeSingleAddress(addr):
    result = ""
    for c in addr:
        if ord(c) >= ord('1') and ord(c) <= ord('9'):
            result += c
        elif c == '.' or c == ':' or c == '/' or c == '\\' or c == '-':
            result += ':'
    return result

def normalizeAddress(address):
    if isinstance(address, list):
        return ",".join(list(map(normalizeSingleAddress, address)))
    return normalizeSingleAddress(address)

class OutputMonitor(threading.Thread):
    def __init__(self, group=None, target=None, name=None,
                 args=(), kwargs=None, verbose=None):
        threading.Thread.__init__(self, group=group, target=target, name=name,
                                  verbose=verbose)
        self.args = args
        self.kwargs = kwargs
        print("Setting up serial: "+kwargs["file"]+" "+str(kwargs["baudrate"]))
        self.ser = serial.Serial(kwargs["file"], kwargs["baudrate"], timeout=0.5)
        self.serialLock = threading.Lock()
        self.cachedValues = {}
        self.bufferedRead = ""


        self.writeData("DLMON\r\n") # enable dimmer level monitoring
        return

    def processLine(self, line):
        parts = list(map(unicode.strip, line.split(',')))
        if len(parts) > 0:
            if parts[0] == "DL":
                self.cachedValues[normalizeAddress(parts[1])] = int(parts[2])

    def run(self):
        while True:
            data_str = ""
            self.serialLock.acquire()
            try:
                if (self.ser.inWaiting()>0):
                    data_str = self.ser.read(self.ser.inWaiting()).decode('ascii')
            finally:
                self.serialLock.release()
            
            self.bufferedRead += data_str
            while self.bufferedRead.find('\r') != -1:
                index = self.bufferedRead.find('\r')
                self.processLine(self.bufferedRead[:index])
                self.bufferedRead = self.bufferedRead[index+1:]

    def writeData(self, str):
        self.serialLock.acquire()
        try:
            print("Writing "+str)
            self.ser.write(str.encode('utf-8'))
        finally:
            self.serialLock.release()

class LutronRS232:
    
    def __init__(self, file, baudrate=115200):
        self.serialManager = OutputMonitor(kwargs={'file': file, 'baudrate': baudrate})
        self.serialManager.daemon = True
        self.serialManager.start()

    def setBrightness(self, address, brightness, fadeTime=1, delayTime=0):
        address = normalizeAddress(address)
        self.serialManager.writeData('FADEDIM,'+str(brightness)+','+str(fadeTime)+','+str(delayTime)+','+address+'\r\n')

    def getBrightness(self, address):
        # I think accessing cachedValues is safe, because of this:
        # "Python's built-in data structures (lists, dictionaries, etc.) are thread-safe as a side-effect of having atomic byte-codes for manipulating them"
        # https://pymotw.com/2/threading/#controlling-access-to-resources
        #
        # Also I only ever read in this thread, all writing is done in the other thread
        return self.serialManager.cachedValues[normalizeAddress(address)]

        

if __name__ == "__main__":
    import time
    lutron = LutronRS232('/dev/tty.usbserial')
    lutron.setBrightness('1.4.2.8.1', 0)
    time.sleep(2)
    lutron.setBrightness('1.4.2.8.1', 50)
    time.sleep(2)
