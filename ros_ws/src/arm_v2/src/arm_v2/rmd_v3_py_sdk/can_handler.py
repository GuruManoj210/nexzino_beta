#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .port_handler import Port_handler
import can


########################################################
# This file provides CAN Enable & Disable functions
########################################################


class CAN_Handler(Port_handler):
    def __init__(self, bustype="socketcan", channel="can0", bitrate=1000000):
        self.bustype = bustype
        self.channel = channel
        self.bitrate = bitrate
        self.bus = can.interface.Bus(
            bustype=self.bustype, channel=self.channel, bitrate=self.bitrate
        )

    # Function to send the CAN Frame
    def Send_Message(self, TX_Packet):
        try:
            self.bus.send(TX_Packet)
            # print(TX_Packet)
        except can.CanError:
            print("Message NOT sent due to can bus error")

    # Function to receive CAN Frames from bus
    def Receive_Message(self):
        try:
            mesgrecv = self.bus.recv(timeout=0.1)
            # print(mesgrecv)
            return mesgrecv
        except can.CanError:
            print("Message NOT received")
