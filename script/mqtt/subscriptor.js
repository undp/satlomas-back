#!/usr/bin/env node
require("dotenv").config();

const process = require("process");
const fs = require("fs");
const mqtt = require("mqtt");
const { Client } = require("pg");

// Environment variables
const mqttUrl = process.env.MQTT_URL;
const clientId = process.env.MQTT_CLIENT_ID || "satlomas-sub";
const logFile = process.env.MQTT_LOG_FILE || "measurements.log";

if (!mqttUrl) {
  console.error(
    "You must set MQTT_URL env var (e.g. mqtt://foo:bar@example.com)"
  );
  process.exit(1);
}

const storeMeasurementAppendOnly = (body, path) => {
  try {
    var stream = fs.createWriteStream(path, { flags: "a" });
    stream.write(JSON.stringify(body) + "\n");
    stream.end();
  } catch (err) {
    console.error("Failed to save measurement to log file", err);
  }
};

const pgClient = new Client();

(async () => {
  // First connect to our database
  await pgClient.connect();

  process.on("SIGINT", async () => {
    console.log("Caught interrupt signal");
    await pgClient.end();
    process.exit();
  });

  const getStationIdFromCode = async (id) => {
    const query = "SELECT id from stations_station WHERE code = $1";
    try {
      const res = await pgClient.query(query, [id]);
      return res.rows[0]["id"];
    } catch (err) {
      console.error("Failed to get ");
      return null;
    }
  };

  const insertMeasurement = async (attributes) => {
    const stationId = await getStationIdFromCode(attributes["id"]);

    const query =
      "INSERT INTO stations_measurement(station_id, datetime, attributes) VALUES($1, $2, $3) RETURNING *";

    const time = attributes["time"];
    delete attributes["time"];
    const values = [stationId, time, attributes];

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
    // mqttClient.subscribe("/stations/+/");
    mqttClient.subscribe("/weather_station/");
  });

  mqttClient.on("message", (topic, message) => {
    let body;
    try {
      body = JSON.parse(message);
    } catch (err) {
      console.error("Failed parsing JSON message", err);
    }

    console.log(topic, body);

    storeMeasurementAppendOnly(body, logFile);
    insertMeasurement(body);
  });
})();
