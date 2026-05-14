# Math Game Touchscreen with Keypad
AI-assisted CircuitPython project with a Feather RP2350 and touchscreen as a fun way to help students practice basic math problems.

<b>Introduction</b>
I wanted to make my grandchildren a "game box" that is educational and single-purpose. Rather than an app on a phone or a tablet (I'm sure there are a lot), I wanted this to only do one thing: math drills, so there would be less distraction from other things. The basic premise of the project is to generate random math questions (addition, subtraction, and multiplication) and let them practice. Like a game, it tracks the player's name and keeps a list of high scores. It also tracks how many correctly answered questions each player has achieved over time, which lets me bribe them by paying a small amount for every x number of questions.

Written in CircuitPython, I use VS Code for my IDE and Copilot AI (letting it choose the actual agent). Honestly, the AI does most of the heavy lifting. It really does a great job taking my concepts entered in chat and writing efficient code. As the program grew from a simple approach into a more complex one, we stopped along the way and optimized the structure, breaking it out into separate modules and trying to make it straightforward to change the hardware.

<b>Hardware</b>
This project was initially designed on an Adafruit TFT Touchscreen FeatherWing. I later redesigned it to run on generic TFT touchscreens from Amazon for cost and size considerations. This code is written for those screens.
- Feather RP2350 (developed with the +PSRAM version, but I plan to optimize memory usage for the non-PSRAM version)
- 320x240 TFT touchscreen - 3.2" using ILI9341 SPI and XPT2046 touch controller (Amazon), also with an SD card slot. This display is available in several different sizes but is essentially pin-compatible between the different sizes available.
- DS3231 real-time clock module connected via I2C (there is a switch in the code to use a PCF8523 RTC module)
- Piezo buzzer
- SD (or microSD with an adapter) card
- 8mm PL9823 NeoPixel-type LED
- LiPo battery
- SPST switch for enablement
- 3D-printed case with heat-set brass inserts and screws

<b>Basic Design</b>
The original design generated random problems using digits 0 to 12 and gave the player four multiple-choice options. The logic generated three incorrect answers close to the real answer, so the correct answer wasn't obvious from the choices. A later iteration of the game added a second mode for keypad entry: rather than multiple-choice selection, the player had to key in the correct answer with an on-screen keypad.

In addition to the three problem types, I added "Mixed," which pulls from all question banks. Players have a choice of 10, 20, 35, or 50 questions.

Although we start with two names pre-programmed (these are in text files on the SD card), there is functionality to add additional names to the box so everyone can have their own scores. For this, we created an on-screen keyboard that is arranged as a 4x4 grid. The top row has buttons for "LAST" [page], "BkSp", "ENTER", and "NEXT" [page]. The second row has the vowels A, E, I, and O. These top two rows are constant. The consonants, U, and a space (underscore) are arranged on three pages. With this layout, it is efficient to enter names without a lot of paging.

Note that there is also a <i>secret</i> reset process to zero out the high scores and the game/problem counts. I added this so players would not get discouraged after the game fills up with high scores. If you choose "NEW" to create a new name and enter the name "RESET", the scores.txt file will be archived on the SD card with a date/time stamp, and the players.txt file will be replaced with the tplayers.txt file.

The keypad entry page is a similar 4x3 grid with buttons for 1, 2, 3, BkSp; 4, 5, 6, Enter; 7, 8, 9, 0. Because the screen is wider than tall, I thought this would be a better arrangement than a traditional 3x4 layout.

For the most part I used libraries and drivers from the Adafruit bundle; however, they don't have one for the touch controller, and there isn't one in the Community Bundle either. I did find a library, <i>xpt2046_circuitpython</i>, but I had to make a few changes to get it to run. The original library source is in the info folder. The updated library files used by this project are in the lib folder.

<b>Project Structure</b>

Top-level application files:
- code.py: Main runtime entry point. Initializes hardware, display pages, fonts, touch input, buzzer/LED feedback, and orchestrates UI/game flow.
- game_engine.py: Reducer/state-transition logic for mode selection, gameplay events, and intent routing.
- logic_core.py: Pure game logic such as problem generation, score parsing, and score calculations.
- adapters.py: Small adapter layer for display rendering, touch input abstraction, and persistence helpers.
- settings.toml: CircuitPython settings and configuration values used at boot/runtime.

Support and test files:
- codeboardtest.py: Board-level test script for hardware validation.
- codesdtest.py: SD card focused test script.

Data and assets:
- files/: Runtime text data files (players and scores), including default seeded data. This repo includes sample files with placeholder names. The <i>tplayers.txt</i> file is a template to start from scratch; replace the placeholders with the actual names that should be available each time the game is reset.
	- players.txt: Player roster.
	- scores.txt: Historical score entries.
	- tplayers.txt: Additional/testing player data file.
- fonts/: Bitmap font assets used by the UI (only a subset are actively loaded by code.py).

Reference and libraries:
- info/: Documentation and sample/reference material used during development.
- lib/: CircuitPython libraries and local modules bundled with the project (including touchscreen support code).

Runtime architecture summary:
- The app keeps game rules and state transitions separate from hardware concerns.
- code.py drives the event loop and presentation layer.
- game_engine.py decides what should happen next.
- logic_core.py computes math content and score values.
- adapters.py isolates hardware/file access details for cleaner main flow.

<b>Quick Start</b>

1. Install CircuitPython on your Feather RP2350.
2. Connect the board over USB and open the CIRCUITPY drive.
3. Copy project files/folders to CIRCUITPY:
	- code.py
	- adapters.py
	- game_engine.py
	- logic_core.py
	- settings.toml
	- lib/ (required libraries)
	- fonts/ (font assets)
4. Insert an SD or microSD card and ensure data files are available:
	- files/players.txt
	- files/scores.txt
	- files/tplayers.txt
5. Reset the board and verify the title screen appears.

<b>Wiring / Pin Map (Current Code)</b>

Shared SPI bus:
- SPI: board.SPI()
- TFT CS: D6
- TFT DC: D10
- TFT RST: D9
- Touch CS: D13
- SD CS: D5

Other pins:
- Touch IRQ/LED helper pin (configured output): D12
- NeoPixel: D24
- Buzzer PWM output: TX

I2C:
- I2C bus: board.I2C() for RTC (DS3231 by default, PCF8523 optional)

<b>Dependencies</b>

Core CircuitPython libraries used by this project:
- adafruit_ili9341
- adafruit_display_text
- adafruit_bitmap_font
- adafruit_displayio_layout
- neopixel
- adafruit_ds3231 (or adafruit_pcf8523 for optional RTC type)

Touch library:
- xpt2046_circuitpython (customized local version included in lib/xpt2046_circuitpython)
- Original/reference notes are in info/docs/xpt2046_circuitpython.md

Notes:
- Most display/UI dependencies are from the Adafruit bundle.
- This repository includes a local lib/ folder with the needed modules for device deployment.

<b>Run / Deploy Workflow</b>

Typical edit/test loop used during development:
1. Edit files in VS Code.
2. Copy updated runtime files to CIRCUITPY, for example in PowerShell:
	Copy-Item -Path .\code.py, .\adapters.py, .\game_engine.py, .\logic_core.py -Destination D:\ -Force
3. The board reloads code.py automatically after copy.
4. Test on device and review serial console output for debug and memory feedback.
