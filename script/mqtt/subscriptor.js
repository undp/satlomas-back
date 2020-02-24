#!/usr/bin/env node
require('dotenv').config()

const process = require('process');
const mqtt = require('mqtt');

const mqttUrl = process.env.MQTT_URL;
const mqttPath = process.env.MQTT_PATH;
const clientId = process.env.MQTT_CLIENT_ID || 'geolomas-db';

if (!mqttUrl) {
  console.error("You must set MQTT_URL env var (e.g. mqtt://foo:bar@example.com)");
  process.exit(1);
}

if (!mqttPath) {
  console.error("You must set MQTT_PATH env var (e.g. /stations)");
  process.exit(1);
}

console.log(`Connecting to ${mqttUrl}`)
const client = mqtt.connect(mqttUrl, {
  clientId
});

client.on('connect', () => {
  console.log(`Client '${clientId}' has connected`);
  client.subscribe(mqttPath);
});

client.on('message', (topic, message) => {
  try {
    const body = JSON.parse(message);
    console.log(topic, body);
  } catch(err) {
    console.error("Failed parsing JSON message", err);
  }
});
