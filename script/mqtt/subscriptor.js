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
const subscriptionPath =
  process.env.MQTT_SUBSCRIPTION_PATH || "/weather_station/";

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

  const getStationSiteIds = async (code) => {
    const query = `
      SELECT stations.id as station, sites.id as site
      FROM stations_station stations
      LEFT JOIN stations_site sites ON stations.id = sites.station
      WHERE code = $1
    `;
    try {
      const res = await pgClient.query(query, [code]);
      return res.rows[0];
    } catch (err) {
      console.error(`Unknown station with code '${code}'`, err);
      return;
    }
  };

  const insertMeasurement = async (attributes) => {
    const code = attributes["id"];
    const ids = await getStationSiteIds(code);

    if (!ids) {
      console.warn(`Skip measurement of unknown station`);
      return;
    }

    const query = `
      INSERT INTO stations_measurement(station_id, site_id, datetime, attributes)
      VALUES($1, $2, $3, $4) RETURNING *
    `;
    const time = attributes["time"];
    delete attributes["time"];
    const values = [ids["station"], ids["site"], time, attributes];

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
    mqttClient.subscribe(subscriptionPath);
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
