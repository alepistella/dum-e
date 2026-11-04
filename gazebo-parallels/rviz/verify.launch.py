"""Verify the normal ROS launch entry point while a TurtleBot simulation runs."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    config = PathJoinSubstitution([
        FindPackageShare('turtlebot3_cartographer'), 'rviz', 'tb3_cartographer.rviz'])
    return LaunchDescription([
        DeclareLaunchArgument('rviz_config', default_value=config),
        Node(package='rviz2', executable='rviz2', name='rviz2_profile_check',
             arguments=['-l', '-t', 'RViz - default accelerated profile',
                        '-d', LaunchConfiguration('rviz_config')],
             parameters=[{'use_sim_time': True}], output='screen'),
    ])
