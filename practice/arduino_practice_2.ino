#define TRIG_PIN 9
#define ECHO_PIN 10

void setup() {
  Serial.begin(9600);        // 시리얼 통신 시작
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
}

void loop() {
  // 초음파 신호 발생
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  // 반사되어 돌아오는 시간 측정
  long duration = pulseIn(ECHO_PIN, HIGH);

  // 거리 계산 (cm)
  float distance = duration * 0.034 / 2;

  // 시리얼 모니터 출력
  Serial.print("거리: ");
  Serial.print(distance);
  Serial.println(" cm");

  delay(500);   // 0.5초 대기
}
