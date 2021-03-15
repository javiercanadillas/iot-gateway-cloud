import machine
from sht30 import SHT30
import usocket
import utime
import ubinascii
import ntptime
import config
import network
import sys
import random

sta_if = network.WLAN(network.STA_IF)

# Set up globals
#device_id = ubinascii.hexlify(machine.unique_id()).decode()
device_id = config.sensor_config['device-id']
server_address = (config.udp_config['server_address'], config.udp_config['port'])

# Creating a UDP socket
client_sock = usocket.socket(usocket.AF_INET, usocket.SOCK_DGRAM)

def connect():
	if not sta_if.isconnected():
		print('Connecting to network...')
		sta_if.active(True)
		sta_if.connect(config.wifi_config['ssid'], config.wifi_config['password'])
		while not sta_if.isconnected():
			pass
	print('network config: {}'.format(sta_if.ifconfig()))

def set_time():
	ntptime.settime()
	tm = utime.localtime()
	tm = tm[0:3] + (0,) + tm[3:6] + (0,)
	machine.RTC().datetime(tm)
	print('current time: {}'.format(utime.localtime()))

def SendCommand(sock, message):
	print('sending "{}"'.format(message))
	sock.sendto(message.encode('utf8'), server_address)

	# Receive response
	print('waiting for response')
	response = sock.recv(config.udp_config['buffer_size'])
	print('received: "{}"'.format(response))
	
	return response

def RunAction(action, data=''):
	global client_sock
	message = MakeMessage(device_id, action, data)
	if not message:
			return
	print('Send data: {} '.format(message))
	event_response = SendCommand(client_sock, message)
	print('Response: {}'.format(event_response))

def MakeMessage(device_id, action, data=''):
	if data:
		return '{{ "device" : "{}", "action":"{}", "data" : "{}" }}'.format(
			device_id, action, data)
	else:
		return '{{ "device" : "{}", "action":"{}" }}'.format(
			device_id, action)

if __name__ == '__main__':

	connect()
	set_time()

	try:
		sensor = SHT30()
		random.seed()
		RunAction('detach')
		RunAction('attach')

		while True:
			temp, hum = sensor.measure()
			message = MakeMessage(
				device_id,
				'event',
				'temperature={}, humidity={}'.format(temp, hum)
			)
			SendCommand(client_sock, message)
			utime.sleep(2)
	
	finally:
		print('closing socket', file=sys.stderr)
		client_sock.close()
