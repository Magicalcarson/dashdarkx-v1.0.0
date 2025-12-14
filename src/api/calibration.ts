// src/api/calibration.ts
import axios from "axios";

const API = "http://192.168.1.50:5000/api/calibration";

//
// ---------- TYPES ----------
//
export interface Zone {
  id: number;
  name: string;
  x: number;
  y: number;
  w: number;
  h: number;
  z: number;
  color: string;
}

export interface AffineParams {
  a: number;
  b: number;
  c: number;
  d: number;
  e: number;
  f: number;
}

export interface AffinePair {
  cam: { x: number; y: number };
  robot: { x: number; y: number };
}

//
// ---------- ZONES API ----------
//
export async function getZones() {
  return axios.get<Zone[]>(`${API}/zones`);
}

export async function saveZones(zones: Zone[]) {
  return axios.post(`${API}/zones`, zones);
}

//
// ---------- AFFINE PARAMS API ----------
//
export async function getAffineParams() {
  return axios.get<{ params: AffineParams }>(`${API}/affine`);
}

export async function saveAffineParams(params: AffineParams) {
  return axios.post(`${API}/affine`, { params });
}

//
// ---------- COMPUTE AFFINE MATRIX ----------
//
export async function computeAffine(pairs: AffinePair[]) {
  return axios.post(`${API}/affine_compute`, { pairs });
}
