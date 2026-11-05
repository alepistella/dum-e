# Hardware-accelerated Gazebo Harmonic for ROS 2 Jazzy on Parallels (Apple silicon)

Ubuntu 24.04 ARM64, ROS 2 Jazzy, Gazebo Sim 8.15, gz-rendering 8.2.3.
Tested with Parallels Desktop **27.0.3 (58680)** and **27.1.0 (58756)** on Apple silicon.

See the [tested Parallels versions and before/after results](README.md#tested-parallels-versions).
On both tested versions, the standard Ogre 2 path fails and the installed
Ogre 1 / private Mesa profile renders on the virtual GPU.

Out of the box, `gz sim` on a Parallels VM either crashes (OGRE 2 shaders fail
on the VirGL driver) or runs in software at 6 fps. This kit makes the stock
`gz sim` and `ros2 launch` commands run on the virtual GPU, at about 60 GUI
updates per second, with working LiDAR and RGB camera sensors.

## Status

| Item | Value |
|---|---|
| Verified on | MacBook Pro M5 Max, Ubuntu 24.04.5 ARM64, 8 vCPU, 16 GB. Initial run: Parallels/Tools 27.0.3 (58680). Rendering/recovery retest: Parallels/Tools 27.1.0 (58756), 5 November 2026. |
| Packages | ros-jazzy-ros-gz, Gazebo Sim 8.15.0, gz-rendering 8.2.3, OGRE 1.9.0, system Mesa 25.2.8 |
| GUI | about 60 camera updates/s on `shapes.sdf` and the TurtleBot3 world in the original tests; the 27.1.0 retest checked rendering, not a new FPS benchmark |
| LiDAR | TurtleBot3 360 rays at 10 Hz, max error 1.5 mm against a known wall (131 rays) |
| RGB camera | 1920x1080, correct frames, 8 to 11 images/s over ROS |
| Clean-VM run | not yet recorded. The kit was rebuilt from pristine sources, but a second VM has not been installed from scratch. Treat this as "reproduced once", not "reproducible". |

Not covered: OGRE 2 only features (PBR materials, thermal, segmentation,
bounding box cameras, global illumination), light shadows (disabled by the
profile), depth/RGB-D cameras (not tested), other Gazebo or Ubuntu versions.

## What it changes, and what it does not

The kit builds a private runtime and makes the two Jazzy entry points use it:

- a patched `libgz-rendering-ogre.so` (OGRE 1 component) built from the
  official gz-rendering 8.2.3 tag;
- a private copy of Mesa 24.0.5 (VirGL driver, LLVM 17, XCB DRI2) extracted
  from Ubuntu packages, used only by Gazebo processes;
- a profile that selects OGRE 1, OpenGL, Qt xcb and the private Mesa for
  `gz sim` and the native `gzserver`;
- a small preload library that sets the same defaults for the native server
  and refreshes the GUI scene state when a LiDAR topic is selected.

Installed under `/usr/local/lib/gazebo-virgl-defaults/`. The two entry points
`/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz` and
`/opt/ros/jazzy/lib/ros_gz_sim/gzserver` are preserved with `dpkg-divert`
and replaced by thin delegates. Backups and a manifest go to
`/var/backups/gazebo-virgl-defaults/` and `/usr/local/share/gazebo-virgl-defaults/`.

Not touched: system Mesa, `/etc/ld.so.preload`, your shell startup files,
SDF/URDF models, worlds, TurtleBot packages. Other desktop applications keep
the system driver.

Why these pieces, in one line each:

- Mesa 24.0.5: with system Mesa 25.2.8 on VirGL, LiDAR returns wrong ranges
  and a camera with Gaussian noise publishes all-black frames at 30 Hz.
  Mesa 24.0.5 on VirGL and llvmpipe both produce valid output (53-trial ablation,
  see `evidence/`).
- OGRE 1 patch: single-row LiDAR texture mapping fix (accepted upstream
  in [gazebosim/gz-rendering#1400](https://github.com/gazebosim/gz-rendering/pull/1400)), plus the upstream corrections from #1370
  and #1378, plus shadows forced off (the GUI flickered with shadows on;
  an isolated A/B recording of this one change is still pending).
- Delegates: so that `ros2 launch turtlebot3_gazebo ...` works unchanged.
  They are convenience, not part of the fix.

## Requirements

- Ubuntu 24.04 ARM64 VM in Parallels Desktop on Apple silicon, with
  Parallels Tools installed and 3D acceleration enabled.
- ROS 2 Jazzy installed from the official packages.
- Network access for `apt` (Mesa packages are downloaded, not bundled).
- A Parallels snapshot of the VM before you start.

Everything below runs inside the Ubuntu VM.

## 1. Check the starting point

```bash
cat /etc/os-release | head -2
uname -m                      # aarch64
dpkg --print-architecture     # arm64
source /opt/ros/jazzy/setup.bash
echo "$ROS_DISTRO"            # jazzy
```

## 2. Install Gazebo and build dependencies

```bash
sudo apt update
sudo apt install ros-jazzy-ros-gz
sudo apt install build-essential cmake pkg-config curl ca-certificates \
  patch unzip python3 python3-pil mesa-utils libogre-1.9-dev \
  libgl-dev qtbase5-dev libprotobuf-dev protobuf-compiler
```

Check the versions the kit is pinned to. If they differ, stop: the hash
gates in the kit will refuse to install, and bypassing them is not safe.

```bash
source /opt/ros/jazzy/setup.bash
gz sim --version                                          # 8.15.0
grep "^Version:" /opt/ros/jazzy/opt/gz_rendering_vendor/lib/pkgconfig/gz-rendering8.pc   # 8.2.3
pkg-config --modversion OGRE                              # 1.9.0
```

## 3. Confirm the virtual GPU is exposed

```bash
glxinfo -B | grep -E "renderer|Accelerated|version string"
```

Expected: a renderer containing `virgl`, `Accelerated: yes`, OpenGL 4.0.
If you see `llvmpipe`, the VM is not exposing a GPU: enable 3D acceleration in
the VM settings and reinstall Parallels Tools before continuing. The kit cannot
create a GPU that is not there.

Also make sure no leftover overrides from earlier attempts are in your shell:

```bash
printenv | grep -E "^(LIBGL_|GALLIUM_|MESA_|LD_PRELOAD=|QT_QPA_PLATFORM=)"
```

That should print nothing.

## 4. Unpack the kit

Clone this repository inside the VM (or copy the `gazebo-parallels/kit`
directory in through a shared folder), then:

```bash
git clone https://github.com/alepistella/dum-e.git "$HOME/dum-e"
mkdir -p "$HOME/gazebo-parallels"
cp -R "$HOME/dum-e/gazebo-parallels/kit" "$HOME/gazebo-parallels/kit"
cd "$HOME/gazebo-parallels/kit"
sha256sum -c SHA256SUMS        # every line OK
source /opt/ros/jazzy/setup.bash
```

The kit builds inside its own directory, so keep it out of the git checkout.

Do not run `prepare.sh` with sudo. Only the install step needs root.

## 5. Build the private runtime

Four phases, one command each. Check the result of each before the next.

```bash
bash prepare.sh mesa       # apt-get download + dpkg-deb -x, nothing installed
bash prepare.sh source     # gz-rendering 8.2.3 tag, SHA256 checked, patch applied
bash prepare.sh build      # builds the OGRE 1 component with 2 jobs
bash prepare.sh assemble   # assembles build/runtime
```

Expected layout:

```bash
ls build/runtime             # profile.rb  libgazebo_virgl_defaults.so  engine/  mesa/
ls build/runtime/engine      # libgz-rendering-ogre.so
ls build/runtime/mesa/dri    # virtio_gpu_dri.so
```

If `prepare.sh mesa` cannot find the pinned Mesa 24.0.5 packages, check that
the official Noble sources are configured and `apt update` succeeded. Do not
substitute another Mesa version.

## 6. Install

Close every Gazebo and ROS launch first.

```bash
python3 install.py --check          # dry run, changes nothing
sudo python3 install.py --install
```

`--check` verifies the runtime and the hashes of the original entry points.
If it stops because a profile or diversion already exists, the VM has already
been patched: do not reinstall.

## 7. Verify

Open a new terminal.

```bash
cd "$HOME/gazebo-parallels/kit"
bash tools/private_glxinfo.sh       # inside the profile: virgl, Mesa 24.0.5
glxinfo -B | grep "version string"  # outside: system Mesa, unchanged
source /opt/ros/jazzy/setup.bash
gz sim -r shapes.sdf
```

Rotate the camera for a minute: no flicker, correct colors, responsive zoom.
Add the "Camera FPS" panel from the plugin menu to read the GUI update rate.

Sensors, with TurtleBot3:

```bash
sudo apt install ros-jazzy-turtlebot3-gazebo ros-jazzy-rqt-image-view
export TURTLEBOT3_MODEL=waffle
ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py
```

In a second terminal:

```bash
source /opt/ros/jazzy/setup.bash
ros2 topic hz /scan                        # about 10 Hz
ros2 run rqt_image_view rqt_image_view     # select /camera/image_raw, expect the scene
```

Analytical check against a known wall (2 m in front of a static sensor):

```bash
# terminal A
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=gazebo_kit_check
gz sim -r -s "$HOME/gazebo-parallels/kit/tests/known-distance.sdf"
# terminal B
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=gazebo_kit_check
cd "$HOME/gazebo-parallels/kit" && python3 tools/validate_known.py   # passed: true, max error < 0.02 m
```

Use `--3d` with `known-distance-3d.sdf` for the 3D LiDAR case (1083 rays).
A smooth window and an existing topic are not proof: the range check is.

## 8. Everyday use

Nothing to type: `gz sim ...` and `ros2 launch ...` pick up the profile
through the delegates. Before changing worlds, stop the previous launch with
Ctrl+C and wait for the processes to exit; a server left running makes the
next GUI reconnect to the old world.

```bash
ps -u "$USER" -o pid,args | grep "gz sim"   # a profiled process shows --render-engine <private path>
```

`GZ_VIRGL_DEFAULTS=0` in front of a command bypasses the profile for that
process only (diagnostics, not a supported mode).

## 9. Next step: RViz 2

The profile above applies to Gazebo processes only. On the same VM, RViz 2
opens with a black viewport (system Mesa 25 on VirGL). The optional
[RViz kit](../rviz-parallels/README.md) makes the packaged `rviz2` load the private Mesa
installed in section 6, with its own hash gates, backups and rollback. It needs
no new packages and keeps hardware rendering. Install it only after section 7
passes, following `rviz-parallels/README.md` step by step.

## 10. Rollback

```bash
sudo /usr/local/sbin/gazebo-virgl-defaults-rollback
```

Removes the delegates and restores the `.vendor` entry points through
`dpkg-divert`. The runtime stays on disk but is no longer loaded by Gazebo; the
RViz add-on, if installed, keeps using it and has its own rollback
(`rviz-parallels/README.md`, section 8). After major
ROS, Gazebo, Parallels or Mesa updates, re-run the checks in section 7; the
private runtime is not updated by `apt`.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Version or hash mismatch at install | The kit does not cover that combination. Do not remove the gate. |
| Pinned Mesa package not found | Official Noble repositories configured, `apt update` done. Do not downgrade system Mesa. |
| `llvmpipe` in glxinfo | VM 3D acceleration and Parallels Tools. Compare normal and `private_glxinfo.sh` output. |
| Black camera image, all LiDAR ranges at minimum | The process did not load the private runtime: check `/proc/<pid>/maps` for `gazebo-virgl`, `virtio_gpu`, `libgallium`. |
| LiDAR rays drawn at the world origin | GUI scene state: select the topic again in Visualize Lidar, or run `build/engine/refresh_gui_state <world>`. Do not move the sensor in the model. |
| The old world keeps opening | A server is still running. Stop the launch, check `ps`. |
| RViz viewport black while Gazebo works | Expected: the Gazebo profile does not configure RViz. Section 9 and [rviz-parallels/README.md](../rviz-parallels/README.md). |
| Odd rates or clock | Two servers on the same topics. Close your test processes. |

Capture a log for a report:

```bash
gz sim -v 4 -r shapes.sdf 2>&1 | tee gazebo-test.log
```

## Evidence and upstream

- `evidence/`: 53-trial ablation (Mesa 24 vs 25 vs llvmpipe, shadows on/off,
  eight LiDAR variants), raw results, renderer strings, loaded libraries.
- `overlay/`: a colcon overlay of gz_rendering_vendor with only the numerical
  patches, no delegates, no private Mesa. Cleaner, passes the functional
  tests, but not validated for daily GUI use yet. Do not stack it on top of
  the installed profile.
- Upstream: gazebosim/gz-rendering#1400 (single-row and single-column GPU
  ray mapping, with regression tests). #1370 and #1378 are earlier upstream
  fixes by their respective authors and are included in the patch with credit.

## Credits and license

gz-rendering is Apache-2.0, copyright Open Source Robotics Foundation.
Mesa packages are redistributed under their own licenses (copies in the
runtime). Kit scripts and this document: Apache-2.0, Alessandro Pistella.
