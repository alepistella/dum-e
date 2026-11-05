#!/usr/bin/env python3
"""Synthetic map and static TF for an isolated RViz rendering comparison."""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import TransformStamped
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster

rclpy.init()
node = Node('rendering_retest_fixture')
qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                reliability=ReliabilityPolicy.RELIABLE)
pub = node.create_publisher(OccupancyGrid, '/map', qos)
msg = OccupancyGrid()
msg.header.frame_id = 'map'
msg.info.resolution = 0.1
msg.info.width = msg.info.height = 100
msg.info.origin.position.x = msg.info.origin.position.y = -5.0
msg.info.origin.orientation.w = 1.0
msg.data = [100 if x in (0, 99) or y in (0, 99) or
            (20 <= x <= 30 and 20 <= y <= 35) or
            (65 <= x <= 80 and 60 <= y <= 75) else 0
            for y in range(100) for x in range(100)]
broadcaster = StaticTransformBroadcaster(node)
transforms = []
for parent, child in [('map', 'odom'), ('odom', 'base_footprint'),
                      ('base_footprint', 'base_link'), ('base_link', 'base_scan')]:
    tf = TransformStamped()
    tf.header.frame_id = parent
    tf.child_frame_id = child
    tf.header.stamp = node.get_clock().now().to_msg()
    tf.transform.rotation.w = 1.0
    transforms.append(tf)
broadcaster.sendTransform(transforms)
def publish():
    msg.header.stamp = node.get_clock().now().to_msg()
    pub.publish(msg)
node.create_timer(1.0, publish)
publish()
try:
    rclpy.spin(node)
except KeyboardInterrupt:
    pass
finally:
    node.destroy_node()
    rclpy.try_shutdown()
