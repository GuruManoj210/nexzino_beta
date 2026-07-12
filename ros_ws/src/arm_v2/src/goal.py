#!/usr/bin/env python3

from tf import transformations
import sys
import rospy
import moveit_commander
import moveit_msgs.msg
import geometry_msgs.msg
from shape_msgs.msg import SolidPrimitive


class MoveGroupPythonInterfaceTutorial(object):
    """MoveGroupPythonInterfaceTutorial"""

    def __init__(self):
        super(MoveGroupPythonInterfaceTutorial, self).__init__()

        ## First initialize `moveit_commander`_ and a `rospy`_ node:
        moveit_commander.roscpp_initialize(sys.argv)
        rospy.init_node("move_group_python_interface_tutorial", anonymous=True)

        ## Instantiate a `RobotCommander`_ object. Provides information such as the robot's
        ## kinematic model and the robot's current joint states
        robot = moveit_commander.RobotCommander()

        ## Instantiate a `PlanningSceneInterface`_ object.  This provides a remote interface
        ## for getting, setting, and updating the robot's internal understanding of the
        ## surrounding world:
        scene = moveit_commander.PlanningSceneInterface()

        ## Create a `DisplayTrajectory`_ ROS publisher which is used to display
        ## trajectories in Rviz:
        display_trajectory_publisher = rospy.Publisher(
            "/move_group/display_planned_path",
            moveit_msgs.msg.DisplayTrajectory,
            queue_size=20,
        )

        ## Getting Basic Information
        # We can get a list of all the groups in the robot:
        group_names = robot.get_group_names()
        print("Available Planning Groups:", robot.get_group_names())

        # Sometimes for debugging it is useful to print the entire state of the robot
        print("Printing robot state")
        print(robot.get_current_state())
        print("")

        # Misc variables
        self.robot = robot
        self.scene = scene
        self.display_trajectory_publisher = display_trajectory_publisher
        self.group_names = group_names
        self.move_group = None

    # To send the particular group to the goal position using Inverse Kinematics
    def go_to_pose_goal(self, group_name, x, y, z, roll, pitch, yaw):
        self.move_group = moveit_commander.MoveGroupCommander(group_name)
        pose_goal = geometry_msgs.msg.Pose()
        q = transformations.quaternion_from_euler(roll, pitch, yaw)
        pose_goal.orientation.x = q[0]
        pose_goal.orientation.y = q[1]
        pose_goal.orientation.z = q[2]
        pose_goal.orientation.w = q[3]
        pose_goal.position.x = x
        pose_goal.position.y = y
        pose_goal.position.z = z
        self.move_group.set_pose_target(pose_goal)
        self.move_group.go(wait=True)
        self.move_group.clear_pose_targets()

    # send particular group to named target(named target values are defined in config/srdf) (Kinamatics)
    def home(self, group_name, pose_name):
        self.move_group = moveit_commander.MoveGroupCommander(group_name)
        self.move_group.set_named_target(pose_name)
        self.move_group.go(wait=True)

    def add_box(
        self, x, y, z, roll, pitch, yaw, l, b, h, box_name, ref_frame, timeout=4
    ):
        ## First, we will create a box in the planning scene between the fingers:
        box_pose = geometry_msgs.msg.PoseStamped()
        box_pose.header.frame_id = ref_frame
        q = transformations.quaternion_from_euler(roll, pitch, yaw)
        box_pose.pose.orientation.x = q[0]
        box_pose.pose.orientation.y = q[1]
        box_pose.pose.orientation.z = q[2]
        box_pose.pose.orientation.w = q[3]
        box_pose.pose.position.x = x
        box_pose.pose.position.y = y
        box_pose.pose.position.z = z
        self.scene.add_box(box_name, box_pose, size=(l, b, h))

    def add_cylinder_to_planning_scene(
        self, x, y, z, roll, pitch, yaw, radius, height, name, ref_frame
    ):

        # Define the properties of the cylinder
        cylinder_height = height
        cylinder_radius = radius

        cylinder_pose = geometry_msgs.msg.PoseStamped()
        cylinder_pose.header.frame_id = ref_frame
        q = transformations.quaternion_from_euler(roll, pitch, yaw)
        cylinder_pose.pose.orientation.x = q[0]
        cylinder_pose.pose.orientation.y = q[1]
        cylinder_pose.pose.orientation.z = q[2]
        cylinder_pose.pose.orientation.w = q[3]
        cylinder_pose.pose.position.x = x
        cylinder_pose.pose.position.y = y
        cylinder_pose.pose.position.z = z

        test_pose = geometry_msgs.msg.Pose()
        test_pose.position.x = 1
        test_pose.position.y = 1
        test_pose.position.z = 1
        # Create the collision object
        cylinder = SolidPrimitive()
        cylinder.type = SolidPrimitive.CYLINDER
        cylinder.dimensions = [cylinder_height, cylinder_radius]

        # Create a collision object message
        collision_object = moveit_msgs.msg.CollisionObject()
        collision_object.id = name
        collision_object.operation = collision_object.ADD
        collision_object.primitives = [cylinder]
        collision_object.primitive_poses = [test_pose]

        # Add the collision object to the planning scene
        self.scene.add_cylinder(name, cylinder_pose, height, radius)
        # self.scene.add_object(collision_object)


if __name__ == "__main__":
    try:
        arm2 = MoveGroupPythonInterfaceTutorial()
        arm2.go_to_pose_goal("r_arm", 0.3, -0.2, 1, 0, 1.5708, 0)

    except KeyboardInterrupt:
        print("end")
