// src/api/data.ts
import axios from "axios";
import { API_ENDPOINTS } from "../config/api";

export async function getRobotData() {
  return axios.get(API_ENDPOINTS.data);
}

export function getVideoFeedUrl() {
  return API_ENDPOINTS.videoFeed;
}

export function getVideoFeed2Url() {
  return API_ENDPOINTS.videoFeed2;
}

export async function downloadLog() {
  window.location.href = API_ENDPOINTS.downloadLog;
}
