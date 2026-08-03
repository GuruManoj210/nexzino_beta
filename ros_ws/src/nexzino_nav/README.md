# nexzino_nav

Navigation and mapping package for the `nexzino` ROS Noetic robot.

## What this package contains

- Base bringup for the `nexzino` URDF and wheel odometry driver
- RealSense bringup with depth alignment and point cloud output
- Gazebo simulation using the `nexzino` xacro description
- RTAB-Map mapping pipeline
- RTAB-Map localization pipeline
- `move_base` navigation with RealSense point cloud used directly for obstacle detection

## Launch files

- `bringup.launch`
  Selects hardware or Gazebo bringup using one argument.
- `base_bringup.launch`
  Starts `robot_state_publisher`, the ZLTech differential drive node, and the hardware RealSense node.
- `simulation_bringup.launch`
  Starts Gazebo and spawns the simulated Nexzino with the RealSense Gazebo plugin.
- `mapping.launch`
  Starts either hardware or simulation bringup and RTAB-Map mapping.
- `navigation.launch`
  Starts either hardware or simulation bringup, RTAB-Map localization, and move_base.
- `map_saver.launch`
  Saves the current `/map` topic to a 2D occupancy map if you want a YAML/PGM export.

## Files you must review and fill

1. `config/diff_drive.yaml`
   Set your motor serial port, command signs, encoder signs, wheel radius, wheel separation, meters per revolution, and max RPM.
2. `config/costmap_common.yaml`
   Set the `footprint` and point-cloud filtering limits to match the real robot body and sensor mount.
3. `config/rtabmap_mapping.yaml`
   Tune the mapping behavior if needed.
4. `config/rtabmap_localization.yaml`
   Tune localization-only behavior against a saved RTAB-Map database.
5. `launch/realsense_bringup.launch`
   If your RealSense model or topic layout differs, adjust the launch arguments or topic remaps here.
6. `nexzino/urdf/nexzino.urdf.xacro`
   This is now the main robot description. The RealSense mesh has been replaced by the RealSense description macro and Gazebo plugin chain.
7. `worlds/nexzino_navigation.world`
   Default lightweight Gazebo world for mapping and navigation simulation.

## Recommended bringup order

### 1. Base only

```bash
roslaunch nexzino_nav base_bringup.launch use_realsense:=false
```

Check:

- `/odom`
- `/joint_states`
- `/tf`
- robot motion from `/cmd_vel`

### 2. Base + RealSense

```bash
roslaunch nexzino_nav base_bringup.launch
```

Check:

- `/camera/color/image_raw`
- `/camera/aligned_depth_to_color/image_raw`
- `/camera/depth/color/points`

### 3. Simulation bringup

```bash
roslaunch nexzino_nav bringup.launch simulation:=true
```

Check:

- `/odom`
- `/camera/color/image_raw`
- `/camera/depth/image_raw`
- `/camera/depth/color/points`

### 4. Mapping pipeline

```bash
roslaunch nexzino_nav mapping.launch
```

Simulation mapping:

```bash
roslaunch nexzino_nav mapping.launch simulation:=true
```

The RTAB-Map database is written to:

```bash
$HOME/.ros/nexzino_rtabmap.db
```

### 5. Navigation on saved map

```bash
roslaunch nexzino_nav navigation.launch database_path:=$HOME/.ros/nexzino_rtabmap.db
```

Simulation navigation:

```bash
roslaunch nexzino_nav navigation.launch simulation:=true database_path:=$HOME/.ros/nexzino_rtabmap.db
```

## Notes

- This stack uses wheel odometry from the ZLTech base driver as the primary odometry source.
- RealSense is used directly as a 3D obstacle sensor through `/camera/depth/color/points`.
- RTAB-Map handles both mapping and localization, which fits a RealSense-only robot better than AMCL.
- In hardware, the RealSense node is configured with `publish_tf:=false` so the URDF/xacro remains the source of truth for the camera TF tree.
- In simulation, the RealSense topics come from the Gazebo plugin embedded in the robot xacro.
