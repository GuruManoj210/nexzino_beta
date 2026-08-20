# Deploy

Runs the Nexzino robot's on-device services in a single Docker container:
a local `roscore`, the `diff_drive_controller.py` ROS node, the
`servo_tester` web UI, `web_teleop`'s joystick page, `rosbridge_websocket`,
`nav_console` (mapping/navigation web UI), and `web_video_server` (live
camera view). Intended to run directly on the robot (e.g. the Jetson), not
in the VSCode dev container.

The image also carries the full navigation/SLAM stack
(`ros-noetic-navigation`, `rtabmap`, `realsense2-camera`, `nexzino`/
`nexzino_nav`'s launch files) - `nav_console` launches `mapping.launch`/
`navigation.launch` as subprocesses **on demand** (via its Start
Mapping/Start Navigation buttons), inside this same running container - see
[Mapping and navigation](#mapping-and-navigation) below.

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
5. `rosbridge_websocket` (port **9090**) - ROS-over-websocket bridge;
   `nav_console`'s frontend talks to ROS directly from the browser over this
6. `nav_console/app.py` - mapping/navigation web UI + joystick, port **5001**;
   launches/stops `mapping.launch`/`navigation.launch` as subprocesses
7. `web_video_server` (port **8080**) - re-streams `/camera/color/image_raw`
   as MJPEG; `nav_console`'s Mapping/Navigation pages embed it directly so
   you can see what the robot's camera sees while driving. Idle/blank until
   a mapping or navigation session brings the camera up.

If any one of these exits, the entrypoint tears the rest down and exits
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
official ROS image, which genuinely publishes amd64/arm64/armv7 builds, and
installs the navigation/RTAB-Map/RealSense packages it needs directly via
apt on top of that. This also means the same `docker compose build` works
unchanged on an x86 dev machine or the Jetson.

`nexzino` and `nexzino_nav` (the URDF/meshes and the launch/config files)
are copied in as plain source - they're pure Python/resource packages with
no messages or compiled code, so being on `ROS_PACKAGE_PATH` (set via the
image's `ENV`) is enough for `$(find ...)` and `roslaunch` to find them; no
`catkin build` needed inside this image.

## Run

```bash
cd deploy
docker compose up -d      # start in the background
docker compose logs -f    # follow all processes' output
docker compose down       # stop and remove the container
```

- servo_tester: `http://<robot-ip>:5000`
- web_teleop: `http://<robot-ip>:8000`
- nav_console (mapping/navigation + joystick + live camera view): `http://<robot-ip>:5001`
- web_video_server (raw MJPEG stream, mostly useful for debugging outside
  `nav_console`): `http://<robot-ip>:8080/stream?topic=/camera/color/image_raw`

The container uses host networking (`network_mode: host`), so all ports
are reachable directly on the robot's IP - there's no `ports:` mapping to
edit.

## Mapping and navigation

The easiest way to do this is **`nav_console`** at `http://<robot-ip>:5001`
- pick Mapping or Navigation from the home page, drive around with its
on-screen joystick, click **Save Map** when you're done (prompts for a
name), and load any saved map later from the Navigation page's map
dropdown to localize and send goals by clicking on the map.

`nav_console` handles the one thing you'd otherwise have to remember
yourself: `diff_drive_controller.py` is already running as one of the
always-on services, so it always launches `mapping.launch`/
`navigation.launch` with `start_motor_driver:=false` - a second process
trying to reopen the same wheel-controller serial port would break both.
It also always passes `open_rviz:=false` (no display in the container -
see below for viewing the map).

**Map storage**: "Save Map" copies the just-finished mapping session's live
RTAB-Map database into `nav_console/data/maps_db/<name>.db` (this is the
actual map `navigation.launch`'s `database_path` loads back later) and also
snapshots a `.pgm`/`.yaml`/`.png` thumbnail via `map_saver` for the web UI's
map preview. Saving **stops the current mapping session** - RTAB-Map's
database needs to be cleanly closed to copy it safely (copying a sqlite
file that's still open for writing risks grabbing a corrupt/partial
snapshot); if you want to keep mapping after saving, just click Start
Mapping again.

### Manual alternative

You can still drive `mapping.launch`/`navigation.launch` by hand instead of
through `nav_console` - useful for scripting or debugging:

```bash
docker exec -it nexzino-deploy bash
source /opt/ros/noetic/setup.bash

roslaunch nexzino_nav mapping.launch start_motor_driver:=false open_rviz:=false \
    database_path:=/opt/nexzino/nav_console/data/mapping_session.db

roslaunch nexzino_nav navigation.launch start_motor_driver:=false open_rviz:=false \
    database_path:=/opt/nexzino/nav_console/data/maps_db/<name>.db
```

### Viewing the map/robot

`open_rviz:=false` everywhere above because the container has no display
attached. Two ways to actually see it:

- **`nav_console`'s own map view** (the easiest option, works from any
  browser on the network, no setup) - navigate to the Mapping or Navigation
  page and the live map/robot pose renders right there via rosbridge.
- **RViz on a separate machine** on the same network:
  ```bash
  # On your dev laptop, NOT the Jetson:
  export ROS_MASTER_URI=http://<jetson-ip>:11311
  rosrun rviz rviz -d <path to>/nexzino_nav/config/nexzino_nav.rviz
  ```
  This works because the deploy container uses host networking, so its
  `roscore` (port 11311) is directly reachable from other machines on the
  same LAN - standard multi-machine ROS, no extra setup needed. Your laptop
  needs its own ROS Noetic + a checkout of `nexzino_nav` (for the `.rviz`
  config and, if you want the robot mesh rendered, the `nexzino` package)
  - nothing extra needs installing inside the Jetson's container.

### Debugging with RViz on the robot itself

For diagnosing SLAM/costmap issues (e.g. the occupancy grid painting solid
black over open floor) it's often easier to watch the raw point cloud,
`/map`, and (during navigation) the local/global costmaps live in RViz on a
monitor plugged straight into the robot, rather than the simplified view
`nav_console` renders in-browser - `nexzino_nav.rviz` already has all of
these wired up (`/camera/depth/color/points`, `/map`,
`/move_base/global_costmap/costmap`, `/move_base/local_costmap/costmap`).

`docker-compose.yml` passes `DISPLAY` through and mounts `/tmp/.X11-unix`
for exactly this. Steps, run directly on the Jetson (with a monitor
attached to it, not over SSH from another machine):

1. Allow the container's root user to open windows on your X session (run
   once per login, on the Jetson's own desktop, before starting the stack):
   ```bash
   xhost +si:localuser:root
   ```
2. Start the stack in the foreground so you can watch all services' logs:
   ```bash
   cd deploy
   docker compose up
   ```
3. In a second terminal on the Jetson, exec into the running container and
   launch mapping (or navigation) by hand with `open_rviz:=true`:
   ```bash
   docker exec -it nexzino-deploy bash
   source /opt/ros/noetic/setup.bash

   roslaunch nexzino_nav mapping.launch start_motor_driver:=false open_rviz:=true \
       database_path:=/opt/nexzino/nav_console/data/mapping_session.db
   ```
   **Don't also click Start Mapping in `nav_console` while doing this** -
   that would launch a second `rtabmap` process fighting the first one over
   the same camera topics. Drive the robot with `web_teleop` (port 8000,
   already running) instead, and watch RViz for what the point cloud/grid
   are actually doing as you drive it over floor you know is clear.
4. `Ctrl+C` the `roslaunch` in the second terminal when done (this closes
   RViz too); `nav_console`'s own Start Mapping/Start Navigation continue to
   work normally afterward.

This image is `FROM ros:noetic-ros-base`, not a Jetson L4T base image, so it
doesn't have the Jetson's proprietary GL/EGL libraries - RViz will very
likely fall back to software rendering (Mesa llvmpipe) here rather than
using the GPU. Expect it to feel sluggish; it's still fine for visually
checking what the point cloud/grid are doing. If it's unusably slow or
fails to get a GL context at all, fall back to the
[RViz on a separate machine](#viewing-the-maprobot) option above instead -
that runs a normal ROS Noetic install on your dev laptop, which has no
GL-in-container problems to deal with.

## Rebuilding after code changes

```bash
cd deploy
docker compose build
docker compose up -d
```

## Persistent data

Named volumes so rebuilding or recreating the container doesn't wipe this:

| Volume | Container path | What's in it |
| --- | --- | --- |
| `servo-data` | `/opt/nexzino/servo_tester/data` | Saved animations, timelines, profiles, dev-mode flag |
| `ros-home` | `/root/.ros` | Manually-run `mapping.launch`/`navigation.launch`'s default RTAB-Map database (only relevant if you skip `nav_console` and don't pass `database_path:=` yourself) |
| `nav-console-data` | `/opt/nexzino/nav_console/data` | `maps.json` registry + one saved RTAB-Map `.db` per named map |
| `nav-console-maps` | `/opt/nexzino/nav_console/static/maps` | `.pgm`/`.yaml`/`.png` map thumbnails `nav_console`'s UI displays |

To reset everything (all saved maps, servo profiles/animations, etc.):

```bash
docker compose down -v   # removes all of the above volumes too
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
  check which process is failing. Missing serial hardware is the most
  common cause - both `diff_drive_controller.py` and `servo_tester`'s servo
  controller connect to hardware at startup.
- **Can't reach port 5000/8000/5001 from another machine**: confirm the
  container is actually running (`docker compose ps`) and that nothing on
  the robot's host firewall is blocking those ports (host networking means
  there's no Docker-level port mapping to misconfigure - if the container
  is up and the port isn't reachable, it's a host firewall or wrong IP).
- **`roslaunch nexzino_nav ...` fails with "package not found"** (only
  relevant if you're running it by hand, not through `nav_console`):
  confirm `ROS_PACKAGE_PATH` includes `/opt/nexzino/ros_ws/src` (`echo
  $ROS_PACKAGE_PATH` inside the container after sourcing
  `/opt/ros/noetic/setup.bash`) - it's appended in `entrypoint.sh` and baked
  into `/root/.bashrc` for interactive shells, but a shell that sources ROS's
  own `setup.bash` through some other path won't pick it up (that script
  overwrites `ROS_PACKAGE_PATH` rather than appending to it).
- **`mapping.launch`/`navigation.launch` can't open the wheel controller
  port**: you're running it by hand without `start_motor_driver:=false` -
  it's trying to open the same serial device `diff_drive_controller.py`
  already has open. `nav_console` always passes this correctly on its own.
- **No RGB/depth topics, camera never comes up**: check
  `rostopic list | grep camera` and the `realsense2_camera` node's own log
  output for a hardware-not-found error - confirm the D435i is actually
  enumerated on the host (`rs-enumerate-devices` if `librealsense2-utils`
  is available, or `lsusb`).
- **`nav_console`'s map view/joystick never connects (stays blank, or the
  joystick doesn't move anything)**: this goes over `rosbridge_websocket`
  (port 9090), not a plain HTTP call - check `docker compose logs -f` for
  rosbridge actually being up, and open the browser's console for a
  websocket connection error. If you're accessing `nav_console` through
  something other than its direct `http://<robot-ip>:5001` URL (an SSH
  tunnel, a reverse proxy, etc.), the frontend derives the rosbridge host
  from `window.location.hostname` - a proxy that changes the hostname the
  browser sees will break this.
- **"Save Map" in `nav_console` returns an error / no map appears in the
  dropdown afterward**: it only works while a mapping session is actually
  running - check that "Start Mapping" was clicked first and the camera
  came up successfully (see the RGB/depth item above).
- **Camera view on the Mapping/Navigation page stays a broken-image icon**:
  it only has something to show once a mapping/navigation session has the
  camera up (same prerequisite as the RGB/depth item above) - it's normal
  for it to be blank before you click Start Mapping/Start Navigation. If it's
  still blank after that, confirm `web_video_server` is running (`docker
  compose logs -f | grep web_video_server`) and that
  `http://<robot-ip>:8080/stream?topic=/camera/color/image_raw` loads
  directly in a browser.
- **Occupancy grid renders solid black, including in open floor space**:
  this is a classic symptom of the depth camera picking up the floor itself
  as a close-range "obstacle" - usually either the camera is physically
  angled slightly downward, or there's a mounting-angle error somewhere in
  the TF chain feeding RTAB-Map (`camer_joint`/`realsense_mount_joint`/the
  `sensor_d435` macro origin in `nexzino.urdf.xacro`). Use the camera view
  above to check: if the color image itself looks tilted toward the floor
  rather than roughly level/forward, that's the mounting angle, not a
  software bug in the grid params. If the color image looks level but the
  map is still solid black, the likelier cause is bad/noisy depth data
  (worth comparing against the pre-bandwidth-fix 848x480 depth stream if you
  still have hardware headroom to test it) rather than a `Grid/*` param
  tuning issue - `rtabmap_mapping.yaml`'s ground-detection params
  (`Grid/NormalsSegmentation`, `Grid/MaxGroundAngle`, `Grid/GroundIsObstacle`)
  are all already at RTAB-Map's own defaults, which are the right defaults
  for a level-mounted camera.
