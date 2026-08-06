# Deploy

Runs the Nexzino robot's on-device services in a single Docker container:
a local `roscore`, the `diff_drive_controller.py` ROS node, the
`servo_tester` web UI, and the `web_teleop` joystick page. Intended to run
directly on the robot (e.g. the Jetson), not in the VSCode dev container.

## What's running

`deploy/entrypoint.sh` starts these, in order, inside one container:

1. `roscore`
2. `ros_ws/src/nexzino_nav/scripts/diff_drive_controller.py` - the wheel
   motor ROS node, with its private params loaded from
   `ros_ws/src/nexzino_nav/config/diff_drive.yaml` (same params
   `diff_drive.launch` uses)
3. `servo_tester/app.py` - arm servo control/animation UI, port **5000**
4. `web_teleop/app.py` - joystick teleop UI, port **8000**, publishes
   `geometry_msgs/Twist` on `/cmd_vel`

If any one of the four exits, the entrypoint tears the rest down and exits
too, so the container's restart policy brings everything back up together
instead of leaving some services running against a half-dead ROS graph.

## Prerequisites

- Docker + the Compose plugin (`docker compose version` should work)
- The robot's serial hardware attached before starting: the ZLAC8015D wheel
  controller (`/dev/ttyACM0`) and the Feetech USB servo adapter. Both nodes
  connect to their hardware at startup and will crash (triggering a restart)
  if it's missing. If more than one USB-serial adapter is plugged in, see
  [Pinning serial ports](#pinning-serial-ports) below before starting -
  otherwise auto-detection could pick the wrong one.

## Build

```bash
cd deploy
docker compose build
```

This image is deliberately **not** built on top of `.devcontainer/Dockerfile`.
That image is `FROM osrf/ros:noetic-desktop-full`, which only publishes an
amd64 manifest - no arm64 build exists at all (confirmed with `docker buildx
imagetools inspect osrf/ros:noetic-desktop-full`), so it can't build natively
on a Jetson. `deploy/Dockerfile` instead uses `ros:noetic-ros-base`, the
official ROS image, which genuinely publishes amd64/arm64/armv7 builds - and
it's all this container needs anyway, since `entrypoint.sh` never runs
gazebo/rviz/rtabmap, only `roscore` plus two plain Python/Flask processes.
This also means the same `docker compose build` works unchanged on an x86
dev machine or the Jetson.

## Run

```bash
cd deploy
docker compose up -d      # start in the background
docker compose logs -f    # follow all four processes' output
docker compose down       # stop and remove the container
```

- servo_tester: `http://<robot-ip>:5000`
- web_teleop: `http://<robot-ip>:8000`

The container uses host networking (`network_mode: host`), so both ports
are reachable directly on the robot's IP - there's no `ports:` mapping to
edit.

## Rebuilding after code changes

```bash
cd deploy
docker compose build
docker compose up -d
```

## Persistent data

`servo_tester`'s saved animations, timelines, profiles, and dev-mode flag
live in `/opt/nexzino/servo_tester/data` inside the container, which is
backed by the `servo-data` named volume. Rebuilding or recreating the
container does **not** wipe this data. To reset it:

```bash
docker compose down -v   # removes the servo-data volume too
```

## Hardware access

The container runs `privileged: true` with `/dev:/dev` bind-mounted (same
pattern as `.devcontainer/devcontainer.json`), so both the wheel controller
and servo USB adapter appear inside the container under their normal host
device paths, including `/dev/serial/by-id/...` symlinks. `ros:noetic-ros-base`
runs as root by default, which sidesteps needing a `dialout` group membership
to open the serial devices.

## Pinning serial ports

With multiple USB-serial adapters plugged into the robot, raw device names
like `/dev/ttyACM0` or `/dev/ttyUSB0` aren't reliable - which name goes to
which physical device can change between reboots or reconnects, so
auto-detection (or a stale saved path) can end up talking to the wrong one.
To fix this, pin exact devices for both the wheel controller and the arm
servo adapter:

1. With everything plugged in, list stable-by-id paths:

   ```bash
   ls -l /dev/serial/by-id/
   ```

   If two devices share the same vendor:product ID (e.g. two identical USB
   adapters) and look identical in that list, unplug one at a time and
   re-run the command to tell which `by-id` entry is which, or check
   `udevadm info -a -n /dev/ttyACM0` (etc.) for a distinguishing serial
   number.

2. Copy `deploy/.env.example` to `deploy/.env` (gitignored - each robot
   pins its own) and fill in the two paths:

   ```bash
   cd deploy
   cp .env.example .env
   # edit .env with the by-id paths from step 1
   ```

3. `docker compose up -d` (or `restart`) picks these up automatically -
   Compose loads `deploy/.env` on its own.

Setting `WHEEL_CONTROLLER_PORT` overrides `diff_drive_controller.py`'s
`~port` param (normally loaded from `diff_drive.yaml`, default
`/dev/ttyACM0`); it always wins when set. Setting `SERVO_CONTROLLER_PORT`
overrides `servo_tester`'s serial port the same way, taking priority over
whatever's saved in its active profile - so even a stale profile setting
can't cause it to open the wrong adapter. Leave either blank in `.env` (or
delete the file) to fall back to the previous behavior (yaml default /
saved profile / auto-detect).

## Velocity safety limits

`web_teleop` clamps every command to **±0.3 m/s linear / ±0.3 rad/s
angular** server-side before publishing - a client sending larger values
(bug, tampering, whatever) still can't exceed that. It also fails safe: if
no command arrives for 0.3s (frozen tab, dropped network, joystick stuck) or
the websocket disconnects (tab closed, browser crash) it publishes zero
velocity immediately, independent of what the browser is doing.

The page also has an **Enable/Disable Publishing** button, and publishing
starts **disabled** every time the server (re)starts - the operator has to
explicitly arm it first. The enabled/disabled flag is enforced server-side,
not just in the browser: incoming commands are dropped outright while
disabled, and flipping the switch in *either* direction always resets the
published velocity to zero first, so nothing held from before the flip (or
raced against it) can leak onto `/cmd_vel`.

## Auto-start on boot

Since `restart: unless-stopped` is set, once you've run `docker compose up
-d` at least once, this stack comes back automatically after a reboot as
long as Docker itself starts at boot (`systemctl is-enabled docker` should
say `enabled`; enable it with `sudo systemctl enable docker` if not) - no
extra systemd unit needed for this stack specifically.

## Troubleshooting

- **A service keeps restarting in a loop**: `docker compose logs -f` and
  check which of the four processes is failing. Missing serial hardware is
  the most common cause - both `diff_drive_controller.py` and
  `servo_tester`'s servo controller connect to hardware at startup.
- **Can't reach port 5000/8000 from another machine**: confirm the
  container is actually running (`docker compose ps`) and that nothing on
  the robot's host firewall is blocking those ports (host networking means
  there's no Docker-level port mapping to misconfigure - if the container
  is up and the port isn't reachable, it's a host firewall or wrong IP).
