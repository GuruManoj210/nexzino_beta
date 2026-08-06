#!/usr/bin/env python3

import json
import threading
import time

import rospy
from flask import Flask, render_template, request
from flask_sock import Sock
from geometry_msgs.msg import Twist

MAX_LINEAR = 0.3
MAX_ANGULAR = 0.3
# Failsafe: if no command is received within this window - joystick stuck,
# tab frozen, network drop, page closed - the publish loop zeroes the
# command on its own regardless of what the websocket connection is doing.
COMMAND_TIMEOUT_SECONDS = 0.3
PUBLISH_RATE_HZ = 20

app = Flask(__name__)
sock = Sock(app)

state_lock = threading.Lock()
# publish_enabled starts False - the operator must explicitly arm the
# publisher before any joystick input can reach /cmd_vel.
state = {
    "linear": 0.0,
    "angular": 0.0,
    "last_update": 0.0,
    "publish_enabled": False,
}


def clamp(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


def set_command(linear, angular) -> None:
    with state_lock:
        if not state["publish_enabled"]:
            # Dropped, not queued - a client that's disabled (or racing a
            # disable) can't leave a stale command sitting around to leak
            # out later.
            return
        state["linear"] = clamp(float(linear), MAX_LINEAR)
        state["angular"] = clamp(float(angular), MAX_ANGULAR)
        state["last_update"] = time.monotonic()


def zero_command() -> None:
    with state_lock:
        state["linear"] = 0.0
        state["angular"] = 0.0
        state["last_update"] = 0.0


def set_publish_enabled(enabled: bool) -> bool:
    with state_lock:
        state["publish_enabled"] = bool(enabled)
        # Toggling either direction always lands on zero - never resume
        # whatever was last held before the flip.
        state["linear"] = 0.0
        state["angular"] = 0.0
        state["last_update"] = 0.0
        return state["publish_enabled"]


def get_publish_enabled() -> bool:
    with state_lock:
        return state["publish_enabled"]


def publisher_loop(publisher: "rospy.Publisher") -> None:
    rate = rospy.Rate(PUBLISH_RATE_HZ)
    while not rospy.is_shutdown():
        with state_lock:
            timed_out = (
                time.monotonic() - state["last_update"]
            ) > COMMAND_TIMEOUT_SECONDS
            active = state["publish_enabled"] and not timed_out
            linear = state["linear"] if active else 0.0
            angular = state["angular"] if active else 0.0

        twist = Twist()
        twist.linear.x = linear
        twist.angular.z = angular
        publisher.publish(twist)
        rate.sleep()


@app.get("/")
def index() -> str:
    return render_template("index.html", max_linear=MAX_LINEAR, max_angular=MAX_ANGULAR)


@app.get("/api/publish-enabled")
def get_publish_enabled_route():
    return {"enabled": get_publish_enabled()}


@app.post("/api/publish-enabled")
def set_publish_enabled_route():
    payload = request.get_json(force=True) or {}
    enabled = set_publish_enabled(payload.get("enabled", False))
    return {"ok": True, "enabled": enabled}


@sock.route("/ws/cmd_vel")
def cmd_vel_ws(ws) -> None:
    try:
        while True:
            message = ws.receive()
            if message is None:
                break
            try:
                payload = json.loads(message)
                set_command(payload.get("linear", 0.0), payload.get("angular", 0.0))
            except (ValueError, TypeError, KeyError):
                continue
    finally:
        # Connection closed for any reason (tab closed, network drop,
        # browser crash) - fail safe immediately instead of waiting for
        # the watchdog timeout to catch up.
        zero_command()


def main() -> None:
    rospy.init_node("web_teleop", anonymous=False)
    publisher = rospy.Publisher("cmd_vel", Twist, queue_size=10)
    thread = threading.Thread(target=publisher_loop, args=(publisher,), daemon=True)
    thread.start()
    app.run(host="0.0.0.0", port=8000, debug=False)


if __name__ == "__main__":
    main()
