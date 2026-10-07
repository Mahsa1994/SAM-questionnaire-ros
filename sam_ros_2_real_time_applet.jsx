import React, { useEffect, useState } from "react";
import ROSLIB from "roslib";
import { Card, CardContent } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";

/**
 * Self-Assessment Manikin (SAM) interface based on Bradley & Lang (1994)
 * Scales:
 * 1–9 for Valence (Pleasure), Arousal, Dominance
 * Publishes via ROS2 bridge (rosbridge_suite) as std_msgs/Int32MultiArray
 */

export default function SAMApplet() {
  const [valence, setValence] = useState(5);
  const [arousal, setArousal] = useState(5);
  const [dominance, setDominance] = useState(5);

  const [ros, setRos] = useState(null);
  const [topic, setTopic] = useState(null);

  useEffect(() => {
    // Connect to rosbridge server
    const rosConnection = new ROSLIB.Ros({
      url: "ws://localhost:9090"
    });

    rosConnection.on("connection", () => {
      console.log("Connected to ROS bridge");
    });

    rosConnection.on("error", (error) => {
      console.error("ROS connection error:", error);
    });

    const samTopic = new ROSLIB.Topic({
      ros: rosConnection,
      name: "/sam_emotion",
      messageType: "std_msgs/Int32MultiArray"
    });

    setRos(rosConnection);
    setTopic(samTopic);

    return () => rosConnection.close();
  }, []);

  useEffect(() => {
    if (!topic) return;

    const msg = new ROSLIB.Message({
      data: [valence, arousal, dominance]
    });

    topic.publish(msg);
  }, [valence, arousal, dominance, topic]);

  const SAMSlider = ({ label, value, setValue, lowLabel, highLabel }) => (
    <div className="space-y-2">
      <Label>{label}: {value}</Label>
      <Slider
        min={1}
        max={9}
        step={1}
        value={[value]}
        onValueChange={(v) => setValue(v[0])}
      />
      <div className="flex justify-between text-xs text-gray-500">
        <span>{lowLabel}</span>
        <span>{highLabel}</span>
      </div>
    </div>
  );

  return (
    <div className="p-6 max-w-xl mx-auto">
      <Card>
        <CardContent className="space-y-6 p-6">
          <h2 className="text-xl font-bold">
            Self-Assessment Manikin (SAM)
          </h2>

          <SAMSlider
            label="Pleasure (Valence)"
            value={valence}
            setValue={setValence}
            lowLabel="Unpleasant"
            highLabel="Pleasant"
          />

          <SAMSlider
            label="Arousal"
            value={arousal}
            setValue={setArousal}
            lowLabel="Calm"
            highLabel="Excited"
          />

          <SAMSlider
            label="Dominance"
            value={dominance}
            setValue={setDominance}
            lowLabel="Controlled"
            highLabel="In Control"
          />

          <div className="text-sm text-gray-500 pt-2">
            Publishing to ROS2 topic <code>/sam_emotion</code> as
            std_msgs/Int32MultiArray [V, A, D]
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
