#!/usr/bin/env python3

import rospy
from sensor_msgs.msg import JointState
from std_msgs.msg import Header
import json
import os
from arm_v2.rmd_v3_py_sdk.protocol1_packet_maker import RMD1
from arm_v2.rmd_v3_py_sdk.protocol3_packet_maker import RMD3
from arm_v2.dynamixel_sdk import *

if os.name == "nt":
    import msvcrt

    def getch():
        return msvcrt.getch().decode()

else:
    import sys, tty, termios

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    def getch():
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


# Control table address
ADDR_TORQUE_ENABLE = 64  # Control table address is different in Dynamixel model
ADDR_GOAL_POSITION = 116
ADDR_PRESENT_POSITION = 132
# Protocol version
PROTOCOL_VERSION = 2.0  # See which protocol version is used in the Dynamixel
# Default setting
BAUDRATE = 1000000  # Dynamixel default baudrate : 57600
DEVICENAME = "/dev/ttyUSB0"  # Check which port is being used on your controller
# ex) Windows: "COM1"   Linux: "/dev/ttyUSB0" Mac: "/dev/tty.usbserial-*
TORQUE_ENABLE = 1  # Value for enabling the torque
TORQUE_DISABLE = 0  # Value for disabling the torque


portHandler = PortHandler(DEVICENAME)
packetHandler = PacketHandler(PROTOCOL_VERSION)

try:
    portHandler.openPort()
    print("Succeeded to open the port")
except:
    print("Failed to open the port")
    quit()
# Set port baudrate
try:
    portHandler.setBaudRate(BAUDRATE)
    print("Succeeded to change the baudrate")
except:
    print("Failed to change the baudrate")
    quit()

rmd1 = RMD1()
rmd3 = RMD3()
publisher = rospy.Publisher("/hw_feedback", JointState, queue_size=10)
fd_msg = JointState()
fd_msg.header = Header()
count = 0


def msg(data):
    global count
    config_data = json.load(open("src/arm_v2/src/Hardware_Config.json", "r"))
    mimic_data = json.load(open("src/arm_v2/src/mimic_lib.json", "r"))
    fd_data = list(data.position)
    for name in data.name:
        if name in config_data:
            id = config_data[name]["motor_id"]
            position = data.position[data.name.index(name)] * config_data[name]["scale"]
            if position <= config_data[name]["user_min"]:
                position = config_data[name]["user_min"]
            elif position >= config_data[name]["user_max"]:
                position = config_data[name]["user_max"]

            if count == 1:
                if (position >= config_data[name]["user_min"]) and (
                    position <= config_data[name]["user_max"]
                ):
                    if config_data[name]["hardware"] == "RMD_V1":
                        rmd1.Send_Receive_Message(
                            rmd1.TX_Packet(
                                id,
                                rmd1.Position_Ctrl_2(
                                    config_data[name]["user_speed"], position
                                ),
                            )
                        )
                        rmd1.Send_Receive_Message(
                            rmd1.TX_Packet(id, rmd1.RD_Multi_turn_Angle())
                        )
                        fd_data[data.name.index(name)] = (
                            rmd1.MULTI_TURN_ANG_OUT / config_data[name]["scale"]
                        )
                        # print(id, rmd1.MULTI_TURN_ANG_OUT/config_data[name]['scale'],data.position[data.name.index(name)])
                    elif config_data[name]["hardware"] == "RMD_V3":
                        rmd3.Send_Receive_Message(
                            rmd3.TX_Packet(
                                id,
                                rmd3.Absolute_Position_ctrl(
                                    config_data[name]["user_speed"], position
                                ),
                            )
                        )
                        rmd3.Send_Receive_Message(
                            rmd3.TX_Packet(id, rmd3.RD_Multi_Turn_Angle())
                        )
                        fd_data[data.name.index(name)] = (
                            rmd3.MULTI_TURN_ANG_OUT / config_data[name]["scale"]
                        )
                        # print(id, rmd3.MULTI_TURN_ANG_OUT/config_data[name]['scale'],data.position[data.name.index(name)])
                    elif config_data[name]["hardware"] == "Dynamixel":
                        motor_value = int(
                            config_data[name]["motor_min"]
                            + (
                                (
                                    (
                                        config_data[name]["motor_max"]
                                        - config_data[name]["motor_min"]
                                    )
                                    / (
                                        config_data[name]["user_max"]
                                        - config_data[name]["user_min"]
                                    )
                                )
                                * (position - config_data[name]["user_min"])
                            )
                        )
                        dxl_comm_result, dxl_error = packetHandler.write4ByteTxRx(
                            portHandler, id, ADDR_GOAL_POSITION, motor_value
                        )
                        present_position = packetHandler.read4ByteTxRx(
                            portHandler, id, ADDR_PRESENT_POSITION
                        )
                        fd_data[data.name.index(name)] = int(
                            config_data[name]["user_min"]
                            + (
                                (
                                    (
                                        config_data[name]["user_max"]
                                        - config_data[name]["user_min"]
                                    )
                                    / (
                                        config_data[name]["motor_max"]
                                        - config_data[name]["motor_min"]
                                    )
                                )
                                * (present_position[0] - config_data[name]["motor_min"])
                            )
                        )
                        # print(id,fb_value,position)
                    else:
                        pass

                    if name in mimic_data:
                        for x in range(len(mimic_data[name]["mimic_links"])):
                            fd_data[
                                data.name.index(mimic_data[name]["mimic_links"][x])
                            ] = (
                                data.position[data.name.index(name)]
                                * mimic_data[name]["multiplier"][x]
                            ) + mimic_data[
                                name
                            ][
                                "offset"
                            ][
                                x
                            ]
            else:
                if config_data[name]["hardware"] == "RMD_V1":
                    rmd1.Send_Receive_Message(
                        rmd1.TX_Packet(
                            id,
                            rmd1.WR_Acceleration_Data(
                                config_data[name]["user_acceleration"]
                            ),
                        )
                    )
                if config_data[name]["hardware"] == "RMD_V3":
                    rmd3.Send_Receive_Message(
                        rmd3.TX_Packet(
                            id,
                            rmd3.WR_Acceleration_Data(
                                config_data[name]["user_acceleration"]
                            ),
                        )
                    )
                if config_data[name]["hardware"] == "Dynamixel":
                    dxl_comm_result, dxl_error = packetHandler.write1ByteTxRx(
                        portHandler, id, ADDR_TORQUE_ENABLE, TORQUE_ENABLE
                    )
                else:
                    pass
        else:
            pass
    count = 1
    fd_msg.header.stamp = rospy.Time.now()
    fd_msg.name = data.name
    fd_msg.position = fd_data
    publisher.publish(fd_msg)


def interface():
    try:
        rospy.init_node("HW_interface", anonymous=True)
        rospy.Subscriber("joint_states", JointState, msg, queue_size=2)
        rospy.spin()
    except rospy.ROSInterruptException:
        return
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    interface()
