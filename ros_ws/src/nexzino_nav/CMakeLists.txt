cmake_minimum_required(VERSION 3.0.2)
project(nexzino_nav)

find_package(catkin REQUIRED COMPONENTS
  dwa_local_planner
  gazebo_ros
  geometry_msgs
  map_server
  move_base
  nav_msgs
  navfn
  nexzino
  pal_gazebo_worlds
  realsense2_camera
  robot_state_publisher
  rospy
  rtabmap_ros
  rviz
  sensor_msgs
  std_msgs
  tf
)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/diff_drive_controller.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY launch config maps worlds
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
