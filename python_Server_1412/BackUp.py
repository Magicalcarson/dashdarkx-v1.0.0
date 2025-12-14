# main.server.robot.py
# Final Complete: Auto Mode + Real-time Target Sync + Green Status

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

# Import Dobot API
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
# 1. CONFIGURATION & GLOBAL VARIABLES
# ======================================================================================

# --- Camera Settings ---
RTSP_URL_CAM1 = "rtsp://admin:OokamiMio-2549@192.168.1.124/stream1" # Top View
RTSP_URL_CAM2 = "rtsp://admin:OokamiMio-2549@192.168.1.109/stream1" # Side View

# --- GPIO Settings ---
SUCTION_SENSOR_PIN = 33  

# --- File Paths ---
DB_FILE = "robot_history_log.csv"
ZONE_FILE_CAM1 = "zones_config_cam1.json"
ZONE_FILE_CAM2 = "zones_config_cam2.json"
AFFINE_FILE_CAM1 = "affine_params_cam1.json"
AFFINE_FILE_CAM2 = "affine_params_cam2.json"
ZONE_OVERRIDES_FILE = "zone_overrides.json"
AUTO_CAL_FILE = "auto_z_calibration.json"

# --- Object Data ---
OBJECT_INFO = {
    0: {'name': 'Thin Plate',   'height': 5.0},
    1: {'name': 'Small Box',    'height': 15.0},
    2: {'name': 'Medium Box',   'height': 25.0},
    3: {'name': 'Large Box',    'height': 35.0},
    4: {'name': 'Extra Large',  'height': 50.0},
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
    "x": 0.0, 
    "y": 0.0, 
    "stack_h": 0.0,
    "total_picked": 0, 
    "cycle_time": 0.0,
    "status": "IDLE", 
    "history": [], 
    "active_id": "-",  # [FIX] จะถูกอัปเดตเมื่อเจอ Tag
    "object_counts": {0: 0, 1: 0, 2: 0, 3: 0, 4: 0},
    "tags": [],           
    "cam2_enabled": True,
    "robot_mode": "MANUAL",
    "target_x": 0.0, # [FIX] ส่งค่า XY เป้าหมายขึ้นเว็บ
    "target_y": 0.0
}

# --- Logic Variables ---
history_log = []
sequence_count = 0
current_stack = 0.0
total_picked = 0
last_process_time = time.time()

# --- Vision State ---
current_visible_tags_cam1 = [] 
current_visible_tags_cam2 = []
processed_tags = {}   
tag_stability = {}    

# --- Frame Buffers ---
output_frame_cam1 = None
lock_cam1 = threading.Lock()

output_frame_cam2 = None
lock_cam2 = threading.Lock()

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
    """บันทึกข้อมูลลง CSV และอัปเดต History Log"""
    global history_log
    try:
        with open(DB_FILE, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([seq, tag_id, timestamp, "Success", zone_name, rx, ry])
        
        history_log.insert(0, {
            "seq": seq, 
            "id": tag_id, 
            "time": timestamp, 
            "status": "Success", 
            "zone": zone_name
        })
        if len(history_log) > 50: history_log.pop()
        
        web_data['history'] = history_log
        print(f"[DB] Saved Record #{seq}")
        
    except Exception as e:
        print(f"[DB Error] {e}")

# ======================================================================================
# 3. COORDINATE SYSTEM
# ======================================================================================

default_zones = [
    {"id": 1, "name": "Zone 1", "x": 50, "y": 50, "w": 150, "h": 150, "z": 0.0, "color": "#00ff00"},
    {"id": 2, "name": "Zone 2", "x": 250, "y": 50, "w": 150, "h": 150, "z": 0.0, "color": "#ffff00"},
    {"id": 3, "name": "Zone 3", "x": 450, "y": 50, "w": 150, "h": 150, "z": 0.0, "color": "#ff0000"}
]

zones_config_cam1 = load_json(ZONE_FILE_CAM1, default_zones)
zones_config_cam2 = load_json(ZONE_FILE_CAM2, default_zones)
zone_overrides = load_json(ZONE_OVERRIDES_FILE, {})

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

def pixel_to_robot_cam1(px, py, zone_id):
    if zone_id in zone_matrices_cam1:
        pt = np.array([px, py, 1.0], dtype=np.float32)
        res = zone_matrices_cam1[zone_id].dot(pt)
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

def hex_to_bgr(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))[::-1]

def get_distance(x1, y1, x2, y2):
    return math.sqrt((x1-x2)**2 + (y1-y2)**2)

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

# [UPDATED] Pick Sequence
def execute_pick_sequence(rx, ry, z_pick, z_hover, sb, tag_id, zone_name):
    global is_robot_busy, web_data, sequence_count, total_picked
    
    try:
        is_robot_busy = True
        # [FIX] Freeze Target on UI while picking
        web_data['target_x'] = round(rx, 2)
        web_data['target_y'] = round(ry, 2)
        web_data['active_id'] = str(tag_id)
        web_data['status'] = f"MOVING TO ID:{tag_id}"
        
        set_light('yellow')
        print(f"[ROBOT] Picking ID:{tag_id} Zone:{zone_name}")

        # 1. Standby
        client_move.MovJ(float(sb['x']), float(sb['y']), float(sb['z']), float(sb['r'])); client_move.Sync()
        
        # 2. Hover & Pick
        web_data['status'] = "PICKING"
        client_move.MovL(rx, ry, z_hover, float(sb['r'])); client_move.Sync()
        client_move.MovL(rx, ry, z_pick, float(sb['r'])); client_move.Sync()

        # 3. Suction
        control_suction('on')
        time.sleep(0.8)

        # 4. Check Sensor
        if check_suction_status():
            print(">>> SUCTION SUCCESS")
            web_data['status'] = "SUCTION SUCCESS"
            
            # [FIX] Save History on Success
            sequence_count += 1
            total_picked += 1
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            save_to_database(sequence_count, tag_id, ts, zone_name, round(rx, 2), round(ry, 2))
            
            client_move.MovL(rx, ry, z_hover, float(sb['r'])); client_move.Sync()
            client_move.MovJ(float(sb['x']), float(sb['y']), float(sb['z']), float(sb['r'])); client_move.Sync()
            
            web_data['status'] = "HOME"
            client_move.JointMovJ(0.0, 0.0, 0.0, 200.0); client_move.Sync()
            set_light('green')
            
            is_robot_busy = False
            return True
        else:
            print(">>> SUCTION FAILED")
            web_data['status'] = "FAILED"
            control_suction('off')
            client_move.MovL(rx, ry, z_hover, float(sb['r'])); client_move.Sync()
            set_light('red')
            is_robot_busy = False
            return False

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
        web_data['robot_mode'] = ROBOT_MODE
        return jsonify({"status": "success", "mode": ROBOT_MODE})
    return jsonify({"status": "error"}), 400

@app.route('/api/robot/click_move', methods=['POST'])
def click_move():
    global is_connected
    if not is_connected: return jsonify({"status": "error", "message": "Not Connected"})
    if ROBOT_MODE == 'AUTO': return jsonify({"status": "error", "message": "Cannot click in AUTO mode"})

    cx, cy = request.json.get('x'), request.json.get('y')
    target_tag = None; min_dist = 50.0

    for tag in current_visible_tags_cam1:
        dist = get_distance(cx, cy, tag['cx'], tag['cy'])
        if dist < min_dist: min_dist = dist; target_tag = tag

    if not target_tag: return jsonify({"status": "error", "message": "No Tag"})
    zone_data = target_tag['zone']
    if not zone_data: return jsonify({"status": "error", "message": "Outside Zone"})

    tag_id = int(target_tag['id'])
    rx, ry = pixel_to_robot_cam1(target_tag['cx'], target_tag['cy'], zone_data['id'])
    
    z_base = float(zone_data.get('z', 0.0))
    h_obj = float(OBJECT_INFO.get(tag_id, {'height': 20.0})['height'])
    z_off = get_zone_tag_offset(zone_data['id'], tag_id)
    z_pick = z_base + h_obj + z_off - 2.0
    sb = zone_data.get('standby', {"x": 250, "y": 0, "z": 100, "r": 0})

    threading.Thread(target=execute_pick_sequence, args=(rx, ry, z_pick, z_pick+20, sb, tag_id, zone_data['name'])).start()
    
    return jsonify({"status": "success", "message": "Command Sent"})

# --- Robot APIs ---
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

# --- Cam2 & Calibration APIs ---
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
def data_stream(): return jsonify(web_data)

@app.route("/video_feed")
def feed1(): return Response(gen_frames_cam1(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/video_feed_2")
def feed2(): return Response(gen_frames_cam2(), mimetype="multipart/x-mixed-replace; boundary=frame")

# ======================================================================================
# 6. VISION LOOPS
# ======================================================================================

def vision_loop_cam1():
    """Main Camera Loop"""
    global output_frame_cam1, web_data, current_visible_tags_cam1
    global processed_tags, tag_stability

    cap = cv2.VideoCapture(RTSP_URL_CAM1)
    at_detector = Detector(families="tag36h11")
    print(">>> CAM1: STARTED (Top View) <<<")

    while True:
        ret, frame = cap.read()
        if not ret: time.sleep(2); cap.release(); cap = cv2.VideoCapture(RTSP_URL_CAM1); continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY); tags = at_detector.detect(gray)
        current_visible_tags_cam1 = []; visible_tags_info = []; status_text = "SCANNING..."; current_time = time.time(); visible_ids = set()

        for z in zones_config_cam1:
            color = hex_to_bgr(z['color'])
            cv2.rectangle(frame, (z['x'], z['y']), (z['x']+z['w'], z['y']+z['h']), color, 2)
            cv2.putText(frame, z['name'], (z['x'], z['y']-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        for tag in tags:
            cx, cy = int(tag.center[0]), int(tag.center[1]); zone = check_zone_cam1(cx, cy); visible_ids.add(tag.tag_id)
            current_visible_tags_cam1.append({"id": tag.tag_id, "cx": cx, "cy": cy, "zone": zone})
            rx, ry = 0, 0
            
            if zone:
                rx, ry = pixel_to_robot_cam1(cx, cy, zone['id'])
                cv2.polylines(frame, [tag.corners.astype(int)], True, (0, 255, 0), 2)
                
                # [FIX] Update Real-time Target (Display only if robot not busy picking)
                if not is_robot_busy:
                    web_data['target_x'] = round(rx, 2)
                    web_data['target_y'] = round(ry, 2)
                    web_data['active_id'] = str(tag.tag_id)

                if tag.tag_id not in tag_stability: tag_stability[tag.tag_id] = current_time
                
                # Check Stability
                if current_time - tag_stability[tag.tag_id] > 1.5:
                    status_text = "DETECTED" # [FIX] Green Status
                    
                    # AUTO PICK EXECUTION
                    if ROBOT_MODE == 'AUTO' and not is_robot_busy and is_connected:
                        if current_time - processed_tags.get(tag.tag_id, 0) > 10.0:
                            processed_tags[tag.tag_id] = current_time
                            
                            # Calculate Pick Params
                            tag_id = int(tag.tag_id)
                            z_base = float(zone.get('z', 0.0))
                            h_obj = float(OBJECT_INFO.get(tag_id, {'height': 20.0})['height'])
                            z_off = get_zone_tag_offset(zone['id'], tag_id)
                            z_pick = z_base + h_obj + z_off - 2.0
                            sb = zone.get('standby', {"x": 250, "y": 0, "z": 100, "r": 0})
                            
                            threading.Thread(target=execute_pick_sequence, 
                                             args=(rx, ry, z_pick, z_pick+20, sb, tag_id, zone['name'])).start()
            else:
                cv2.polylines(frame, [tag.corners.astype(int)], True, (0, 0, 255), 2)

            visible_tags_info.append({"id": int(tag.tag_id), "cx": cx, "cy": cy, "rx": round(rx, 2), "ry": round(ry, 2), "zone": zone['name'] if zone else "None"})

        for tid in list(tag_stability.keys()):
            if tid not in visible_ids: del tag_stability[tid]

        # Update Web Data (Prevent status overwrite if busy)
        update_data = {
            "x": 0, "y": 0, "stack_h": current_stack,
            "total_picked": total_picked,
            "history": history_log,
            "tags": visible_tags_info,
            "cam2_enabled": CAM2_ENABLED,
            "robot_mode": ROBOT_MODE
        }
        if not is_robot_busy: update_data["status"] = status_text
        web_data.update(update_data)

        with lock_cam1: output_frame_cam1 = frame.copy()
    cap.release()

def vision_loop_cam2():
    global output_frame_cam2
    cap = cv2.VideoCapture(RTSP_URL_CAM2); at_detector = Detector(families="tag36h11")
    print(">>> CAM2: STARTED (Side View) <<<")
    while True:
        ret, frame = cap.read()
        if not ret: time.sleep(2); cap.release(); cap = cv2.VideoCapture(RTSP_URL_CAM2); continue
        if CAM2_ENABLED:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY); tags = at_detector.detect(gray)
            for tag in tags:
                cx, cy = int(tag.center[0]), int(tag.center[1])
                cv2.polylines(frame, [tag.corners.astype(int)], True, (255, 0, 0), 2)
                cv2.putText(frame, f"ID:{tag.tag_id}", (cx-10, cy-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 1)
        else:
            cv2.putText(frame, "CAM2 DISABLED", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)
        with lock_cam2: output_frame_cam2 = frame.copy()

def gen_frames_cam1():
    while True:
        with lock_cam1:
            if output_frame_cam1 is None: time.sleep(0.1); continue
            _, img = cv2.imencode(".jpg", output_frame_cam1)
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(img) + b'\r\n')

def gen_frames_cam2():
    while True:
        with lock_cam2:
            if output_frame_cam2 is None: time.sleep(0.1); continue
            _, img = cv2.imencode(".jpg", output_frame_cam2)
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(img) + b'\r\n')

if __name__ == "__main__":
    t1 = threading.Thread(target=vision_loop_cam1); t1.daemon = True; t1.start()
    t2 = threading.Thread(target=vision_loop_cam2); t2.daemon = True; t2.start()
    print("--- ROBOT SERVER READY (FIXED) ---")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)