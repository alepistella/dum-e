#!/usr/bin/env python3
"""Check sampled Waffle house scans against visual boxes and Gazebo model pose."""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bag', required=True)
    parser.add_argument('--model', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    import numpy as np
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    def transform(p):
        x, y, z, roll, pitch, yaw = p
        cr, sr = math.cos(roll), math.sin(roll)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        t = np.eye(4)
        t[:3, :3] = [[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                     [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr], [-sp, cp*sr, cp*cr]]
        t[:3, 3] = [x, y, z]
        return t

    def quaternion_transform(p):
        a, b, c, x, y, z, w = p
        t = np.eye(4)
        t[:3, 3] = [a, b, c]
        t[:3, :3] = [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]
        return t

    boxes, ignored = [], collections.Counter()

    def walk(element, parent):
        pose = element.find('pose')
        if pose is not None and pose.get('relative_to'):
            raise RuntimeError('This analytic check expects poses relative to their parent.')
        t = parent @ transform([float(x) for x in element.findtext('pose', '0 0 0 0 0 0').split()])
        if element.tag == 'visual':
            geometry = element.find('geometry')
            if geometry is not None:
                size = geometry.find('box/size')
                if size is None:
                    ignored[geometry[0].tag] += 1
                else:
                    boxes.append((element.get('name'), t, np.array([float(x) for x in size.text.split()])/2))
        for child in element:
            if child.tag in ['model', 'link', 'visual']:
                walk(child, t)

    walk(ET.parse(args.model).getroot().find('model'), np.eye(4))
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=args.bag, storage_id='mcap'),
                rosbag2_py.ConverterOptions('', ''))
    names = ['/scan', '/debug/gazebo_ground_truth']
    reader.set_filter(rosbag2_py.StorageFilter(topics=names))
    types = {t.name: get_message(t.type) for t in reader.get_all_topics_and_types() if t.name in names}
    truth, scans, count = [], [], 0
    while reader.has_next():
        topic, raw, _ = reader.read_next()
        msg = deserialize_message(raw, types[topic])
        ts = msg.header.stamp.sec + msg.header.stamp.nanosec/1e9
        if topic == '/scan':
            if count % 10 == 0:
                scans.append((ts, msg.angle_min, msg.angle_increment, np.array(msg.ranges)))
            count += 1
        else:
            p = msg.pose.pose
            truth.append([ts, p.position.x, p.position.y, p.position.z,
                          p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w])
    truth = np.array(truth)
    if len(truth) < 2 or not scans:
        raise RuntimeError('Insufficient scan/ground-truth data.')
    if np.any(np.diff(truth[:, 0]) < 0):
        raise RuntimeError('Backward ground-truth timestamps; segment clock resets first.')
    results = []
    for ts, amin, ainc, actual in scans:
        j = min(max(np.searchsorted(truth[:, 0], ts), 1), len(truth)-1)
        if abs(truth[j-1, 0]-ts) < abs(truth[j, 0]-ts):
            j -= 1
        t = quaternion_transform(truth[j, 1:]) @ transform([-.064, 0, .121, 0, 0, 0])
        origin = t[:3, 3]
        angles = amin + np.arange(len(actual))*ainc
        directions = t[:3, :3] @ np.array([np.cos(angles), np.sin(angles), np.zeros(len(angles))])
        expected = np.full(len(actual), np.inf)
        wall = np.zeros(len(actual), bool)
        for name, box, half in boxes:
            o = box[:3, :3].T @ (origin-box[:3, 3])
            rays = box[:3, :3].T @ directions
            with np.errstate(divide='ignore', invalid='ignore'):
                a, b = (-half[:, None]-o[:, None])/rays, (half[:, None]-o[:, None])/rays
                near = np.max(np.minimum(a, b), axis=0)
                far = np.min(np.maximum(a, b), axis=0)
            distance = np.where((far >= np.maximum(near, 0)) & (near >= .12), near, np.inf)
            ids = distance < expected
            expected[ids], wall[ids] = distance[ids], name.startswith('Wall')
        valid = wall & (expected > .30) & (expected < 3.40) & np.isfinite(actual)
        delta = actual[valid]-expected[valid]
        if len(delta):
            results.append([ts, len(delta), np.median(abs(delta)), np.mean(delta > .1),
                            np.mean(delta < -.1), np.sum(abs(delta) < .05)])
    if not results:
        raise RuntimeError('No comparable wall rays; check the model, poses and scope.')
    values = np.array(results)
    args.output.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output/'wall-check.csv.gz', 'wt', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['simulation_time_s', 'compared_wall_rays', 'median_abs_error_m',
                         'fraction_observed_more_than_10cm_farther',
                         'fraction_observed_more_than_10cm_closer', 'rays_within_5cm'])
        writer.writerows(values)
    summary = {'sampled_scans': len(scans), 'evaluated_scans': len(values),
               'wall_rays': int(values[:, 1].sum()), 'visual_boxes': len(boxes),
               'ignored_geometry': dict(ignored),
               'median_of_frame_median_abs_error_m': float(np.median(values[:, 2])),
               'maximum_frame_median_abs_error_m': float(values[:, 2].max()),
               'fraction_within_5cm': float(values[:, 5].sum()/values[:, 1].sum()),
               'model_sha256': hashlib.sha256(args.model.read_bytes()).hexdigest(),
               'scope': 'Waffle / house visual boxes; nearest-time model pose; known sensor offset; 0.30-3.40 m wall hits only'}
    (args.output/'wall-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
