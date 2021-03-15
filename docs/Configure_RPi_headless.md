# Initial SD Card setup

Mount your SDCard in your PC and access the `boot` directory. Therey, you need to do three things:

1. Create an empty ssh file, marking the enablement of the SSH daemon
  ```bash
  touch ssh
  ```
2. Configure the on boot wifi by creating a **`/boot/wpa_supplicant.conf`** and modifying your network configuration `ssid` and `psk` to match your wifi network configuration:
  ```text
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

network={
     ssid="Your network name/SSID"
     psk="Your WPA/WPA2 security key"
     key_mgmt=WPA-PSK
}
  ```
3. Enable UART to allow serial connection to the RPi by adding the following the **`/boot/config.txt`** file:
```text
# Enable UART
enable_uart=1
```

# Connect to the RPi Zero Wireless

You have two connection options:

1. Through SSH: the Pi should have connected to the WiFi you set up before. Find out the IP your DHCP has assigned to it, and connect to it using the credentials `pi/raspberrypi`
2. Through serial: connect the four cables as specified in this Adafruit page. Note that you will need a serial cable (Adafruit's one is perfect) and the cable can power the Pi itself.

For serial connection, please connect an Adafruit cable as shown in the image (**only connect the Vcc terminal if you're *not* powering up the Pi with a power USB cable**):

<p align="center">
  <img width="460" src="../img/raspberry_pi_gpio_connection.jpeg">
</p>

# Enable VNC access

Now that you have access to the Pi, we'll configure VCN to be able to have graphical access to Raspbian OS.

## Enable the service

Run [**Raspi-config**](https://www.raspberrypi.org/documentation/configuration/raspi-config.md) and enable VNC:

```bash
sudo raspi-config
```

## Additional VNC configuration

If you rebooted after applying changes with `raspi-config`, relog into the RPiW, and become root
```bash
sudo su -
```

Set a VNC password:
```bash
vncpasswd -service
```

Enable VNC authentication and disable encryption
```bash
cat <<EOF >> /root/.vnc/config.d/vncserver-x11
Authentication=VncAuth
Encryption=PreferOff
EOF
```

The final file should like something like this:
```text
Password=[REDACTED]
Authentication=VncAuth
Encryption=PreferOff
```

Reboot your Pi and test everything:

```bash
sudo shutdown -r now
```