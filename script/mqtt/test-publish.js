#!/usr/bin/env node
require('dotenv').config()

const process = require('process');
const mqtt = require('mqtt');

const mqttUrl = process.env.MQTT_URL;
const mqttPath = process.env.MQTT_PATH;

const client = mqtt.connect(mqttUrl, {
  clientId: 'test'
});

client.on('connect', () => {
  let i = 0;

  setInterval(() => {
    const data = { type: 'simple', message: 'this is a test', index: i };
    client.publish(mqttPath, JSON.stringify(data));
    i += 1;
  }, 1000);
});
