// versi: 2 - Parallel Execution + Button 3 Interrupt
// Reverse smooth servo - REFACTORED
// Update 28/08/2026: Final movement duration

#include <Servo.h>

const int BUTTON_PIN1   = 9;  // servo 1: toggle gerak menjauhi/kembali ke home
const int BUTTON_PIN2   = 10; // servo 2: 180° → 90° → 180°
const int BUTTON_PIN3   = 11; // INTERRUPT ALL: emergency routine
const int IR_SENSOR_PIN = 12; // IR reset position (servo 1)
const int SERVO_PIN1    = 4;  // servo continuous rotation
const int SERVO_PIN2    = 5;  // servo positional 180 derajat

const int SERVO_STOP = 90;    // netral (berhenti) - servo 1
const int SERVO_CW   = 180;   // putar CW - servo 1
const int SERVO_CCW  = 0;     // putar CCW - servo 1

// ==== Durasi servo 1 ====
const unsigned long MOVE_OUT_DURATION_BTN1   = 1350; // button 1: CW duration
const unsigned long MOVE_OUT_DURATION_BTN3   = 250;  // button 3: CW duration (interrupt)
const unsigned long BUTTON3_DELAY            = 2000; // button 3: delay sebelum homing

// ==== Konfigurasi Servo 2 (MG996R positional 180 derajat) ====
const int SERVO2_HOME_ANGLE   = 180;  // posisi awal
const int SERVO2_TARGET_ANGLE = 90;   // posisi target button 1 & 2
const int SERVO2_ZERO_ANGLE   = 0;    // posisi target button 3

// Kecepatan gerakan Servo 2 (10 ms = setiap 1 derajat diberi jeda 10 ms)
const unsigned long SERVO2_STEP_DELAY = 10;

const unsigned long SERVO2_HOLD_DELAY = 2000; // tahan 2 detik di posisi target


// ================= STATE MACHINE SERVO 1 =================

enum Servo1State {
  S1_IDLE,                    // diam di posisi awal
  S1_MOVING_OUT_CW,           // bergerak CW menjauh dari home (button 1)
  S1_HOMING_CCW,              // bergerak CCW kembali ke home
  S1_BTN3_MOVING_OUT,         // bergerak CW 250ms (button 3 interrupt)
  S1_BTN3_DELAY,              // delay 2 detik (button 3)
  S1_BTN3_HOMING              // bergerak CCW sampai IR LOW (button 3)
};


// ================= STATE MACHINE SERVO 2 =================

enum Servo2State {
  S2_IDLE,
  S2_MOVING_TO_TARGET,        // ke 90° (button 1 & 2)
  S2_HOLDING,                 // tahan di 90°
  S2_RETURNING_HOME,          // kembali ke 180°
  S2_BTN3_TO_ZERO,            // ke 0° (button 3 interrupt)
  S2_BTN3_HOLDING,            // tahan di 0°
  S2_BTN3_RETURNING           // kembali ke 180°
};


Servo1State currentState1 = S1_IDLE;
Servo2State currentState2 = S2_IDLE;

unsigned long stateStartTime1 = 0;
unsigned long stateStartTime2 = 0;


// ================= BUTTON 1 =================

bool lastButtonReading1 = HIGH;
bool buttonStableState1 = HIGH;
unsigned long lastDebounceTime1 = 0;


// ================= BUTTON 2 =================

bool lastButtonReading2 = HIGH;
bool buttonStableState2 = HIGH;
unsigned long lastDebounceTime2 = 0;


// ================= BUTTON 3 =================

bool lastButtonReading3 = HIGH;
bool buttonStableState3 = HIGH;
unsigned long lastDebounceTime3 = 0;

bool button3Executing = false;  // Lock: cegah re-trigger saat button 3 sedang jalan

const unsigned long debounceDelay = 50;


// ================= SERVO =================

Servo myServo;   // Servo 1 - continuous rotation
Servo myServo2;  // Servo 2 - MG996R positional


// ================= SERVO 2 SMOOTH MOVEMENT =================

int servo2CurrentAngle = SERVO2_HOME_ANGLE;
int servo2TargetAngle = SERVO2_HOME_ANGLE;
unsigned long servo2LastStepTime = 0;


// ================= SETUP =================

void setup() {

  pinMode(BUTTON_PIN1, INPUT_PULLUP);
  pinMode(BUTTON_PIN2, INPUT_PULLUP);
  pinMode(BUTTON_PIN3, INPUT_PULLUP);

  pinMode(IR_SENSOR_PIN, INPUT);

  // Servo 1
  myServo.attach(SERVO_PIN1);
  myServo.write(SERVO_STOP);

  // Servo 2
  myServo2.attach(SERVO_PIN2);
  myServo2.write(SERVO2_HOME_ANGLE);

  servo2CurrentAngle = SERVO2_HOME_ANGLE;
  servo2TargetAngle = SERVO2_HOME_ANGLE;

  currentState1 = S1_IDLE;
  currentState2 = S2_IDLE;
}


// ================= LOOP =================

void loop() {

  // =====================================================
  // READ SEMUA INPUT
  // =====================================================

  bool button1PressedEvent =
    readButtonPressed(
      BUTTON_PIN1,
      lastButtonReading1,
      buttonStableState1,
      lastDebounceTime1
    );

  bool button2PressedEvent =
    readButtonPressed(
      BUTTON_PIN2,
      lastButtonReading2,
      buttonStableState2,
      lastDebounceTime2
    );

  bool button3PressedEvent =
    readButtonPressed(
      BUTTON_PIN3,
      lastButtonReading3,
      buttonStableState3,
      lastDebounceTime3
    );

  bool irSensorHigh = (digitalRead(IR_SENSOR_PIN) == HIGH);


  // =====================================================
  // BUTTON 3 INTERRUPT LOGIC (Priority tertinggi)
  // =====================================================

  if (button3PressedEvent && !button3Executing) {

    // Interrupt semua state
    button3Executing = true;

    // Interrupt Servo 1
    currentState1 = S1_BTN3_MOVING_OUT;
    stateStartTime1 = millis();
    myServo.write(SERVO_CW);

    // Interrupt Servo 2
    currentState2 = S2_BTN3_TO_ZERO;
    servo2TargetAngle = SERVO2_ZERO_ANGLE;
    servo2LastStepTime = millis();
  }


  // =========================================================
  // STATE MACHINE SERVO 1
  // =========================================================

  switch (currentState1) {

    // =======================================================
    // IDLE - menunggu input button 1
    // =======================================================
    case S1_IDLE:

      myServo.write(SERVO_STOP);

      // Button 1 pressed
      if (button1PressedEvent) {

        if (!irSensorHigh) {
          // IR LOW: ada object di home → mulai gerak CW menjauhi home

          myServo.write(SERVO_CW);
          stateStartTime1 = millis();
          currentState1 = S1_MOVING_OUT_CW;

        } else {
          // IR HIGH: servo sudah jauh dari home → mulai homing CCW

          myServo.write(SERVO_CCW);
          currentState1 = S1_HOMING_CCW;
        }
      }

      break;


    // =======================================================
    // SERVO 1 BERGERAK CW MENJAUHI HOME (Button 1)
    // =======================================================
    case S1_MOVING_OUT_CW:

      if (millis() - stateStartTime1 >= MOVE_OUT_DURATION_BTN1) {

        // 1250ms selesai → stop dan idle
        myServo.write(SERVO_STOP);
        currentState1 = S1_IDLE;
      }

      break;


    // =======================================================
    // SERVO 1 BERGERAK CCW KEMBALI KE HOME (Button 1)
    // =======================================================
    case S1_HOMING_CCW:

      myServo.write(SERVO_CCW);

      if (!irSensorHigh) {
        // IR LOW → posisi home tercapai

        myServo.write(SERVO_STOP);
        currentState1 = S1_IDLE;
      }

      break;


    // =======================================================
    // BUTTON 3: SERVO 1 BERGERAK CW 250ms (INTERRUPT)
    // =======================================================
    case S1_BTN3_MOVING_OUT:

      if (millis() - stateStartTime1 >= MOVE_OUT_DURATION_BTN3) {

        // 250ms selesai → stop dan delay 2 detik
        myServo.write(SERVO_STOP);
        stateStartTime1 = millis();
        currentState1 = S1_BTN3_DELAY;
      }

      break;


    // =======================================================
    // BUTTON 3: SERVO 1 DELAY 2 DETIK
    // =======================================================
    case S1_BTN3_DELAY:

      if (millis() - stateStartTime1 >= BUTTON3_DELAY) {

        // 2 detik selesai → mulai homing
        myServo.write(SERVO_CCW);
        currentState1 = S1_BTN3_HOMING;
      }

      break;


    // =======================================================
    // BUTTON 3: SERVO 1 HOMING CCW SAMPAI IR LOW
    // =======================================================
    case S1_BTN3_HOMING:

      myServo.write(SERVO_CCW);

      if (!irSensorHigh) {
        // IR LOW → posisi home tercapai

        myServo.write(SERVO_STOP);
        currentState1 = S1_IDLE;

        // Button 3 routine selesai
        button3Executing = false;
      }

      break;
  }


  // =========================================================
  // STATE MACHINE SERVO 2 (PARALLEL - TIDAK MENUNGGU SERVO 1)
  // =========================================================

  switch (currentState2) {

    // =======================================================
    // SERVO 2 IDLE
    // =======================================================
    case S2_IDLE:

      // Button 2 pressed → mulai routine normal
      if (button2PressedEvent) {

        servo2TargetAngle = SERVO2_TARGET_ANGLE;
        servo2LastStepTime = millis();
        currentState2 = S2_MOVING_TO_TARGET;
      }

      break;


    // =======================================================
    // SERVO 2 BERGERAK SMOOTH KE 90° (Button 1 & 2)
    // =======================================================
    case S2_MOVING_TO_TARGET:

      updateServo2Smooth();

      if (servo2CurrentAngle == servo2TargetAngle) {

        stateStartTime2 = millis();
        currentState2 = S2_HOLDING;
      }

      break;


    // =======================================================
    // SERVO 2 MENAHAN DI 90° SELAMA 2 DETIK
    // =======================================================
    case S2_HOLDING:

      if (millis() - stateStartTime2 >= SERVO2_HOLD_DELAY) {

        servo2TargetAngle = SERVO2_HOME_ANGLE;
        servo2LastStepTime = millis();
        currentState2 = S2_RETURNING_HOME;
      }

      break;


    // =======================================================
    // SERVO 2 KEMBALI SMOOTH KE 180°
    // =======================================================
    case S2_RETURNING_HOME:

      updateServo2Smooth();

      if (servo2CurrentAngle == servo2TargetAngle) {

        currentState2 = S2_IDLE;
      }

      break;


    // =======================================================
    // BUTTON 3: SERVO 2 BERGERAK KE 0° (INTERRUPT)
    // =======================================================
    case S2_BTN3_TO_ZERO:

      updateServo2Smooth();

      if (servo2CurrentAngle == servo2TargetAngle) {

        stateStartTime2 = millis();
        currentState2 = S2_BTN3_HOLDING;
      }

      break;


    // =======================================================
    // BUTTON 3: SERVO 2 MENAHAN DI 0° SELAMA 2 DETIK
    // =======================================================
    case S2_BTN3_HOLDING:

      if (millis() - stateStartTime2 >= SERVO2_HOLD_DELAY) {

        servo2TargetAngle = SERVO2_HOME_ANGLE;
        servo2LastStepTime = millis();
        currentState2 = S2_BTN3_RETURNING;
      }

      break;


    // =======================================================
    // BUTTON 3: SERVO 2 KEMBALI SMOOTH KE 180°
    // =======================================================
    case S2_BTN3_RETURNING:

      updateServo2Smooth();

      if (servo2CurrentAngle == servo2TargetAngle) {

        currentState2 = S2_IDLE;
      }

      break;
  }
}


// =============================================================
// FUNGSI GERAK SMOOTH SERVO 2
// =============================================================

void updateServo2Smooth() {

  unsigned long currentTime = millis();

  // Belum waktunya pindah 1 derajat
  if (currentTime - servo2LastStepTime < SERVO2_STEP_DELAY) {
    return;
  }

  servo2LastStepTime = currentTime;

  // Bergerak menuju sudut yang lebih besar
  if (servo2CurrentAngle < servo2TargetAngle) {

    servo2CurrentAngle++;
    myServo2.write(servo2CurrentAngle);
  }

  // Bergerak menuju sudut yang lebih kecil
  else if (servo2CurrentAngle > servo2TargetAngle) {

    servo2CurrentAngle--;
    myServo2.write(servo2CurrentAngle);
  }
}


// =============================================================
// BUTTON DEBOUNCE
// =============================================================

// Mengembalikan TRUE satu kali setiap ada tap/tombol baru
// Menggunakan falling edge dengan debounce

bool readButtonPressed(
  int pin,
  bool &lastReading,
  bool &stableState,
  unsigned long &lastDebounceTime
) {

  bool reading = digitalRead(pin);
  bool pressedEvent = false;

  if (reading != lastReading) {
    lastDebounceTime = millis();
  }

  if ((millis() - lastDebounceTime) > debounceDelay) {

    if (reading != stableState) {

      stableState = reading;

      if (stableState == LOW) {
        pressedEvent = true;
      }
    }
  }

  lastReading = reading;

  return pressedEvent;
}
