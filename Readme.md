# Intro

This repo shows how to connect devices with limited capabilities reporting telemetry and accepting events to Google Cloud IoT Core. Specifically, we'll assume the devices are not powerful enough to handle all security requirements to connect to the GCP IoT endpoint:
- Generate and sign a JWT token.
- Establish a connection over TLS.

When using Micropython as the programming language for the devices, the libraries involved to do all this may be too much for specific MCU dev boards (they are for sure for ESP8266-base dev boards). Because of this, we'll be using an IoT Gateway that connects to GCP IoT. The actors in the setup will be:
- IoT Registry, MQTT Server: Google Cloud IoT Core.
- IoT Gateway: Raspberry Pi running custom Python code.
- IoT Devices: ESP8266-based Wemos D1 mini devices with support for Micropython and WiFi chipset and antenna.

Your devices will connect to this gateway device through UDP sockets over a local network, which in turn will connect to IoT Core through the MQTT bridge. The example is good since our specific devices have IP connectivity, but not enough power to both sign JWTs and do encrypted connections. So the heavy lifting of the connectivity will be performed by the Pi running the gateway software, in exchange for considerably decreased security in the local network connecting the devices and the gateway.

The high level architecture would be as follows:

<p align="center">
  <img width="" src="img/IoT Gateway Cloud.png">
</p>

We're going through the custom Python code gateway route instead of using Mosquitto because the scenario where you connect an MQTT Gateway in the edge to Google Cloud IoT core is not supported. The Gateway needs to be the MQTT client and be configured a specific way to handle the device identification to the registry.

Other options not explored could have involved both Mosquitto and Node-Red installed in the Raspberry Pi, or using more capable devices, but I wanted to make a point about device capabilites by setting this lab this way.

All this docs has been written with Mac OS X in mind as the Lab Laptop OS. Using other OS's will require some minor changes to the docs and tools involved.

## Bill of materials

Here's what you'll need:

- Raspberry Pi, any model (I've used a model B) with standard Raspberry OS installation.
- SD Card to host the Gateway OS, and a way to insert the card into your PC.
- 1 ESP8266 board with WiFi support (Wemos D1 mini for this lab) and a micro USB cable.
- [Optional] 1 Wemos D1 mini board with the SHT30 sensor hat installed.
- A Google Cloud Project.
- [Optional] Adafruit Serial Cable.
- Access to a WiFi access point with WEP/WPA/WPA2 encryption (certificate based or proxified authentications won't work)

# Laptop Lab setup

First, review the env vars in file `setup-env` file and source it. Make sure you modify at least one important var now, which is `PROJECT_ID` (you can leave the rest unaltered for now):

```bash
vim utils/setup-env
source utils/setup-env
```

Clone the following repository and change into the directory for this tutorial's code:
```bash
git clone gitlab.com/javiercanadillas/iot-gateway-cloud
```

Create a Python virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-devices.txt
```

Get `Pyboard.py` (a tool for managing your devices):
```bash
curl -L https://raw.githubusercontent.com/micropython/micropython/master/tools/pyboard.py --output tools/pyboard.py
chmod 755 tools/pyboard.py
```

Get Micropython:
```bash
curl -OL https://micropython.org/resources/firmware/esp8266-20210202-v1.14.bin
```

Finally, if you don't have it already, [install the Google Cloud SDK by following these instructions](https://cloud.google.com/sdk/docs/install#deb).

You should have all required software now and be ready to proceed with the next steps.

# Cloud Setup

You will be executing all these steps in your lab laptop, as you should have Google Cloud SDK installed there.

Create two Pub Sub topics to support both state and telemetry messages in the MQTT server:
```bash
gcloud pubsub topics create $TELEMETRY_TOPIC --project=$PROJECT_ID
gcloud pubsub topics create $STATE_TOPIC --project=$PROJECT_ID
```

Create an IoT registry:

```bash
gcloud iot registries create ${REGISTRY_ID} \
    --project=${PROJECT_ID} \
    --region=${REGION} \
    --event-notification-config=topic=${TELEMETRY_TOPIC} \
    --state-pubsub-topic=${STATE_TOPIC}
```

Now, create a gateway in the new registry:
```bash
gcloud iot devices create my-gateway \
    --device-type=gateway \
    --project=$PROJECT_ID \
    --region=$REGION \
    --registry=$REGISTRY_ID \
    --public-key path=rsa_public.pem,type=rsa-pem \
    --auth-method=ASSOCIATION_ONLY
```

Let's now create our devices in the registry. Let's start by creating device 1:

```bash
gcloud iot devices create $DEVICE_ID_1 \
  --region $REGION \
  --registry $REGISTRY_ID
```

and bind it to the gateway:

```bash
gcloud iot devices gateways bind \
  --device=$DEVICE_ID_1 \
  --device-region=$REGION \
  --device-registry=$REGISTRY_ID  \
  --gateway=my-gateway \
  --gateway-region=$REGION \
  --gateway-registry=$REGISTRY_ID
```

If you're going to be using an additional device for telemetry events, proceed to register this second device:
```bash
gcloud iot devices create $DEVICE_ID_2 \
  --region $REGION \
  --registry $REGISTRY_ID
```

and bind it to the gateway:
```bash
gcloud iot devices gateways bind \
  --device=$DEVICE_ID_2 \
  --device-region=$REGION \
  --device-registry=$REGISTRY_ID  \
  --gateway=my-gateway \
  --gateway-region=$REGION \
  --gateway-registry=$REGISTRY_ID
```

As a final step, set the initial configuration for the led device in Cloud IoT Core:

```bash
gcloud iot devices configs update \
  --region=$REGION  \
  --registry=$REGISTRY_ID \
  --device=$DEVICE_ID_1  \
  --config-data="ON"
```

and create a subscription to the telemetry topics so later on we can observe any message coming from the devices:

```bash
gcloud pubsub subscriptions create my-subscription --topic ${TELEMETRY_TOPIC}
```

Cloud configuration should be ready to go. Let's move to setting up our IoT components in the field.

# Gateway setup

The first thing to do is to download Raspbian (the full image with Desktop and recommended software) and [follow the official installation guide](https://www.raspberrypi.org/documentation/installation/installing-images/) to flash Raspbian onto your microSD card. If you're starting with this I recommend you using their [Raspberry Pi Imager](https://downloads.raspberrypi.org/imager/imager_1.5.dmg), it's pretty good and convenient, but if you love the command line as I do, [you can try `dd` as well](https://www.raspberrypi.org/documentation/installation/installing-images/mac.md).

Now, you have two paths to follow:

## Headless setup
If you want headless connectivity to your Pi (because you don't have access to additonal monitors, keyboard, mouse, or you don't have the necessary adapters), follow the instructions in [Configuring a headless Raspberry Pi](docs/Configure_RPi_headless.md)

## Regular setup
If you have access to monitor, keyboard, mouse and necessary adapters, follow along:

- Connect your keyboard and mouse to the Raspberry Pi USB ports.
- Connect the Raspberry Pi to a monitor through the HDMI port.
- Insert the microSD card with Raspbian into your Raspberry Pi.
- Attach a power source to the Raspberry Pi using the USB cable (make sure you're sourcing enough current depending on your model, see the oficial specifications).
- Go through the default setup steps for Raspbian upon boot.
- Connect your Pi to your local WiFi or Ethernet in your local network, and do the setup so you can access the Pi through IP
- [Enable SSH access](https://www.raspberrypi.org/documentation/remote-access/ssh/)
- [Enable VNC access](https://www.raspberrypi.org/documentation/remote-access/vnc/). To make sure access work from any device (for instance, Mac OS X clients will require this), disable VNC encryption and setup a VNC specific as mentioned in [Configuring a headless Raspberry Pi](docs/Configure_RPi_headless.md).
- Grab your laptop and check the connectivity to your Pi.
- Power cycle the Pi and make sure you can access the Pi both via VNC and SSH withouth monitor or keyboard/mouse attached this time.

## Setup Gateway software

Now that your basic setup is complete, open a terminal and make sure that git, python3, and other required dependencies are installed. Specifically, for Python you can check with:

```bash
python3 --version
```

If not, install them by running the following:

```bash
sudo apt update && sudo apt upgrade
sudo apt install git
sudo apt install python3
sudo apt install build-essential libssl-dev libffi-dev python3-dev
```

Clone the following repository and change into the directory for this tutorial's code:
```bash
git clone gitlab.com/javiercanadillas/iot-gateway-cloud
```

Generate an RS256 public/private key pair by running the following:
```
./utils/generate_keys.sh
```

Download Google's CA root certificate:
```bash
wget https://pki.goog/roots.pem
```

Now, create a virtual environment to keep installations local to a workspace rather than installing libraries onto your system directly:

``` bash
python3 -m venv venv
source venv/bin/activate
```

Install the gateway software dependencies (Python packages) with pip:

```bas
pip install -r requirements-gateway.txt
```

Ok, you've got the basics of the Gateway completed. Let's now move on to setting up our devices.

# LED Device Setup

## Flashing Micropython

Go back to your laptop, and connect to the first Wemos D1 mini dev board (the one without the sensor hat) through a micro USB cable to it.

Check the port that appears in your PC, in the case of Linux/Mac it should be something like `/dev/cu.usbserial...`. Assign that port in the `setup-env` file and source it:

```bash
vi utils/setup-env
source utils/setup-env
```

You should have all the necessary tools installed from previous steps in your Laptop. First, you're going to check the conection by asking for its flash status:

```bash
esptool.py flash_id
```

Now, let's erase whatever is inside the board and flash the Micropyton image you downloaded before:

```bash
esptool.py erase_flash
esptool.py --baud 1000000 write_flash --flash_size=4MB -fm dio 0 esp8266-20210202-v1.14.bin
```

Connect to the freshly installed micropython REPL in the Wemos device:

```bash
minicom
```

and press ENTER once to get the Micropython REPL. Let's test everything works by typing in:

```python
uos.uname()
```

## Transferring the device software

You need to update the Gateway IP adddress that you wrote down in the previous section in the file `config.py`. If the IP address is `192.18.0.159`, the corresponding section should look as follows:

```text
udp_config = {
    'server_address': '192.168.0.159',
    'port': 10000,
    'buffer_size': 4096
}
```

Use the tool `deploy_device` that will help you deploy Micropython's code to the device:

```bash
utils/deploy_device deploy-main-led
```

You can now disconnect your device.

# Sensor device setup [Optional]

## Flashing Micropython

If you have a second device with the SHT30 sensor hat, disconnect this first device from the micro USB cable, connect the second one, and repeat all the steps in [the previous section](#Flashing-Micropython) to have Micropython flashed in the second device as well.

## Transferring the device software

Use the tool `deploy_device` that will help you deploy Micropython's code to the device:

```bash
utils/deploy_device deploy-main-sensor
```

You can now disconnect your device.

# Running the demo

## Run the gateway

Connect to your gateway. Then, substitute the variables in the `run-gateway` file and run the gateway software:
```bash
envsubst < run-gateway-template > run-gateway
source run-gateway
```

Leave the connection to the gateway opened and the process running so the demo works and you can see the console output.

## Run the devices

Just attach the devices to a power source, they should acquire a valid IP from your WiFi access point and run main.py.

## Change device configuration

Perform a change in the device profile of the registry and watch how the led in the device goes off:

```bash
gcloud iot devices configs update \
  --region=$REGION  \
  --registry=$REGISTRY_ID \
  --device=$DEVICE_ID_1  \
  --config-data="ON"
```

## Get telemetry data

In your lab laptop, connect to the subscription to the telemetry topic that you created before, so you can observe the different messages:

```bash
gcloud pubsub subscriptions pull my-subscription --auto-ack --limit=100
```

You should see something like this:

```text
[...]
│ temperature=27.665, humidity=32.192   │ 2132042286157962 │              │ deviceId=wemos-d1-2                 │                  │
│                                       │                  │              │ deviceNumId=2973720764039275        │                  │
│                                       │                  │              │ deviceRegistryId=gw-registry        │                  │
│                                       │                  │              │ deviceRegistryLocation=europe-west1 │                  │
│                                       │                  │              │ gatewayId=my-gateway                │                  │
│                                       │                  │              │ projectId=javiercm-main-demos       │                  │
│                                       │                  │              │ subFolder=                          │                  │
│ temperature=29.1203, humidity=29.8802 │ 2132001739453284 │              │ deviceId=wemos-d1-2                 │                  │
│                                       │                  │              │ deviceNumId=2973720764039275        │                  │
│                                       │                  │              │ deviceRegistryId=gw-registry        │                  │
│                                       │                  │              │ deviceRegistryLocation=europe-west1 │                  │
│                                       │                  │              │ gatewayId=my-gateway                │                  │
│                                       │                  │              │ projectId=javiercm-main-demos       │                  │
│                                       │                  │              │ subFolder=                          │                  │
│ temperature=27.721, humidity=32.2408  │ 2132042431640268 │              │ deviceId=wemos-d1-2                 │                  │
│                                       │                  │              │ deviceNumId=2973720764039275        │                  │
│                                       │                  │              │ deviceRegistryId=gw-registry        │                  │
│                                       │                  │              │ deviceRegistryLocation=europe-west1 │                  │
│                                       │                  │              │ gatewayId=my-gateway                │                  │
│                                       │                  │              │ projectId=javiercm-main-demos       │                  │
│                                       │                  │              │ subFolder=                          │                  │
[...]
```

# Links

- https://cloud.google.com/community/tutorials/cloud-iot-gateways-rpi