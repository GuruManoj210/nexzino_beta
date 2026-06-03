#!/bin/bash

set -e # Add pipe fail command to exit on error

printf "=====< Setting up ROS environment >=====\n\n"
echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc
mkdir -p /home/developer/.ros/log
sudo chown -R developer:developer ~/.ros
# cd /workspaces/nexzino_beta/ros_ws/ && catkin build
echo "source /workspaces/nexzino_beta/ros_ws/devel/setup.bash" >> ~/.bashrc
sudo touch /home/developer/.cache/mesa_shader_cache
printf "=====< ROS environment setup is done >=====\n\n"

echo "export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:/workspaces/nexzino_beta/gazebo_models_worlds_collection/models" >> ~/.bashrc
echo "export GAZEBO_RESOURCE_PATH=$GAZEBO_RESOURCE_PATH:/workspaces/nexzino_beta/gazebo_models_worlds_collection/worlds" >> ~/.bashrc
