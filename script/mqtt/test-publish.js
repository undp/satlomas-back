#!/usr/bin/env node
require("dotenv").config();

const process = require("process");
const mqtt = require("mqtt");

const mqttUrl = process.env.MQTT_URL;

const randFloat = (min, max, prec) => {
  return (Math.random() * (max - min) + min).toFixed(prec);
};

const randInt = (min, max) => {
  return Math.floor(Math.random() * (max - min + 1) + min);
};

const client = mqtt.connect(mqttUrl, {
  clientId: "test",
});

client.on("connect", () => {
  let i = 1;

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
      time: now.toISOString(),
      tip_count: randInt(0, 3000),
    };

    const mqttPath = `/stations/${i % 3}/`;
    console.log(data);
    client.publish(mqttPath, JSON.stringify(data));

    i += 1;
  }, 1000);
});
