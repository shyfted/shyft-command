# Petey ESP32 controller

This is the source baseline recovered from the Arduino IDE sketch deployed to
Petey's internal ESP32 on 2026-08-30. The only source-level change is moving
Wi-Fi and OTA credentials into the ignored `secrets.h` file.

The baseline provides:

- Wi-Fi station connectivity
- ArduinoOTA with hostname `petey-esp32`
- `GET /ping`
- `GET /status`
- `GET` or `POST /lcd/on`
- `GET` or `POST /lcd/off`
- GPIO25 LCD MOSFET control, with LCD ON as the safe boot default
- passive C4001 UART observation on Serial2 (`RX=GPIO16`, `TX=GPIO17`, 9600 baud)
- recent raw C4001 frames at `GET /c4001/raw`
- validated C4001 presence state and timestamps in `GET /status`

The C4001 observer does not call the LCD endpoints or change GPIO25. The
programming/debug UART remains at 115200 baud and is not reused by the sensor.

Before compiling, copy `secrets.example.h` to `secrets.h` and set local Wi-Fi
and OTA credentials. Do not commit `secrets.h`.
