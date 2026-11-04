# dum-e

Weekend robotics, embedded and Edge AI builds, with the measurements.
Occasionally they even work.

Each directory is one build or one problem, with the commands, the data and
the decision that came out of it.

## Contents

| Directory | What it is | State |
|---|---|---|
| [gazebo-parallels](gazebo-parallels/INSTALL.md) | Hardware-accelerated Gazebo Harmonic for ROS 2 Jazzy on Parallels (Apple silicon): about 60 GUI updates/s on the virtual GPU, with working LiDAR and RGB camera. Build kit, colcon overlay, 53-trial ablation. | Reproduced on one machine. Clean-VM run pending. Upstream fix [merged](https://github.com/gazebosim/gz-rendering/pull/1400). |
| [gazebo-parallels/rviz](gazebo-parallels/rviz/README.md) | Add-on for the kit above: RViz 2 black viewport fixed by pointing the packaged `rviz2` at the same private Mesa runtime, hardware rendering kept. Covers `rviz2`, `ros2 run` and `ros2 launch`; gated install and rollback. | Verified on the same VM, 4 November 2026. |

## Conventions

- Every claim with a number has the raw data next to it, in `evidence/`.
- Version pins and hash gates are deliberate. If a check stops you, the
  combination is untested; do not remove the check.
- Nothing here is an official package of the projects it touches.

## License

Apache-2.0 unless a file says otherwise. Third-party code keeps its own
license and credits.
