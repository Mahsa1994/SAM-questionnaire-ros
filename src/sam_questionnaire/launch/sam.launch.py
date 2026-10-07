from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    args = {
        'host': '0.0.0.0',     # reachable from a tablet on the LAN; 127.0.0.1 = this PC only
        'port': '8080',
        'participant': '',
        'log_dir': '~/sam_logs',
    }
    return LaunchDescription(
        [DeclareLaunchArgument(k, default_value=v) for k, v in args.items()] + [
            Node(
                package='sam_questionnaire',
                executable='sam_node',
                name='sam_questionnaire',
                output='screen',
                parameters=[{k: LaunchConfiguration(k) for k in args}],
            ),
        ])
