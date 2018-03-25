import argparse
import lutronhomeworks as hw
import paho.mqtt.client as mqttlib
import re
import socket
import json
import sys
import threading, sched

# addresses are colon separated numbers
# don't use leading zeros, addresses must be exactly this format
# as we use them as dictionary keys
NUMBER = '(?:0|(?:[1-9][0-9]*))'
ADDRESS_STR = '('+NUMBER+'(?:[:]'+NUMBER+')*)'
MQTT_DIMMER_STATE = re.compile('homeworks/dimmer/'+ADDRESS_STR+'/state')
MQTT_DIMMER_COMMAND = re.compile('homeworks/dimmer/'+ADDRESS_STR+'/command')

oldBrightnesses = {}
oldBrightnessesLock = threading.Lock()
scheduler = sched.scheduler()

def saveOldBrightnesses(fileName, time):
    try:
        with open(fileName, "wt") as cacheFile:
            oldBrightnessesLock.acquire()
            json.dump(oldBrightnesses, cacheFile)
            oldBrightnessesLock.release()
        print("Saved cache to "+fileName)
    except OSError as e:
        print("[WARNING] Unable to open cache file: "+e.strerror)
    scheduler.enter(time, 1, saveOldBrightnesses, argument=(fileName,time))
    
def onMqttConnect(client, lutron, flags, rc):
    print('Connected!')
    client.subscribe('homeworks/dimmer/#')

def onMqttSubscribe(client, lutron, mid, granted_qos):
    print("Subscribed", mid, granted_qos)
    
def onMqttDisconnect(client, lutron, rc):
    print('Disconnected!')

def onMqttMessage(client, lutron, message):
    try:
        print('Received: '+message.topic+": "+message.payload.decode())
        match = MQTT_DIMMER_COMMAND.match(message.topic)
        if match:
            payload = json.loads(message.payload.decode())
            address = match.group(1)
            if 'brightness' not in payload:
                if payload['state'] == 'ON':
                    oldBrightnessesLock.acquire()
                    if address in oldBrightnesses:
                        payload['brightness'] = int(oldBrightnesses[address]*255/100)
                    else:
                        payload['brightness'] = 255
                    oldBrightnessesLock.release()
                else:
                    payload['brightness'] = 0
            payload['brightness'] = int(payload['brightness'] / 255 * 100)
            lutron.setBrightness(address, payload['brightness'])
    except json.decoder.JSONDecodeError:
        print("[WARNING] Invalid MQTT message. Topic: "+message.topic+" Payload: "+message.payload.decode())

def brightnessChanged(mqtt, address, brightness):
    payload = json.dumps({
        "state": "ON" if brightness > 0 else "OFF",
        "brightness": int(brightness / 100 * 255)
    })
    topic = 'homeworks/dimmer/'+address+'/state'
    print("Sending on topic "+topic+": "+payload)
    mqtt.publish(topic, payload, retain=True)

    # Hack to deal with improperly wired lights that
    # flicker between 0 and a low value (3 in our case)
    # Can also be nice to not save a super low value
    # so you don't think it didn't actually turn on
    # when in turns on very slightly
    if brightness >= 5:
        oldBrightnessesLock.acquire()
        oldBrightnesses[address] = brightness
        oldBrightnessesLock.release()

parser = argparse.ArgumentParser(description='Lutron Homeworks MQTT client')
parser.add_argument('serial_interface')
parser.add_argument('-b', '--broker-ip', default='localhost')
parser.add_argument('-u', '--username')
parser.add_argument('-p', '--password')
parser.add_argument('-P', '--broker-port', default=1883, type=int)
parser.add_argument('-B', '--baudrate', default=115200, type=int)
parser.add_argument('-c', '--cache-file', default='lutroncache.json')
parser.add_argument('-t', '--cache-save-time', default=3600, type=int)
args = parser.parse_args()

try:
    with open(args.cache_file) as cacheFile:
        oldBrightnesses = json.load(cacheFile)
    if type(oldBrightnesses) is not dict:
        oldBrightnesses = {}
        print("[WARNING] Cache file is not dictionary")
    for key in oldBrightnesses:
        if type(oldBrightnesses[key]) is not int:
            oldBrightnesses[key] = 255
            print("[WARNING] Cache has invalid entry at address "+key)
except OSError as e:
    print("[WARNING] Unable to open cache file: "+e.strerror)
except json.decoder.JSONDecodeError:
    print("[WARNING] Unable to decode cache file")

lutron = hw.LutronRS232(args.serial_interface, args.baudrate)

# load the current state of all the lights
for key in oldBrightnesses:
    lutron.forceBrightnessUpdate(key)

mqtt = mqttlib.Client(userdata=lutron)
lutron.brightnessChangedCallback = lambda addr, brightness: brightnessChanged(mqtt, addr, brightness)

if args.username is not None:
    mqtt.username_pw_set(args.username, args.password)

mqtt.on_disconnect = onMqttDisconnect
mqtt.on_message = onMqttMessage
mqtt.on_connect = onMqttConnect
mqtt.on_subscribe = onMqttSubscribe
mqtt.connect(args.broker_ip, args.broker_port)
mqtt.loop_start()

scheduler.enter(args.cache_save_time, 1, saveOldBrightnesses, argument=(args.cache_file,args.cache_save_time))
scheduler.run()
