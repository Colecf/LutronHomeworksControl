# Lutron Homeworks Control

This is a simple python 3 library to control lights on a Lutron Homeworks system. It only supports the RS-232 interface as documented in [this pdf.](http://www.lutron.com/TechnicalDocumentLibrary/HWI%20RS232%20Protocol.pdf)

## Usage

```
from LutronHomeworks import LutronRS232

lutron = LutronRS232('/dev/tty.usbserial')
lutron.setBrightness('1.4.2.8.1', 0)
time.sleep(2)
lutron.setBrightness('1.4.2.8.1', 50)
```


### Future plans

- Ethernet interface (currently only works with RS-232 port)
