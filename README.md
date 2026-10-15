# FriESP

A small electronic character with an animated face, powered by an ESP32 and MicroPython.

> **Platform:** ESP32 (LilyGO TTGO T-Display) · **Language:** MicroPython · **Display:** ST7789 · **Status:** in development

FriESP turns an ESP32 board with a display into a character that reacts to its surroundings. The goal is for it to blink, change expression with the ambient temperature, and get dizzy when it is moved or rotated, all drawn directly on the TFT display, with no computer or internet connection required.

The code is written in MicroPython and organized into independent modules: display driver, face rendering, sensor reading, and behavior logic. This separation makes it possible to swap a sensor or display without rewriting the rest of the application.

> **Current state:** the display driver, text scrolling, screen rotation, and color themes already work on real hardware. The animated face and sensor integration are under development.

Read in Portuguese: [README.md](README-PT Br.md)

---

## What it does

The features below combine what is already validated on the board and what is planned.

| Feature | Description | Status |
|---|---|---|
| Display initialization | Low-level ST7789 driver with configurable orientation and color inversion | Done |
| Scrolling banner | Continuous Pac-Man style scrolling with a title and subtitle | Done |
| Screen rotation | Four orientations (landscape, portrait, and both inverted), switched by a button | Done |
| Color themes | Four background and font pairs, switched by a button | Done |
| Animated face | Eyes, mouth, and basic expressions | In progress |
| Blinking and movement | Dynamic idle facial animations | Planned |
| Temperature reactions | Hot and cold expressions | Planned |
| Motion detection | Dizziness simulation on movement and rotation | Planned |
| Automatic expressions | Behavior engine combining all inputs | Planned |

---

## How it works

The application runs a main loop split into four stages:

1. **Input.** Reads the buttons and, in the future, the temperature and motion sensors.
2. **Behavior.** Converts the readings into an expression state (neutral, hot, cold, dizzy).
3. **Rendering.** Draws the face for the current state, updating only the screen regions that changed.
4. **Display.** Sends the pixels to the ST7789 over SPI.

Because the SPI bus is emulated in software, rendering avoids redrawing the whole screen on every frame.

---

## Hardware

### Development board

| Component | Specification |
|---|---|
| Board | LilyGO TTGO T-Display |
| Microcontroller | ESP32 (dual-core Xtensa LX6, Wi-Fi and Bluetooth) |
| Display | 1.14" IPS TFT, 240 x 135 pixels, ST7789 controller, RGB565 |
| Buttons | 2 onboard (GPIO 0 and GPIO 35) |
| Connection | USB-C |

### Optional sensors

The T-Display has no motion or temperature sensors. The reactive features require external modules connected over I2C:

| Function | Suggested module | Interface |
|---|---|---|
| Accelerometer and gyroscope | MPU6050 or MPU9250 | I2C |
| Temperature (and pressure) | BMP280, BME280 or similar | I2C |

Sensor choice is subject to hardware verification. The code is designed so that each sensor driver can be replaced without changing the rest of the application.

### Porting note

The project originally targeted the ESP32-S3. The S3 variant of the T-Display uses an 8-bit parallel display bus instead of SPI, which changes the pins and initialization. The current code targets the **classic ESP32** with an SPI bus.

---

## Pin mapping

### Display (ST7789, SPI)

| Signal | GPIO |
|---|---|
| SCK (clock) | 18 |
| MOSI (data) | 19 |
| CS (chip select) | 5 |
| DC (data/command) | 16 |
| RST (reset) | 23 |
| BL (backlight) | 4 |

### Buttons

| Button | GPIO | Function |
|---|---|---|
| BOOT | 0 | Change color theme |
| Right | 35 | Rotate screen |

GPIO 35 is input-only and relies on the board's external pull-up. GPIO 0 uses the internal pull-up.

> **Warning:** do not hold the BOOT button while powering on the board. It enters firmware flashing mode and the program does not run.

---

## Software and technologies

| Item | Detail |
|---|---|
| Language | MicroPython |
| Firmware | MicroPython for ESP32 (`ESP32_GENERIC` build recommended) |
| Display driver | Custom ST7789 routines using `machine.SoftSPI` |
| Graphics | `framebuf` (RGB565 frame buffers) |
| Development environment | Thonny IDE |

---

## Installation

### 1. Flash the firmware

1. Download the **ESP32_GENERIC** build from [micropython.org/download](https://micropython.org/download/ESP32_GENERIC/).
2. In Thonny, open **Tools > Options > Interpreter** and select **MicroPython (ESP32)**.
3. Click **Install or update MicroPython** and follow the prompts.

### 2. Upload the project

1. Clone or download this repository.
2. In Thonny, open **View > Files**.
3. Copy the project files to the root of the device storage.

### 3. Run automatically on boot

MicroPython runs the `main.py` file at startup. Save the entry point on the device with exactly that name, in the root directory.

To check for startup errors, open the Thonny shell and press `Ctrl+D`, which reboots the board and runs `main.py`.

---

## Project structure

The codebase is organized into modules for maintainability. The planned layout is:

```text
FriESP/
├── main.py        Entry point: main loop and state handling
├── config.py      Pin mapping, colors, and tunable parameters
├── display.py     ST7789 driver: initialization, windowing, rotation
├── face.py        Face rendering: eyes, mouth, expressions, blinking
├── sensors.py     Temperature and motion sensor abstraction
├── behavior.py    Logic that maps sensor data to expressions
└── README.md
```

The current prototype (display driver, scrolling banner, rotation and color buttons) lives in a single script and will be split into these modules as development progresses.

---

## Display technical notes

| Topic | Detail |
|---|---|
| Hardware SPI vs. SoftSPI | During bring-up, the display stayed blank (backlight on, no image) with hardware SPI on the installed firmware build. Switching to `SoftSPI` solved it. It is slower, so rendering updates only the regions that change. |
| Color inversion | The panel requires the inversion command (`0x21`) for correct colors. |
| Byte order | `framebuf` stores RGB565 in little-endian order, while the display expects big-endian. Color bytes are swapped before drawing. |
| Memory | Large frame buffers can raise `MemoryError` on an ESP32 without PSRAM. Keep text scales moderate. |
| Automatic rotation | The T-Display has no motion sensor, so rotation is manual, by button. It becomes possible after integrating an external accelerometer. |

The ST7789 RAM is 240 x 320 while the physical panel is 135 x 240, so an offset is applied to the address window in each orientation:

| Orientation | MADCTL | X offset | Y offset |
|---|---|---|---|
| Landscape | `0x60` | 40 | 53 |
| Portrait | `0xC0` | 53 | 40 |
| Landscape (inverted) | `0xA0` | 40 | 52 |
| Portrait (inverted) | `0x00` | 52 | 40 |

---

## Roadmap

- [x] Initial display test
- [x] Display driver with orientation and color support
- [x] Scrolling banner with title and subtitle
- [x] Button-controlled rotation and color themes
- [ ] Basic facial design
- [ ] Facial animations (blinking and idle movement)
- [ ] Temperature sensor integration
- [ ] Motion and rotation detection
- [ ] Automatic expression changes
- [ ] Code refactoring into modules

---

## Goals

The project aims to explore:

- embedded systems programming with MicroPython;
- low-level display control and graphical rendering on constrained hardware;
- sensor integration over I2C;
- interactive, state-driven behavior on a microcontroller.

Development is incremental and validated on physical hardware, with assistance from AI tools during implementation and debugging.

---

## Author

**Gabriel Nascimento**, Developer, Cybersecurity.

## Acknowledgments

- The [MicroPython](https://micropython.org/) project and community.
- LilyGO, for the TTGO T-Display hardware documentation.
- AI-assisted development tools, used for code generation and debugging support.
