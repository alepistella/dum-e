# dum-e

Dum-e is my ROS 2 robot project: embedded motor control, simulation, mapping
and navigation, built and tested outside working hours.

Weekend robotics, embedded and Edge AI builds, with the measurements.
Occasionally they even work.

This repository collects the code, experiments and development notes. Some
folders cover tools and fixes needed along the way, rather than the robot
itself.

## Development tools and fixes

The development environment includes ROS 2 Jazzy on Ubuntu 24.04 ARM64,
running in Parallels on Apple silicon.

- [Gazebo on Parallels](gazebo-parallels/README.md): the simulation setup,
  rendering workaround, installation guide and measurements.
- [RViz on Parallels](rviz-parallels/README.md): the black-viewport workaround,
  installation guide and verification results.

Each folder contains its own screenshots, tested versions, evidence and
rollback instructions.

## Conventions

- Every claim with a number has the supporting data beside it.
- Version pins and hash gates are deliberate. If a check stops you, the
  combination is untested; do not remove the check.
- Nothing here is an official package of the projects it touches.

## License

Apache-2.0 unless a file says otherwise. Third-party code keeps its own
license and credits.
