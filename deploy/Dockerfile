# Build context is the repo root (see docker-compose.yml), so paths below
# are relative to the repository root, not this deploy/ folder.
#
# Deliberately NOT built on top of .devcontainer/Dockerfile: that image is
# FROM osrf/ros:noetic-desktop-full, which only publishes an amd64 manifest
# (verified with `docker buildx imagetools inspect osrf/ros:noetic-desktop-full`
# - no arm64 variant exists at all, so it can't build natively on a Jetson).
# ros:noetic-ros-base is the official multi-arch image (amd64 + arm64 + armv7).
FROM ros:noetic-ros-base

ENV DEBIAN_FRONTEND=noninteractive
# Python fully buffers stdout (not line-by-line) when it isn't attached to a
# real terminal - exactly the case under `docker compose up`/`logs`. Without
# this, output from background processes (rospy.loginfo, print, etc.) can sit
# in an unflushed buffer and vanish entirely if the process is killed before
# it fills or exits cleanly, making "no output" impossible to trust.
ENV PYTHONUNBUFFERED=1

# ros-noetic-tf: geometry_msgs/nav_msgs/sensor_msgs/tf2, all diff_drive_controller.py
# needs. ros-noetic-navigation: move_base/navfn/dwa_local_planner/map_server for
# navigation.launch. ros-noetic-rtabmap(-ros): SLAM for mapping.launch/navigation.launch.
# ros-noetic-realsense2-camera: the D435i driver, installed as an apt binary (a
# compiled C++ node - building it from the vendored source under
# ros_ws/src/realsense-ros-gazebo/ would need a full catkin build in this image,
# which is the whole thing this minimal image is trying to avoid).
# realsense2_description is NOT installed via apt here on purpose: the apt
# package's _d435.urdf.xacro macro signature doesn't match what nexzino's URDF
# actually calls it with (missing a `topics_ns` param, confirmed by testing -
# roslaunch fails with "Invalid parameter topics_ns"). nexzino.urdf.xacro was
# written against the vendored realsense2_description under
# ros_ws/src/realsense-ros-gazebo/ instead (copied below, pure xacro/URDF, no
# build needed) - that's the one that actually matches.
# ros-noetic-robot-state-publisher + ros-noetic-xacro: publish TF from nexzino's
# URDF. ros-noetic-rviz: optional, only used if you explicitly pass open_rviz:=true
# with a display attached - see deploy/README.md for the (recommended) remote-RViz
# alternative for a headless robot. ros-noetic-rosbridge-server: nav_console's
# frontend (roslibjs) talks to ROS directly from the browser over this -
# map view, click-to-navigate goals, and its joystick all need it running.
# ros-noetic-web-video-server: re-serves any sensor_msgs/Image topic (here,
# /camera/color/image_raw) as a plain MJPEG HTTP stream nav_console's pages
# embed via <img>. Deliberately NOT sent over rosbridge instead - raw Image
# messages there are uncompressed and base64'd over the websocket, which
# would be a lot of extra load on the same USB3 hub bandwidth we already had
# to work around for the D435 (see realsense_bringup.launch).
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        ros-noetic-tf \
        ros-noetic-navigation \
        ros-noetic-rtabmap \
        ros-noetic-rtabmap-ros \
        ros-noetic-realsense2-camera \
        ros-noetic-robot-state-publisher \
        ros-noetic-xacro \
        ros-noetic-rviz \
        ros-noetic-rosbridge-server \
        ros-noetic-web-video-server \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

# pymodbus is pinned <3 because zlac8015d/ZLAC8015D.py imports the legacy
# `pymodbus.client.sync` module path that pymodbus 3.x removed. flask-sock
# backs the web_teleop websocket. Pillow backs nav_console's pgm->png map
# thumbnail conversion (avoids adding imagemagick just for that one step).
RUN pip3 install --no-cache-dir \
        "Flask>=2.2.5" \
        "flask-sock>=0.7.0" \
        "pyserial>=3.5" \
        "pymodbus>=2.5,<3" \
        "numpy" \
        "Pillow>=9.0.0"

WORKDIR /opt/nexzino

COPY ros_ws/src/nexzino_nav/scripts ros_ws/src/nexzino_nav/scripts
COPY ros_ws/src/nexzino_nav/config ros_ws/src/nexzino_nav/config
COPY ros_ws/src/nexzino_nav/launch ros_ws/src/nexzino_nav/launch
COPY ros_ws/src/nexzino_nav/maps ros_ws/src/nexzino_nav/maps
COPY ros_ws/src/nexzino_nav/package.xml ros_ws/src/nexzino_nav/package.xml
COPY ros_ws/src/nexzino ros_ws/src/nexzino
COPY ros_ws/src/realsense-ros-gazebo/realsense-ros/realsense2_description ros_ws/src/realsense2_description
COPY ros_ws/src/ZLAC8015D_python ros_ws/src/ZLAC8015D_python
COPY servo_tester servo_tester
COPY web_teleop web_teleop
COPY nav_console nav_console

COPY deploy/entrypoint.sh entrypoint.sh

RUN chmod +x entrypoint.sh ros_ws/src/nexzino_nav/scripts/diff_drive_controller.py

# entrypoint.sh's own `export ROS_PACKAGE_PATH=...` only lives in its own
# process - it does NOT carry over to a fresh `docker exec -it ... bash`
# session, which starts with just the image's env + .bashrc. Bake it into
# .bashrc too (this image runs as root) so an interactive shell that sources
# /opt/ros/noetic/setup.bash itself - e.g. to manually roslaunch
# mapping.launch/navigation.launch - ends up with the same working
# ROS_PACKAGE_PATH without the user needing to know about this at all.
RUN echo "source /opt/ros/noetic/setup.bash" >> /root/.bashrc && \
    echo 'export ROS_PACKAGE_PATH="/opt/nexzino/ros_ws/src:${ROS_PACKAGE_PATH}"' >> /root/.bashrc

ENTRYPOINT ["/opt/nexzino/entrypoint.sh"]
