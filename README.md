Micro Hexapod Robot
===================

**Table of Content**

1. [Introduction](#introduction)
2. [Locomotion](#locomotion)
3. [Firmware](#firmware)
	1. [Control Protocol](#control-protocol)
		1. [Web Sockets](#web-sockets)
			1. [WS Actions](#ws-actions)
				1. [version](#version)
				2. [active](#active)
				3. [memory](#memory)
				4. [trim](#trim)
				5. [center](#center)
				6. [motion](#motion)
				7. [dir](#dir)
				8. [speed](#speed)
				9. [angle](#angle)
				10. [stroke](#stroke)
				11. [obst](#obst)
	2. [Web Interface](#web-interface)
	3. [Python](#python)
2. [Operation](#operation)
3. [Development](#development)
	1. [3D Design](#3d-design)
	2. [Firmware](#firmware)
		1. [Dev environment](#dev-environment)
		2. [Firmware upload](#firmware-upload)
		3. [Testing locally](#testing-locally)
3. [Visuals](#visuals)
4. [Resources](#resources)

![Hexapod Isometric View](docs/hexapod_iso.png "Hexapod 3D")

## Introduction
This is a project to build a micro [hexapod] type robot using only 3 hobby
servos and MCU like ESP32 or similar that has WiFi or Bluetooth connectivity
options. Other sensors, like an [HC-SR04] Ultrasonic Distance sensor, or maybe
an [IMU] could optionally be added. The firmware is written in [MicroPython]

The body is be 3D printed and once all the electronics are tested and
completed, a custom driver board including the MCU, battery management, sensor
drivers and connectors, etc. can be designed and manufactured.

## Locomotion

_TBD - describe the locomotion_

## Firmware

### Control Protocol

#### Web Sockets

For control over a WebSocket (WS), the Hexapod will listen for a WS connection
on the URI `http://hostname.dom.main/ws`. Once the WS connection has been
established, it uses a very simple protocol for communication.

All messages are made up as string with the format:

    action[:args]

where:  
    `action`: is a predefined action string - see below
    `args`:   optional arguments that the action may require. This could be any
            format that makes sense for the action. For simple arguments this
            could a single string, or a colon separated args string. For more
            complex args, this could be a JSON encoded string.

##### WS Actions

The various actions currently supported by the WS protocol is defined below.

Keys are:

* `HP` : When received by the Hexapod
* `CL` : When received by the JS UI client.

###### version

**Format**: `version:[maj.min.patch]`

* `HP`: responds by sending a `version` action with the current API version
* `CL`: expects a version response with the current API version.

###### active

**Format**: `active:ping|pong`

* `HP`: responds to a ping by sending `pong`
* `CL`: responds to a ping by sending `pong`

###### memory

**Format**: `memory:[alloc:free]`

* `HP`: responds by sending the currently allocated and free memory as bytes
      values
* `CL`: expects a memory response with the allocated and free values as
      indicated.

###### trim

**Format**: `trim:[left:mid:right:[center]]`

* `HP`: sets and saves the servo trim values if the trim values have been
      passed in. The center field is optional and if supplied should be 'true'
      or 'false', defaulting to false if not supplied. If true, the servos will
      be centered after setting the trim values.  Always responds with the
      current trim values.
* `CL`: expects a response as indicated with current trim value - sans the
      center field. If there was an error setting the values, the args string
      will be "err:error message"

###### center

**Format**: `center`

* `HP`: stops the servos, centers them taking trim values into account.  Since
      centering the servos will cause the pause state be entered, a
      `motion:state` response will be received to indicate the current state of
      motion. No response specific to the centering will be received.
* `CL`: ignored

###### motion

**Format**: `motion:run|pause`

* `HP`: run or pause the oscillators
* `CL`: indicator or ''run' or 'pause' to indicate the current state

###### dir

**Format**: `dir:fwd|rev|rotr|rotl`

* `HP`: set the direction to forward or reverse or starts rotating left or
      right on the spot. Will automatically reset steer angle to 0% and send a
      `steer` action with newly set 0° angle arg
* `CL`: indicator that fwd, rev direction, or rotl or rotr rotation have been
      set

###### speed

**Format**: `speed:int`

* `HP`: set the speed to the integer percentage argument between 0% and 100%
* `CL`: indicator that current speed has been set to this percentage value

###### angle

**Format**: `angle:[-]int`

* `HP`: set the steering angle to the integer angle between -90° and 90°, with
      0° being straight ahead
* `CL`: indicator that steering angle has been set to this angle

###### stroke

**Format**: `stroke:int`

* `HP`: set the stroke to the integer percentage argument between 0% and 100%
* `CL`: indicator that current stroke has been set to this percentage value

###### obst

**Format**: `obst:float|clear`

* `HP`: ignored
* `CL`: indicator that an obstacle was detected and the distance in mm as a
      float, or that a previous obstacle has now been clearer with an argument
      of 'clear'

### Web Interface

### Python

## Operation

_TBD - describe how to set up and control the hexapod_

## Development

_TBD - describe the various development aspects_

### 3D Design

### Firmware

#### Dev environment

#### Firmware upload

#### Testing locally


## Visuals
![Hexapod Top View](docs/hexapod_top.png "Hexapod top view")
![Hexapod Front View](docs/hexapod_front.png "Hexapod front view")
![Hexapod Left View](docs/hexapod_left.png "Hexapod left view")

## Resources
* [ArduSnake] - Inspiration for the locomotion used for this project
* [Amplitude, Period, Phase Shift and Frequency](https://www.mathsisfun.com/algebra/amplitude-period-frequency-phase-shift.html) -
  Theory behind the ServoOscillator code, and based on [ArduSnake]
* 3D [design] - The design of the body and parts in [OnShape]


<!-- Links -->
[hexapod]: https://en.wikipedia.org/wiki/Hexapod_(robotics)
[ArduSnake]: https://github.com/Obijuan/ArduSnake
[HC-SR04]: https://www.theengineeringprojects.com/2018/10/introduction-to-hc-sr04-ultrasonic-sensor.html
[IMU]: https://itp.nyu.edu/physcomp/lessons/accelerometers-gyros-and-imus-the-basics/
[design]: https://cad.onshape.com/documents/7f1f6312272fa1634f1a9c3c/w/0b019e5d4fce4172f4dcc484/e/9b3c33fb966bfcde9440cbd6
[OnShape]: https://www.onshape.com/en/
[MicroPython]: https://micropython.org
