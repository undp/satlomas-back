#!/usr/bin/env node
require("dotenv").config();

const process = require("process");
const mqtt = require("mqtt");

const mqttUrl = process.env.MQTT_URL;
const clientId = "test";

const randFloat = (min, max, prec) => {
  return parseFloat((Math.random() * (max - min) + min).toFixed(prec));
};

const randInt = (min, max) => {
  return Math.floor(Math.random() * (max - min + 1) + min);
};

console.log("Connect to MQTT broker", mqttUrl, "with client id", clientId);
const client = mqtt.connect(mqttUrl, { clientId });

client.on("connect", () => {
  setInterval(() => {
    const now = new Date(Date.now());

    const data = {
      altitude: randFloat(70, 85, 2),
      ambient_temperature: randFloat(15, 25, 2),
      atmospheric_pressure: randFloat(800, 1200, 2),
      internal_temperature: randFloat(16, 28, 2),
      PM1_0: randInt(20, 40),
      PM2_5: randInt(20, 40),
      PM4_0: randInt(20, 40),
      PM10_0: randInt(20, 40),
      relative_humidity: randFloat(0, 100, 2),
      tip_count: randInt(0, 3000),
      wind_speed: randFloat(0, 5, 1),
      wind_direction: randInt(0, 360, 2),
      time: now.toISOString(),
      id: "pcb_radio_nebli",
    };

    const mqttPath = `/weather_station/`;
    console.log(data);
    client.publish(mqttPath, JSON.stringify(data));
  }, 3000);
});
