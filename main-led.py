import machine
from machine import Pin
import usocket
import utime
import ubinascii
import ntptime
import config
import network
import sys

sta_if = network.WLAN(network.STA_IF)

# Set up globals
#device_id = ubinascii.hexlify(machine.unique_id()).decode()
device_id = config.led_config['device-id']
server_address = (config.udp_config['server_address'], config.udp_config['port'])

# Set led
led = Pin(config.led_config['led_pin'], Pin.OUT)

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
	sock.sendto(message.encode(), server_address)

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
		RunAction('detach')
		RunAction('attach')
		RunAction('event', 'Test event is ON')
		RunAction('subscribe')

		while True:
			response = client_sock.recv(config.udp_config['buffer_size']).decode('utf8')
			print('Client received {}'.format(response))
			if response.upper() == 'ON' or response.upper() == b'ON':
					led(0)
					print(" LED is ON ")
			elif response.upper() == "OFF" or response.upper() == b'OFF':
					led(1)
					print(' LED is OFF ')
			else:
					print('Invalid message {}'.format(response))
	
	finally:
		print('closing socket', file=sys.stderr)
		client_sock.close()
