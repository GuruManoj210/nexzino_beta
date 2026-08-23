#!/usr/bin/env python3
"""Republishes the map->base_footprint TF transform as a plain PoseStamped.

Same purpose as mr_carter's robot_pose_publisher.cpp (TF lookup between
/map and /base_link, republished as a Pose) - here as pure Python against
tf2_ros, which ships with ROS Noetic, so no compiled node/new package is
needed. nav_console's web UI (nav2d.js) subscribes to this topic instead of
raw /odom, since raw odom never reflects rtabmap's map->odom correction.
"""

import rospy
import tf2_ros
from geometry_msgs.msg import PoseStamped


def main():
    rospy.init_node("robot_pose_publisher")

    map_frame = rospy.get_param("~map_frame", "map")
    base_frame = rospy.get_param("~base_frame", "base_footprint")
    publish_rate = rospy.get_param("~publish_rate", 10.0)

    pose_pub = rospy.Publisher("robot_pose", PoseStamped, queue_size=1)

    tf_buffer = tf2_ros.Buffer()
    tf2_ros.TransformListener(tf_buffer)

    rate = rospy.Rate(publish_rate)
    while not rospy.is_shutdown():
        try:
            transform = tf_buffer.lookup_transform(map_frame, base_frame, rospy.Time(0))
        except (
            tf2_ros.LookupException,
            tf2_ros.ConnectivityException,
            tf2_ros.ExtrapolationException,
        ):
            rate.sleep()
            continue

        pose = PoseStamped()
        pose.header.stamp = transform.header.stamp
        pose.header.frame_id = map_frame
        pose.pose.position.x = transform.transform.translation.x
        pose.pose.position.y = transform.transform.translation.y
        pose.pose.position.z = transform.transform.translation.z
        pose.pose.orientation = transform.transform.rotation
        pose_pub.publish(pose)

        rate.sleep()


if __name__ == "__main__":
    main()
