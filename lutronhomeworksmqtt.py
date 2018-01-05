import argparse
import lutronhomeworks as hw
import paho.mqtt.client as mqttlib
import re
import socket
import json
import sys

# addresses are colon separated numbers
# don't use leading zeros, addresses must be exactly this format
# as we use them as dictionary keys
NUMBER = '(?:0|(?:[1-9][0-9]*))'
ADDRESS_STR = '('+NUMBER+'(?:[:]'+NUMBER+')*)'
MQTT_DIMMER_STATE = re.compile('homeworks/dimmer/'+ADDRESS_STR+'/state')
MQTT_DIMMER_COMMAND = re.compile('homeworks/dimmer/'+ADDRESS_STR+'/command')

def onMqttConnect(client, lutron, flags, rc):
    print('Connected!')
    client.subscribe('homeworks/dimmer/#')

def onMqttSubscribe(client, lutron, mid, granted_qos):
    print("Subscribed", mid, granted_qos)
    
def onMqttDisconnect(client, lutron, rc):
    print('Disconnected!')

def onMqttMessage(client, lutron, message):
    print('Received: '+message.topic+": "+message.payload.decode())
    match = MQTT_DIMMER_COMMAND.match(message.topic)
    if match:
        payload = json.loads(message.payload.decode())
        if 'brightness' not in payload:
            payload['brightness'] = 255 if payload['state'] == 'ON' else 0
        payload['brightness'] = int(payload['brightness'] / 255 * 100)
        lutron.setBrightness(match.group(1), payload['brightness'])

def brightnessChanged(mqtt, address, brightness):
    payload = json.dumps({
        "state": "ON" if brightness > 0 else "OFF",
        "brightness": int(brightness / 100 * 255)
    })
    topic = 'homeworks/dimmer/'+address+'/state'
    print("Sending on topic "+topic+": "+payload)
    mqtt.publish(topic, payload, retain=True)

parser = argparse.ArgumentParser(description='Lutron Homeworks MQTT client')
parser.add_argument('serial_interface')
parser.add_argument('-b', '--broker-ip', default='localhost')
parser.add_argument('-u', '--username')
parser.add_argument('-p', '--password')
parser.add_argument('-P', '--broker-port', default=1883, type=int)
parser.add_argument('-B', '--baudrate', default=115200, type=int)
args = parser.parse_args()

lutron = hw.LutronRS232(args.serial_interface, args.baudrate)
mqtt = mqttlib.Client(userdata=lutron)
lutron.brightnessChangedCallback = lambda addr, brightness: brightnessChanged(mqtt, addr, brightness)

if args.username is not None:
    mqtt.username_pw_set(args.username, args.password)

mqtt.on_disconnect = onMqttDisconnect
mqtt.on_message = onMqttMessage
mqtt.on_connect = onMqttConnect
mqtt.on_subscribe = onMqttSubscribe
mqtt.connect(args.broker_ip, args.broker_port)

mqtt.loop_forever()
