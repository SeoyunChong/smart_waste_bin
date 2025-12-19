#include <Servo.h>

/*
  스마트 쓰레기통 (3분류) 스켈레톤 코드
  Metal / Cardboard / Plastic
*/

// =======================
// 1. 핀 설정
// =======================

// 서보 모터 핀 (0:Metal, 1:Cardboard, 2:Plastic)
const int SERVO_PINS[3] = { ___, ___, ___ };

// 초음파 센서 핀
const int TRIG_PINS[3] = { ___, ___, ___ };
const int ECHO_PINS[3] = { ___, ___, ___ };

// =======================
// 2. 기본 설정 값
// =======================
const int SERVO_OPEN_ANGLE  = 150;
const int SERVO_CLOSE_ANGLE = 90;

// =======================
Servo servos[3];

// =======================
// 3. 초음파 거리 측정 함수
// =======================
long measureDistanceCM(int index) {
  digitalWrite(TRIG_PINS[index], LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PINS[index], HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PINS[index], LOW);

  long duration = pulseIn(ECHO_PINS[index], HIGH, 30000);
  if (duration == 0) return -1;

  return duration / 58;
}

// =======================
// 4. setup
// =======================
void setup() {
  Serial.begin(9600);

  for (int i = 0; i < 3; i++) {
    pinMode(TRIG_PINS[i], OUTPUT);
    pinMode(ECHO_PINS[i], INPUT);

    // TODO 5️⃣ 서보 모터를 연결하세요
    servos[i].attach( ___ );
    servos[i].write(SERVO_CLOSE_ANGLE);
  }

  Serial.println("READY");
}

// =======================
// 5. loop
// =======================
void loop() {

  // -----------------------
  // (1) 초음파 거리 출력
  // -----------------------
  for (int i = 0; i < 3; i++) {
    long dist = measureDistanceCM(i);

    Serial.print("Dist");
    Serial.print(i);
    Serial.print(": ");
    Serial.println(dist);
  }

  delay(300);

  // -----------------------
  // (2) Python → Arduino 명령
  // -----------------------
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    int idx = -1;

    // TODO 6️⃣ "Metal"일 때 idx 값은?
    if (cmd == "Metal") {
      idx = ___;
    }
    // TODO 7️⃣ "Cardboard"일 때 idx 값은?
    else if (cmd == "Cardboard") {
      idx = ___;
    }
    // Plastic은 이미 완성되더 있음(참고 가능)
    else if (cmd == "Plastic") {
      idx = 2;
    }

    // -----------------------
    // (3) 해당 통 열기
    // -----------------------
    if (idx != -1) {
      servos[idx].write(SERVO_OPEN_ANGLE);
      delay(800);
      servos[idx].write(SERVO_CLOSE_ANGLE);
    }
  }
}
