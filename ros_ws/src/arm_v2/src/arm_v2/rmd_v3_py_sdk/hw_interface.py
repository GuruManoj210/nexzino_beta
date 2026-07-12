#!/usr/bin/env python

from protocol3_packet_maker import RMD3
from protocol1_packet_maker import RMD1

from turtle import position
import rospy
from sensor_msgs.msg import JointState
import numpy as np
from port_handler import RMD
import time


prev_array = [None] * 8
motor = RMD()
for y in range(6):
    motor.Send_Message(y + 1, motor.WR_Acceleration_Data(50))
    time.sleep(0.0035)


def send_all(angle_array):
    for i in range(6):
        if angle_array[i] != prev_array[i]:
            if i == 0 or i == 1:
                angle_array[i] = angle_array[i] * (-1)
            else:
                pass
            motor.Send_Message(i + 1, motor.Position_Ctrl_2(30, angle_array[i]))
            time.sleep(0.004)
            print(i + 1)
            prev_array[i] = angle_array[i]


def msg(data):
    angle = np.around(((np.array(data.position)) * (180 / 3.14159)), 1)
    send_all(angle)


def interface():
    try:
        rospy.init_node("rmd_interface", anonymous=True)
        rospy.Subscriber("joint_states", JointState, msg, queue_size=1)
        rospy.spin()
    except rospy.ROSInterruptException:
        return
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    interface()
