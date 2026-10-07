# SAM questionnaire (ROS2)

Self-Assessment Manikin (Bradley & Lang, 1994) as a ROS2 node. The node serves
the questionnaire page over HTTP and publishes every submitted rating to ROS2
topics, so the ratings end up in the same rosbag as the robot, shimmer3 and
mediapipe streams. You don't need rosbridge, npm, or any custom message package.

```
browser ──HTTP POST──▶ sam_node (rclpy) ──▶ /sam/rating, /sam/pad, /sam/events ──▶ ros2 bag record
```

## Quick start: questionnaire on a phone

The campus Wi-Fi blocks phones from reaching the PC. Use the phone's hotspot instead:

1. Keep the PC on **Ethernet** for its normal network.
2. Turn on the **phone's hotspot** and connect the PC's USB Wi-Fi adapter to it.
3. Start the node on the PC:
   ```bash
   export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
   source /opt/ros/jazzy/setup.bash
   source ~/DataCollection/SAM_questionnaire/install/setup.bash
   ros2 launch sam_questionnaire sam.launch.py participant:=P01
   ```
4. The node prints one `Tablet/phone URL (...)` line for each network. Open the
   **`wlx...`** one (the hotspot) in Chrome on the phone, typing the full
   `http://...:8080/`. The IP can change each session, so always read it from
   this output.
5. Add `/sam/rating /sam/pad /sam/events` to the `ros2 bag record` command in
   `mc_admittance`. Before recording, run `ros2 topic hz biosensors/shimmer3_gsr/ppg`
   there and check it shows about 50 Hz, since the extra network can affect DDS.
6. Submit a test rating on the phone and check that `ros2 topic echo /sam/pad`
   prints it. The Session chip's dot turns green once the bag recorder is running.

If the page doesn't load: `ss -ltnp | grep 8080` must show `0.0.0.0:8080`, and
the URL must be the `wlx...` one, not the Ethernet (`enp...`) one.

## Topics

| Topic | Type | Content |
|---|---|---|
| `/sam/rating` | `std_msgs/String` | JSON, one message per submit: `participant, trial, valence, arousal, dominance, shown_at_iso, submitted_at_iso, client_epoch_ms, response_time_ms, n_changes, ros_time_ns` |
| `/sam/pad` | `std_msgs/Int32MultiArray` | `[valence, arousal, dominance]`, one message per submit |
| `/sam/events` | `std_msgs/String` | JSON interaction log: `shown`, every `select` (dimension + value), `submit` |

A rating is published only when the participant presses **Submit**. Changing a
selection does not publish a rating. Each submission is also appended to
`~/sam_logs/sam_<date>.jsonl` as a backup in case the bag is empty.

## Build (host, once)

```bash
cd ~/DataCollection/SAM_questionnaire
source /opt/ros/jazzy/setup.bash
colcon build            # needs system python (/usr/bin/python3) with rclpy
```

## Run (every session, host terminal)

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp   # same RMW as everything else
source /opt/ros/jazzy/setup.bash
source ~/DataCollection/SAM_questionnaire/install/setup.bash
ros2 launch sam_questionnaire sam.launch.py participant:=P01
```

Open <http://localhost:8080/> on the participant's screen (use kiosk mode:
`google-chrome --kiosk http://localhost:8080/`).

To use a tablet or phone, connect it to the same Wi-Fi network and open the
`Tablet/phone URL` printed when the node starts (if several are printed, use
the one on the network the phone is connected to).

Launch arguments: `host` (default `0.0.0.0`, reachable from other devices on
the network; use `127.0.0.1` to allow only this PC), `port` (default `8080`),
`participant`, and `log_dir` (default `~/sam_logs`).

Participant ID and trial label are also editable in the **Session** chip in the
top-right corner of the page. They are stored in the browser and can be set in
the URL, e.g. `?participant=P01&trial=baseline`. A numeric trial number
auto-increments after each submit. The chip's dot is **green** when a subscriber
(your `ros2 bag record`) is attached to `/sam/rating`, **amber** when the
node is reachable but no subscriber is attached, and **red** when the node
can't be reached.

## Record

Add the three topics to the existing `ros2 bag record` command inside
`mc_admittance`. They use only `std_msgs` types, which are already
available there:

```bash
ros2 bag record -o session_<participant>_<trial> \
  ... existing topics ... \
  /sam/rating /sam/pad /sam/events
```

Check before a real session: `ros2 topic echo /sam/pad` from the recording
shell should print a message after you submit a test rating.

## Read back

```python
import json
import rosbag2_py
from rclpy.serialization import deserialize_message
from std_msgs.msg import String

reader = rosbag2_py.SequentialReader()
reader.open(rosbag2_py.StorageOptions(uri='session_P01_1'),
            rosbag2_py.ConverterOptions('cdr', 'cdr'))
reader.set_filter(rosbag2_py.StorageFilter(topics=['/sam/rating']))
while reader.has_next():
    topic, raw, t_ns = reader.read_next()
    print(t_ns, json.loads(deserialize_message(raw, String).data))
```
