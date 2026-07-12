#!/bin/bash -e

sudo modprobe peak_usb
sudo modprobe can_raw
#sudo modprobe mttcan
sudo ip link set can0 up type can bitrate 1000000 #dbitrate 1000000 berr-reporting on fd on
#sudo ip link set can0 type can bitrate 1000000 dbitrate 1000000 berr-reporting on fd on
#sudo ip link set can1 type can bitrate 1000000 dbitrate 1000000 berr-reporting on fd on
sudo ip link set up can0
#sudo ip link set up can1

exit 0
