#!/usr/bin/env python

from protocol3_packet_maker import RMD3
from protocol1_packet_maker import RMD1
import time

packet3 = RMD3(channel="can0")
packet1 = RMD1(channel="can0")

while True:
    try:
        data3 = packet3.RD_PID_Data()
        tx_packet3 = packet3.TX_Packet(5, data3)
        packet3.Send_Receive_Message(tx_packet3)

        data1 = packet1.RD_PID_Data()
        tx_packet1 = packet1.TX_Packet(1, data1)
        packet1.Send_Receive_Message(tx_packet1)
        time.sleep(0.05)
    except KeyboardInterrupt:
        break
