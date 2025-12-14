import cv2

# ลองเปลี่ยนเลขท้ายเป็น stream1 หรือ stream2 ดูครับ
RTSP_URL = "rtsp://admin:OokamiMio-2549@192.168.1.109/stream1" 

print(f"Trying to connect: {RTSP_URL}")
cap = cv2.VideoCapture(RTSP_URL)

if not cap.isOpened():
    print("❌ เปิดกล้องไม่ได้! เช็ค IP/User/Pass ด่วน")
else:
    print("✅ เชื่อมต่อติดแล้ว! กำลังลองอ่านภาพ...")
    ret, frame = cap.read()
    if ret:
        print(f"🎉 ได้ภาพแล้ว! ขนาด: {frame.shape}")
        cv2.imshow("TEST", frame)
        cv2.waitKey(0)
    else:
        print("⚠️ เชื่อมติด แต่ไม่ส่งภาพมา (Frame Drop)")

cap.release()
cv2.destroyAllWindows()