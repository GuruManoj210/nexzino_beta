#!/usr/bin/env python3

import math
import os
import sys

import rospy
from geometry_msgs.msg import Quaternion, Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import JointState
from std_msgs.msg import Int32
from tf.broadcaster import TransformBroadcaster
from tf.transformations import quaternion_from_euler


SDK_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "ZLAC8015D_python")
)
if SDK_PATH not in sys.path:
    sys.path.insert(0, SDK_PATH)

from zlac8015d import ZLAC8015D  # noqa: E402


class NexzinoDiffDriveController(object):
    def __init__(self):
        self.port = rospy.get_param("~port", "/dev/ttyACM0")
        self.control_rate = rospy.get_param("~control_rate", 30.0)
        self.cmd_vel_timeout = rospy.get_param("~cmd_vel_timeout", 0.5)

        self.wheel_radius = rospy.get_param("~wheel_radius", 0.105)
        self.wheel_separation = rospy.get_param("~wheel_separation", 0.33956)
        self.meters_per_rev = rospy.get_param("~meters_per_rev", 0.655)
        self.ticks_per_rev = rospy.get_param("~ticks_per_rev", 16385.0)
        self.max_rpm = rospy.get_param("~max_rpm", 300.0)

        self.left_command_sign = rospy.get_param("~left_command_sign", 1.0)
        self.right_command_sign = rospy.get_param("~right_command_sign", -1.0)
        self.left_encoder_sign = rospy.get_param("~left_encoder_sign", 1.0)
        self.right_encoder_sign = rospy.get_param("~right_encoder_sign", -1.0)

        self.accel_time_ms = rospy.get_param("~accel_time_ms", 1000)
        self.decel_time_ms = rospy.get_param("~decel_time_ms", 1000)
        self.publish_odom_tf = rospy.get_param("~publish_odom_tf", True)
        self.base_frame = rospy.get_param("~base_frame", "base_footprint")
        self.odom_frame = rospy.get_param("~odom_frame", "odom")
        self.left_wheel_joint = rospy.get_param("~left_wheel_joint", "leftwheel_joint")
        self.right_wheel_joint = rospy.get_param(
            "~right_wheel_joint", "rightwheel_joint"
        )

        self.target_linear = 0.0
        self.target_angular = 0.0
        self.last_cmd_time = rospy.Time.now()
        self.last_update_time = rospy.Time.now()
        self.last_left_tick = None
        self.last_right_tick = None
        self.last_left_pos = 0.0
        self.last_right_pos = 0.0

        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0

        self.left_tick_pub = rospy.Publisher("left_wheel/ticks", Int32, queue_size=10)
        self.right_tick_pub = rospy.Publisher("right_wheel/ticks", Int32, queue_size=10)
        self.joint_state_pub = rospy.Publisher(
            "joint_states", JointState, queue_size=10
        )
        self.odom_pub = rospy.Publisher("odom", Odometry, queue_size=10)
        self.tf_broadcaster = TransformBroadcaster()

        self.cmd_vel_sub = rospy.Subscriber("cmd_vel", Twist, self.cmd_vel_callback)

        self.motor = ZLAC8015D.Controller(port=self.port)
        self.configure_motor()
        rospy.on_shutdown(self.on_shutdown)

    def configure_motor(self):
        rospy.loginfo("Connecting to ZLAC8015D controller on %s", self.port)
        self.motor.disable_motor()
        self.motor.clear_alarm()
        self.motor.set_accel_time(self.accel_time_ms, self.accel_time_ms)
        self.motor.set_decel_time(self.decel_time_ms, self.decel_time_ms)
        self.motor.set_mode(self.motor.VEL_CONTROL)
        self.motor.enable_motor()

    def cmd_vel_callback(self, msg):
        self.target_linear = msg.linear.x
        self.target_angular = msg.angular.z
        self.last_cmd_time = rospy.Time.now()

    def meters_per_second_to_rpm(self, velocity_mps):
        wheel_circumference = 2.0 * math.pi * self.wheel_radius
        rev_per_sec = velocity_mps / wheel_circumference
        return rev_per_sec * 60.0

    def clamp_rpm(self, rpm):
        return max(-self.max_rpm, min(self.max_rpm, rpm))

    def compute_wheel_commands(self):
        timed_out = (
            rospy.Time.now() - self.last_cmd_time
        ).to_sec() > self.cmd_vel_timeout
        linear = 0.0 if timed_out else self.target_linear
        angular = 0.0 if timed_out else self.target_angular

        left_velocity = linear - (angular * self.wheel_separation / 2.0)
        right_velocity = linear + (angular * self.wheel_separation / 2.0)

        left_rpm = self.clamp_rpm(
            self.meters_per_second_to_rpm(left_velocity) * self.left_command_sign
        )
        right_rpm = self.clamp_rpm(
            self.meters_per_second_to_rpm(right_velocity) * self.right_command_sign
        )
        return left_rpm, right_rpm

    def tick_to_joint_position(self, tick_delta, sign):
        return sign * (float(tick_delta) / self.ticks_per_rev) * 2.0 * math.pi

    def tick_to_distance(self, tick_delta, sign):
        return sign * (float(tick_delta) / self.ticks_per_rev) * self.meters_per_rev

    def publish_feedback(self, left_tick, right_tick, left_rpm, right_rpm, stamp, dt):
        self.left_tick_pub.publish(Int32(data=int(left_tick)))
        self.right_tick_pub.publish(Int32(data=int(right_tick)))

        if self.last_left_tick is None or self.last_right_tick is None:
            self.last_left_tick = left_tick
            self.last_right_tick = right_tick
            return

        left_tick_delta = int(left_tick - self.last_left_tick)
        right_tick_delta = int(right_tick - self.last_right_tick)
        self.last_left_tick = left_tick
        self.last_right_tick = right_tick

        left_distance = self.tick_to_distance(left_tick_delta, self.left_encoder_sign)
        right_distance = self.tick_to_distance(
            right_tick_delta, self.right_encoder_sign
        )

        delta_s = (left_distance + right_distance) / 2.0
        delta_theta = (right_distance - left_distance) / self.wheel_separation
        heading = self.yaw + (delta_theta / 2.0)

        self.x += delta_s * math.cos(heading)
        self.y += delta_s * math.sin(heading)
        self.yaw += delta_theta

        self.last_left_pos += self.tick_to_joint_position(
            left_tick_delta, self.left_encoder_sign
        )
        self.last_right_pos += self.tick_to_joint_position(
            right_tick_delta, self.right_encoder_sign
        )

        left_joint_velocity = self.left_encoder_sign * (left_rpm * 2.0 * math.pi / 60.0)
        right_joint_velocity = self.right_encoder_sign * (
            right_rpm * 2.0 * math.pi / 60.0
        )
        linear_velocity = delta_s / dt if dt > 0.0 else 0.0
        angular_velocity = delta_theta / dt if dt > 0.0 else 0.0

        joint_state = JointState()
        joint_state.header.stamp = stamp
        joint_state.name = [self.left_wheel_joint, self.right_wheel_joint]
        joint_state.position = [self.last_left_pos, self.last_right_pos]
        joint_state.velocity = [left_joint_velocity, right_joint_velocity]
        self.joint_state_pub.publish(joint_state)

        quaternion = quaternion_from_euler(0.0, 0.0, self.yaw)

        odom = Odometry()
        odom.header.stamp = stamp
        odom.header.frame_id = self.odom_frame
        odom.child_frame_id = self.base_frame
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation = Quaternion(*quaternion)
        odom.twist.twist.linear.x = linear_velocity
        odom.twist.twist.angular.z = angular_velocity
        self.odom_pub.publish(odom)

        if self.publish_odom_tf:
            self.tf_broadcaster.sendTransform(
                (self.x, self.y, 0.0),
                quaternion,
                stamp,
                self.base_frame,
                self.odom_frame,
            )

    def spin(self):
        rate = rospy.Rate(self.control_rate)

        while not rospy.is_shutdown():
            now = rospy.Time.now()
            dt = (now - self.last_update_time).to_sec()
            self.last_update_time = now

            left_cmd_rpm, right_cmd_rpm = self.compute_wheel_commands()
            self.motor.set_rpm(int(left_cmd_rpm), int(right_cmd_rpm))

            try:
                left_tick, right_tick = self.motor.get_wheels_tick()
                left_rpm, right_rpm = self.motor.get_rpm()
                self.publish_feedback(
                    left_tick, right_tick, left_rpm, right_rpm, now, dt
                )
            except Exception as exc:
                rospy.logwarn_throttle(2.0, "Motor feedback read failed: %s", exc)

            rate.sleep()

    def on_shutdown(self):
        try:
            self.motor.set_rpm(0, 0)
            self.motor.disable_motor()
        except Exception:
            pass


def main():
    rospy.init_node("nexzino_diff_drive")
    controller = NexzinoDiffDriveController()
    controller.spin()


if __name__ == "__main__":
    main()
