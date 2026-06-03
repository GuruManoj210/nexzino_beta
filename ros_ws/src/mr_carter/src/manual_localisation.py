#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
from std_srvs.srv import Empty
from geometry_msgs.msg import Twist
from geometry_msgs.msg import PoseWithCovarianceStamped
import time
import numpy as np

rospy.init_node("manual_localiser")
Localisation = rospy.ServiceProxy("global_localization", Empty)
cmd_vel = rospy.Publisher("/cmd_vel", Twist, queue_size=1)

prev_error_status = 0


def callback(data):
    cov_arry = np.asarray(data.pose.covariance)
    global prev_error_status

    for i in range(0, len(cov_arry)):
        if cov_arry[i] < 0.1 and cov_arry[i] > -0.1:
            if prev_error_status == 1:
                # Sending command for carter to stop rotating
                rotate = Twist()
                rotate.angular.z = 0.0
                cmd_vel.publish(rotate)
                print("corrected")
                prev_error_status = 0

            else:
                print("No Error", cov_arry[i])
                pass
        else:
            if prev_error_status == 0:
                # Scatter the posibilities through out the map
                rospy.loginfo("Sending Request for manual Localisation.....")
                resp = Localisation()
                prev_error_status = 1
                print("started")
                # Sending command to rotate the carter
                rotate = Twist()
                rotate.angular.z = 0.5
                cmd_vel.publish(rotate)
                print("sent command")
                break
            else:
                # Sending command to rotate the carter
                rotate = Twist()
                rotate.angular.z = 0.5
                cmd_vel.publish(rotate)
                print("correcting")
                break


def amcl_pose_listner():
    rospy.Subscriber("amcl_pose", PoseWithCovarianceStamped, callback)


try:
    while True:
        amcl_pose_listner()
        time.sleep(0.5)
except KeyboardInterrupt:
    print("intrupted")
