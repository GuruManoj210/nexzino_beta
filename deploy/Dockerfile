# Build context is the repo root (see docker-compose.yml), so paths below
# are relative to the repository root, not this deploy/ folder.
#
# Deliberately NOT built on top of .devcontainer/Dockerfile: that image is
# FROM osrf/ros:noetic-desktop-full, which only publishes an amd64 manifest
# (verified with `docker buildx imagetools inspect osrf/ros:noetic-desktop-full`
# - no arm64 variant exists at all, so it can't build natively on a Jetson).
# ros:noetic-ros-base is the official multi-arch image (amd64 + arm64 + armv7),
# and it's all this container actually needs - entrypoint.sh never runs
# gazebo/rviz/rtabmap, only roscore + two plain Python/Flask processes.
FROM ros:noetic-ros-base

ENV DEBIAN_FRONTEND=noninteractive
# Python fully buffers stdout (not line-by-line) when it isn't attached to a
# real terminal - exactly the case under `docker compose up`/`logs`. Without
# this, output from background processes (rospy.loginfo, print, etc.) can sit
# in an unflushed buffer and vanish entirely if the process is killed before
# it fills or exits cleanly, making "no output" impossible to trust.
ENV PYTHONUNBUFFERED=1

# ros-noetic-tf pulls in geometry_msgs/nav_msgs/sensor_msgs/tf2 transitively,
# which is all diff_drive_controller.py needs.
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        ros-noetic-tf \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

# pymodbus is pinned <3 because zlac8015d/ZLAC8015D.py imports the legacy
# `pymodbus.client.sync` module path that pymodbus 3.x removed. flask-sock
# backs the web_teleop websocket.
RUN pip3 install --no-cache-dir \
        "Flask>=2.2.5" \
        "flask-sock>=0.7.0" \
        "pyserial>=3.5" \
        "pymodbus>=2.5,<3" \
        "numpy"

WORKDIR /opt/nexzino

COPY ros_ws/src/nexzino_nav/scripts ros_ws/src/nexzino_nav/scripts
COPY ros_ws/src/nexzino_nav/config ros_ws/src/nexzino_nav/config
COPY ros_ws/src/ZLAC8015D_python ros_ws/src/ZLAC8015D_python
COPY servo_tester servo_tester
COPY web_teleop web_teleop

COPY deploy/entrypoint.sh entrypoint.sh

RUN chmod +x entrypoint.sh ros_ws/src/nexzino_nav/scripts/diff_drive_controller.py

ENTRYPOINT ["/opt/nexzino/entrypoint.sh"]
