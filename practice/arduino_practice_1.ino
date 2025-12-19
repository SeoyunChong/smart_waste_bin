void setup() {
  pinMode(13, OUTPUT);   // 13번 핀을 출력으로 설정
}

void loop() {
  digitalWrite(13, HIGH); // 전기 신호 ON (LED 켜짐)
  delay(1000);            // 1초 대기

  digitalWrite(13, LOW);  // 전기 신호 OFF (LED 꺼짐)
  delay(1000);            // 1초 대기
}
