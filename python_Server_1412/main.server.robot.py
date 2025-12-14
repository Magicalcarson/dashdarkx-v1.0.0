import cv2
import time
import threading
import datetime
import csv
import os
import json
import numpy as np
import math
import re
from flask import Flask, Response, jsonify, request, send_file
from flask_cors import CORS
from pupil_apriltags import Detector
from dobot_api import DobotApiDashboard, DobotApi, DobotApiMove

# ======================================================================================
# GLOBAL CONSTANTS & HARDWARE SETUP
# ======================================================================================

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

def setup_gpio():
    if HAS_GPIO:
        try:
            GPIO.setmode(GPIO.BOARD)
            GPIO.setup(SUCTION_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            print(f"[SYSTEM] GPIO Setup: Pin {SUCTION_SENSOR_PIN} as INPUT (PUD_UP)")
        except Exception as e:
            print(f"[ERROR] GPIO Setup failed: {e}")

# -------------------------------------------------------------------------
# ✨ NEW: CORRECTED 5-POINT CALIBRATION DATA (Hardcoded Defaults)
# -------------------------------------------------------------------------
ZONE_BASE_HEIGHTS = {
    1: 150.0,  # 15 cm base
    2: 105.0,  # 10.5 cm base
    3: 48.0,   # 4.8 cm base
}
OBJECT_HEIGHT = 30.0  # 3 cm object height
SUCTION_CUP_LENGTH = 62.0  # Tool length offset (Z_PICK_OFFSET)

# --- Default Calibration Points (Used if files are not found) ---
ZONE1_CALIBRATION_POINTS = [
    {"name": "P1", "ref_x": 267.19, "ref_y": 71.70,   "true_x": 267.19, "true_y": 71.70,   "true_z": -18.91},
    {"name": "P2", "ref_x": 272.76, "ref_y": 211.78,  "true_x": 272.76, "true_y": 211.78,  "true_z": -22.53},
    {"name": "P3", "ref_x": 352.69, "ref_y": 71.82,   "true_x": 352.69, "true_y": 71.82,   "true_z": -21.33},
    {"name": "P4", "ref_x": 355.20, "ref_y": 214.03,  "true_x": 355.20, "true_y": 214.03,  "true_z": -23.65},
    {"name": "C",  "ref_x": 315.10, "ref_y": 144.56,  "true_x": 315.10, "true_y": 144.56,  "true_z": -20.78}
]

ZONE2_CALIBRATION_POINTS = [
    {"name": "P1", "ref_x": 122.41, "ref_y": 173.4,   "true_x": 122.41, "true_y": 173.4,   "true_z": -59.35},
    {"name": "P2", "ref_x": 125.30, "ref_y": 314.47,  "true_x": 125.30, "true_y": 314.47,  "true_z": -66.62},
    {"name": "P3", "ref_x": 202.37, "ref_y": 175.30,  "true_x": 202.37, "true_y": 175.30,  "true_z": -62.67},
    {"name": "P4", "ref_x": 204.72, "ref_y": 316.77,  "true_x": 204.72, "true_y": 316.77,  "true_z": -69.01},
    {"name": "C",  "ref_x": 165.91, "ref_y": 247.9,   "true_x": 165.91, "true_y": 247.9,   "true_z": -64.01}
]

ZONE3_CALIBRATION_POINTS = [
    {"name": "P1", "ref_x": -85.79, "ref_y": 222.69,  "true_x": -85.79, "true_y": 222.69,  "true_z": -119.09},
    {"name": "P2", "ref_x": -86.74, "ref_y": 303.57,  "true_x": -86.74, "true_y": 303.57,  "true_z": -123.90},
    {"name": "P3", "ref_x": 50.63,  "ref_y": 222.94,  "true_x": 50.63,  "true_y": 222.94,  "true_z": -117.92},
    {"name": "P4", "ref_x": 50.0,   "ref_y": 303.0,   "true_x": 50.0,   "true_y": 303.0,   "true_z": -121.0},
    {"name": "C",  "ref_x": -18.0,  "ref_y": 263.0,   "true_x": -18.0,  "true_y": 263.0,   "true_z": -120.0}
]

# --- Default Affine Points (Used to calculate initial matrix) ---
ZONE1_CAM_POINTS = np.float32([[48.1, 459.4], [43.0, 321.2], [-28.3, 455.8], [-35.8, 322.0], [2.0, 390.7]])
ZONE1_ROBOT_POINTS = np.float32([[267.19, 71.70], [272.76, 211.78], [352.69, 71.82], [355.20, 214.03], [315.10, 144.56]])
ZONE2_CAM_POINTS = np.float32([[-25.9, 361.2], [159.0, 362.4], [-27.0, 463.8], [157.0, 465.0], [68.0, 415.5]])
ZONE2_ROBOT_POINTS = np.float32([[122.41, 173.4], [125.30, 314.47], [202.37, 175.30], [204.72, 316.77], [165.91, 247.9]])
ZONE3_CAM_POINTS = np.float32([[607.0, 106.0], [705.0, 108.0], [605.0, 273.0], [705.0, 273.0], [655.0, 189.5]])
ZONE3_ROBOT_POINTS = np.float32([[-85.79, 222.69], [-86.74, 303.57], [50.63, 222.94], [50.0, 303.0], [-18.0, 263.0]])

# --- File Paths ---
RTSP_URL_CAM1 = "rtsp://admin:OokamiMio-2549@192.168.1.124/stream1"
RTSP_URL_CAM2 = "rtsp://admin:OokamiMio-2549@192.168.1.109/stream1"
SUCTION_SENSOR_PIN = 33
DB_FILE = "robot_history_log.csv"
ZONE_FILE_CAM1 = "zones_config_cam1.json"
ZONE_FILE_CAM2 = "zones_config_cam2.json"
AFFINE_FILE_CAM1 = "affine_params_cam1.json"
AFFINE_FILE_CAM2 = "affine_params_cam2.json"
ZONE_OVERRIDES_FILE = "zone_overrides.json"
CALIBRATION_5POINT_FILE_CAM1 = "calibration_5point_cam1.json"
CALIBRATION_5POINT_FILE_CAM2 = "calibration_5point_cam2.json"

# --- Mappings ---
TAG_TO_POINT_NAME = { 0: "P1", 1: "P2", 2: "P3", 3: "P4", 4: "C" }
POINT_NAME_TO_TAG = {v: k for k, v in TAG_TO_POINT_NAME.items()}

# --- State Variables ---
CAM2_ENABLED = True  
ROBOT_MODE = 'MANUAL' 
is_robot_busy = False 

client_dash = None
client_move = None
client_feed = None
is_connected = False

web_data = {
    "x": 0.0, "y": 0.0, "stack_h": 0.0, "total_picked": 0, "cycle_time": 0.0,
    "status": "IDLE", "history": [], "active_id": "-",
    "object_counts": {0: 0, 1: 0, 2: 0, 3: 0, 4: 0},
    "tags": [], "cam2_enabled": True, "robot_mode": "MANUAL",
    "target_x": 0.0, "target_y": 0.0,
}

history_log = []
sequence_count = 0
current_stack = 0.0
total_picked = 0
last_process_time = time.time()
current_visible_tags_cam1 = []
current_visible_tags_cam2 = []
processed_tags = {}
tag_stability = {}

locked_target_id = None
locked_target_id_cam2 = None
AUTO_PICK_DELAY = 5.0

output_frame_cam1 = None; lock_cam1 = threading.Lock()
output_frame_cam2 = None; lock_cam2 = threading.Lock()

zone_5point_calibrations_cam1 = {}
zone_5point_calibrations_cam2 = {}
zone_matrices_cam1 = {}
zone_matrices_cam2 = {}

# ======================================================================================
# I. UTILITY FUNCTIONS
# ======================================================================================

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
        history_log.insert(0, {"seq": seq, "id": tag_id, "time": timestamp, "status": "Success", "zone": zone_name})
        if len(history_log) > 50: history_log.pop()
        web_data['history'] = history_log
    except Exception as e:
        print(f"[DB Error] {e}")

def hex_to_bgr(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (4, 2, 0))

def get_distance(x1, y1, x2, y2):
    return math.sqrt((x1-x2)**2 + (y1-y2)**2)

# ======================================================================================
# II. CALIBRATION AND COORDINATE TRANSFORMATION
# ======================================================================================

default_zones = [
    {"id": 1, "name": "Zone 1", "x": 50, "y": 50, "w": 250, "h": 200, "z": ZONE_BASE_HEIGHTS[1], "color": "#00ff00"},
    {"id": 2, "name": "Zone 2", "x": 580, "y": 150, "w": 200, "h": 200, "z": ZONE_BASE_HEIGHTS[2], "color": "#ffff00"},
    {"id": 3, "name": "Zone 3", "x": 450, "y": 50, "w": 150, "h": 150, "z": ZONE_BASE_HEIGHTS[3], "color": "#ff0000"}
]
zones_config_cam1 = load_json(ZONE_FILE_CAM1, default_zones)
zones_config_cam2 = load_json(ZONE_FILE_CAM2, default_zones)
zone_overrides = load_json(ZONE_OVERRIDES_FILE, {})

def load_5point_calibrations():
    global zone_5point_calibrations_cam1, zone_5point_calibrations_cam2
    global ZONE1_CALIBRATION_POINTS, ZONE2_CALIBRATION_POINTS, ZONE3_CALIBRATION_POINTS

    data_cam1 = load_json(CALIBRATION_5POINT_FILE_CAM1, {})
    zone_5point_calibrations_cam1 = data_cam1
    data_cam2 = load_json(CALIBRATION_5POINT_FILE_CAM2, {})
    zone_5point_calibrations_cam2 = data_cam2
    
    # Update calibration points if saved for CAM1 Zones
    if "zone_1" in data_cam1 and "points" in data_cam1["zone_1"]:
        ZONE1_CALIBRATION_POINTS = data_cam1["zone_1"]["points"]
        print(f"[5-POINT] ✓ Loaded Zone 1 calibration from file")
    if "zone_2" in data_cam1 and "points" in data_cam1["zone_2"]:
        ZONE2_CALIBRATION_POINTS = data_cam1["zone_2"]["points"]
        print(f"[5-POINT] ✓ Loaded Zone 2 calibration from file")
    if "zone_3" in data_cam1 and "points" in data_cam1["zone_3"]:
        ZONE3_CALIBRATION_POINTS = data_cam1["zone_3"]["points"]
        print(f"[5-POINT] ✓ Loaded Zone 3 calibration from file")
    
    print(f"[5-POINT] CAM1: {len(zone_5point_calibrations_cam1)} zones, CAM2: {len(zone_5point_calibrations_cam2)} zones")

def compute_initial_affine_matrices():
    """Compute Affine Matrices from hardcoded/default points at startup."""
    global zone_matrices_cam1, zone_matrices_cam2

    print(">>> [INIT] Computing Affine Matrices from Calibration Data...")
    
    # --- CAM 1 (Initial Affine based on hardcoded defaults) ---
    ZONE1_MATRIX, _ = cv2.estimateAffine2D(ZONE1_CAM_POINTS, ZONE1_ROBOT_POINTS)
    ZONE2_MATRIX, _ = cv2.estimateAffine2D(ZONE2_CAM_POINTS, ZONE2_ROBOT_POINTS)
    ZONE3_MATRIX, _ = cv2.estimateAffine2D(ZONE3_CAM_POINTS, ZONE3_ROBOT_POINTS)
    
    zone_matrices_cam1[1] = ZONE1_MATRIX
    zone_matrices_cam1[2] = ZONE2_MATRIX
    zone_matrices_cam1[3] = ZONE3_MATRIX
    
    print(f"[INIT] Zone 1 Matrix:\n{ZONE1_MATRIX}")
    print(f"[INIT] Zone 2 Matrix:\n{ZONE2_MATRIX}")
    print(f"[INIT] Zone 3 Matrix:\n{ZONE3_MATRIX}")
    
    # --- CAM 2 ---
    # Placeholder for actual CAM2 Matrix computation if points were available
    # For now, it will load from AFFINE_FILE_CAM2 in the main execution block
    
    print(">>> [INIT] Affine Matrices Ready!")

def calculate_z_from_5_points(rx, ry, calibration_points, power=3.0):
    """
    Calculate Z-height using IDW interpolation from 5 calibration points
    """
    numerator_z = 0.0
    denominator = 0.0

    for p in calibration_points:
        # Use ref_x/ref_y for distance calculation (which are robot coordinates)
        dist = math.sqrt((rx - p['ref_x'])**2 + (ry - p['ref_y'])**2)
        
        if dist < 0.1:
            return p['true_z']
            
        weight = 1.0 / (dist ** power)
        numerator_z += (p['true_z'] * weight)
        denominator += weight
        
    if denominator == 0:
        # Fallback to average true_z
        true_z_values = [p['true_z'] for p in calibration_points if 'true_z' in p]
        if true_z_values:
            return sum(true_z_values) / len(true_z_values)
        return -20.0 # Safe default fallback

    return numerator_z / denominator

def pixel_to_robot_cam1(px, py, zone_id):
    """Transform pixel coordinates to robot XY using Affine Matrix."""
    if zone_id not in zone_matrices_cam1 or zone_matrices_cam1[zone_id] is None:
        print(f"[WARNING] No matrix for Cam1 Zone {zone_id}, returning raw coordinates")
        return float(px), float(py)

    pt = np.array([px, py, 1.0], dtype=np.float32)
    matrix = zone_matrices_cam1[zone_id]
    if matrix.shape != (2, 3):
         print(f"[ERROR] Cam1 Matrix for Zone {zone_id} has wrong shape: {matrix.shape}")
         return float(px), float(py)

    res = matrix.dot(pt)
    return float(res[0]), float(res[1])

def pixel_to_robot_cam2(px, py, zone_id):
    if zone_id not in zone_matrices_cam2 or zone_matrices_cam2[zone_id] is None:
        print(f"[WARNING] No matrix for Cam2 Zone {zone_id}, returning raw coordinates")
        return float(px), float(py)

    pt = np.array([px, py, 1.0], dtype=np.float32)
    matrix = zone_matrices_cam2[zone_id]
    if matrix.shape != (2, 3):
         print(f"[ERROR] Cam2 Matrix for Zone {zone_id} has wrong shape: {matrix.shape}")
         return float(px), float(py)
         
    res = matrix.dot(pt)
    return float(res[0]), float(res[1])

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

# ======================================================================================
# III. ROBOT CONTROL & PICK SEQUENCE
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

        # FIX R-AXIS ROTATION: Use R=0.0 for picking motions (Vertical alignment)
        R_PICK_ANGLE = 0.0
        
        # 1. Standby (MovJ) - Use the R value defined in the standby configuration
        client_move.MovJ(float(sb['x']), float(sb['y']), float(sb['z']), float(sb['r'])); client_move.Sync()
        
        # 2. Hover (MovJ) - Use the fixed R for vertical picking
        client_move.MovJ(rx, ry, z_hover, R_PICK_ANGLE); client_move.Sync()
        
        # 3. Pick (MovL) - ลงแนวดิ่ง - Use the fixed R for vertical picking
        client_move.MovL(rx, ry, z_pick, R_PICK_ANGLE); client_move.Sync()

        # 4. Suction
        control_suction('on')
        time.sleep(0.8)

        # 5. Check Sensor
        if check_suction_status():
            print(">>> SUCTION SUCCESS")
            web_data['status'] = "SUCTION SUCCESS"
            sequence_count += 1; total_picked += 1
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            save_to_database(sequence_count, tag_id, ts, zone_name, round(rx, 2), round(ry, 2))
            
            # ยกขึ้น (MovL) - Use the fixed R for vertical picking
            client_move.MovL(rx, ry, z_hover, R_PICK_ANGLE); client_move.Sync()
            # กลับ Standby (MovJ) - Use the R value defined in the standby configuration
            client_move.MovJ(float(sb['x']), float(sb['y']), float(sb['z']), float(sb['r'])); client_move.Sync()
            # Home
            client_move.JointMovJ(0.0, 0.0, 0.0, 200.0); client_move.Sync()
            set_light('green')
            is_robot_busy = False
            return True
        else:
            print(">>> SUCTION FAILED")
            web_data['status'] = "FAILED"
            control_suction('off')
            client_move.MovL(rx, ry, z_hover, R_PICK_ANGLE); client_move.Sync()
            set_light('red')
            is_robot_busy = False
            return False

    except Exception as e:
        print(f"[ERROR] Motion: {e}")
        is_robot_busy = False
        set_light('red')
        return False

# ======================================================================================
# IV. FLASK API SERVER
# ======================================================================================
app = Flask(__name__)
CORS(app)

# --- Robot Mode & Manual Control APIs ---
@app.route('/api/robot/mode', methods=['POST'])
def set_robot_mode():
    global ROBOT_MODE, web_data, tag_stability, locked_target_id, locked_target_id_cam2
    body = request.json or {}
    new_mode = body.get('mode')
    if new_mode in ['MANUAL', 'AUTO']:
        ROBOT_MODE = new_mode
        web_data['robot_mode'] = new_mode
        tag_stability = {}
        locked_target_id = None
        locked_target_id_cam2 = None
        return jsonify({"status": "success", "mode": new_mode})
    return jsonify({"status": "error"}), 400

@app.route('/api/robot/click_move', methods=['POST'])
def click_move():
    global is_connected
    if not is_connected: return jsonify({"status": "error", "message": "Not Connected"})
    if ROBOT_MODE == 'AUTO': return jsonify({"status": "error", "message": "Cannot click in AUTO mode"})

    cx, cy = request.json.get('x'), request.json.get('y')
    target_tag = None; min_dist = 50.0
    all_tags = current_visible_tags_cam1 + current_visible_tags_cam2
    
    for tag in all_tags:
        dist = get_distance(cx, cy, tag['cx'], tag['cy'])
        if dist < min_dist: min_dist = dist; target_tag = tag

    if not target_tag: return jsonify({"status": "error", "message": "No Tag"})
    zone_data = target_tag['zone']
    if not zone_data: return jsonify({"status": "error", "message": "Outside Zone"})

    tag_id = int(target_tag['id'])
    final_rx = target_tag['rx']
    final_ry = target_tag['ry']
    z_pick = target_tag['z_pick']
    z_hover = z_pick + 40.0
    
    # Load standby point from the zone config, ensure R is float
    sb = zone_data.get('standby', {"x": 250, "y": 0, "z": 100, "r": 0.0})
    
    # Check if 'r' is present and convert to float, otherwise default
    if 'r' not in sb:
        sb['r'] = 0.0
    else:
        try:
            sb['r'] = float(sb['r'])
        except ValueError:
            sb['r'] = 0.0


    print(f"[CLICK] Pixel:({cx:.1f},{cy:.1f}) -> Final:({final_rx:.1f},{final_ry:.1f}, Z:{z_pick:.1f})")
    threading.Thread(target=execute_pick_sequence, args=(final_rx, final_ry, z_pick, z_hover, sb, tag_id, zone_data['name'])).start()
    return jsonify({"status": "success", "message": "Command Sent"})

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

@app.route('/api/robot/position', methods=['GET'])
def get_robot_position():
    if not is_connected or client_feed is None: return jsonify({"status": "error"}), 400
    try:
        p = client_feed.GetPose() 
        numbers = re.findall(r'-?\d+\.?\d*', p)
        
        # The first number is usually the state (1.0 for success)
        if len(numbers) >= 4:
            # numbers[1]=X, numbers[2]=Y, numbers[3]=Z, numbers[4]=R
            return jsonify({
                "status": "success",
                "x": float(numbers[1]),
                "y": float(numbers[2]),
                "z": float(numbers[3]),
                "r": float(numbers[4]) if len(numbers) > 4 else 0.0
            })
        else:
            return jsonify({"status": "error", "message": f"Invalid pose response format: {p}"}), 500
    except Exception as e:
        print(f"[ERROR] GetPose: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/robot/move', methods=['POST'])
def move_robot():
    if not is_connected: return jsonify({"status": "error"})
    d = request.json or {}; m = d.get('mode')
    try:
        r_val = float(d.get('r', 0.0))
        
        if m == 'MovJ': client_move.MovJ(float(d['x']), float(d['y']), float(d['z']), r_val)
        elif m == 'MovL': client_move.MovL(float(d['x']), float(d['y']), float(d['z']), r_val)
        elif m == 'JointMovJ': client_move.JointMovJ(float(d['j1']), float(d['j2']), float(d['j3']), float(d['j4']))
        elif m == 'home': client_move.JointMovJ(0.0, 0.0, 0.0, 200.0)
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
        save_json(AFFINE_FILE_CAM1, data)
        return jsonify({"status": "saved"})
    return jsonify({"status": "error"}), 400
@app.route('/api/cam2/calibration/affine', methods=['GET', 'POST'])
def handle_affine_cam2():
    if request.method == 'GET': return jsonify(load_json(AFFINE_FILE_CAM2, {}))
    body = request.json or {}; zid = str(body.get('zone_id'))
    if zid:
        data = load_json(AFFINE_FILE_CAM2, {})
        data[zid] = body
        save_json(AFFINE_FILE_CAM2, data)
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
def sync_affine_1(zone_id): 
    global zone_matrices_cam1, zone_matrices_cam2
    load_affine_matrices(AFFINE_FILE_CAM1, zone_matrices_cam1)
    load_affine_matrices(AFFINE_FILE_CAM2, zone_matrices_cam2)
    return jsonify({"status":"synced"})

@app.route('/api/robot/sync_affine_cam2/<int:zone_id>', methods=['POST'])
def sync_affine_2(zone_id): 
    global zone_matrices_cam1, zone_matrices_cam2
    load_affine_matrices(AFFINE_FILE_CAM1, zone_matrices_cam1)
    load_affine_matrices(AFFINE_FILE_CAM2, zone_matrices_cam2)
    return jsonify({"status":"synced"})

@app.route('/api/calibration/auto_z_probe', methods=['POST'])
def auto_z_probe(): return jsonify({"status": "started", "msg": "Z-Probe Logic triggered"})
@app.route('/api/download_log')
def download_log():
    if os.path.exists(DB_FILE): return send_file(DB_FILE, as_attachment=True, download_name=f"log_{int(time.time())}.csv")
    return jsonify({"status": "error"}), 404

# ============================================================================
# AUTO 5-POINT CALIBRATION APIs
# ============================================================================
@app.route('/api/calibration/auto_detect_tags', methods=['POST'])
def auto_detect_tags():
    body = request.json or {}
    zone_id = int(body.get('zone_id', 1))
    camera = body.get('camera', 'cam1')

    print(f"[AUTO-DETECT] Zone {zone_id}, Camera: {camera}")
    
    if camera == 'cam1':
        with lock_cam1:
            frame = output_frame_cam1.copy() if output_frame_cam1 is not None else None
        zones = zones_config_cam1
    else:
        with lock_cam2:
            frame = output_frame_cam2.copy() if output_frame_cam2 is not None else None
        zones = zones_config_cam2

    if frame is None:
        return jsonify({"status": "error", "message": "No camera frame available"}), 400

    zone = next((z for z in zones if z['id'] == zone_id), None)
    if not zone:
        return jsonify({"status": "error", "message": f"Zone {zone_id} not found"}), 404

    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        at_detector = Detector(families="tag36h11")
        tags = at_detector.detect(gray)
        
        print(f"[AUTO-DETECT] Found {len(tags)} total tags in frame")
        
        result = {}
        found_ids = set()
        
        zone_x, zone_y, zone_w, zone_h = zone['x'], zone['y'], zone['w'], zone['h']
        
        # 1. Detect tags within the defined zone boundary
        for tag in tags:
            cx, cy = int(tag.center[0]), int(tag.center[1])
            tag_id = tag.tag_id

            if (zone_x < cx < zone_x + zone_w and 
                zone_y < cy < zone_y + zone_h):
                
                if tag_id in TAG_TO_POINT_NAME:
                    point_name = TAG_TO_POINT_NAME[tag_id]
                    result[point_name] = {
                        "name": point_name,
                        "tag_id": tag_id,
                        "cam_x": float(cx),
                        "cam_y": float(cy),
                        "robot_x": 0.0,
                        "robot_y": 0.0,
                        "robot_z": 0.0,
                    }
                    found_ids.add(tag_id)
                    print(f"[AUTO-DETECT] ✓ Found {point_name} (ID:{tag_id}) at ({cx}, {cy})")

        # 2. Check for missing required points (P1, P2, P3, P4, C)
        all_required_ids = set(TAG_TO_POINT_NAME.keys())
        missing_ids = all_required_ids - found_ids
        
        point_list = []
        for tag_id, name in TAG_TO_POINT_NAME.items():
            if name in result:
                point_list.append(result[name])
            else:
                # Add placeholder for missing tags
                point_list.append({
                    "name": name,
                    "tag_id": tag_id,
                    "cam_x": 0.0,
                    "cam_y": 0.0,
                    "robot_x": 0.0,
                    "robot_y": 0.0,
                    "robot_z": 0.0,
                })

        status = "success" if not missing_ids else "partial"
        
        return jsonify({
            "status": status,
            "points": point_list,
            "missing_tags": [TAG_TO_POINT_NAME[tid] for tid in missing_ids],
            "zone_info": {
                "id": zone['id'],
                "name": zone['name'],
                "x": zone_x,
                "y": zone_y,
                "w": zone_w,
                "h": zone_h
            }
        })

    except Exception as e:
        print(f"[AUTO-DETECT ERROR] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/calibration/save_5point', methods=['POST'])
def save_5point_calibration():
    global ZONE1_CALIBRATION_POINTS, ZONE2_CALIBRATION_POINTS, ZONE3_CALIBRATION_POINTS
    global zone_matrices_cam1, zone_matrices_cam2

    body = request.json or {}
    zone_id = int(body.get('zone_id'))
    camera = body.get('camera', 'cam1')
    points = body.get('points', [])

    print(f"[SAVE-5POINT] Zone {zone_id}, Camera: {camera}, Points: {len(points)}")

    if len(points) != 5:
        return jsonify({"status": "error", "message": "Need exactly 5 points"}), 400

    # 1. Validate Points and Prepare Affine Data
    required_names = {"P1", "P2", "P3", "P4", "C"}
    received_names = {p['name'] for p in points}
    if required_names != received_names:
        return jsonify({
            "status": "error", 
            "message": f"Invalid point names. Expected: {required_names}, Got: {received_names}"
        }), 400

    calibration_points = []
    src_points_affine = [] # Cam XY
    dst_points_affine = [] # Robot XY

    # Ensure data is processed in P1, P2, P3, P4, C order for matrix consistency
    point_map = {p['name']: p for p in points}
    
    # We must iterate over the required names to maintain order for cv2.estimateAffine2D
    for name in TAG_TO_POINT_NAME.values():
        p = point_map.get(name)
        if p is None:
             return jsonify({"status": "error", "message": f"Missing point data during final save for: {name}"}), 400

        try:
            calib_data = {
                "name": p['name'],
                "tag_id": int(p['tag_id']),
                "ref_x": float(p['robot_x']),
                "ref_y": float(p['robot_y']),
                "true_x": float(p['robot_x']),
                "true_y": float(p['robot_y']),
                "true_z": float(p['robot_z']),
                "cam_x": float(p['cam_x']),
                "cam_y": float(p['cam_y'])
            }
            calibration_points.append(calib_data)
            
            src_points_affine.append([calib_data['cam_x'], calib_data['cam_y']])
            dst_points_affine.append([calib_data['ref_x'], calib_data['ref_y']])

        except ValueError as e:
            return jsonify({"status": "error", "message": f"Invalid numeric data for point {name}: {e}"}), 400

    # 2. Compute NEW Affine Matrix
    src = np.float32(src_points_affine)
    dst = np.float32(dst_points_affine)
    
    matrix, _ = cv2.estimateAffine2D(src, dst)
    
    if matrix is None:
        return jsonify({"status": "error", "message": "Failed to compute Affine Matrix (Data Collinear/Invalid)"}), 500

    # Extract parameters
    params = {
        "a": float(matrix[0, 0]), "b": float(matrix[0, 1]), "c": float(matrix[0, 2]),
        "d": float(matrix[1, 0]), "e": float(matrix[1, 1]), "f": float(matrix[1, 2])
    }
    
    # 3. Save 5-Point Data and Affine Matrix
    file_path_5point = CALIBRATION_5POINT_FILE_CAM1 if camera == 'cam1' else CALIBRATION_5POINT_FILE_CAM2
    file_path_affine = AFFINE_FILE_CAM1 if camera == 'cam1' else AFFINE_FILE_CAM2
    
    # --- Save 5-Point Data ---
    data_5point = load_json(file_path_5point, {})
    zone_key = f"zone_{zone_id}"
    data_5point[zone_key] = {
        "last_calibrated": datetime.datetime.now().isoformat(),
        "idw_power": 3.0,
        "points": calibration_points
    }
    save_json(file_path_5point, data_5point)
    
    # --- Save Affine Matrix (for direct loading later) ---
    data_affine = load_json(file_path_affine, {})
    data_affine[str(zone_id)] = {
        "params": params,
        "residual": 0.0, # Placeholder
        "timestamp": datetime.datetime.now().isoformat()
    }
    save_json(file_path_affine, data_affine)


    # 4. Apply to Runtime
    applied_to_runtime = False
    if camera == 'cam1':
        if zone_id == 1: ZONE1_CALIBRATION_POINTS = calibration_points
        elif zone_id == 2: ZONE2_CALIBRATION_POINTS = calibration_points
        elif zone_id == 3: ZONE3_CALIBRATION_POINTS = calibration_points
        zone_matrices_cam1[zone_id] = matrix
        applied_to_runtime = True
    else: # cam2
        zone_matrices_cam2[zone_id] = matrix
        applied_to_runtime = True


    print(f"[SAVE-5POINT] ✓ Saved and Matrix Applied (Zone {zone_id}, Cam {camera})")
    
    return jsonify({
        "status": "success",
        "message": f"Zone {zone_id} calibration saved and applied successfully.",
        "applied_to_runtime": applied_to_runtime,
        "params": params
    })

@app.route('/api/calibration/get_5point/<int:zone_id>/<camera>', methods=['GET'])
def get_5point_calibration(zone_id, camera):
    print(f"[GET-5POINT] Zone {zone_id}, Camera: {camera}")

    if camera == 'cam1':
        file_path = CALIBRATION_5POINT_FILE_CAM1
    else:
        file_path = CALIBRATION_5POINT_FILE_CAM2

    calibrations = load_json(file_path, {})
    zone_key = f"zone_{zone_id}"
    
    if zone_key in calibrations:
        return jsonify({
            "status": "success",
            "zone_id": zone_id,
            "camera": camera,
            "data": calibrations[zone_key]
        })
    else:
        return jsonify({
            "status": "not_found",
            "zone_id": zone_id,
            "camera": camera,
            "message": "No calibration data found for this zone"
        }), 404

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

# --- General Utility APIs ---
@app.route('/api/robot/sync_affine/<int:zone_id>', methods=['POST'])
def sync_affine_1(zone_id): 
    global zone_matrices_cam1, zone_matrices_cam2
    # Ensure matrices are reloaded into runtime from files
    load_affine_matrices(AFFINE_FILE_CAM1, zone_matrices_cam1)
    load_affine_matrices(AFFINE_FILE_CAM2, zone_matrices_cam2)
    return jsonify({"status":"synced"})

@app.route('/api/robot/sync_affine_cam2/<int:zone_id>', methods=['POST'])
def sync_affine_2(zone_id): 
    global zone_matrices_cam1, zone_matrices_cam2
    load_affine_matrices(AFFINE_FILE_CAM1, zone_matrices_cam1)
    load_affine_matrices(AFFINE_FILE_CAM2, zone_matrices_cam2)
    return jsonify({"status":"synced"})

@app.route('/api/calibration/auto_z_probe', methods=['POST'])
def auto_z_probe(): return jsonify({"status": "started", "msg": "Z-Probe Logic triggered"})
@app.route('/api/download_log')
def download_log():
    if os.path.exists(DB_FILE): return send_file(DB_FILE, as_attachment=True, download_name=f"log_{int(time.time())}.csv")
    return jsonify({"status": "error"}), 404

@app.route("/data")
def data_stream():
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
# V. VISION LOOPS
# ======================================================================================

def vision_loop_cam1():
    """ CAM 1: Zone 1, 2, 3 with Anti-Flicker """
    global output_frame_cam1, web_data, current_visible_tags_cam1, locked_target_id
    global processed_tags, tag_stability

    cap = cv2.VideoCapture(RTSP_URL_CAM1)
    at_detector = Detector(families="tag36h11")
    print(">>> CAM1: STARTED (Top View) <<<")
    
    tag_history = {}
    HISTORY_SIZE = 5

    while True:
        try:
            ret, frame = cap.read()
            if not ret: 
                time.sleep(2)
                cap.release()
                cap = cv2.VideoCapture(RTSP_URL_CAM1)
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            tags = at_detector.detect(gray)
            current_visible_tags_cam1 = []
            status_text = web_data['status']
            current_time = time.time()
            
            newly_detected_tags = {}
            closest_tag_id = None
            min_dist_to_center = float('inf')
            visible_ids = set() # Track visible IDs this frame

            # Draw Zones
            for z in zones_config_cam1:
                color = hex_to_bgr(z['color'])
                cv2.rectangle(frame, (z['x'], z['y']), (z['x']+z['w'], z['y']+z['h']), color, 2)
                cv2.putText(frame, z['name'], (z['x'], z['y']-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            for tag in tags:
                cx, cy = int(tag.center[0]), int(tag.center[1])
                zone = check_zone_cam1(cx, cy)
                tag_id = tag.tag_id
                visible_ids.add(tag_id)
                
                if not zone:
                    cv2.polylines(frame, [tag.corners.astype(int)], True, (0, 0, 255), 2)
                    continue
                
                zone_id = int(zone['id'])
                
                # --- Anti-Flicker: Average position from history ---
                if tag_id not in tag_history:
                    tag_history[tag_id] = []
                
                tag_history[tag_id].append((cx, cy, current_time))
                tag_history[tag_id] = tag_history[tag_id][-HISTORY_SIZE:]
                
                recent_positions = tag_history[tag_id]
                if recent_positions:
                    avg_cx = sum(p[0] for p in recent_positions) / len(recent_positions)
                    avg_cy = sum(p[1] for p in recent_positions) / len(recent_positions)
                else:
                    avg_cx, avg_cy = cx, cy
                
                # 1. FIXED: Single-pass transformation (XY)
                rx, ry = pixel_to_robot_cam1(avg_cx, avg_cy, zone_id)
                
                # 2. Calculate Z using IDW
                if zone_id == 1:
                    z_calib_points = ZONE1_CALIBRATION_POINTS
                elif zone_id == 2:
                    z_calib_points = ZONE2_CALIBRATION_POINTS
                elif zone_id == 3:
                    z_calib_points = ZONE3_CALIBRATION_POINTS
                else:
                    z_calib_points = []
                
                z_interpolated = calculate_z_from_5_points(rx, ry, z_calib_points)
                z_pick = z_interpolated - OBJECT_HEIGHT # Final Z = interpolated Z - object height
                
                tag_data = {
                    "id": tag_id,
                    "cx": int(avg_cx),
                    "cy": int(avg_cy),
                    "rx": rx,
                    "ry": ry,
                    "z_pick": z_pick,
                    "zone": zone,
                    "cam": 1
                }
                
                newly_detected_tags[tag_id] = tag_data
                
                # Track closest
                dist = get_distance(avg_cx, avg_cy, frame.shape[1]/2, frame.shape[0]/2)
                if dist < min_dist_to_center:
                    min_dist_to_center = dist
                    closest_tag_id = tag_id
                
                # --- Drawing with Stability Indicator ---
                if tag_id not in tag_stability:
                    tag_stability[tag_id] = current_time
                
                time_elapsed = current_time - tag_stability[tag_id]
                remaining_delay = max(0.0, AUTO_PICK_DELAY - time_elapsed)
                
                if remaining_delay > 0:
                    color = hex_to_bgr("#ffff00")
                    cv2.polylines(frame, [tag.corners.astype(int)], True, color, 2)
                    cv2.putText(frame, f"WAIT {remaining_delay:.1f}s", (int(avg_cx) - 10, int(avg_cy) + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                else:
                    color = hex_to_bgr("#00ff00")
                    cv2.polylines(frame, [tag.corners.astype(int)], True, color, 2)
                    cv2.putText(frame, "READY", (int(avg_cx) - 10, int(avg_cy) + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                
                # Show coordinates (Rob R value forced to 0.0)
                cv2.putText(frame, f"ID:{tag_id} R:({rx:.0f},{ry:.0f}, 0)",
                            (int(avg_cx) - 30, int(avg_cy) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

            # --- Cleanup old history ---
            for tid in list(tag_history.keys()):
                # If tag disappeared completely from the frame, remove from history
                if tid not in visible_ids:
                    del tag_history[tid]
            
            # --- Target Locking Logic ---
            target_data = None
            if locked_target_id in newly_detected_tags:
                target_data = newly_detected_tags[locked_target_id]
            else:
                locked_target_id = None
                if closest_tag_id is not None:
                    locked_target_id = closest_tag_id
                    target_data = newly_detected_tags[closest_tag_id]
            
            if target_data:
                tag_id = target_data['id']
                web_data['target_x'] = round(target_data['rx'], 2)
                web_data['target_y'] = round(target_data['ry'], 2)
                
                time_elapsed = current_time - tag_stability.get(tag_id, current_time)

                if ROBOT_MODE == 'AUTO' and not is_robot_busy and is_connected:
                    if time_elapsed < AUTO_PICK_DELAY:
                        status_text = "DETECTED (WAITING)" 
                    else:
                        status_text = "DETECTED (READY)"
                        if current_time - processed_tags.get(tag_id, 0) > 10.0:
                            processed_tags[tag_id] = current_time
                            z_pick = target_data['z_pick']
                            zone = target_data['zone']
                            rx = target_data['rx']
                            ry = target_data['ry']
                            z_hover = z_pick + 40.0
                            sb = zone.get('standby', {"x": 250, "y": 0, "z": 100, "r": 0})
                            
                            threading.Thread(target=execute_pick_sequence, args=(rx, ry, z_pick, z_hover, sb, tag_id, zone['name'])).start()
                
                elif not is_robot_busy:
                    status_text = f"DETECTED (MANUAL)" 
            
            elif not is_robot_busy:
                status_text = "IDLE"
                web_data['target_x'] = 0.0
                web_data['target_y'] = 0.0
            
            # Cleanup stability dictionary (only based on visible_ids)
            for tid in list(tag_stability.keys()):
                if tid not in visible_ids: 
                    del tag_stability[tid]
            
            if locked_target_id is not None and locked_target_id not in visible_ids:
                locked_target_id = None

            current_visible_tags_cam1 = list(newly_detected_tags.values())

            web_data.update({
                "x": 0, "y": 0, "stack_h": current_stack,
                "total_picked": total_picked,
                "history": history_log,
                "cam2_enabled": CAM2_ENABLED,
                "robot_mode": ROBOT_MODE
            })
            if not is_robot_busy: web_data["status"] = status_text

            with lock_cam1: output_frame_cam1 = frame.copy()
            
        except Exception as e:
            print(f"[ERROR CAM1 VISION LOOP] {e}")
            time.sleep(0.1)

    cap.release()

def vision_loop_cam2():
    """ CAM 2: Zone 1 (if needed) """
    global output_frame_cam2, current_visible_tags_cam2, locked_target_id_cam2
    global processed_tags, tag_stability
    
    cap = cv2.VideoCapture(RTSP_URL_CAM2)
    at_detector = Detector(families="tag36h11")
    print(">>> CAM2: STARTED (Side View) <<<")
    
    while True:
        try:
            ret, frame = cap.read()
            if not ret: 
                time.sleep(2)
                cap = cv2.VideoCapture(RTSP_URL_CAM2)
                continue
            
            current_visible_tags_cam2 = []
            current_time = time.time()
            
            newly_detected_tags = {}
            closest_tag_id = None
            min_dist_to_center = float('inf')
            visible_ids = set()

            # Draw Zones 
            for z in zones_config_cam2:
                color = hex_to_bgr(z['color']) 
                cv2.rectangle(frame, (z['x'], z['y']), (z['x']+z['w'], z['y']+z['h']), color, 2)
                cv2.putText(frame, z['name'], (z['x'], z['y']-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            if CAM2_ENABLED:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                tags = at_detector.detect(gray)
                
                for tag in tags:
                    cx, cy = int(tag.center[0]), int(tag.center[1]); zone = check_zone_cam2(cx, cy); visible_ids.add(tag.tag_id)
                    
                    if zone:
                        # --- Simplified logic for CAM2: XY only (needs Z from main logic later) ---
                        zone_id = int(zone['id'])
                        rx, ry = pixel_to_robot_cam2(cx, cy, zone_id)
                        
                        tag_data = {
                            "id": tag.tag_id, "cx": cx, "cy": cy, "rx": rx, "ry": ry, 
                            "z_pick": -20.0, "zone": zone, "cam": 2 # Z is fallback/placeholder here
                        }
                        newly_detected_tags[tag.tag_id] = tag_data

                        # Track closest tag for potential new lock
                        dist = get_distance(cx, cy, frame.shape[1]/2, frame.shape[0]/2)
                        if dist < min_dist_to_center:
                            min_dist_to_center = dist
                            closest_tag_id = tag.tag_id
                            
                        # --- Drawing Logic with Stability Indicator ---
                        if tag.tag_id not in tag_stability:
                            tag_stability[tag.tag_id] = current_time
                        
                        time_elapsed = current_time - tag_stability[tag.tag_id]
                        remaining_delay = max(0.0, AUTO_PICK_DELAY - time_elapsed)

                        if remaining_delay > 0:
                            color = hex_to_bgr("#ffff00")
                            cv2.polylines(frame, [tag.corners.astype(int)], True, color, 2)
                            cv2.putText(frame, f"WAIT {remaining_delay:.1f}s", (cx - 10, cy + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                        else:
                            color = hex_to_bgr("#00ff00")
                            cv2.polylines(frame, [tag.corners.astype(int)], True, color, 2)
                            cv2.putText(frame, "READY", (cx - 10, cy + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    
                    else:
                         cv2.polylines(frame, [tag.corners.astype(int)], True, hex_to_bgr(zone['color']), 2)
            
            # --- Target Locking Logic (Cam2 handles lock only if Cam1 is free) ---
            target_data = None
            if locked_target_id is None: 
                if locked_target_id_cam2 in newly_detected_tags:
                    target_data = newly_detected_tags[locked_target_id_cam2]
                else:
                    locked_target_id_cam2 = None
                    if closest_tag_id is not None:
                        locked_target_id_cam2 = closest_tag_id
                        target_data = newly_detected_tags[closest_tag_id]
                
                if target_data and not is_robot_busy:
                    # Update web_data with Cam2's target (Cam2 currently doesn't trigger auto pick)
                    web_data['target_x'] = round(target_data['rx'], 2)
                    web_data['target_y'] = round(target_data['ry'], 2)
                    web_data['status'] = f"DETECTED (MANUAL, CAM2)"
            
            # Cleanup stability dictionary
            for tid in list(tag_stability.keys()):
                if tid not in visible_ids: 
                    del tag_stability[tid]
            
            if locked_target_id_cam2 is not None and locked_target_id_cam2 not in visible_ids:
                locked_target_id_cam2 = None

            current_visible_tags_cam2 = list(newly_detected_tags.values())

            with lock_cam2: output_frame_cam2 = frame.copy()

        except Exception as e:
            print(f"[ERROR CAM2 VISION LOOP] {e}")
            time.sleep(0.1)

    cap.release()

# --- Video Stream Generators ---
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

# ======================================================================================
# VI. MAIN EXECUTION
# ======================================================================================
if __name__ == "__main__":
    setup_gpio()
    load_5point_calibrations()
    # Compute initial affine matrices based on hardcoded/loaded defaults
    # This must be done AFTER loading 5-point data if that data affects the matrix calculation logic (which it doesn't in the current file structure)
    compute_initial_affine_matrices()
    
    t1 = threading.Thread(target=vision_loop_cam1); t1.daemon = True; t1.start()
    t2 = threading.Thread(target=vision_loop_cam2); t2.daemon = True; t2.start()
    
    print("--- ROBOT SERVER READY (R-AXIS FIXED) ---")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)