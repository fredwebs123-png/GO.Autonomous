/*
  Car Wash Guidance LED Sign
  ---------------------------
  Receives signal strings over USB serial from run_guidance.py and drives
  the LEDs.

  Wiring:
    LEFT_LED     -> pin 2 (through ~220 ohm resistor to GND)
    RIGHT_LED    -> pin 3
    STOP_LED     -> pin 4
    STRAIGHT_LED -> pin 5

  Python sends one of: MOVE_LEFT, MOVE_RIGHT, STRAIGHT, STOP,
  CONVEYOR_MOVING, WAIT -- each terminated with a newline, and re-sends the
  current signal every 0.5 s as a heartbeat.

  Fail-safe: if nothing arrives for HEARTBEAT_TIMEOUT_MS (Python crashed,
  cable pulled), the sign falls back to WAIT (all LEDs off).

  After editing, re-upload the sketch (Sketch > Upload) and close the
  Serial Monitor before running Python.
*/

const int LEFT_PIN = 2;
const int RIGHT_PIN = 3;
const int STOP_PIN = 4;
const int STRAIGHT_PIN = 5;

const unsigned long BLINK_INTERVAL_MS = 400;
const unsigned long HEARTBEAT_TIMEOUT_MS = 2000;

unsigned long lastBlinkTime = 0;
unsigned long lastMessageTime = 0;
bool blinkState = false;
String currentSignal = "WAIT";

void setup() {
  pinMode(LEFT_PIN, OUTPUT);
  pinMode(RIGHT_PIN, OUTPUT);
  pinMode(STOP_PIN, OUTPUT);
  pinMode(STRAIGHT_PIN, OUTPUT);
  allOff();
  Serial.begin(9600);
  Serial.setTimeout(50);
}

void loop() {
  if (Serial.available() > 0) {
    String incoming = Serial.readStringUntil('\n');
    incoming.trim();
    if (incoming.length() > 0) {
      if (incoming != currentSignal) {
        Serial.print("Received: ");
        Serial.println(incoming);
      }
      currentSignal = incoming;
      lastMessageTime = millis();
    }
  }

  if (millis() - lastMessageTime > HEARTBEAT_TIMEOUT_MS) {
    currentSignal = "WAIT";
  }

  applySignal(currentSignal);
}

void allOff() {
  digitalWrite(LEFT_PIN, LOW);
  digitalWrite(RIGHT_PIN, LOW);
  digitalWrite(STOP_PIN, LOW);
  digitalWrite(STRAIGHT_PIN, LOW);
}

void applySignal(const String &signal) {
  if (signal == "MOVE_LEFT") {
    allOff();
    digitalWrite(LEFT_PIN, HIGH);
  } else if (signal == "MOVE_RIGHT") {
    allOff();
    digitalWrite(RIGHT_PIN, HIGH);
  } else if (signal == "STRAIGHT") {
    allOff();
    digitalWrite(STRAIGHT_PIN, HIGH);
  } else if (signal == "STOP") {
    // Blink the stop LED - more attention-grabbing than solid
    digitalWrite(LEFT_PIN, LOW);
    digitalWrite(RIGHT_PIN, LOW);
    digitalWrite(STRAIGHT_PIN, LOW);
    if (millis() - lastBlinkTime >= BLINK_INTERVAL_MS) {
      blinkState = !blinkState;
      lastBlinkTime = millis();
    }
    digitalWrite(STOP_PIN, blinkState ? HIGH : LOW);
  } else if (signal == "CONVEYOR_MOVING") {
    allOff();
    digitalWrite(STOP_PIN, HIGH);  // solid stop light while moving through
  } else {  // "WAIT" or anything unrecognized -> fail-safe: no "go" signals
    allOff();
  }
}
