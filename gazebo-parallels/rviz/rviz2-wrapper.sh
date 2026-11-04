#!/bin/sh
# RVIZ_VIRGL_DEFAULTS_ENTRY_V1
# Process-local Mesa selection; preserve the normal RViz CLI and ROS arguments.
if [ "${RVIZ_VIRGL_DEFAULTS:-1}" != 0 ]; then
  rviz_mesa=/usr/local/lib/gazebo-virgl-defaults/runtime-v2/mesa
  if [ ! -r "$rviz_mesa/libGLX_mesa.so.0" ] || [ ! -r "$rviz_mesa/dri/virtio_gpu_dri.so" ]; then
    echo "RViz private Mesa runtime missing: $rviz_mesa" >&2
    echo "Use RVIZ_VIRGL_DEFAULTS=0 only to diagnose the original driver." >&2
    exit 1
  fi
  export LD_LIBRARY_PATH="$rviz_mesa${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  export LIBGL_DRIVERS_PATH="$rviz_mesa/dri"
fi
exec "$0.distrib" "$@"
