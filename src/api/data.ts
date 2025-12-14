// src/api/data.ts
import axios from "axios";

export async function getRobotData() {
  return axios.get("http://192.168.1.50:5000/data");
}

export function getVideoFeedUrl() {
  return "http://192.168.1.50:5000/video_feed";
}

export function getVideoFeed2Url() {
  return "http://192.168.1.50:5000/video_feed_2";
}

export async function downloadLog() {
  window.location.href = "http://192.168.1.50:5000/api/download_log";
}
