FROM osrf/ros:noetic-desktop-full
ARG USERNAME=developer
ARG USER_UID=1000
ARG USER_GID=$USER_UID

ENV DEBIAN_FRONTEND=noninteractive


RUN apt update && \
    apt install --no-install-recommends -y \
    python3-pip \
    gedit \
    git \
    imagemagick \
    ros-dev-tools \
    python3-catkin-tools \
    ros-noetic-navigation \
    ros-noetic-slam-gmapping \
    ros-noetic-teleop-twist-keyboard \
    ros-noetic-rosbridge-server \
    ros-noetic-roswww \
    ros-noetic-tf2-web-republisher \
    ros-noetic-xacro \
    ros-noetic-gazebo-ros \
    ros-noetic-robot-state-publisher \
    ros-noetic-joint-state-publisher \
    ros-noetic-rviz \
    ros-noetic-gazebo-plugins \
    software-properties-common \
    net-tools \
    ros-noetic-ddynamic-reconfigure \
    ros-noetic-joint-trajectory-controller \
    ros-noetic-rtabmap \
    ros-noetic-rtabmap-ros \
    ros-noetic-imu-filter-madgwick \
    ros-noetic-octomap-rviz-plugins \
    curl \
    gnupg2 \
    ca-certificates \
    lsb-release


RUN pip3 install pre-commit \
    flask==2.2.5

# RealSense repository setup
RUN curl -fsSL https://librealsense.intel.com/Debian/librealsense.pgp \
    | apt-key add -

RUN echo "deb https://librealsense.intel.com/Debian/apt-repo focal main" \
    > /etc/apt/sources.list.d/librealsense.list

RUN apt-get update --allow-insecure-repositories && \
    apt-get install -y --allow-unauthenticated \
    librealsense2-utils \
    librealsense2-dev

# adding dev user
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -ms /bin/bash $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

USER developer
