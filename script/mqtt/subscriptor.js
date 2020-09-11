#!/usr/bin/env node
require("dotenv").config();

const process = require("process");
const mqtt = require("mqtt");
const { Client } = require("pg");

const mqttUrl = process.env.MQTT_URL;
const clientId = process.env.MQTT_CLIENT_ID || "geolomas-db";

if (!mqttUrl) {
  console.error(
    "You must set MQTT_URL env var (e.g. mqtt://foo:bar@example.com)"
  );
  process.exit(1);
}

const pgClient = new Client();

(async () => {
  // First connect to our database
  await pgClient.connect();

  process.on("SIGINT", async () => {
    console.log("Caught interrupt signal");
    await pgClient.end();
    process.exit();
  });

  const insertMeasurement = async (id, attributes) => {
    const query =
      "INSERT INTO stations_measurement(station_id, datetime, attributes) VALUES($1, $2, $3) RETURNING *";

    const time = attributes["time"];
    delete attributes["time"];
    const values = [id, time, attributes];

    // async/await
    try {
      const res = await pgClient.query(query, values);
      console.log("INSERT ok:", res.rows[0]);
    } catch (err) {
      console.error("INSERT failed!", err.stack);
    }
  };

  console.log(`Connecting to ${mqttUrl} with client id '${clientId}'`);
  const mqttClient = mqtt.connect(mqttUrl, {
    clientId,
  });

  mqttClient.on("connect", () => {
    console.log(`Client '${clientId}' has connected`);
    // Subscribe to all stations topics
    mqttClient.subscribe("/stations/+/");
  });

  mqttClient.on("message", (topic, message) => {
    try {
      const body = JSON.parse(message);
      console.log(topic, body);

      const parts = topic.split("/");
      const stationId = parts[parts.length - 1];
      insertMeasurement(stationId, body);
    } catch (err) {
      console.error("Failed parsing JSON message", err);
    }
  });
})();
