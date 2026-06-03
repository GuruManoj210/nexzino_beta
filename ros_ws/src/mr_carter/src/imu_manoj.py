#!/usr/bin/env python3
import time
import struct
import rospy
import numpy as np
from sensor_msgs.msg import Imu
from tf import transformations

imu_data = Imu()


def callback(data):
    # print(data.linear_acceleration.x, data.linear_acceleration.y, data.linear_acceleration.z)
    # print(data.angular_velocity.x, data.angular_velocity.y, data.angular_velocity.z)
    # print(data.orientation.x, data.orientation.y, data.orientation.z)
    q = transformations.quaternion_from_euler(
        data.orientation.x, data.orientation.y, data.orientation.z
    )

    imu_data.header.frame_id = "imu_link"

    imu_data.angular_velocity.x = data.angular_velocity.x * (3.141592653589793 / 180)
    imu_data.angular_velocity.y = data.angular_velocity.y * (3.141592653589793 / 180)
    imu_data.angular_velocity.z = data.angular_velocity.z * (3.141592653589793 / 180)

    imu_data.linear_acceleration.x = (data.linear_acceleration.x) * 9.81
    imu_data.linear_acceleration.y = (data.linear_acceleration.y) * 9.81
    imu_data.linear_acceleration.z = (data.linear_acceleration.z) * 9.81

    accel = (
        imu_data.linear_acceleration.x,
        imu_data.linear_acceleration.y,
        imu_data.linear_acceleration.z,
    )
    ref = np.array([0, 0, 1])
    acceln = accel / np.linalg.norm(accel)
    axis = np.cross(acceln, ref)
    angle = np.arccos(np.dot(acceln, ref))
    orientation = transformations.quaternion_about_axis(angle, axis)

    imu_data.orientation.x = orientation[0]
    imu_data.orientation.y = orientation[1]
    imu_data.orientation.z = orientation[2]
    imu_data.orientation.w = orientation[3]

    pub.publish(imu_data)


def listener():
    rospy.Subscriber("imu/raw_data", Imu, callback)
    rospy.spin()


if __name__ == "__main__":
    rospy.init_node("imu_node1", anonymous=True)
    pub = rospy.Publisher("imu/data", Imu, queue_size=1000)
    imu_timer = rospy.Timer(rospy.Duration(0.02), listener())
#  listener()
# imu_pub = rospy.Publisher('imu/data_raw', Imu,queue_size=10)
