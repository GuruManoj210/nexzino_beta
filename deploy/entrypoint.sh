#!/bin/bash
# Entrypoint for the nexzino deploy image. Starts (1) a local roscore,
# (2) the diff_drive_controller.py ROS node, (3) the servo_tester Flask app
# (port 5000), (4) the web_teleop Flask app (port 8000), (5) rosbridge_websocket
# (port 9090, ROS-over-websocket for nav_console's browser-side roslibjs),
# (6) the nav_console Flask app (port 5001), and (7) web_video_server
# (port 8080, MJPEG re-stream of the camera for nav_console's live view), then
# waits: if any one dies, this script exits so the container's restart policy
# can bring everything back up cleanly together.
set -eo pipefail

source /opt/ros/noetic/setup.bash
# /opt/ros/noetic/setup.bash overwrites ROS_PACKAGE_PATH rather than
# appending to it, so a Docker-image-level ENV for this gets wiped out the
# moment this line runs - it has to be set here, after sourcing, instead.
# nexzino/nexzino_nav are pure Python/resource packages (no messages, no
# C++ nodes), so being on ROS_PACKAGE_PATH is enough for $(find ...) and
# `roslaunch nexzino_nav ...` to work - no catkin build/devel space needed.
export ROS_PACKAGE_PATH="/opt/nexzino/ros_ws/src:${ROS_PACKAGE_PATH}"

APP_ROOT=/opt/nexzino
NAV_PKG="${APP_ROOT}/ros_ws/src/nexzino_nav"
DIFF_DRIVE_NODE_NAME="nexzino_diff_drive"

export ROS_MASTER_URI="${ROS_MASTER_URI:-http://localhost:11311}"
export ROS_HOSTNAME="${ROS_HOSTNAME:-localhost}"

pids=()

cleanup() {
    trap - TERM INT
    echo "==> Shutting down..."
    for pid in "${pids[@]}"; do
        kill -TERM "${pid}" 2>/dev/null || true
    done
    wait
}
trap cleanup TERM INT

# Only start roscore ourselves if we're the ones expected to host the master.
if [[ "${ROS_MASTER_URI}" == "http://localhost:11311" || "${ROS_MASTER_URI}" == "http://127.0.0.1:11311" ]]; then
    echo "==> Starting roscore"
    roscore &
    pids+=($!)

    echo "==> Waiting for roscore..."
    until rostopic list >/dev/null 2>&1; do
        sleep 0.5
    done
else
    echo "==> Using external ROS master at ${ROS_MASTER_URI}"
fi

echo "==> Loading ${NAV_PKG}/config/diff_drive.yaml onto /${DIFF_DRIVE_NODE_NAME}"
rosparam load "${NAV_PKG}/config/diff_drive.yaml" "/${DIFF_DRIVE_NODE_NAME}"

# Deploy-time hard override for which serial device is the wheel controller,
# e.g. when multiple USB-serial adapters are plugged in and the yaml's
# default (/dev/ttyACM0) might not be the right one. Always wins over the
# yaml when set - see deploy/docker-compose.yml.
if [[ -n "${WHEEL_CONTROLLER_PORT:-}" ]]; then
    echo "==> Overriding wheel controller port -> ${WHEEL_CONTROLLER_PORT}"
    rosparam set "/${DIFF_DRIVE_NODE_NAME}/port" "${WHEEL_CONTROLLER_PORT}"
fi

echo "==> Starting diff_drive_controller.py"
python3 "${NAV_PKG}/scripts/diff_drive_controller.py" &
pids+=($!)

echo "==> Starting servo_tester app.py (port 5000)"
python3 "${APP_ROOT}/servo_tester/app.py" &
pids+=($!)

echo "==> Starting web_teleop app.py (port 8000)"
python3 "${APP_ROOT}/web_teleop/app.py" &
pids+=($!)

echo "==> Starting rosbridge_websocket (port 9090)"
roslaunch rosbridge_server rosbridge_websocket.launch &
pids+=($!)

echo "==> Starting nav_console app.py (port 5001)"
python3 "${APP_ROOT}/nav_console/app.py" &
pids+=($!)

# Harmless to run even when no camera topic exists yet (idle, no mapping/
# navigation session active) - it just serves an empty response until
# /camera/color/image_raw shows up.
echo "==> Starting web_video_server (port 8080)"
rosrun web_video_server web_video_server &
pids+=($!)

# Exit as soon as any one of these processes exits, so the whole
# container restarts together instead of limping along half-alive.
wait -n "${pids[@]}"
exit_code=$?
echo "==> A process exited (code ${exit_code}), shutting down the rest"
cleanup
exit "${exit_code}"
