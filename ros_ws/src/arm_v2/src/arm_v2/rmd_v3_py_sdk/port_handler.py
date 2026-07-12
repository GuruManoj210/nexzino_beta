#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os


class Port_handler:

    # Disable CAN Ports on Processor
    def CAN_OFF(self):
        os.popen("sh can_files/can_disable.sh")
        print("CAN communication is disabled")

    # Enable CAN Ports on Processor
    def CAN_ON(self):
        os.popen("sh can_files/pcan_enable.sh")
        print("CAN communication is established")
