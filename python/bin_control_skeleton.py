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
# Discord (단일 Webhook)
# ==================================================
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/XXX/XXX"

ALERT_FILL_THRESHOLD = 80      # %
ALERT_COOLDOWN_SEC = 300       # 5분

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
    requests.post(DISCORD_WEBHOOK_URL, json={"content": msg}, timeout=5)

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
last_alert_time = 0   # 🔥 단일 쿨타임

hold_start = None
last_infer = 0
last_object_time = None

last_label = None
last_conf = 0.0

cap = cv2.VideoCapture(0)

# ==================================================
# loop
# ==================================================
while True:
    # ---------- 거리 수신 ----------
    try:
        line = ser.readline().decode().strip()
        for label, cfg in BIN_CONFIG.items():
            if line.startswith(f"Dist{cfg['idx']}:"):
                last_dist[cfg['idx']] = int(line.split(":")[1].strip())
    except:
        pass

    # ---------- 통별 fill 계산 + 단일 알림 ----------
    now = time.time()
    for label, cfg in BIN_CONFIG.items():
        d = last_dist[cfg["idx"]]
        fill = calc_fill_percent(d, cfg["empty_cm"], cfg["full_cm"])
        if fill is None:
            continue

        if (
            fill >= ALERT_FILL_THRESHOLD and
            now - last_alert_time >= ALERT_COOLDOWN_SEC
        ):
            send_discord(label, d, fill)
            last_alert_time = now
            break   # 🔑 한 번에 하나만 알림

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

    raw_obj = (std > STD_THRESHOLD) or (edge_ratio > EDGE_THRESHOLD)

    if raw_obj:
        object_exists = True
        last_object_time = now
    else:
        object_exists = last_object_time and now - last_object_time < OBJECT_LOST_GRACE

    # ---------- ViT ----------
    if object_exists and now - last_infer >= COOLDOWN_SEC:
        if hold_start is None:
            hold_start = now
        elif now - hold_start >= HOLD_TIME_SEC:
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

            last_infer = now
            hold_start = None
    else:
        hold_start = None

    # ---------- UI ----------
    cv2.rectangle(frame,(x1,y1),(x2,y2),
                  (0,255,0) if object_exists else (0,0,255),2)

    cv2.putText(frame,f"{last_label} ({last_conf:.2f})",(10,30),
                cv2.FONT_HERSHEY_SIMPLEX,0.9,(255,255,255),2)

    y = 70
    for label, cfg in BIN_CONFIG.items():
        d = last_dist[cfg["idx"]]
        fill = calc_fill_percent(d, cfg["empty_cm"], cfg["full_cm"])
        if d is not None:
            cv2.putText(frame,f"{label}: {d}cm / {fill}%",
                        (10,y),cv2.FONT_HERSHEY_SIMPLEX,0.7,(200,200,100),2)
            y += 25

    cv2.imshow("Smart 3-Bin System", frame)
    if cv2.waitKey(1)&0xFF==ord('q'):
        break

cap.release()
ser.close()
cv2.destroyAllWindows()