# Settings and workarounds

Keep each subsystem in its own directory, with the reason for the setting,
the environment where it was measured, evidence, limitations and rollback.
Avoid changing upstream defaults for unrelated robots.

| Subsystem | Scope | Status |
|---|---|---|
| [Cartographer](cartographer/README.md) | 2D loop-closure search | Validated on two TurtleBot3 house recordings; candidate for Dum-e, not yet tested on Dum-e hardware |

Graphics workarounds remain in [Gazebo](../../gazebo-parallels/README.md) and
[RViz](../../rviz-parallels/README.md). Those change rendering; the Cartographer
setting changes map estimation.
