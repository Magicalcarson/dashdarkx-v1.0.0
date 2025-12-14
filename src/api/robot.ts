// src/api/robot.ts
import axios from "axios";

const API = "http://192.168.1.50:5000/api/robot";

export interface MoveJPayload {
  mode: "MovJ";
  x: number;
  y: number;
  z: number;
  r: number;
}

export interface MoveLPayload {
  mode: "MovL";
  x: number;
  y: number;
  z: number;
  r: number;
}

export interface JointMovePayload {
  mode: "JointMovJ";
  j1: number;
  j2: number;
  j3: number;
  j4: number;
}

export type MovePayload = MoveJPayload | MoveLPayload | JointMovePayload;

export async function connectRobot(ip: string) {
  return axios.post(`${API}/connect`, { ip });
}

export async function enableRobot(enable: boolean) {
  return axios.post(`${API}/enable`, { enable });
}

export async function resetRobot() {
  return axios.post(`${API}/reset`);
}

export async function clearRobotError() {
  return axios.post(`${API}/clear`);
}

export async function emergencyStop() {
  return axios.post(`${API}/emergency_stop`);
}

export async function setRobotSpeed(val: number) {
  return axios.post(`${API}/speed`, { val });
}

export async function setDO(index: number, status: "On" | "Off") {
  return axios.post(`${API}/do`, { index, status });
}

export async function moveRobot(payload: MovePayload) {
  return axios.post(`${API}/move`, payload);
}

export async function clickMove(x: number, y: number) {
  return axios.post(`${API}/click_move`, { x, y });
}
