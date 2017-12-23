import argparse
import lutronhomeworks as hw
import paho.mqtt.client as mqttlib
import re
import socket
import json
import sys

# addresses as documented under "Device Address Formatting" of
# this pdf: http://www.lutron.com/TechnicalDocumentLibrary/HWI%20RS232%20Protocol.pdf
# except for letters, as supporting / and letters would make it difficult
# to differentiate the address from the rest of the MQTT topic 
# not that supporting this really matters, as they come out in a different
# format when using dimmer monitoring anyways...
NUM_OR_SPACE_STR = '(?:[0-9]+[ ]*)+'
ENCLOSED_ADDRESS_STR = '(?:'+NUM_OR_SPACE_STR+'(?:[.:\\/-]'+NUM_OR_SPACE_STR+')*)'
ADDRESS_STR = '('+ENCLOSED_ADDRESS_STR+'|(?:\['+ENCLOSED_ADDRESS_STR+'\]))'
MQTT_DIMMER_STATE = re.compile('homeworks/dimmer/'+ADDRESS_STR+'/state')
MQTT_DIMMER_COMMAND = re.compile('homeworks/dimmer/'+ADDRESS_STR+'/command')


def brightnessChanged(address, brightness):
    payload = json.dumps({
        "state": "ON" if brightness > 0 else "OFF",
        "brightness": brightness
    })
    topic = 'homeworks/dimmer/'+address+'/state'
    print("Sending on topic "+topic+": "+payload)
    mqtt.publish(topic, payload)

def onMqttDisconnect(client, lutron, rc):
    print('Disconnected!')
#    # Disconnected because we called disconnect()
#    if rc == 0:
#        return
#
#    while True:
#        try:
#            if client.reconnect() == 0:
#                break
#        except socket.error:
#            pass
#        time.sleep(5)

def onMqttMessage(client, lutron, message):
    print(message.topic+": "+message.payload)
    match = MQTT_DIMMER_COMMAND.match(message.topic)
    if match:
        lutron.setBrightness(match.group(0), json.loads(message.payload).brightness)

def onMqttConnect(client, lutron, flags, rc):
    print('Connected!')
    client.subscribe('homeworks/dimmer/#')

parser = argparse.ArgumentParser(description='Lutron Homeworks MQTT client')
parser.add_argument('serial_interface')
parser.add_argument('-b', '--broker-ip', default='localhost')
parser.add_argument('-u', '--username')
parser.add_argument('-p', '--password')
parser.add_argument('-P', '--broker-port', default=1883, type=int)
parser.add_argument('-B', '--baudrate', default=115200, type=int)
#parser.add_argument('-a', '--address', action='append')
args = parser.parse_args()

#for i in range(len(args.address)):
#    args.address[i] = 

lutron = hw.LutronRS232(args.serial_interface, args.baudrate)
lutron.brightnessChangedCallback = brightnessChanged

mqtt = mqttlib.Client(userdata=lutron)
if args.username is not None:
    mqtt.username_pw_set(args.username, args.password)

mqtt.on_disconnect = onMqttDisconnect
mqtt.on_message = onMqttMessage
mqtt.on_connect = onMqttConnect
mqtt.connect(args.broker_ip, args.broker_port)

mqtt.loop_forever()

