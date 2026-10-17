#include <Servo.h>

const uint8_t NUM_SERVOS = 6;
const uint8_t PIN[NUM_SERVOS] = { 2, 3, 4, 5, 7, 6 };
const uint8_t HOME_ANGLE[NUM_SERVOS] = { 90, 0, 170, 0, 90, 100 };
const unsigned SWEEP_MS = 30;

Servo servo[NUM_SERVOS];
int pos[NUM_SERVOS];
int tgt[NUM_SERVOS];
bool donePending[NUM_SERVOS];

const size_t LINE_MAX = 32;
char line[LINE_MAX];
size_t lineLen = 0;
bool overflowing = false;
unsigned long lastStep = 0;

void setup() {
  Serial.begin(115200);
  for (uint8_t i = 0; i < NUM_SERVOS; i++) {
    servo[i].attach(PIN[i]);
    pos[i] = tgt[i] = HOME_ANGLE[i];
    servo[i].write(pos[i]);
  }
  Serial.println(F("ready"));
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;      // tolerate CRLF
    if (c == '\n' || c == '+') {  // newline is end of command, use + for several commands same in line
      line[lineLen] = '\0';
      if (overflowing) Serial.println(F("err toolong"));
      else handleLine(line);
      lineLen = 0;
      overflowing = false;
    } else if (lineLen < LINE_MAX - 1) {
      line[lineLen++] = c;
    } else {
      overflowing = true;  // drop rest of line
    }
  }

  // non-blocking sweep: all 6 servos can move at once, but it's a bit janky if they do
  if (millis() - lastStep >= SWEEP_MS) {
    lastStep = millis();
    for (uint8_t i = 0; i < NUM_SERVOS; i++) {
      if (pos[i] != tgt[i]) {
        pos[i] += (tgt[i] > pos[i]) ? 1 : -1;
        servo[i].write(pos[i]);
      }
      if (pos[i] == tgt[i] && donePending[i]) {
        donePending[i] = false;
        Serial.print(F("done "));
        Serial.println(i);
      }
    }
  }
}

void handleLine(char *s) {
  while (*s == ' ' || *s == '\t') s++;
  if (*s == '\0') return;  // empty line: ignore
  char cmd = *s++;
  switch (cmd) {
    case 'm':
      move(s);
      break;
    case 'h':
      home();
      break;
    default:
      Serial.println(F("err cmd"));
  }
}

void move(char *s) {
  char *p, *end;
  long n = strtol(s, &p, 10);
  long a = strtol(p, &end, 10);
  if (p == s || end == p) {
    Serial.println(F("err args"));
    return;
  }
  while (*end == ' ' || *end == '\t') end++;
  if (*end != '\0') {
    Serial.println(F("err junk"));
    return;
  }

  if (n < 0 || n >= NUM_SERVOS) {
    Serial.println(F("err servo"));
    return;
  }
  if (a < 0 || a > 180) {
    Serial.print(F("err angle "));
    Serial.println(n);  
    return;
  }

  tgt[n] = (int)a;
  donePending[n] = true;
}

void home() {
  for (uint8_t n = 0; n < NUM_SERVOS; n++) {
    tgt[n] = HOME_ANGLE[n];
    donePending[n] = true;
  }
}