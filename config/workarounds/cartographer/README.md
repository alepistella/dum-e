# Cartographer: conservative loop-closure search

## Why this setting exists

In the TurtleBot3 house simulation, the default 7 m translational search
allowed global map associations that produced multi-meter distortion.
Reducing the search window to 1 m retained global optimization and reduced
final position error to 0.090 m on replay. An independent live route ended
at 0.060 m, with 0.119 m maximum position error.

The complete [experiment and measurements](../../../rviz-parallels/addons/cartographer-house/MEASUREMENTS.md)
separate numerical results, controls and limitations. This is a tested
configuration choice for that setup, not proof of a Cartographer code bug
or a universal solution for every sensor or environment.

## Reuse in Dum-e's own 2D profile

Copy [conservative_loop_closure.lua](conservative_loop_closure.lua) into the
configuration directory installed by the robot's ROS package. In the robot's
main Lua file, after initializing `options`, add this immediately before its
final return:

```lua
include "conservative_loop_closure.lua"
return options
```

The included file sets:

```lua
POSE_GRAPH.constraint_builder.fast_correlative_scan_matcher.linear_search_window = 1.0
```

The search is centered on the predicted alignment. This parameter controls
where Cartographer searches for a matching location; it does not change
LiDAR range, the physical map extent or odometry units. Global optimization
and loop closure remain enabled.

Treat 1 m as a candidate when validating Dum-e. A smaller window rejects
some wrong associations, but also excludes a correct match if the prior
position is already too far away. The right window depends on odometry,
sensor coverage, geometry and the amount of drift between revisits. This
2D setting is not a configuration for Cartographer's 3D scan matcher.

## Validation procedure for a new robot

1. Check sensor frame offsets, timestamp monotonicity, scan/odometry rates
   and TF ownership. Confirm that raw scans match measured geometry.
2. Record scans, odometry, TF/static TF, clock when simulated, commands,
   the exact Lua files, package versions and a route description.
3. Establish an independent reference. In Gazebo, use model ground truth.
   On hardware, use surveyed checkpoints, external tracking or another
   reference with known uncertainty. Wheel odometry alone is not truth.
4. Replay the same data with the original configuration. Remove recorded
   `map -> odom` transforms and isolate the replay from the live robot.
5. Temporarily disable global optimization to distinguish local drift from
   errors introduced by global associations. This is a diagnostic control.
6. Change one parameter at a time. Compare final, maximum, RMS and 95th
   percentile position errors, heading error and occupancy-grid consistency.
   Inspect the times of large corrections rather than relying on a screenshot.
7. Validate the chosen setting on a new live route with revisits, turns,
   the difficult room and different starting/approach directions. Repeat on
   additional environments before treating it as a general robot setting.

Do not accept a visually clean map as the only criterion. Preserve failed
recordings and explain excluded runs. A parameter tuned on one recording
can overfit it.

## Defaults and rollback

The managed default in the companion add-on changes only the packaged
TurtleBot3 2D configuration. It does not modify Cartographer's shared
`pose_graph.lua`, custom robot profiles, or this Dum-e include.

For Dum-e, removing the include restores the values inherited by its main
configuration. For the managed TurtleBot3 default, use the documented
[rollback](../../../rviz-parallels/addons/cartographer-house/README.md#make-the-tested-turtlebot3-profile-the-default).

**Dum-e hardware status: not yet validated.** Keep the robot's actual sensor
limits, frames and odometry settings in its own main profile; do not copy
TurtleBot3's configuration wholesale.
