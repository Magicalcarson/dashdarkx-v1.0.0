import cv2
import math
import time
import threading
import numpy as np
from flask import Flask, Response, jsonify
from flask_cors import CORS
from pupil_apriltags import Detector
# from dobot_api import DobotApiDashboard, DobotApi, DobotApiMove # <--- เปิดใช้งานเมื่อต่อหุ่นจริง

# ================== CONFIGURATION =====================
# RTSP_URL = "rtsp://admin:OokamiMio-2549@192.168.1.101/stream2" 
RTSP_URL = 0  # ใช้ 0 = Webcam (สำหรับทดสอบ)

# Simulation Mode (True = ไม่ต่อหุ่นจริง, False = ต่อหุ่นจริง)
SIMULATION_MODE = True 

# Global Variables for Web Server
output_frame = None
lock = threading.Lock()

# Data ที่จะส่งไปให้ React
web_data = {
    "x": 0.0,
    "y": 0.0,
    "stack_h": 0.0,
    "status": "IDLE",
    "history": [],
    "active_id": "-"
}

# ================== FLASK APP SETUP =====================
app = Flask(__name__)
CORS(app) # อนุญาตให้ React (Port 5173/3000) ดึงข้อมูลได้

# ================== VISION & ROBOT LOGIC LOOP =====================
def robot_vision_loop():
    global output_frame, web_data

    # Setup Camera
    cap = cv2.VideoCapture(RTSP_URL)
    at_detector = Detector(families="tag36h11")

    print(">>> CAMERA & ROBOT SYSTEM STARTED <<<")

    # ตัวแปรจำลอง Logic
    current_stack = 0.0
    history_log = []

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(1)
            continue

        # --- IMAGE PROCESSING ---
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        tags = at_detector.detect(gray)
        
        status_text = "SCANNING..."
        active_id = "-"
        target_x, target_y = 0, 0

        if len(tags) > 0:
            status_text = "DETECTED"
            
            # เลือก Tag แรกที่เจอ
            tag = tags[0]
            active_id = str(tag.tag_id)
            cx, cy = int(tag.center[0]), int(tag.center[1])
            target_x, target_y = float(cx), float(cy) # สมมติค่าพิกัด

            # วาดกรอบ
            corners = tag.corners.astype(int)
            cv2.polylines(frame, [corners], True, (0, 255, 0), 3)
            cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
            cv2.putText(frame, f"ID: {active_id}", (cx, cy-10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            # (จำลอง) ถ้าเจอของ ให้เพิ่ม History นานๆ ที
            if int(time.time()) % 5 == 0 and active_id not in history_log:
                 history_log.append(int(active_id))
                 if len(history_log) > 5: history_log.pop(0)
                 current_stack += 10.0
                 status_text = "BUSY (MOVING)"

        # --- UPDATE WEB DATA ---
        # อัปเดตตัวแปร Global เพื่อให้ API ดึงไปใช้
        web_data["x"] = target_x
        web_data["y"] = target_y
        web_data["stack_h"] = current_stack
        web_data["status"] = status_text
        web_data["history"] = history_log
        web_data["active_id"] = active_id

        # อัปเดตภาพสำหรับ Video Stream
        with lock:
            output_frame = frame.copy()
        
        # (Optional) โชว์หน้าจอ Python ด้วยก็ได้
        # cv2.imshow("Server Monitor", frame)
        # if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release()

# ================== FLASK ROUTES =====================

# 1. ส่งภาพวิดีโอ (MJPEG Stream)
def generate():
    while True:
        with lock:
            if output_frame is None:
                continue
            # Encode ภาพเป็น JPG
            (flag, encodedImage) = cv2.imencode(".jpg", output_frame)
            if not flag:
                continue
        
        # ส่งข้อมูลแบบ Multipart (ภาพต่อภาพ)
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
              bytearray(encodedImage) + b'\r\n')

@app.route("/video_feed")
def video_feed():
    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

# 2. ส่งข้อมูล JSON (API)
@app.route("/data")
def get_data():
    return jsonify(web_data)

# ================== RUNNER =====================
if __name__ == "__main__":
    # รันระบบหุ่นยนต์ใน Thread แยก (เพื่อให้ Server ไม่ค้าง)
    t = threading.Thread(target=robot_vision_loop)
    t.daemon = True
    t.start()

    # รัน Web Server
    print("--- WEB SERVER RUNNING ON PORT 5000 ---")
    # host='0.0.0.0' เพื่อให้เครื่องอื่นในวง LAN เข้าถึงได้
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)