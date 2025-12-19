#include <Servo.h>

Servo myServo;          // 서보 객체 생성
int servoPin = 9;       // 서보 신호 핀 (PWM 핀)

int angle = 0;          // 입력받은 각도 저장 변수

void setup() {
  Serial.begin(9600);   // 시리얼 통신 시작
  myServo.attach(servoPin);

  Serial.println("=== 서보 모터 각도 실습 프로그램 ===");
  Serial.println("0~180 사이의 각도를 입력 후 Enter를 누르세요.");
}

void loop() {

  // 시리얼로 값이 들어오면 처리
  if (Serial.available() > 0) {

    int inputAngle = Serial.parseInt();  // 정수 값 읽기

    // 입력 범위 체크
    if (inputAngle >= 0 && inputAngle <= 180) {
      angle = inputAngle;
      myServo.write(angle);              // 서보 이동

      Serial.print("서보 이동 → ");
      Serial.print(angle);
      Serial.println(" 도");
    }
    else {
      Serial.println("⚠ 오류: 0~180 사이의 숫자를 입력하세요.");
    }

    // 시리얼 버퍼 정리
    while (Serial.available() > 0) {
      Serial.read();
    }
  }
}
