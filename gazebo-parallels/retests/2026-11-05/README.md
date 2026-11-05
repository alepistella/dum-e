# Parallels 27.1.0 rendering retest, 5 November 2026

**Result: retain the existing Gazebo and RViz profiles.** Both applications
still fail with the standard runtime on this Ubuntu 24.04 ARM64 VM after
updating Parallels Desktop and Parallels Tools to 27.1.0 (58756).

| Application | Standard effective runtime | Existing profile re-enabled |
|---|---|---|
| Gazebo Harmonic | Ogre 2 / system Mesa 25.2.8: GUI aborts compiling a fragment shader | Private Ogre 1 / Mesa 24.0.5: 3D shapes visible |
| RViz Jazzy | Original executable / system Mesa 25.2.8 / VirGL: black or empty viewport | Private Mesa 24.0.5 / VirGL: map visible |

The operator confirmed the RViz stock failure and both successful profile
checks on the VM display. Driver logs and loaded libraries supplement the
visual checks. This was a functional rendering check, not a new FPS benchmark,
sensor-accuracy experiment or clean-VM reproduction.

## How the standard runtime was tested

Before testing, selected installed entry points, saved vendor executables,
manifests, runtime libraries and saved GUI/server settings were hashed.
Small configuration files and executables were also copied into a temporary
backup directory on the VM.

The installed profiles were bypassed for the test processes; they were not
uninstalled. This lets the applications load the standard binaries and
system Mesa while leaving the working installation available for immediate
recovery. No profile library or private Mesa path was inherited by stock
launches. `session.py` records the environment cleanup and exact arguments.

- Gazebo used `GZ_VIRGL_DEFAULTS=0`, `shapes.sdf`, an explicit `ogre2` engine
  and a copy of the packaged GUI configuration. The saved user GUI config
  did not choose the engine for this test. The failed shader reports
  `no matching function for call to texelFetch(usampler2D, int)`, followed by
  an OGRE exception and abort.
- RViz used the retained original executable, a copy of the packaged
  Cartographer display configuration, and simulation time disabled.
  `/proc/<pid>/maps` showed the system Mesa 25.2.8 Gallium library.
- A synthetic 100x100 occupancy grid and static transforms were published in
  ROS domain 86, independently of the course's simulation and mapping nodes.
  This ensures that a missing Cartographer publisher cannot explain an empty
  map. The synthetic scene contains a square boundary and two obstacles.
- The Gazebo test used its own transport partition.

No package, model, shader, system driver or shell-startup file was modified.
The subsequent profile checks used the same map/display fixture for RViz
and `shapes.sdf` for Gazebo. Both normal entry points selected their existing
private runtime again.

## End state

`evidence/final-state.json` reports no changed configuration files and an
identical diversion registry. Both profiles remain enabled for ordinary
`gz sim`, `rviz2` and ROS launch commands. All test applications and the
synthetic map publisher were stopped after verification.

The selected-file hash comparison is an installation/configuration check;
normal application logs and shader caches are not expected to stay unchanged.
The runtime was never removed, so no reinstall or driver downgrade was needed.

## Evidence

- `results.json`: concise outcomes and scope.
- `evidence/environment.txt`: guest Tools, kernel, driver and package versions.
- `evidence/before.json`, `final-state.json`: hashes and diversion comparison.
- `evidence/loaded-libraries.json`: restored processes and private libraries.
- `evidence/gazebo-stock/`: console failure and Ogre 2 compile log.
- `evidence/rviz-stock/`: driver log and map-loading output.
- `evidence/gazebo-profile/`, `rviz-profile/`: restored-profile logs.
- `session.py`, `map_fixture.py`: scripts used for this isolated session.

The session scripts use fixed paths and an isolated ROS domain. They are
records of this test, not a general installer. Source Jazzy and review the
paths before reusing them; the companion fixture must be stopped afterwards.

## Release notes

The official [Parallels 27 updates summary](https://kb.parallels.com/en/131168)
places the 27.1.0 OpenGL application fixes in its Windows VM section. Its Linux
section lists other fixes. These notes alone would not establish that Gazebo
or RViz on Linux was fixed; the comparison above tests this VM directly.
