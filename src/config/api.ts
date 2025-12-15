// API Configuration
// เปลี่ยน URL ได้ที่จุดเดียว

// เปลี่ยน BASE_URL ตรงนี้เมื่อต้องการเปลี่ยน Server
// - ถ้าอยู่เครื่องเดียวกัน: "http://localhost:5000"
// - ถ้าอยู่คนละเครื่อง: "http://192.168.1.50:5000"
export const BASE_URL = "http://192.168.1.50:5000";

// API Endpoints
export const API_ENDPOINTS = {
  // Data
  data: `${BASE_URL}/data`,

  // Video Feeds
  videoFeed: `${BASE_URL}/video_feed`,
  videoFeed2: `${BASE_URL}/video_feed_2`,

  // Robot API
  robot: `${BASE_URL}/api/robot`,
  robotPosition: `${BASE_URL}/api/robot/position`,
  robotMode: `${BASE_URL}/api/robot/mode`,
  robotClickMove: `${BASE_URL}/api/robot/click_move`,
  robotSyncAffine: (zoneId: number) => `${BASE_URL}/api/robot/sync_affine/${zoneId}`,
  robotSyncAffineCam2: (zoneId: number) => `${BASE_URL}/api/robot/sync_affine_cam2/${zoneId}`,

  // Calibration API
  calibration: `${BASE_URL}/api/calibration`,
  calibrationZones: `${BASE_URL}/api/calibration/zones`,
  calibrationAffine: `${BASE_URL}/api/calibration/affine`,
  calibrationAffineCompute: `${BASE_URL}/api/calibration/affine_compute`,

  // Download
  downloadLog: `${BASE_URL}/api/download_log`,
};

export default API_ENDPOINTS;
