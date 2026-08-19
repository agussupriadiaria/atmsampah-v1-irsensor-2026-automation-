#include <Servo.h>

const int BUTTON_PIN1   = 9;  // pin raspi 5 = trigger servo continuous
const int BUTTON_PIN2   = 10; // pin raspi 6
const int BUTTON_PIN3   = 11; // pin raspi 16
const int IR_SENSOR_PIN = 12; // IR reset position
const int SERVO_PIN1    = 4;  // servo continuous rotation
const int SERVO_PIN2    = 5;  // servo positional 180 derajat

const int SERVO_STOP = 90;    // netral (berhenti) - servo 1
const int SERVO_CW   = 180;   // putar CW - servo 1
const int SERVO_CCW  = 0;     // putar CCW - servo 1

// Catatan asumsi sensor IR:
// IR_SENSOR_PIN == HIGH -> BELUM di posisi awal -> servo1 CCW
// IR_SENSOR_PIN == LOW  -> SUDAH di posisi awal -> servo1 berhenti
//
// Jika modul sensor IR mempunyai polaritas terbalik,
// kondisi pembacaan irSensorHigh perlu dibalik.

// ==== Durasi servo 1 ====
const unsigned long MOVE_OUT_DURATION = 1000; // durasi gerak CW menjauh dari home

// ==== Konfigurasi Servo 2 (MG996R positional 180 derajat) ====
const int SERVO2_HOME_ANGLE   = 180;  // posisi awal
const int SERVO2_TARGET_ANGLE = 90;   // posisi target

// Kecepatan gerakan Servo 2
// 10 ms = setiap perubahan 1 derajat diberi jeda 10 ms
// Semakin besar nilainya = semakin lambat
const unsigned long SERVO2_STEP_DELAY = 10;

const unsigned long SERVO2_HOLD_DELAY = 2000; // tahan 2 detik di posisi target


// ================= STATE MACHINE SERVO 1 =================

enum Servo1State {
  S1_HOMING,         // mencari posisi awal (bergerak CCW)
  S1_IDLE,           // diam di posisi awal
  S1_MOVING_OUT,     // bergerak CW menjauh dari home
  S1_HOLDING         // menahan posisi, menunggu button berikutnya
};


// ================= STATE MACHINE SERVO 2 =================

enum Servo2State {
  S2_IDLE,
  S2_MOVING_TO_TARGET,
  S2_HOLDING,
  S2_RETURNING_HOME
};


Servo1State currentState1 = S1_HOMING;
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

const unsigned long debounceDelay = 50;


// ================= SERVO =================

Servo myServo;   // Servo 1 - continuous rotation
Servo myServo2;  // Servo 2 - MG996R positional


// ================= QUEUE BUTTON 2 =================

bool button2Queued = false;
bool button2DelayActive = false;
unsigned long button2DelayStart = 0;


// ================= SERVO 2 SMOOTH MOVEMENT =================

// Posisi aktual Servo 2
int servo2CurrentAngle = SERVO2_HOME_ANGLE;

// Target posisi Servo 2
int servo2TargetAngle = SERVO2_HOME_ANGLE;

// Waktu terakhir Servo 2 bergerak 1 derajat
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

  // Posisi awal Servo 2 = 180 derajat
  myServo2.write(SERVO2_HOME_ANGLE);

  servo2CurrentAngle = SERVO2_HOME_ANGLE;
  servo2TargetAngle = SERVO2_HOME_ANGLE;
}


// ================= LOOP =================

void loop() {

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


  // ================= IR SENSOR =================

  bool irSensorHigh =
    (digitalRead(IR_SENSOR_PIN) == HIGH);


  // =========================================================
  // STATE MACHINE SERVO 1
  // =========================================================

  switch (currentState1) {

    // =======================================================
    // SERVO 1 HOMING - MENCARI POSISI HOME DENGAN IR SENSOR
    // =======================================================

    case S1_HOMING:

      // Selama IR HIGH, Servo 1 CCW mencari home
      if (irSensorHigh) {

        myServo.write(SERVO_CCW);

      } else {

        // IR LOW = posisi home tercapai
        myServo.write(SERVO_STOP);

        currentState1 = S1_IDLE;
      }

      break;


    // =======================================================
    // SERVO 1 IDLE - MENUNGGU INPUT BUTTON
    // =======================================================

    case S1_IDLE:

      myServo.write(SERVO_STOP);

      // Jika IR tiba-tiba HIGH, lakukan homing ulang
      if (irSensorHigh) {

        currentState1 = S1_HOMING;

        break;
      }


      // Servo 1 hanya boleh mulai jika Servo 2 idle
      if (
        (button1PressedEvent || button3PressedEvent) &&
        currentState2 == S2_IDLE
      ) {

        myServo.write(SERVO_CW);

        stateStartTime1 = millis();

        currentState1 = S1_MOVING_OUT;
      }

      break;


    // =======================================================
    // SERVO 1 MOVING OUT - GERAK CW MENJAUH DARI HOME
    // =======================================================

    case S1_MOVING_OUT:

      if (millis() - stateStartTime1 >= MOVE_OUT_DURATION) {

        myServo.write(SERVO_STOP);

        currentState1 = S1_HOLDING;
      }

      break;


    // =======================================================
    // SERVO 1 HOLDING - DIAM DI POSISI, TUNGGU BUTTON BERIKUTNYA
    // =======================================================

    case S1_HOLDING:

      myServo.write(SERVO_STOP);

      // Jika IR tiba-tiba HIGH, lakukan homing ulang
      if (irSensorHigh) {

        currentState1 = S1_HOMING;

        break;
      }

      // Button ditekan → kembali ke home (S1_HOMING)
      if (button1PressedEvent || button3PressedEvent) {

        myServo.write(SERVO_CCW);

        currentState1 = S1_HOMING;
      }

      break;
  }


  // =========================================================
  // STATE MACHINE SERVO 2
  // =========================================================

  switch (currentState2) {


    // =======================================================
    // SERVO 2 IDLE
    // =======================================================

    case S2_IDLE:

      // BUTTON 2 ditekan
      if (button2PressedEvent) {

        // Jika Servo 1 belum kembali ke home,
        // masukkan BUTTON 2 ke queue
        if (irSensorHigh) {

          button2Queued = true;

        } else {

          // Servo 1 sudah home
          // mulai Servo 2 bergerak ke 90 derajat

          servo2TargetAngle = SERVO2_TARGET_ANGLE;

          servo2LastStepTime = millis();

          currentState2 = S2_MOVING_TO_TARGET;
        }
      }


      // =====================================================
      // EKSEKUSI BUTTON 2 YANG DI-QUEUE
      // =====================================================

      if (button2Queued && !irSensorHigh) {

        if (!button2DelayActive) {

          button2DelayActive = true;

          button2DelayStart = millis();
        }


        // Tunggu 2 detik setelah IR LOW
        if (millis() - button2DelayStart >= 2000) {

          button2Queued = false;

          button2DelayActive = false;

          // Mulai gerakan smooth ke 90 derajat
          servo2TargetAngle = SERVO2_TARGET_ANGLE;

          servo2LastStepTime = millis();

          currentState2 = S2_MOVING_TO_TARGET;
        }
      }

      break;


    // =======================================================
    // SERVO 2 BERGERAK SMOOTH KE TARGET
    // =======================================================

    case S2_MOVING_TO_TARGET:

      updateServo2Smooth();

      // Jika sudah sampai target
      if (servo2CurrentAngle == servo2TargetAngle) {

        stateStartTime2 = millis();

        currentState2 = S2_HOLDING;
      }

      break;


    // =======================================================
    // SERVO 2 MENAHAN POSISI 90 DERAJAT
    // =======================================================

    case S2_HOLDING:

      if (millis() - stateStartTime2 >= SERVO2_HOLD_DELAY) {

        // Setelah 2 detik,
        // Servo 2 kembali ke 180 derajat

        servo2TargetAngle = SERVO2_HOME_ANGLE;

        servo2LastStepTime = millis();

        currentState2 = S2_RETURNING_HOME;
      }

      break;


    // =======================================================
    // SERVO 2 KEMBALI SMOOTH KE HOME
    // =======================================================

    case S2_RETURNING_HOME:

      updateServo2Smooth();

      // Jika sudah sampai 180 derajat
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