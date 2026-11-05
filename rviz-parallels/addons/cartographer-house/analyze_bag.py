#!/usr/bin/env python3
"""Compare TurtleBot3 live SLAM/odometry against independently recorded Gazebo pose."""
import argparse
import csv
import gzip
import json
import math
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bag', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    import numpy as np
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=args.bag, storage_id='mcap'),
                rosbag2_py.ConverterOptions('', ''))
    names = ['/odom', '/debug/gazebo_ground_truth', '/tf', '/scan']
    reader.set_filter(rosbag2_py.StorageFilter(topics=names))
    types = {t.name: get_message(t.type) for t in reader.get_all_topics_and_types()
             if t.name in names}
    rows = {'odom': [], 'truth': [], 'map_odom': []}
    scans = []
    scan_nan_count = 0
    last_tf = -1.0

    def stamp(s):
        return s.sec + s.nanosec / 1e9

    def pose(p):
        return [p.position.x, p.position.y, p.position.z,
                p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w]

    while reader.has_next():
        topic, raw, _ = reader.read_next()
        msg = deserialize_message(raw, types[topic])
        if topic in ['/odom', '/debug/gazebo_ground_truth']:
            key = 'odom' if topic == '/odom' else 'truth'
            rows[key].append([stamp(msg.header.stamp)] + pose(msg.pose.pose))
        elif topic == '/scan':
            scans.append(stamp(msg.header.stamp))
            scan_nan_count += sum(math.isnan(x) for x in msg.ranges)
        elif topic == '/tf':
            for tf in msg.transforms:
                t = stamp(tf.header.stamp)
                if (tf.header.frame_id.lstrip('/') == 'map'
                        and tf.child_frame_id.lstrip('/') == 'odom' and t - last_tf >= .095):
                    last_tf = t
                    p, q = tf.transform.translation, tf.transform.rotation
                    rows['map_odom'].append([t, p.x, p.y, p.z, q.x, q.y, q.z, q.w])
    arrays = {key: np.array(value) for key, value in rows.items()}
    for name, a in arrays.items():
        if len(a) < 2:
            raise RuntimeError(f'Missing or insufficient {name} data.')
        if np.any(np.diff(a[:, 0]) < 0):
            raise RuntimeError(f'Backward timestamps in {name}; segment clock resets first.')

    def yaw(a):
        x, y, z, w = a[:, 4:8].T
        return np.unwrap(np.arctan2(2 * (w*z + x*y), 1 - 2 * (y*y + z*z)))

    g, o, f = arrays['truth'], arrays['odom'], arrays['map_odom']
    # Known initial frame transform, not an optimized trajectory alignment.
    heading0 = yaw(g)[0]
    fx = f[(f[:, 0] >= max(g[0, 0], o[0, 0]))
           & (f[:, 0] <= min(g[-1, 0], o[-1, 0]))]
    if len(fx) < 2:
        raise RuntimeError('Insufficient overlap between pose streams.')
    t = fx[:, 0]
    wx = np.interp(t, g[:, 0], g[:, 1]) - g[0, 1]
    wy = np.interp(t, g[:, 0], g[:, 2]) - g[0, 2]
    gx = math.cos(heading0)*wx + math.sin(heading0)*wy
    gy = -math.sin(heading0)*wx + math.cos(heading0)*wy
    ox, oy = [np.interp(t, o[:, 0], o[:, k]) for k in [1, 2]]
    fy = yaw(fx)
    sx = fx[:, 1] + np.cos(fy)*ox - np.sin(fy)*oy
    sy = fx[:, 2] + np.sin(fy)*ox + np.cos(fy)*oy
    se, oe = np.hypot(sx-gx, sy-gy), np.hypot(ox-gx, oy-gy)
    heading_error = fy + np.interp(t, o[:, 0], yaw(o)) - (np.interp(t, g[:, 0], yaw(g))-heading0)
    heading_error = np.degrees(np.arctan2(np.sin(heading_error), np.cos(heading_error)))

    def metrics(error):
        return {'final_m': float(error[-1]), 'maximum_m': float(error.max()),
                'rms_m': float(np.sqrt(np.mean(error**2))),
                'median_m': float(np.median(error)), 'p95_m': float(np.percentile(error, 95))}

    args.output.mkdir(parents=True, exist_ok=True)
    result = {'alignment': 'Known initial world position and heading; no trajectory fitting',
              'scope': 'TurtleBot3 Waffle model origin and base_footprint coincide in XY; start recording before motion',
              'time_interval_s': [float(t[0]), float(t[-1])], 'pose_samples': len(t),
              'message_counts': {k: len(v) for k, v in rows.items()},
              'scan_count': len(scans), 'scan_nan_range_count': scan_nan_count,
              'slam': metrics(se), 'odometry': metrics(oe),
              'slam_heading_error_deg': {'final': float(heading_error[-1]),
                                         'maximum_absolute': float(abs(heading_error).max())}}
    if len(scans) > 1:
        dt = np.diff(scans)
        result['scan_header_interval_s'] = {'minimum': float(dt.min()), 'maximum': float(dt.max())}
    (args.output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    with gzip.open(args.output / 'trajectory.csv.gz', 'wt', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['simulation_time_s', 'truth_x_m', 'truth_y_m', 'odom_x_m', 'odom_y_m',
                         'slam_x_m', 'slam_y_m', 'odom_position_error_m', 'slam_position_error_m',
                         'slam_heading_error_deg'])
        writer.writerows(zip(t, gx, gy, ox, oy, sx, sy, oe, se, heading_error))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
