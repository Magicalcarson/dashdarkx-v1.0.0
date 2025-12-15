# main.server.robot.py
# Final Stable Base Code: 5-Point Map, Safe Z, Correct Colors, Tag Locking, and Delay Logic

import cv2
import time
import threading
import datetime
import csv
import os
import json
import numpy as np
import math
from flask import Flask, Response, jsonify, request, send_file
from flask_cors import CORS
from pupil_apriltags import Detector
from dobot_api import DobotApiDashboard, DobotApi, DobotApiMove

# -------------------------------------------------------------------------
# [HARDWARE SETUP] GPIO for Jetson Nano / Orin Nano
# -------------------------------------------------------------------------
HAS_GPIO = False
try:
    import Jetson.GPIO as GPIO
    HAS_GPIO = True
    GPIO.setwarnings(False)
except ImportError:
    print("!!! WARNING: Jetson.GPIO library not found. Running in SIMULATION mode.")

# ======================================================================================
# 1. 5-POINT CALIBRATION CONFIG (ZONE 2 UPDATED)
# ======================================================================================

# [FIXED] ใช้ค่า Robot Coordinates เป็นจุดอ้างอิง (ref) เพื่อให้ Map ทำงานถูกต้อง
# และใช้ค่า Z จริงที่คุณวัดมา (-34 ถึง -40)
ZONE2_CALIBRATION_POINTS = [
    # P1: Top-Left
    {"ref_x": 122.18, "ref_y": 175.45, "true_x": 122.18, "true_y": 175.45, "true_z": -34.59},
    
    # P2: Top-Right
    {"ref_x": 121.66, "ref_y": 318.27, "true_x": 121.66, "true_y": 318.27, "true_z": -38.92},
    
    # P3: Bottom-Left
    {"ref_x": 205.21, "ref_y": 175.15, "true_x": 205.21, "true_y": 175.15, "true_z": -36.00},
    
    # P4: Bottom-Right
    {"ref_x": 208.83, "ref_y": 318.74, "true_x": 208.83, "true_y": 318.74, "true_z": -40.68},
    
    # C: Center
    {"ref_x": 166.41, "ref_y": 246.13, "true_x": 166.41, "true_y": 246.13, "true_z": -37.30}
]

# --- Picking Settings ---
FIXED_OBJECT_HEIGHT = 20.0 
Z_PICK_OFFSET = 62.0  # (ใช้สำหรับ Zone 1 และ 3)

# ======================================================================================
# GLOBAL SETTINGS
# ======================================================================================
RTSP_URL_CAM1 = "rtsp://admin:OokamiMio-2549@192.168.1.124/stream1"
RTSP_URL_CAM2 = "rtsp://admin:OokamiMio-2549@192.168.1.109/stream1"
SUCTION_SENSOR_PIN = 31
DB_FILE = "robot_history_log.csv"
ZONE_FILE_CAM1 = "zones_config_cam1.json"
ZONE_FILE_CAM2 = "zones_config_cam2.json"
AFFINE_FILE_CAM1 = "affine_params_cam1.json"
AFFINE_FILE_CAM2 = "affine_params_cam2.json"
ZONE_OVERRIDES_FILE = "zone_overrides.json"
AUTO_CAL_FILE = "auto_z_calibration.json"
NINE_POINTS_FILE = "nine_points_config.json"

# --- Object Data ---
OBJECT_INFO = {
    0: {'name': 'Fixed Box',   'height': FIXED_OBJECT_HEIGHT},
    1: {'name': 'Fixed Box',   'height': FIXED_OBJECT_HEIGHT},
    2: {'name': 'Fixed Box',   'height': FIXED_OBJECT_HEIGHT},
    3: {'name': 'Fixed Box',   'height': FIXED_OBJECT_HEIGHT},
    4: {'name': 'Fixed Box',   'height': FIXED_OBJECT_HEIGHT},
}

# --- State Control ---
CAM2_ENABLED = True  
ROBOT_MODE = 'MANUAL' # 'MANUAL' or 'AUTO'
is_robot_busy = False 


# --- Robot Clients ---
client_dash = None
client_move = None
client_feed = None
is_connected = False

# --- Global Data for Web ---
web_data = {
    "x": 0.0, "y": 0.0, "stack_h": 0.0, "total_picked": 0, "cycle_time": 0.0,
    "status": "IDLE", "history": [], "active_id": "-",
    "object_counts": {0: 0, 1: 0, 2: 0, 3: 0, 4: 0},
    "tags": [], "cam2_enabled": True, "robot_mode": "MANUAL",
    "target_x": 0.0, "target_y": 0.0,
}

# --- Logic Variables ---
history_log = []
sequence_count = 0
current_stack = 0.0
total_picked = 0
last_process_time = time.time()

# --- Vision State (แยกเก็บข้อมูลจาก 2 กล้อง) ---
current_visible_tags_cam1 = [] 
current_visible_tags_cam2 = []
processed_tags = {}   
tag_stability = {}    
# [NEW STATE] Lock ID for Target Stability
locked_target_id = None
locked_target_id_cam2 = None
AUTO_PICK_DELAY = 1.5 # Required delay in seconds before triggering auto pick


# --- Frame Buffers ---
output_frame_cam1 = None; lock_cam1 = threading.Lock()
output_frame_cam2 = None; lock_cam2 = threading.Lock()

# ======================================================================================
# 2. SYSTEM SETUP FUNCTIONS
# ======================================================================================

def setup_gpio():
    if HAS_GPIO:
        try:
            GPIO.setmode(GPIO.BOARD)
            GPIO.setup(SUCTION_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            print(f"[SYSTEM] GPIO Setup: Pin {SUCTION_SENSOR_PIN} as INPUT (PUD_UP)")
        except Exception as e:
            print(f"[ERROR] GPIO Setup failed: {e}")

setup_gpio()

def check_suction_status():
    if not HAS_GPIO: return True 
    try:
        return GPIO.input(SUCTION_SENSOR_PIN) == GPIO.LOW 
    except Exception: return False

def load_json(file_path, default_data):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f: return json.load(f)
        except Exception: pass
    return default_data

def save_json(file_path, data):
    try:
        with open(file_path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)
        return True
    except Exception: return False

if not os.path.exists(DB_FILE):
    with open(DB_FILE, 'w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(["Sequence", "Tag_ID", "Time", "Status", "Zone", "RobotX", "RobotY"])

def save_to_database(seq, tag_id, timestamp, zone_name, rx, ry):
    global history_log
    try:
        with open(DB_FILE, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([seq, tag_id, timestamp, "Success", zone_name, rx, ry])
        # [FIXED] Ensure history_log is correctly updated for dashboard
        history_log.insert(0, {"seq": seq, "id": tag_id, "time": timestamp, "status": "Success", "zone": zone_name})
        if len(history_log) > 50: history_log.pop()
        web_data['history'] = history_log
    except Exception as e:
        print(f"[DB Error] {e}")

# ======================================================================================
# 3. COORDINATE SYSTEM & CALIBRATION
# ======================================================================================

default_zones = [
    {"id": 1, "name": "Zone 1", "x": 50, "y": 50, "w": 250, "h": 200, "z": 150.0, "color": "#00ff00"},  
    {"id": 2, "name": "Zone 2", "x": 580, "y": 150, "w": 200, "h": 200, "z": -37.0, "color": "#ffff00"}, 
    {"id": 3, "name": "Zone 3", "x": 450, "y": 50, "w": 150, "h": 150, "z": 50.0, "color": "#ff0000"}
]

zones_config_cam1 = load_json(ZONE_FILE_CAM1, default_zones)
zones_config_cam2 = load_json(ZONE_FILE_CAM2, default_zones)
zone_overrides = load_json(ZONE_OVERRIDES_FILE, {})

# === [NEW] Load 9-Points Lookup Table ===
nine_points_data = load_json(NINE_POINTS_FILE, {})
print(f">>> [INIT] Loaded 9-points data: {list(nine_points_data.keys())}")

zone_matrices_cam1 = {}
zone_matrices_cam2 = {}

def load_affine_matrices(file_path, target_dict):
    data = load_json(file_path, {})
    if isinstance(data, dict):
        for zid_str, rec in data.items():
            try:
                p = rec.get("params")
                if p:
                    mtx = np.array([[float(p["a"]), float(p["b"]), float(p["c"])],
                                    [float(p["d"]), float(p["e"]), float(p["f"])]], dtype=np.float32)
                    target_dict[int(zid_str)] = mtx
            except Exception: pass

load_affine_matrices(AFFINE_FILE_CAM1, zone_matrices_cam1)
load_affine_matrices(AFFINE_FILE_CAM2, zone_matrices_cam2)

# ======================================================================
# [HARDCODED] CALIBRATION DATA
# ======================================================================
print(">>> [INIT] Computing Calibration Matrices...")

# Zone 1 (Original)
ZONE1_SRC = np.float32([[429.0, 452.0],[620.0, 459.0],[425.0, 557.0],[617.0, 569.0],[522.0, 506.0]])
ZONE1_DST = np.float32([[269.24, 71.70],[272.26, 212.65],[350.53, 71.82],[354.85, 214.52],[309.74, 143.01]])

# Zone 2 (Shifted +570 to match true frame coordinates)
ZONE2_SRC = np.float32([
    [112.0+570, 172.5],   # P1 Cam (Adjusted)
    [112.0+570, 319.6],   # P2 Cam (Adjusted)
    [195.5+570, 172.5],   # P3 Cam (Adjusted)
    [195.5+570, 319.6],   # P4 Cam (Adjusted)
    [155.5+570, 246.8]    # C Cam (Adjusted)
])
ZONE2_DST = np.float32([
    [122.18, 175.45], # P1 Robot
    [121.66, 318.27], # P2 Robot
    [205.21, 175.15], # P3 Robot
    [208.83, 318.74], # P4 Robot
    [166.41, 246.13]  # C Robot
])

ZONE1_MATRIX, _ = cv2.estimateAffine2D(ZONE1_SRC, ZONE1_DST)
ZONE2_MATRIX, _ = cv2.estimateAffine2D(ZONE2_SRC, ZONE2_DST)

zone_matrices_cam1[1] = ZONE1_MATRIX
zone_matrices_cam1[2] = ZONE2_MATRIX
print(">>> [INIT] Calibration Applied Success!")

# --- 5-POINT CALIBRATION LOGIC (IDW) ---
def calculate_correction_from_5_points(current_x, current_y):
    """
    คำนวณค่า X, Y, Z ที่ถูกต้อง โดยการเฉลี่ยน้ำหนักจาก 5 จุด (IDW)
    ref_x, ref_y คือค่า Robot Coordinate ของจุด Calibration
    """
    points = ZONE2_CALIBRATION_POINTS
    numerator_z = 0.0; numerator_x = 0.0; numerator_y = 0.0
    denominator = 0.0
    power = 3.0 # Power สูง เพื่อดึงค่าเข้าหาจุดที่ใกล้ที่สุด

    for p in points:
        dist = math.sqrt((current_x - p['ref_x'])**2 + (current_y - p['ref_y'])**2)
        
        if dist < 0.1: return p['true_x'], p['true_y'], p['true_z']
        
        weight = 1.0 / (dist ** power)
        
        # คำนวณ Offset (จริงๆแล้ว ref=true ดังนั้น offset=0 แต่นี่เผื่อไว้ปรับแก้ละเอียด)
        offset_x = p['true_x'] - p['ref_x']
        offset_y = p['true_y'] - p['ref_y']
        
        numerator_x += (offset_x * weight)
        numerator_y += (offset_y * weight)
        numerator_z += (p['true_z'] * weight)
        denominator += weight

    if denominator == 0: return current_x, current_y, -37.0 

    avg_offset_x = numerator_x / denominator
    avg_offset_y = numerator_y / denominator
    final_z = numerator_z / denominator
    
    # พิกัดใหม่
    final_x = current_x + avg_offset_x
    final_y = current_y + avg_offset_y
    
    return final_x, final_y, final_z

def pixel_to_robot_cam1(px, py, zone_id):
    if zone_id in zone_matrices_cam1:
        pt = np.array([px, py, 1.0], dtype=np.float32)
        res = zone_matrices_cam1[zone_id].dot(pt)
        return float(res[0]), float(res[1])
    return float(px), float(py)

def pixel_to_robot_cam2(px, py, zone_id):
    if zone_id in zone_matrices_cam2:
        pt = np.array([px, py, 1.0], dtype=np.float32)
        res = zone_matrices_cam2[zone_id].dot(pt)
        return float(res[0]), float(res[1])
    return float(px), float(py)

def get_zone_tag_offset(zone_id, tag_id):
    try: return float(zone_overrides.get(str(zone_id), {}).get(str(tag_id), 0.0))
    except: return 0.0

def check_zone_cam1(cx, cy):
    for zone in zones_config_cam1:
        if zone['x'] < cx < zone['x'] + zone['w'] and zone['y'] < cy < zone['y'] + zone['h']:
            return zone
    return None

def check_zone_cam2(cx, cy):
    for zone in zones_config_cam2:
        if zone['x'] < cx < zone['x'] + zone['w'] and zone['y'] < cy < zone['y'] + zone['h']:
            return zone
    return None

def hex_to_bgr(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (4, 2, 0))

def get_distance(x1, y1, x2, y2):
    return math.sqrt((x1-x2)**2 + (y1-y2)**2)

# === [NEW] 9-Point Lookup System ===
def find_nearest_nine_point(cx, cy, zone_id):
    """
    หาจุดที่ใกล้ที่สุดจาก 9 จุดใน zone ที่กำหนด
    Returns: (dobot_x, dobot_y, dobot_z, point_id) หรือ None ถ้าไม่เจอ
    """
    print(f"[9-POINT DEBUG] Looking for nearest point: cx={cx}, cy={cy}, zone_id={zone_id}")
    zone_key = f"zone{zone_id}"
    if zone_key not in nine_points_data:
        print(f"[9-POINT ERROR] Zone {zone_id} not found in nine_points_data")
        print(f"[9-POINT ERROR] Available zones: {list(nine_points_data.keys())}")
        return None

    points = nine_points_data[zone_key]['points']
    print(f"[9-POINT DEBUG] Zone {zone_id} has {len(points)} points")

    min_dist = float('inf')
    nearest_point = None

    for point in points:
        web_x = point['web_x']
        web_y = point['web_y']
        dist = get_distance(cx, cy, web_x, web_y)
        print(f"[9-POINT DEBUG] Point {point['id']}: web({web_x}, {web_y}) distance={dist:.2f}")

        if dist < min_dist:
            min_dist = dist
            nearest_point = point

    if nearest_point:
        print(f"[9-POINT SUCCESS] Nearest point: ID={nearest_point['id']}, distance={min_dist:.2f}")
        print(f"[9-POINT SUCCESS] Dobot coords: ({nearest_point['dobot_x']}, {nearest_point['dobot_y']}, {nearest_point['dobot_z']})")
        return (
            nearest_point['dobot_x'],
            nearest_point['dobot_y'],
            nearest_point['dobot_z'],
            nearest_point['id']
        )

    print(f"[9-POINT ERROR] No nearest point found!")
    return None

def get_zone_standby(zone_id):
    """
    คืนค่า standby point ของ zone
    Returns: {"x": x, "y": y, "z": z}
    """
    zone_key = f"zone{zone_id}"
    if zone_key in nine_points_data:
        return nine_points_data[zone_key]['standby']
    # Fallback to default
    return {"x": 250, "y": 0, "z": 100}

# ======================================================================================
# 4. ROBOT & LOGIC HELPERS
# ======================================================================================

def set_light(color):
    if not is_connected: return
    try:
        client_dash.DO(3, 0); client_dash.DO(4, 0); client_dash.DO(5, 0)
        if color == 'green': client_dash.DO(3, 1)
        elif color == 'yellow': client_dash.DO(4, 1)
        elif color == 'red': client_dash.DO(5, 1)
    except: pass

def control_suction(action):
    if not is_connected: return
    try:
        if action == 'on':
            client_dash.DO(9, 1); time.sleep(0.5); client_dash.DO(9, 0)
        elif action == 'off':
            client_dash.DO(9, 1); time.sleep(0.5); client_dash.DO(9, 0)
    except: pass

# [UPDATED] Pick Sequence with Retry Until Success
def execute_pick_sequence(rx, ry, z_pick, z_hover, sb, tag_id, zone_name):
    global is_robot_busy, web_data, sequence_count, total_picked

    try:
        is_robot_busy = True
        web_data['target_x'] = round(rx, 2)
        web_data['target_y'] = round(ry, 2)
        web_data['active_id'] = str(tag_id)
        web_data['status'] = f"MOVING TO ID:{tag_id}"

        set_light('yellow')
        print(f"[ROBOT] Picking ID:{tag_id} Zone:{zone_name} at XYZ: ({rx:.2f}, {ry:.2f}, {z_pick:.2f})")

        # 1. Go to Standby first
        client_move.MovJ(float(sb['x']), float(sb['y']), float(sb['z']), float(sb['r'])); client_move.Sync()

        # 2. Go to Hover position
        client_move.MovJ(rx, ry, z_hover, float(sb['r'])); client_move.Sync()

        # === [NEW] Retry Loop Until Suction Success ===
        retry_count = 0
        while True:
            retry_count += 1
            print(f"[ROBOT] Attempt #{retry_count} - Trying to pick at ({rx:.2f}, {ry:.2f}, {z_pick:.2f})")
            web_data['status'] = f"ATTEMPT #{retry_count}"

            # 3. Pick (MovL) - ลงแนวดิ่ง
            client_move.MovL(rx, ry, z_pick, float(sb['r'])); client_move.Sync()

            # 4. Suction On
            control_suction('on')
            time.sleep(0.8)

            # 5. Check Sensor
            if check_suction_status():
                # === SUCCESS! ===
                print(f">>> SUCTION SUCCESS on attempt #{retry_count}")
                web_data['status'] = f"SUCCESS (Attempt #{retry_count})"
                sequence_count += 1; total_picked += 1
                ts = datetime.datetime.now().strftime("%H:%M:%S")
                save_to_database(sequence_count, tag_id, ts, zone_name, round(rx, 2), round(ry, 2))

                # Lift up
                client_move.MovL(rx, ry, z_hover, float(sb['r'])); client_move.Sync()
                # Return to Standby
                client_move.MovJ(float(sb['x']), float(sb['y']), float(sb['z']), float(sb['r'])); client_move.Sync()
                # Go Home
                client_move.JointMovJ(0.0, 0.0, 0.0, 200.0); client_move.Sync()

                set_light('green')
                is_robot_busy = False
                return True

            else:
                # === FAILED - Retry ===
                print(f">>> SUCTION FAILED on attempt #{retry_count} - Retrying...")
                web_data['status'] = f"FAILED - RETRY #{retry_count}"
                control_suction('off')
                time.sleep(0.3)

                # Lift up a bit before retry
                client_move.MovL(rx, ry, z_hover, float(sb['r'])); client_move.Sync()
                time.sleep(0.5)

                # Continue to next retry (loop continues)

    except Exception as e:
        print(f"[ERROR] Motion: {e}")
        is_robot_busy = False
        set_light('red')
        return False

# ======================================================================================
# 5. FLASK API SERVER
# ======================================================================================
app = Flask(__name__)
CORS(app)

@app.route('/api/robot/mode', methods=['POST'])
def set_robot_mode():
    global ROBOT_MODE, web_data
    body = request.json or {}
    new_mode = body.get('mode')
    if new_mode in ['MANUAL', 'AUTO']:
        ROBOT_MODE = new_mode
        web_data['robot_mode'] = new_mode
        # Reset Target stability and locking when mode changes
        global tag_stability, locked_target_id, locked_target_id_cam2
        tag_stability = {}
        locked_target_id = None
        locked_target_id_cam2 = None
        
        return jsonify({"status": "success", "mode": new_mode})
    return jsonify({"status": "error"}), 400

@app.route('/api/robot/click_move', methods=['POST'])
def click_move():
    global is_connected
    if not is_connected:
        print("[CLICK ERROR] Robot not connected")
        return jsonify({"status": "error", "message": "Not Connected"})
    if ROBOT_MODE == 'AUTO':
        print("[CLICK ERROR] Cannot click in AUTO mode")
        return jsonify({"status": "error", "message": "Cannot click in AUTO mode"})

    cx, cy = request.json.get('x'), request.json.get('y')
    print(f"[CLICK DEBUG] Received click at: ({cx}, {cy})")

    target_tag = None; min_dist = 50.0

    # [UPDATED] Use Cam1 only (Cam2 disabled for tag detection)
    all_tags = current_visible_tags_cam1
    print(f"[CLICK DEBUG] Total tags visible (Cam1 only): {len(all_tags)}")

    for tag in all_tags:
        dist = get_distance(cx, cy, tag['cx'], tag['cy'])
        if dist < min_dist: min_dist = dist; target_tag = tag

    if not target_tag:
        print("[CLICK ERROR] No tag found near click position")
        return jsonify({"status": "error", "message": "No Tag"})

    print(f"[CLICK DEBUG] Found target tag: ID={target_tag['id']}, cx={target_tag['cx']}, cy={target_tag['cy']}")

    zone_data = target_tag['zone']
    if not zone_data:
        print("[CLICK ERROR] Tag outside zone")
        return jsonify({"status": "error", "message": "Outside Zone"})

    tag_id = int(target_tag['id'])
    zone_id = int(zone_data['id'])

    # [FIXED] Use Tag position, not click position!
    tag_cx = target_tag['cx']
    tag_cy = target_tag['cy']
    print(f"[CLICK DEBUG] Tag ID: {tag_id}, Zone ID: {zone_id}, Zone Name: {zone_data['name']}")
    print(f"[CLICK DEBUG] Tag position: ({tag_cx}, {tag_cy})")

    # === [NEW] Use 9-Point Lookup System ===
    result = find_nearest_nine_point(tag_cx, tag_cy, zone_id)
    if not result:
        print(f"[CLICK ERROR] No 9-point data for zone {zone_id}")
        return jsonify({"status": "error", "message": "No 9-point data for this zone"})

    final_rx, final_ry, z_pick, point_id = result
    z_hover = z_pick + 40.0
    sb = get_zone_standby(zone_id)

    print(f"[CLICK] Pixel:({cx:.1f},{cy:.1f}) -> Tag:{tag_id} Zone:{zone_id} Point:{point_id} -> Dobot:({final_rx:.1f},{final_ry:.1f}, Z:{z_pick:.1f})")
    print(f"[CLICK] Standby: {sb}, z_hover: {z_hover}")
    print(f"[CLICK] Starting execute_pick_sequence thread...")

    # [FIXED] In MANUAL mode, execute immediately (no delay)
    threading.Thread(target=execute_pick_sequence, args=(final_rx, final_ry, z_pick, z_hover, sb, tag_id, zone_data['name'])).start()

    return jsonify({"status": "success", "message": "Command Sent", "point_id": point_id})

# --- Robot APIs (Omitted for brevity) ---
@app.route('/api/robot/connect', methods=['POST'])
def connect_robot():
    global client_dash, client_move, client_feed, is_connected
    ip = request.json.get('ip', '192.168.1.6')
    try:
        if is_connected:
            try: client_dash.close(); client_move.close(); client_feed.close()
            except: pass
        client_dash = DobotApiDashboard(ip, 29999)
        client_move = DobotApiMove(ip, 30003)
        client_feed = DobotApi(ip, 30004)
        is_connected = True
        client_dash.SpeedFactor(50); set_light('green')
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)})

@app.route('/api/robot/enable', methods=['POST'])
def enable_robot():
    if not is_connected: return jsonify({"status": "error"})
    if request.json.get('enable'): client_dash.EnableRobot(); set_light('green')
    else: client_dash.DisableRobot(); set_light('yellow')
    return jsonify({"status": "success"})

@app.route('/api/robot/reset', methods=['POST'])
def reset_robot():
    if is_connected: client_dash.ResetRobot(); set_light('green')
    return jsonify({"status": "success"})

@app.route('/api/robot/clear', methods=['POST'])
def clear_error():
    if is_connected: client_dash.ClearError(); set_light('green')
    return jsonify({"status": "success"})

@app.route('/api/robot/emergency_stop', methods=['POST'])
def emergency_stop():
    if is_connected: client_dash.EmergencyStop(); set_light('red')
    return jsonify({"status": "success"})

@app.route('/api/robot/speed', methods=['POST'])
def set_speed():
    if is_connected: client_dash.SpeedFactor(int(request.json.get('val', 30)))
    return jsonify({"status": "success"})

@app.route('/api/robot/do', methods=['POST'])
def set_do():
    if is_connected: client_dash.DO(int(request.json.get('index', 1)), 1 if request.json.get('status') == 'On' else 0)
    return jsonify({"status": "success"})

@app.route('/api/robot/move', methods=['POST'])
def move_robot():
    if not is_connected: return jsonify({"status": "error"})
    d = request.json or {}; m = d.get('mode')
    try:
        if m == 'MovJ': client_move.MovJ(float(d['x']), float(d['y']), float(d['z']), float(d['r']))
        elif m == 'MovL': client_move.MovL(float(d['x']), float(d['y']), float(d['z']), float(d['r']))
        elif m == 'JointMovJ': client_move.JointMovJ(float(d['j1']), float(d['j2']), float(d['j3']), float(d['j4']))
        elif m == 'home': client_move.JointMovJ(0.0, 0.0, 0.0, 200.0)
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)})

@app.route('/api/robot/position', methods=['GET'])
def get_robot_position():
    if not is_connected or client_feed is None: return jsonify({"status": "error"}), 400
    try:
        p = client_feed.GetPose()
        return jsonify({"status": "success", "x": float(p[0]), "y": float(p[1]), "z": float(p[2]), "r": float(p[3])})
    except: return jsonify({"status": "error"}), 500

@app.route('/api/robot/io', methods=['GET'])
def get_robot_io():
    if not is_connected or client_feed is None: return jsonify({"status": "error"}), 400
    try:
        di = [int(client_feed.DI(i)) for i in range(1, 9)]
        do = [int(client_feed.DO(i)) for i in range(1, 9)]
        return jsonify({"status": "success", "di": di, "do": do})
    except: return jsonify({"status": "error"}), 500

@app.route('/api/cam2/toggle', methods=['POST'])
def toggle_cam2():
    global CAM2_ENABLED, web_data
    body = request.json or {}
    if 'active' in body:
        CAM2_ENABLED = bool(body['active'])
        web_data['cam2_enabled'] = CAM2_ENABLED
    return jsonify({"status": "success", "active": CAM2_ENABLED})

@app.route('/api/cam2/state', methods=['GET'])
def get_cam2_state(): return jsonify({"active": CAM2_ENABLED})

@app.route('/api/calibration/zones', methods=['GET', 'POST'])
def handle_zones_cam1():
    global zones_config_cam1
    if request.method == 'POST': zones_config_cam1 = request.json; save_json(ZONE_FILE_CAM1, zones_config_cam1)
    return jsonify(zones_config_cam1)

@app.route('/api/cam2/calibration/zones', methods=['GET', 'POST'])
def handle_zones_cam2():
    global zones_config_cam2
    if request.method == 'POST': zones_config_cam2 = request.json; save_json(ZONE_FILE_CAM2, zones_config_cam2)
    return jsonify(zones_config_cam2)

@app.route('/api/calibration/affine', methods=['GET', 'POST'])
def handle_affine_cam1():
    if request.method == 'GET': return jsonify(load_json(AFFINE_FILE_CAM1, {}))
    body = request.json or {}; zid = str(body.get('zone_id'))
    if zid:
        data = load_json(AFFINE_FILE_CAM1, {})
        data[zid] = body
        save_json(AFFINE_FILE_CAM1, data); load_affine_matrices(AFFINE_FILE_CAM1, zone_matrices_cam1)
        return jsonify({"status": "saved"})
    return jsonify({"status": "error"}), 400

@app.route('/api/cam2/calibration/affine', methods=['GET', 'POST'])
def handle_affine_cam2():
    if request.method == 'GET': return jsonify(load_json(AFFINE_FILE_CAM2, {}))
    body = request.json or {}; zid = str(body.get('zone_id'))
    if zid:
        data = load_json(AFFINE_FILE_CAM2, {})
        data[zid] = body
        save_json(AFFINE_FILE_CAM2, data); load_affine_matrices(AFFINE_FILE_CAM2, zone_matrices_cam2)
        return jsonify({"status": "saved"})
    return jsonify({"status": "error"}), 400

@app.route('/api/calibration/affine_compute', methods=['POST'])
@app.route('/api/cam2/calibration/affine_compute', methods=['POST'])
def compute_affine():
    body = request.json or {}; pairs = body.get('pairs', [])
    if len(pairs) < 3: return jsonify({"error": "Need 3 pts"}), 400
    A = []; B = []
    for p in pairs:
        try:
            cx, cy = float(p['cam']['x']), float(p['cam']['y'])
            rx, ry = float(p['robot']['x']), float(p['robot']['y'])
            A.append([cx, cy, 1, 0, 0, 0]); B.append(rx)
            A.append([0, 0, 0, cx, cy, 1]); B.append(ry)
        except: continue
    if not A: return jsonify({"error": "Invalid"}), 400
    try:
        x, _, _, _ = np.linalg.lstsq(np.array(A), np.array(B), rcond=None)
        params = {"a": float(x[0]), "b": float(x[1]), "c": float(x[2]), "d": float(x[3]), "e": float(x[4]), "f": float(x[5])}
        res = float(np.sqrt(np.mean((np.array(B) - np.array(A).dot(x)) ** 2)))
        return jsonify({"params": params, "residual": res})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/calibration/zone_override', methods=['POST'])
def override_z():
    body = request.json or {}; zid = str(body.get('zone_id')); tid = str(body.get('tag_id')); off = float(body.get('offset_mm', 0.0))
    if zid not in zone_overrides: zone_overrides[zid] = {}
    zone_overrides[zid][tid] = off; save_json(ZONE_OVERRIDES_FILE, zone_overrides)
    return jsonify({"status": "success"})

@app.route('/api/robot/sync_affine/<int:zone_id>', methods=['POST'])
def sync_affine_1(zone_id): load_affine_matrices(AFFINE_FILE_CAM1, zone_matrices_cam1); return jsonify({"status":"synced"})

@app.route('/api/robot/sync_affine_cam2/<int:zone_id>', methods=['POST'])
def sync_affine_2(zone_id): load_affine_matrices(AFFINE_FILE_CAM2, zone_matrices_cam2); return jsonify({"status":"synced"})

@app.route('/api/calibration/auto_z_probe', methods=['POST'])
def auto_z_probe(): return jsonify({"status": "started", "msg": "Z-Probe Logic triggered"})

@app.route('/api/download_log')
def download_log():
    if os.path.exists(DB_FILE): return send_file(DB_FILE, as_attachment=True, download_name=f"log_{int(time.time())}.csv")
    return jsonify({"status": "error"}), 404

@app.route("/data")
def data_stream():
    # [FIXED] Combine tags for web display
    all_visible_tags = current_visible_tags_cam1 + current_visible_tags_cam2
    
    formatted_tags = []
    for tag in all_visible_tags:
        zone_name = tag.get('zone', {}).get('name') if tag.get('zone') else "None"
        formatted_tags.append({
            "id": tag['id'], 
            "cx": tag['cx'], 
            "cy": tag['cy'], 
            "rx": round(tag.get('rx', 0.0), 2), 
            "ry": round(tag.get('ry', 0.0), 2), 
            "zone": zone_name
        })
        
    web_data['tags'] = formatted_tags
    return jsonify(web_data)

@app.route("/video_feed")
def feed1(): return Response(gen_frames_cam1(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/video_feed_2")
def feed2(): return Response(gen_frames_cam2(), mimetype="multipart/x-mixed-replace; boundary=frame")

# ======================================================================================
# 6. VISION LOOPS (Multi-Cam Logic)
# ======================================================================================

def vision_loop_cam1():
    """ CAM 1: รับผิดชอบ Zone 2 (5-Point) และ Zone 3 (Affine) """
    global output_frame_cam1, web_data, current_visible_tags_cam1, locked_target_id
    global processed_tags, tag_stability

    cap = cv2.VideoCapture(RTSP_URL_CAM1)
    at_detector = Detector(families="tag36h11")
    print(">>> CAM1: STARTED (Top View) <<<")

    while True:
        try:
            ret, frame = cap.read()
            if not ret: time.sleep(2); cap.release(); cap = cv2.VideoCapture(RTSP_URL_CAM1); continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY); tags = at_detector.detect(gray)
            current_visible_tags_cam1 = []; status_text = web_data['status']; current_time = time.time(); visible_ids = set()
            
            newly_detected_tags = {}
            closest_tag_id = None
            min_dist_to_center = float('inf')

            # Draw Zones
            for z in zones_config_cam1:
                color = hex_to_bgr(z['color'])
                cv2.rectangle(frame, (z['x'], z['y']), (z['x']+z['w'], z['y']+z['h']), color, 2)
                cv2.putText(frame, z['name'], (z['x'], z['y']-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            for tag in tags:
                cx, cy = int(tag.center[0]), int(tag.center[1]); zone = check_zone_cam1(cx, cy); visible_ids.add(tag.tag_id)
                
                rx, ry, z_pick = 0.0, 0.0, 0.0
                is_processed = False

                if zone:
                    zone_id = int(zone['id'])
                    
                    # 1. Calculate Robot Coordinates
                    if zone_id == 2:
                        # Zone 2: Use 5-Point Correction
                        raw_rx, raw_ry = pixel_to_robot_cam1(cx, cy, zone_id)
                        rx, ry, final_z = calculate_correction_from_5_points(raw_rx, raw_ry)
                        z_pick = final_z - 2.0
                        is_processed = True
                    elif zone_id == 3:
                        # Zone 3: ใช้ Affine ปกติ
                        rx, ry = pixel_to_robot_cam1(cx, cy, zone_id)
                        z_base = float(zone.get('z', 0.0))
                        z_off = get_zone_tag_offset(zone_id, tag.tag_id)
                        z_pick = z_base + FIXED_OBJECT_HEIGHT + z_off - Z_PICK_OFFSET
                        is_processed = True
                    
                    if is_processed:
                        tag_data = {
                            "id": tag.tag_id, "cx": cx, "cy": cy, "rx": rx, "ry": ry, 
                            "z_pick": z_pick, "zone": zone, "cam": 1
                        }
                        
                        newly_detected_tags[tag.tag_id] = tag_data
                        
                        # Track closest tag for potential new lock (using pixel center)
                        dist = get_distance(cx, cy, frame.shape[1]/2, frame.shape[0]/2)
                        if dist < min_dist_to_center:
                            min_dist_to_center = dist
                            closest_tag_id = tag.tag_id

                        # --- Drawing Logic with Stability ---
                        if tag.tag_id not in tag_stability:
                            tag_stability[tag.tag_id] = current_time
                        
                        time_elapsed = current_time - tag_stability[tag.tag_id]
                        remaining_delay = max(0.0, AUTO_PICK_DELAY - time_elapsed)
                        
                        if remaining_delay > 0:
                            # State: WAITING (Yellow frame, countdown text)
                            color = hex_to_bgr("#ffff00") # Yellow
                            cv2.polylines(frame, [tag.corners.astype(int)], True, color, 2)
                            cv2.putText(frame, f"WAIT {remaining_delay:.1f}s", (cx - 10, cy + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                        else:
                            # State: READY (Green frame)
                            color = hex_to_bgr("#00ff00") # Green
                            cv2.polylines(frame, [tag.corners.astype(int)], True, color, 2)
                            cv2.putText(frame, "READY", (cx - 10, cy + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    

                    elif zone_id == 1:
                        # Zone 1 seen by Cam 1 (low priority/distortion) - just draw its color
                        cv2.polylines(frame, [tag.corners.astype(int)], True, hex_to_bgr(zone['color']), 2) 

                else:
                    cv2.polylines(frame, [tag.corners.astype(int)], True, (0, 0, 255), 2)

            
            # --- Target Locking Logic ---
            
            # 1. Check if the currently locked tag is still visible
            target_data = None
            if locked_target_id in newly_detected_tags:
                target_data = newly_detected_tags[locked_target_id]
            
            else:
                # The locked tag is lost or no tag was locked previously
                locked_target_id = None
                if closest_tag_id is not None:
                    # Lock onto the closest visible tag
                    locked_target_id = closest_tag_id
                    target_data = newly_detected_tags[closest_tag_id]
                # If no tags, target_data remains None
                    
            # 2. Update Target Position and Auto Pick Logic
            if target_data:
                tag_id = target_data['id']
                # Update web_data with the stable target position
                web_data['target_x'] = round(target_data['rx'], 2)
                web_data['target_y'] = round(target_data['ry'], 2)
                
                time_elapsed = current_time - tag_stability.get(tag_id, current_time)

                if ROBOT_MODE == 'AUTO' and not is_robot_busy and is_connected:

                    if time_elapsed < AUTO_PICK_DELAY:
                        status_text = "DETECTED (WAITING)"
                    else:
                        status_text = "DETECTED (READY)"
                         # Execute pick sequence after delay
                        if current_time - processed_tags.get(tag_id, 0) > 10.0: # Check if already processed recently
                            processed_tags[tag_id] = current_time

                            zone = target_data['zone']
                            zone_id = int(zone['id'])
                            cx = target_data['cx']
                            cy = target_data['cy']

                            # === [NEW] Use 9-Point Lookup System for AUTO mode ===
                            result = find_nearest_nine_point(cx, cy, zone_id)
                            if result:
                                rx, ry, z_pick, point_id = result
                                z_hover = z_pick + 40.0
                                sb = get_zone_standby(zone_id)

                                print(f"[AUTO CAM1] Tag:{tag_id} Zone:{zone_id} Point:{point_id} -> Dobot:({rx:.1f},{ry:.1f}, Z:{z_pick:.1f})")

                                threading.Thread(target=execute_pick_sequence,
                                                 args=(rx, ry, z_pick, z_hover, sb, tag_id, zone['name'])).start()
                            else:
                                print(f"[AUTO CAM1 ERROR] No 9-point data for Tag:{tag_id} Zone:{zone_id}")
                
                elif not is_robot_busy:
                    status_text = f"DETECTED (MANUAL)" 
            
            elif not is_robot_busy:
                status_text = "IDLE"
                web_data['target_x'] = 0.0
                web_data['target_y'] = 0.0
            
            
            # Cleanup stability dictionary
            for tid in list(tag_stability.keys()):
                if tid not in newly_detected_tags: 
                    del tag_stability[tid]
                
            if locked_target_id is not None and locked_target_id not in newly_detected_tags:
                # If locked tag disappears, allow system to detect new one next frame
                locked_target_id = None
                

            # Update current_visible_tags_cam1 (used for /data API)
            current_visible_tags_cam1 = list(newly_detected_tags.values())


            # Update web_data (Ensure status is passed correctly)
            web_data.update({
                "x": 0, "y": 0, "stack_h": current_stack,
                "total_picked": total_picked,
                "history": history_log,
                "cam2_enabled": CAM2_ENABLED,
                "robot_mode": ROBOT_MODE
            })
            if not is_robot_busy: web_data["status"] = status_text # Prioritize motion status if busy

            with lock_cam1: output_frame_cam1 = frame.copy()
            
        except Exception as e:
            # [FIXED] Catch exceptions in loop to prevent thread crash
            print(f"[ERROR CAM1 VISION LOOP] {e}")
            time.sleep(0.1) # Prevent CPU hogging if a persistent error occurs in one frame
            # Continue the loop

    cap.release()

def vision_loop_cam2():
    """ CAM 2: Live Feed Only (No Tag Detection) """
    global output_frame_cam2, current_visible_tags_cam2

    cap = cv2.VideoCapture(RTSP_URL_CAM2)
    print(">>> CAM2: STARTED (Live Feed Only - No Tag Detection) <<<")
    
    while True:
        try:
            ret, frame = cap.read()
            if not ret:
                time.sleep(2)
                cap = cv2.VideoCapture(RTSP_URL_CAM2)
                continue

            # [DISABLED] No tag detection for Cam2 - only show zones
            current_visible_tags_cam2 = []

            # Draw Zones only (for reference)
            for z in zones_config_cam2:
                color = hex_to_bgr(z['color'])
                cv2.rectangle(frame, (z['x'], z['y']), (z['x']+z['w'], z['y']+z['h']), color, 2)
                cv2.putText(frame, z['name'], (z['x'], z['y']-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            # Display "Live Feed Only" text
            cv2.putText(frame, "CAM 2 - LIVE FEED ONLY", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

            with lock_cam2:
                output_frame_cam2 = frame.copy()

        except Exception as e:
            print(f"[ERROR CAM2 VISION LOOP] {e}")
            time.sleep(0.1)

    cap.release()


def gen_frames_cam1():
    while True:
        try:
            with lock_cam1:
                if output_frame_cam1 is None: time.sleep(0.1); continue
                _, img = cv2.imencode(".jpg", output_frame_cam1)
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(img) + b'\r\n')
        except Exception:
            time.sleep(0.1)

def gen_frames_cam2():
    while True:
        try:
            with lock_cam2:
                if output_frame_cam2 is None: time.sleep(0.1); continue
                _, img = cv2.imencode(".jpg", output_frame_cam2)
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(img) + b'\r\n')
        except Exception:
            time.sleep(0.1)

if __name__ == "__main__":
    t1 = threading.Thread(target=vision_loop_cam1); t1.daemon = True; t1.start()
    t2 = threading.Thread(target=vision_loop_cam2); t2.daemon = True; t2.start()
    print("--- ROBOT SERVER READY (FIXED) ---")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)