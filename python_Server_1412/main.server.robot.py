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
# 1. CALIBRATION CONFIG (Simplified Defaults)
# -------------------------------------------------------------------------
FIXED_OBJECT_HEIGHT = 20.0 
Z_PICK_OFFSET = 60.0  # Tool length offset (SUCTION_CUP_LENGTH)

# --- Default 5-Point Z Data (Retained for Zone 2 IDW logic) ---
ZONE2_CALIBRATION_POINTS = [
    # P1: Top-Left (CAM PIXEL REF) -> (ROBOT REF)
    {"ref_x": -25.9, "ref_y": 363.1, "true_x": 125.44, "true_y": 174.76, "true_z": -58.90},
    # P2: Top-Right
    {"ref_x": 159.0, "ref_y": 364.3, "true_x": 127.32, "true_y": 316.01, "true_z": -63.89},
    # P3: Bottom-Left
    {"ref_x": -28.0, "ref_y": 463.8, "true_x": 204.06, "true_y": 174.96, "true_z": -62.24},
    # P4: Bottom-Right
    {"ref_x": 156.0, "ref_y": 467.0, "true_x": 207.25, "true_y": 317.78, "true_z": -68.08},
    # C: Center
    {"ref_x": 64.0, "ref_y": 419.4, "true_x": 170.17, "true_y": 245.72, "true_z": -63.56}
]

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

# --- State Variables (Global Initialization) ---
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

zone_matrices_cam1 = {}
zone_matrices_cam2 = {}

# ✨ FIXED: Global initialization for zones and overrides to prevent NameError
zones_config_cam1 = [] 
zones_config_cam2 = []
zone_overrides = {}


# ======================================================================================
# II. UTILITY & CALIBRATION FUNCTIONS
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

# --- Affine Matrix Loading ---
def load_affine_matrices(file_path, target_dict):
    """Loads affine matrix parameters from JSON file into numpy matrix structure."""
    data = load_json(file_path, {})
    if isinstance(data, dict):
        for zid_str, rec in data.items():
            try:
                p = rec.get("params")
                if p:
                    mtx = np.array([[float(p["a"]), float(p["b"]), float(p["c"])],
                                    [float(p["d"]), float(p["e"]), float(p["f"])]], dtype=np.float32)
                    target_dict[int(zid_str)] = mtx
            except Exception: 
                pass

# --- Z Calculation Logic (For Zone 2 IDW) ---
def calculate_correction_from_5_points(current_x, current_y):
    """(Used only for Zone 2 in this old version) IDW Z-interpolation logic."""
    points = ZONE2_CALIBRATION_POINTS
    numerator_z = 0.0; denominator = 0.0
    power = 3.0

    for p in points:
        dist = math.sqrt((current_x - p['ref_x'])**2 + (current_y - p['ref_y'])**2)
        
        if dist < 0.1: return p['true_x'], p['true_y'], p['true_z']
        
        weight = 1.0 / (dist ** power)
        
        offset_x = p['true_x'] - p['ref_x']
        offset_y = p['true_y'] - p['ref_y']
        
        numerator_z += (p['true_z'] * weight)
        denominator += weight

    if denominator == 0: return current_x, current_y, -37.0 

    final_z = numerator_z / denominator
    
    return current_x, current_y, final_z


# --- Coordinate Transformation ---
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
    # Uses global zone_overrides defined above
    try: return float(zone_overrides.get(str(zone_id), {}).get(str(tag_id), 0.0))
    except: return 0.0

def check_zone_cam1(cx, cy):
    # Uses global zones_config_cam1 loaded at runtime
    for zone in zones_config_cam1:
        if zone['x'] < cx < zone['x'] + zone['w'] and zone['y'] < cy < zone['y'] + zone['h']:
            return zone
    return None

def check_zone_cam2(cx, cy):
    # Uses global zones_config_cam2 loaded at runtime
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
        
# --------------------------------------------------------------------------------------
# STANDALONE SUCTION TEST FUNCTION (FOR TESTING DI)
# --------------------------------------------------------------------------------------

def test_suction_and_stop():
    """
    Test routine: Turns suction on, waits for the sensor input (suction detected), 
    and turns suction off immediately upon detection or after a timeout.
    """
    global is_robot_busy
    
    if not is_connected:
        print("[TEST] Robot is not connected.")
        return {"status": "error", "message": "Robot is not connected."}

    try:
        is_robot_busy = True
        set_light('yellow')
        print("\n=============================================")
        print("[TEST START] Initiating suction test...")
        
        control_suction('on')
        time.sleep(0.3) 
        
        max_wait_time = 3.0
        start_time = time.time()
        contact_detected = False
        
        print(f"[STEP 2] Monitoring Suction Sensor (DI Pin {SUCTION_SENSOR_PIN}) for contact (Max {max_wait_time}s)...")
        
        while time.time() - start_time < max_wait_time:
            if check_suction_status():
                contact_detected = True
                print(f"!!! SUCCESS !!! Contact/Suction DETECTED after {time.time() - start_time:.2f}s. Stopping suction.")
                break
            
            time.sleep(0.05) 

        control_suction('off')
        
        if contact_detected:
            set_light('green')
            return {"status": "success", "message": "Suction detected and stopped."}
        else:
            set_light('red')
            print(f"!!! FAILURE !!! Test TIMEOUT after {max_wait_time:.2f}s. No contact detected.")
            return {"status": "failure", "message": "Suction timeout or sensor failed."}

    except Exception as e:
        print(f"[CRITICAL ERROR] Test failed unexpectedly: {e}")
        control_suction('off') # Ensure suction is off on error
        set_light('red')
        return {"status": "error", "message": str(e)}
    finally:
        is_robot_busy = False
        print("=============================================")


# ======================================================================================
# V. FLASK API SERVER
# ======================================================================================
app = Flask(__name__)
CORS(app)

# --- NEW API: Suction Test Endpoint ---
@app.route('/api/test/suction', methods=['POST'])
def api_test_suction():
    global is_robot_busy
    if is_robot_busy:
        return jsonify({"status": "busy", "message": "Robot is busy with another task."}), 423
    
    # Run the test function in a separate thread to avoid blocking the main server thread
    def thread_target():
        result = test_suction_and_stop()
        print(f"[TEST RESULT] {result['message']}")
    
    threading.Thread(target=thread_target).start()
    
    return jsonify({"status": "started", "message": "Suction test sequence initiated in background."})


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
        
        if len(numbers) >= 4:
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
                            
                            z_pick = target_data['z_pick']
                            zone = target_data['zone']
                            rx = target_data['rx']
                            ry = target_data['ry']
                            
                            z_hover = z_pick + 40.0
                            sb = zone.get('standby', {"x": 250, "y": 0, "z": 100, "r": 0})
                            
                            threading.Thread(target=execute_pick_sequence, 
                                             args=(rx, ry, z_pick, z_hover, sb, tag_id, zone['name'])).start()
                
                elif not is_robot_busy:
                    status_text = f"DETECTED (MANUAL)" 
            
            elif not is_robot_busy:
                status_text = "IDLE"
                web_data['target_x'] = 0.0
                web_data['target_y'] = 0.0
            
            
            # Cleanup stability dictionary
            for tid in list(tag_stability.keys()):
                if tid not in newly_detected_tags: # Tag is no longer visible
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
    """ CAM 2: รับผิดชอบ Zone 1 (ใช้ Affine) """
    global output_frame_cam2, current_visible_tags_cam2, locked_target_id_cam2
    global processed_tags, tag_stability
    
    cap = cv2.VideoCapture(RTSP_URL_CAM2)
    at_detector = Detector(families="tag36h11")
    print(">>> CAM2: STARTED (Side View) <<<")
    
    while True:
        try:
            ret, frame = cap.read()
            if not ret: time.sleep(2); cap = cv2.VideoCapture(RTSP_URL_CAM2); continue
            
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
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY); tags = at_detector.detect(gray)
                
                for tag in tags:
                    cx, cy = int(tag.center[0]), int(tag.center[1]); zone = check_zone_cam2(cx, cy); visible_ids.add(tag.tag_id)
                    
                    rx, ry, z_pick = 0.0, 0.0, 0.0
                    is_processed = False

                    if zone:
                        zone_id = int(zone['id'])
                        
                        # 1. Calculate Robot Coordinates
                        if zone_id == 1:
                            # Zone 1 (กลางภาพ Cam 2) -> ใช้ Affine ปกติ
                            rx, ry = pixel_to_robot_cam2(cx, cy, zone_id)
                            z_base = float(zone.get('z', 0.0))
                            z_off = get_zone_tag_offset(zone_id, tag.tag_id)
                            z_pick = z_base + FIXED_OBJECT_HEIGHT + z_off - Z_PICK_OFFSET
                            is_processed = True
                        
                        if is_processed:
                            tag_data = {
                                "id": tag.tag_id, "cx": cx, "cy": cy, "rx": rx, "ry": ry, 
                                "z_pick": z_pick, "zone": zone, "cam": 2
                            }
                            newly_detected_tags[tag.tag_id] = tag_data

                            # Track closest tag for potential new lock
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
                        
                        # Draw Zone 2, 3 detected by Cam 2 as low priority 
                        elif zone_id == 2 or zone_id == 3:
                            cv2.polylines(frame, [tag.corners.astype(int)], True, hex_to_bgr(zone['color']), 2)
                    
            
            # --- Target Locking Logic ---
            target_data = None
            
            if locked_target_id is None: # Only process if Cam1 hasn't locked onto a target yet
                
                if locked_target_id_cam2 in newly_detected_tags:
                    target_data = newly_detected_tags[locked_target_id_cam2]
                
                else:
                    locked_target_id_cam2 = None
                    if closest_tag_id is not None:
                        locked_target_id_cam2 = closest_tag_id
                        target_data = newly_detected_tags[closest_tag_id]
                
                if target_data and not is_robot_busy:
                    tag_id = target_data['id']
                    # Update web_data with the stable target position
                    web_data['target_x'] = round(target_data['rx'], 2)
                    web_data['target_y'] = round(target_data['ry'], 2)

                    # 2. Delay Logic (5 seconds)
                    if tag_id not in tag_stability:
                        tag_stability[tag_id] = current_time # First seen time
                    
                    time_elapsed = current_time - tag_stability[tag_id]

                    if ROBOT_MODE == 'AUTO' and not is_robot_busy and is_connected:
                        
                        if time_elapsed < AUTO_PICK_DELAY:
                            web_data['status'] = "DETECTED (WAITING)"
                        else:
                            web_data['status'] = "DETECTED (READY)"
                             # Execute pick sequence after delay
                            if current_time - processed_tags.get(tag_id, 0) > 10.0:
                                processed_tags[tag_id] = current_time
                                
                                z_pick = target_data['z_pick']
                                zone = target_data['zone']
                                rx = target_data['rx']
                                ry = target_data['ry']
                                
                                z_hover = z_pick + 40.0
                                sb = zone.get('standby', {"x": 250, "y": 0, "z": 100, "r": 0})
                                
                                threading.Thread(target=execute_pick_sequence, 
                                                 args=(rx, ry, z_pick, z_hover, sb, tag_id, zone['name'])).start()
                    
                    elif not is_robot_busy:
                        web_data['status'] = f"DETECTED (MANUAL)"
                        
                # Cleanup stability dictionary
                for tid in list(tag_stability.keys()):
                    if tid not in visible_ids: 
                        del tag_stability[tid]
                
                if locked_target_id_cam2 is not None and locked_target_id_cam2 not in visible_ids:
                    locked_target_id_cam2 = None

            elif locked_target_id is not None:
                 # If Cam1 has locked the target, Cam2 should not interfere with target position
                 pass
            else:
                # If no target is locked by either camera and not busy
                if not is_robot_busy:
                    web_data['status'] = "IDLE"
                    web_data['target_x'] = 0.0
                    web_data['target_y'] = 0.0
                
            
            # Update current_visible_tags_cam2 (used for /data API)
            current_visible_tags_cam2 = list(newly_detected_tags.values())


            with lock_cam2: output_frame_cam2 = frame.copy()
            
        except Exception as e:
            # [FIXED] Catch exceptions in loop to prevent thread crash
            print(f"[ERROR CAM2 VISION LOOP] {e}")
            time.sleep(0.1) # Prevent CPU hogging if a persistent error occurs in one frame
            # Continue the loop

    cap.release()


def gen_frames_cam1():
    # [FIXED] Corrected MIME boundary string
    while True:
        try:
            with lock_cam1:
                if output_frame_cam1 is None: time.sleep(0.1); continue
                _, img = cv2.imencode(".jpg", output_frame_cam1)
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(img) + b'\r\n')
        except Exception:
            time.sleep(0.1)

def gen_frames_cam2():
    # [FIXED] Corrected MIME boundary string
    while True:
        try:
            with lock_cam2:
                if output_frame_cam2 is None: time.sleep(0.1); continue
                _, img = cv2.imencode(".jpg", output_frame_cam2)
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(img) + b'\r\n')
        except Exception:
            time.sleep(0.1)

if __name__ == "__main__":
    setup_gpio()
    
    # Initialize default zones for both cameras with the new standby points
    default_zones_with_standby = [
        {"id": 1, "name": "Zone 1", "x": 50, "y": 50, "w": 250, "h": 200, "z": 150.0, "color": "#00ff00", "standby": {"x": 314.40, "y": 141.74, "z": 115.12, "r": 255.29}},
        {"id": 2, "name": "Zone 2", "x": 580, "y": 150, "w": 200, "h": 200, "z": -37.0, "color": "#ffff00", "standby": {"x": 172.41, "y": 249.71, "z": 124.88, "r": 286.40}},
        {"id": 3, "name": "Zone 3", "x": 450, "y": 50, "w": 150, "h": 150, "z": 50.0, "color": "#ff0000", "standby": {"x": 5.36, "y": 269.29, "z": 68.41, "r": 324.87}}
    ]
    
    # Save defaults to JSON files if they don't exist, otherwise load current config
    # Pylance fix: Load/Assign values after 'global' declaration
    zones_config_cam1 = load_json(ZONE_FILE_CAM1, default_zones_with_standby)
    zones_config_cam2 = load_json(ZONE_FILE_CAM2, default_zones_with_standby)
    zone_overrides = load_json(ZONE_OVERRIDES_FILE, {}) # Load overrides here
    
    load_affine_matrices(AFFINE_FILE_CAM1, zone_matrices_cam1)
    load_affine_matrices(AFFINE_FILE_CAM2, zone_matrices_cam2)

    t1 = threading.Thread(target=vision_loop_cam1); t1.daemon = True; t1.start()
    t2 = threading.Thread(target=vision_loop_cam2); t2.daemon = True; t2.start()
    print("--- ROBOT SERVER READY (FIXED) ---")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)