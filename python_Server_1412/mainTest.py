import threading
from dobot_api import DobotApiDashboard, DobotApi, DobotApiMove
import time

# --- CONFIGURATION ---
ROBOT_IP = "192.168.1.6" 
DASH_PORT = 29999
MOVE_PORT = 30003
FEED_PORT = 30004

def connect_robot():
    try:
        print(f"Connecting to {ROBOT_IP}...")
        dashboard = DobotApiDashboard(ROBOT_IP, DASH_PORT)
        move = DobotApiMove(ROBOT_IP, MOVE_PORT)
        feed = DobotApi(ROBOT_IP, FEED_PORT)
        print("Connect Success!")
        return dashboard, move, feed
    except Exception as e:
        print("Connect Failed:", e)
        exit()

def main():
    # 1. เชื่อมต่อ
    dash, move, feed = connect_robot()

    # 2. เปิดระบบ
    print("Enabling Robot...")
    dash.EnableRobot()
    time.sleep(1)

    # 3. ตั้งความเร็ว
    dash.SpeedFactor(30) 
    
    # --- กำหนดค่าคงที่ ---
    
    # ล็อคค่า R ไว้ที่ 269 ตลอดกาล
    FIXED_R = 269.0
    
    HOME_X = 284.0
    HOME_Y = 0.5
    HOME_Z = 121.0
    
    # คำนวณระยะยืดแขน (Radius)
    ARM_RADIUS = 284.0 
    SAFE_Z = 121.0     

    # กำหนดพิกัดโดยใช้ FIXED_R ทุกท่า
    
    # 1. Home
    # X=284, Y=0.5, Z=121, R=269
    
    # 2. Left (90 องศา) -> X=0, Y=284
    LEFT_X = 0.0
    LEFT_Y = ARM_RADIUS 
    
    # 3. Right (-90 องศา) -> X=0, Y=-284
    RIGHT_X = 0.0
    RIGHT_Y = -ARM_RADIUS 

    # --- เริ่มขยับ (R เท่าเดิมตลอด) ---
    
    # Step 1: ไปจุด Home
    print(f"Moving to HOME (R={FIXED_R})...")
    move.MovJ(HOME_X, HOME_Y, HOME_Z, FIXED_R)
    time.sleep(3) 

    # Step 2: ไปทางซ้าย (R=269)
    print(f"Moving LEFT (X={LEFT_X}, Y={LEFT_Y}, R={FIXED_R})...")
    move.MovJ(LEFT_X, LEFT_Y, SAFE_Z, FIXED_R)
    time.sleep(3)

    # Step 3: ไปทางขวา (R=269)
    print(f"Moving RIGHT (X={RIGHT_X}, Y={RIGHT_Y}, R={FIXED_R})...")
    move.MovJ(RIGHT_X, RIGHT_Y, SAFE_Z, FIXED_R)
    time.sleep(4)

    # Step 4: กลับมา Home
    print(f"Back to HOME (R={FIXED_R})...")
    move.MovJ(HOME_X, HOME_Y, HOME_Z, FIXED_R)
    time.sleep(3)

    print("Done.")

if __name__ == "__main__":
    main()