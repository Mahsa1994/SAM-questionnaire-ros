#!/usr/bin/env python3
"""SAM questionnaire ROS2 node.

Serves the Self-Assessment Manikin web page over HTTP and publishes every
submitted rating to ROS2 so it lands in the same rosbag as the other streams.

Topics (standard std_msgs types only, so the recorder needs no custom
message packages):
  /sam/rating   std_msgs/String           JSON record of one submitted rating
  /sam/pad      std_msgs/Int32MultiArray  [valence, arousal, dominance]
  /sam/events   std_msgs/String           JSON interaction log (page shown,
                                          each selection, submit)

Each submission is also appended to <log_dir>/sam_<participant>.jsonl (one
file per participant, filename-sanitized) as a backup that does not depend
on the bag being recorded correctly. Every record carries the node's own
ROS clock timestamp (ros_time/ros_time_ns), the same time source every
other recorded node uses, so this file can be aligned against the rosbag
even if the bag or this node's own ROS topics are ever lost.
"""

import json
import os
import re
import subprocess
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Int32MultiArray, MultiArrayDimension, String

DIMENSIONS = ('valence', 'arousal', 'dominance')


def find_web_dir():
    try:
        from ament_index_python.packages import get_package_share_directory
        web = Path(get_package_share_directory('sam_questionnaire')) / 'web'
        if web.is_dir():
            return web
    except Exception:
        pass
    # Running straight from the source tree (python3 sam_node.py)
    return Path(__file__).resolve().parent.parent / 'web'


def lan_ips():
    """IPv4 addresses of this PC's network interfaces (skips loopback/Docker)."""
    try:
        out = subprocess.run(['ip', '-4', '-o', 'addr', 'show'],
                             capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    ips = []
    for line in out.splitlines():
        fields = line.split()
        iface, ip = fields[1], fields[3].split('/')[0]
        if iface != 'lo' and not iface.startswith(('docker', 'br-', 'veth')):
            ips.append((iface, ip))
    return ips


class SamNode(Node):

    def __init__(self):
        super().__init__('sam_questionnaire')
        self.host = self.declare_parameter('host', '0.0.0.0').value
        self.port = int(self.declare_parameter('port', 8080).value)
        self.participant = str(self.declare_parameter('participant', '').value)
        log_dir = str(self.declare_parameter('log_dir', '~/sam_logs').value)

        self.log_dir = Path(os.path.expanduser(log_dir))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

        qos = QoSProfile(depth=50,
                         reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.VOLATILE)
        self.rating_pub = self.create_publisher(String, '/sam/rating', qos)
        self.pad_pub = self.create_publisher(Int32MultiArray, '/sam/pad', qos)
        self.event_pub = self.create_publisher(String, '/sam/events', qos)

    def stamp(self):
        t = self.get_clock().now()
        return {'ros_time_ns': t.nanoseconds,
                'ros_time': t.nanoseconds / 1e9}

    def publish_event(self, payload):
        payload.update(self.stamp())
        self.event_pub.publish(String(data=json.dumps(payload)))

    def publish_rating(self, payload):
        values = [int(payload[d]) for d in DIMENSIONS]
        if not all(1 <= v <= 9 for v in values):
            raise ValueError('ratings must be integers in 1..9')
        payload.update(self.stamp())

        self.rating_pub.publish(String(data=json.dumps(payload)))
        pad = Int32MultiArray(data=values)
        pad.layout.dim = [MultiArrayDimension(label='valence,arousal,dominance',
                                              size=3, stride=3)]
        self.pad_pub.publish(pad)

        # One file per participant (not per day) so each participant's full
        # set of ratings for the session lives in one place - safe to
        # re-run/resume the same participant across multiple launches, since
        # this appends rather than overwrites. Sanitized because this value
        # comes straight from a free-text field in the browser and lands
        # directly in a filename.
        participant = (payload.get('participant') or self.participant or 'unknown').strip()
        safe_participant = re.sub(r'[^A-Za-z0-9_.-]+', '_', participant).strip('_') or 'unknown'

        with self.lock:
            path = self.log_dir / f'sam_{safe_participant}.jsonl'
            with open(path, 'a') as f:
                f.write(json.dumps(payload) + '\n')

        self.get_logger().info(
            f"rating  participant={payload.get('participant')!r} "
            f"trial={payload.get('trial')!r}  V={values[0]} A={values[1]} D={values[2]}  "
            f"-> {path}")


def make_handler(node, web_dir):

    class Handler(SimpleHTTPRequestHandler):

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(web_dir), **kwargs)

        def log_message(self, fmt, *args):
            pass  # keep the launch terminal quiet

        def end_headers(self):
            self.send_header('Cache-Control', 'no-store')
            super().end_headers()

        def send_json(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == '/api/status':
                return self.send_json(HTTPStatus.OK, {
                    'ok': True,
                    'node': node.get_fully_qualified_name(),
                    'participant': node.participant,
                    'subscribers': node.rating_pub.get_subscription_count(),
                })
            return super().do_GET()

        def do_POST(self):
            try:
                length = int(self.headers.get('Content-Length', 0))
                payload = json.loads(self.rfile.read(length) or b'{}')
                if not isinstance(payload, dict):
                    raise ValueError('expected a JSON object')
                if self.path == '/api/rating':
                    node.publish_rating(payload)
                elif self.path == '/api/event':
                    node.publish_event(payload)
                else:
                    return self.send_json(HTTPStatus.NOT_FOUND, {'ok': False})
            except (ValueError, KeyError, TypeError) as e:
                return self.send_json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': str(e)})
            self.send_json(HTTPStatus.OK, {'ok': True})

    return Handler


def main(args=None):
    rclpy.init(args=args)
    node = SamNode()
    web_dir = find_web_dir()
    server = ThreadingHTTPServer((node.host, node.port), make_handler(node, web_dir))
    threading.Thread(target=server.serve_forever, daemon=True).start()

    node.get_logger().info(f'SAM questionnaire at http://localhost:{node.port}/  '
                           f'(backup log: {node.log_dir})')
    if node.host == '0.0.0.0':
        for iface, ip in lan_ips():
            node.get_logger().info(f'Tablet/phone URL ({iface}): http://{ip}:{node.port}/')
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        server.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
