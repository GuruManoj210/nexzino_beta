#!/bin/bash

sudo -S ip link set down can0
# echo mrobotics | sudo -S ip link set down can1
echo "CAN Networking Disabled"
exit 0
