# RViz on Parallels: use the existing private Mesa runtime

This optional add-on fixes the black RViz viewport observed on the same
Ubuntu 24.04 ARM64 / Parallels VM used for the Gazebo workaround.
It keeps the packaged RViz executable and its OGRE 1.12.10 renderer.
The only rendering change is selecting the existing private Mesa 24.0.5
libraries and VirGL driver for RViz processes.

## What was verified

On 4 November 2026, RViz 14.1.24 loaded system Mesa 25.2.8 and displayed a
black viewport. The Cartographer map had reached RViz; the initial log
reported its dimensions. A software-rendered control displayed the map.

| Test | Observation |
|---|---|
| System Mesa 25 / VirGL, normal launch | Black viewport; reproduced after restart |
| System Mesa 25 / VirGL, OpenGL 2.1 override | Black viewport |
| System Mesa 25 / VirGL, antialiasing disabled | Gray, then black viewport |
| Private Mesa 24 / VirGL, antialiasing disabled | Grid and map visible |
| Private Mesa 24 / VirGL, normal antialiasing | Grid and map visible |

The successful accelerated test logged
`GL_RENDERER = virgl (Apple M5 Max (Compat))`, OpenGL 4.0 and `FSAA=4`.
Its process mapped the private `virtio_gpu_dri.so` and `libGLX_mesa.so.0`.
The visual observations were confirmed on the VM by its operator.
The early unlabeled Mesa 24 trial was inconclusive because multiple windows
were open; the distinctly titled comparison above is the evidence used here.

The `active samplers with a different type refer to the same texture image
unit` shader warning also occurred in the working software control. It does
not, by itself, identify the cause of a black viewport. No shader patch,
OpenGL override, antialiasing shim or software-rendering default is installed.

This is a driver-version workaround verified on one VM. It does not identify
a specific Mesa regression commit, certify every RViz plugin, or establish a
new RViz FPS benchmark. The Gazebo 53-trial matrix is a separate experiment;
these RViz checks do not change that count. Raw logs and the installation
verification are in [evidence](evidence/).

## Prerequisites

- The [Gazebo private runtime](../INSTALL.md) must already be installed at
  `/usr/local/lib/gazebo-virgl-defaults/runtime-v2/mesa`.
- Ubuntu 24.04 ARM64, ROS 2 Jazzy and RViz must already be installed.
- The tested `ros-jazzy-rviz2` package is
  `14.1.24-1noble.20260916.104902`. Both original executable hashes must be
  `8c1b6d120d0bb89d546350d8ed031b2c3df7d15b4f4f8373f7a67310a0e74261`.

The installer refuses other package versions, executable contents or existing
diversions. It also checks both private Mesa file hashes against the tested
runtime. Inspect and revalidate an untested combination rather than
removing the gates. No packages are downloaded or installed by this add-on.

## Install inside the VM

Update your checkout, close RViz, and leave the simulation running if needed.
From the repository root:

```bash
source /opt/ros/jazzy/setup.bash
python3 gazebo-parallels/rviz/manage.py --check
sudo python3 gazebo-parallels/rviz/manage.py --install
```

The first command is read-only. The install command:

1. Backs up both original RViz executables under
   `/var/backups/rviz-virgl-defaults/<UTC timestamp>/`.
2. Registers local `dpkg-divert` entries for
   `/opt/ros/jazzy/bin/rviz2` and `/opt/ros/jazzy/lib/rviz2/rviz2`.
   Their originals are retained alongside them with a `.distrib` suffix.
3. Places the same small wrapper at both entry points. It prepends private
   Mesa to `LD_LIBRARY_PATH`, sets `LIBGL_DRIVERS_PATH`, and executes the
   original binary with every argument preserved.
4. Saves the package version, original/wrapper/runtime checksums and backup
   location in `/usr/local/lib/rviz-virgl-defaults/manifest.json`.
5. Installs `/usr/local/sbin/rviz-virgl-defaults-rollback`.

If installation fails after registering a diversion, it removes the new
wrappers and restores the original entry points. Backups remain available.

This covers the shell command, `ros2 run`, and ordinary ROS launch files that
resolve the installed Jazzy RViz executable. Custom RViz builds in another
workspace are outside this profile. Environment changes are confined to RViz
and any subprocesses it starts. There is no shell-startup edit, system Mesa
downgrade, global preload, Gazebo profile change or model edit.

`dpkg-divert` makes future package updates target the retained `.distrib`
executables. It does not validate compatibility with future RViz versions:
repeat the checks after updates. Private Mesa is not upgraded by APT.

## Normal use

Use the usual commands, without a custom launcher:

```bash
rviz2
ros2 run rviz2 rviz2
ros2 launch turtlebot3_cartographer cartographer.launch.py use_sim_time:=true
```

Only start one Cartographer launch for the simulation. The third command is
an alternative to starting it elsewhere, not an additional mapping process.

To inspect the installed profile:

```bash
python3 /usr/local/lib/rviz-virgl-defaults/manage.py --status
```

For a reproducible RViz-only ROS launch check, while Gazebo and your existing
mapping nodes are already running:

```bash
mkdir -p /tmp/rviz-check
cd /tmp/rviz-check
ros2 launch "$HOME/dum-e/gazebo-parallels/rviz/verify.launch.py"
```

This launches RViz only, with the packaged TurtleBot3 Cartographer display
configuration, simulation time and an OGRE log. It does not launch or restart
Gazebo or Cartographer. A different configuration can be supplied as
`rviz_config:=/absolute/path/to/config.rviz`.

Check that `Ogre.log` contains `virgl`, and that the RViz process maps the
private Mesa driver. A working grid demonstrates rendering; a map also needs
its publishers and TF transforms. A missing map or TF queue warning after
stopping Cartographer is not evidence that the graphics profile failed.

```bash
grep -E 'GL_RENDERER =|GL_VERSION =|FSAA=' Ogre.log
pgrep -a -f '[r]viz2.distrib'
# Substitute the PID printed above:
grep -E 'mesa/|dri/' /proc/<PID>/maps
```

For an individual diagnostic launch with the original driver selection:

```bash
RVIZ_VIRGL_DEFAULTS=0 rviz2
```

An existing RViz window is not changed when the profile is installed or
bypassed; close and restart that process to compare.

## Restore

Close RViz, then:

```bash
sudo /usr/local/sbin/rviz-virgl-defaults-rollback
```

The rollback validates both wrappers and diversions before making changes,
removes the diversions and restores the current packaged executables. It
keeps a timestamped archive of the profile and the original installation
backups. Restoring both original executable hashes and reinstalling the
profile were tested on the VM. Roll back this add-on before removing the
private Mesa files it depends on.

## Files

- `manage.py`: read-only preflight/status, guarded install, rollback.
- `rviz2-wrapper.sh`: the two entry points use identical wrapper contents.
- `verify.launch.py`: optional RViz-only ROS launch check.
- `evidence/`: driver logs, controlled observations and installation record.

Scripts and documentation: Apache-2.0, Alessandro Pistella. ROS, OGRE and Mesa
retain their original licenses. This add-on does not modify or redistribute
their source code or binaries.
