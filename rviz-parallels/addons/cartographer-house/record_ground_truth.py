#!/usr/bin/env python3
"""Publish Gazebo model pose for comparison with ROS SLAM; never command motion."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--world', default='default')
    parser.add_argument('--model', default='waffle')
    args = parser.parse_args()
    import rclpy
    from gz.transport13 import Node
    from gz.msgs10.pose_v_pb2 import Pose_V
    from nav_msgs.msg import Odometry

    rclpy.init(args=[])
    node = rclpy.create_node('house_ground_truth_recorder')
    publisher = node.create_publisher(Odometry, '/debug/gazebo_ground_truth', 100)
    # Fail rather than overwrite an earlier recording.
    stream = args.output.open('x', buffering=1)

    def callback(message):
        for pose in message.pose:
            if pose.name != args.model:
                continue
            msg = Odometry()
            msg.header.stamp.sec = message.header.stamp.sec
            msg.header.stamp.nanosec = message.header.stamp.nsec
            msg.header.frame_id = 'gazebo_world'
            msg.child_frame_id = args.model + '_model_origin'
            msg.pose.pose.position.x = pose.position.x
            msg.pose.pose.position.y = pose.position.y
            msg.pose.pose.position.z = pose.position.z
            msg.pose.pose.orientation.x = pose.orientation.x
            msg.pose.pose.orientation.y = pose.orientation.y
            msg.pose.pose.orientation.z = pose.orientation.z
            msg.pose.pose.orientation.w = pose.orientation.w
            publisher.publish(msg)
            stream.write(json.dumps({
                't': message.header.stamp.sec + message.header.stamp.nsec / 1e9,
                'pose': [pose.position.x, pose.position.y, pose.position.z,
                         pose.orientation.x, pose.orientation.y,
                         pose.orientation.z, pose.orientation.w],
            }) + '\n')

    transport = Node()
    transport.subscribe(Pose_V, f'/world/{args.world}/dynamic_pose/info', callback)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        stream.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
