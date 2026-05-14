# Math Game Touchscreen with Keypad
CircuitPython project with an RP2350 and touchscreen used to drill students in basic math problems

<b>Hardware</b>
- Feather RP2350 (Developed with +PSRAM version but will optimize memory to use non-PSRAM version)
- 320x240 TFT touchscreen - 3.2" using ILI9431 SPI and xpt2046 touch controller (Amazon) also with an SD card slot. This display is available in several different sizes but are essentially pin compatable. 
- ds3231 real time clock module connected via I2C
- Piezo buzzer
- SD (or microSD with an adapter) card
- 8mm PL9823 Neopixel type LED
- Lipo batters
- spst switch for enablement
- 3d printed case with heat set brass inserts and screws

<b>Basic Design</b>
I wanted to make my grandchildren a "game box" that is educational and single purpose. Rather than an app on a phone or a tablet (I'm sure there are a lot) I wanted this to only do one thing - math drills - so there wasn't distraction to other things. The basic premise of the project is to generate random math questions (addition, subtraction and multiplication) and let them practice. Like a game it tracks the player's name and keeps a list of high scores. It also tracks how many correctly answered questions each player had acheived over time - where I can bribe them paying a small amount for x number of questions. 

The original design generated random problems using digits  0 to 12 and gave the player four multiple choice options. The logic generated three incorrect answers close to the real answere so the correct answer wasn't obvious from the choices. A later iteration of the game added a second mode for keypad entry - rather than multiple choice the player had to key in the correct answer with an on-screen keypad. 

In addition to the three problem types I added "Mixed" which would pull from all question banks. Players have a choice of 10, 20, 35 or 50 questions. 

Although we start with two names pre-programmed (these are on text files on the SD card), there is functionality to add additional names to the box so everyone can have their own scores. For this we created an on-screen keyboard which is a grid of 4x4. The top row are buttons for "LAST" [page], "BkSp", "ENTER", and "NEXT" [page]. The second row are the vowels A, E, I and O. These top two rows are constant. The consents, U and a space (underscore) are arranged on three pages. With this it is efficient to enter names without a lot of paging. 

The keypad entry page is a similar grid 4x3 with buttons for 1, 2, 3, BkSp; 4, 5, 6 Enter; 7, 8, 9, 0. Becasue the screen is wider than tall I thought this would be a better arrangement rather than a traditional 3x4 arrangement. 