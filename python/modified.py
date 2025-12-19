import cv2, time, torch, serial, numpy as np, requests
from PIL import Image
from transformers import ViTForImageClassification, ViTImageProcessor

# ==================================================
# 기본 설정
# ==================================================
MODEL_DIR = "vit_wastemodel"
ROI_RATIO = 0.6

STD_THRESHOLD = 10.0
EDGE_THRESHOLD = 0.01
OBJECT_LOST_GRACE = 0.3

HOLD_TIME_SEC = 3.0
CONF_THRESHOLD = 0.5
COOLDOWN_SEC = 5.0

SERIAL_PORT = "COM3"
BAUD_RATE = 9600

LABELS = ["Metal", "Cardboard", "Plastic"]
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ==================================================
# 통별 초음파 기준 (cm)
# ==================================================
BIN_CONFIG = {
    "Metal":     {"idx": 0, "empty_cm": 30, "full_cm": 5},
    "Cardboard": {"idx": 1, "empty_cm": 35, "full_cm": 7},
    "Plastic":   {"idx": 2, "empty_cm": 32, "full_cm": 6},
}

# ==================================================
# Discord
# ==================================================
DISCORD_WEBHOOK_URL = "deleted"
ALERT_FILL_THRESHOLD = 80
ALERT_COOLDOWN_SEC = 300

# ==================================================
# 유틸 함수
# ==================================================
def calc_fill_percent(dist, empty_cm, full_cm):
    if dist is None or dist < 0:
        return None
    if dist <= full_cm:
        return 100
    if dist >= empty_cm:
        return 0
    return int((empty_cm - dist) / (empty_cm - full_cm) * 100)

def send_discord(label, dist, fill):
    msg = (
        f"🚨 **쓰레기통 가득 참 경고** 🚨\n\n"
        f"🗑️ 통 종류: **{label}**\n"
        f"📏 거리: **{dist} cm**\n"
        f"📊 채움률: **{fill}%**\n\n"
        f"확인 후 비워주세요."
    )
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg}, timeout=5)
    except:
        pass

# ==================================================
# 모델 & Serial
# ==================================================
processor = ViTImageProcessor.from_pretrained(MODEL_DIR)
model = ViTForImageClassification.from_pretrained(MODEL_DIR)
model.to(DEVICE).eval()

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.05)
time.sleep(2)

# ==================================================
# 상태 변수
# ==================================================
last_dist = [None, None, None]
last_alert_time = 0

hold_start = None
last_infer = 0
last_object_time = None

last_label = None
last_conf = 0.0

# ==================================================
# Webcam
# ==================================================
cap = cv2.VideoCapture(0)
print("🎥 Smart 3-Bin System started (press 'q' to quit)")

# ==================================================
# Loop
# ==================================================
while True:
    now = time.time()
    progress = 0.0

    # ---------- 거리 수신 ----------
    try:
        line = ser.readline().decode().strip()
        for label, cfg in BIN_CONFIG.items():
            if line.startswith(f"Dist{cfg['idx']}:"):
                last_dist[cfg['idx']] = int(line.split(":")[1].strip())
    except:
        pass

    # ---------- 채움률 계산 + Discord ----------
    for label, cfg in BIN_CONFIG.items():
        d = last_dist[cfg["idx"]]
        fill = calc_fill_percent(d, cfg["empty_cm"], cfg["full_cm"])
        if fill is None:
            continue

        if fill >= ALERT_FILL_THRESHOLD and now - last_alert_time >= ALERT_COOLDOWN_SEC:
            send_discord(label, d, fill)
            last_alert_time = now
            break

    # ---------- Webcam ----------
    ret, frame = cap.read()
    if not ret:
        break

    h, w, _ = frame.shape
    rw, rh = int(w * ROI_RATIO), int(h * ROI_RATIO)
    x1, y1 = (w - rw)//2, (h - rh)//2
    x2, y2 = x1 + rw, y1 + rh
    roi = frame[y1:y2, x1:x2]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    std = np.std(gray)
    edges = cv2.Canny(gray, 50, 150)
    edge_ratio = np.sum(edges > 0) / edges.size

    # ---------- object 판단 (첫 번째 코드 기준) ----------
    raw_obj = (std > STD_THRESHOLD) and (edge_ratio > EDGE_THRESHOLD)

    if raw_obj:
        object_exists = True
        last_object_time = now
    else:
        object_exists = (
            last_object_time is not None and
            now - last_object_time < OBJECT_LOST_GRACE
        )

    # ---------- Hold → 단일 추론 ----------
    if object_exists and now - last_infer >= COOLDOWN_SEC:
        if hold_start is None:
            hold_start = now
        else:
            elapsed = now - hold_start
            progress = min(elapsed / HOLD_TIME_SEC, 1.0)

            if elapsed >= HOLD_TIME_SEC:
                img = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))
                inp = processor(images=img, return_tensors="pt")
                inp = {k:v.to(DEVICE) for k,v in inp.items()}

                with torch.no_grad():
                    out = model(**inp)
                    probs = torch.softmax(out.logits, dim=1)[0]

                idx = torch.argmax(probs).item()
                last_conf = probs[idx].item()
                last_label = LABELS[idx]

                if last_conf >= CONF_THRESHOLD:
                    ser.write(f"{last_label}\n".encode())

                print(f"📸 INFERRED: {last_label} ({last_conf:.3f})")

                last_infer = now
                hold_start = None
    else:
        hold_start = None

    # ---------- UI ----------
    color = (0,255,0) if object_exists else (0,0,255)
    cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)

    if now - last_infer < COOLDOWN_SEC:
        status_text = "Cooldown..."
    elif not object_exists:
        status_text = "Place waste in the box"
    else:
        status_text = "Hold still..."

    cv2.putText(frame, status_text, (10,30),
                cv2.FONT_HERSHEY_SIMPLEX,0.9,color,2)

    if last_label:
        cv2.putText(frame, f"Last: {last_label} ({last_conf:.2f})",
                    (10,65), cv2.FONT_HERSHEY_SIMPLEX,0.8,(255,255,255),2)

    # ---------- 통 상태 ----------
    y = 100
    for label, cfg in BIN_CONFIG.items():
        d = last_dist[cfg["idx"]]
        fill = calc_fill_percent(d, cfg["empty_cm"], cfg["full_cm"])
        if d is not None:
            cv2.putText(frame, f"{label}: {d}cm / {fill}%",
                        (10,y), cv2.FONT_HERSHEY_SIMPLEX,0.7,(200,200,100),2)
            y += 25

    # ---------- Progress Bar ----------
    bar_y = y2 + 15
    bar_h = 15
    cv2.rectangle(frame, (x1, bar_y), (x2, bar_y + bar_h), (50,50,50), -1)

    filled = int(progress * rw)
    bar_color = (0,255,0) if progress >= 1.0 else (0,255,255)
    cv2.rectangle(frame, (x1, bar_y),
                  (x1 + filled, bar_y + bar_h), bar_color, -1)

    cv2.imshow("Smart 3-Bin System", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
ser.close()
cv2.destroyAllWindows()
print("🛑 Program terminated")
