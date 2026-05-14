"""
Simple drawing program using the Adafruit ILI9341 displayio library.
"""

import xpt2046_circuitpython
import time
import busio
import digitalio
import displayio
import fourwire
import terminalio
import board
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
import adafruit_ili9341
import adafruit_ds3231
import neopixel


# Pin config
CS_PIN = board.D6
DC_PIN = board.D10
LED_PIN = board.D11
RST_PIN = board.D9

T_CS_PIN = board.D12
PIXEL_PIN = board.NEOPIXEL

NUM_PIXELS = 1
pixels = neopixel.NeoPixel(PIXEL_PIN, NUM_PIXELS, brightness=0.2, auto_write=True)
pixels[0] = (0, 0, 255)
# Release any existing displays
displayio.release_displays()

# Initialize DS3231 RTC on STEMMA I2C and print current time.
try:
    i2c = board.STEMMA_I2C()
    rtc = adafruit_ds3231.DS3231(i2c)
    rtc_time = rtc.datetime
    print(
        "RTC time: {:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
            rtc_time.tm_year,
            rtc_time.tm_mon,
            rtc_time.tm_mday,
            rtc_time.tm_hour,
            rtc_time.tm_min,
            rtc_time.tm_sec,
        )
    )
except Exception as e:
    print("RTC init/read failed: {}".format(e))

# Set up SPI bus using hardware SPI
spi = busio.SPI(clock=board.SCK, MOSI=board.MOSI, MISO=board.MISO)
# Turn on the LED backlight
led = digitalio.DigitalInOut(LED_PIN)
led.direction = digitalio.Direction.OUTPUT
led.value = True
# Create the display bus and ILI9341 display
display_bus = fourwire.FourWire(spi, command=DC_PIN, chip_select=CS_PIN, reset=RST_PIN)
display = adafruit_ili9341.ILI9341(display_bus, width=320, height=240)

# Create the main display group
splash = displayio.Group()
display.root_group = splash

# Blue background
color_bitmap = displayio.Bitmap(320, 240, 1)
color_palette = displayio.Palette(1)
color_palette[0] = 0x0000FF
bg = displayio.TileGrid(color_bitmap, pixel_shader=color_palette)
splash.append(bg)

# "Touch Screen Test" label at the top
text_label = label.Label(terminalio.FONT, text="Touch Screen Test", color=0xFFFFFF, x=10, y=10)
splash.append(text_label)
print("Display initialized with size: {}x{}".format(display.width, display.height))
time.sleep(2)
# Create touch controller
#  The Adafruit library changes the baudrate to 16M whenever it runs.
#  The touchscreen yields very inaccurate readings at this rate. We'll
#  bump it back down to 100K.
touch = xpt2046_circuitpython.Touch(
    spi, 
    cs = digitalio.DigitalInOut(T_CS_PIN),
    width = 240,
    height = 320,
    x_min = 166,
    x_max = 1960,
    y_min = 162,
    y_max = 1974,
    force_baudrate = 100000
)
print("Touch controller initialized with size: {}x{}".format(touch.width, touch.height))

MAX_SQUARES = 120
SQUARE_SIZE = 20
CLEAR_ZONE_SIZE = 40
CLEAR_HOLD_SECONDS = 1.0
squares = []
clear_hold_start = None
clear_fired = False
touch_active = False
touch_colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
touch_color_index = 0

try:
    while True:
        try:
            tx, ty = touch.get_coordinates()
            if not touch_active:
                pixels[0] = touch_colors[touch_color_index]
                touch_color_index = (touch_color_index + 1) % len(touch_colors)
                touch_active = True

            draw_x = display.width - ty
            draw_y = touch.width - tx

            in_clear_zone = draw_x <= CLEAR_ZONE_SIZE and draw_y <= CLEAR_ZONE_SIZE
            now = time.monotonic()

            # Long-press in top-left corner clears all drawn squares.
            if in_clear_zone:
                if clear_hold_start is None:
                    clear_hold_start = now
                elif not clear_fired and (now - clear_hold_start) >= CLEAR_HOLD_SECONDS:
                    while squares:
                        splash.remove(squares.pop())
                    clear_fired = True
            else:
                clear_hold_start = None
                clear_fired = False

            if not clear_fired:
                square = Rect(
                    max(0, draw_x - (SQUARE_SIZE // 2)),
                    max(0, draw_y - (SQUARE_SIZE // 2)),
                    SQUARE_SIZE,
                    SQUARE_SIZE,
                    fill=0xFFFFFF,
                )
                splash.append(square)
                squares.append(square)

                if len(squares) > MAX_SQUARES:
                    splash.remove(squares.pop(0))
        except Exception:
            clear_hold_start = None
            clear_fired = False
            touch_active = False
        
        # Delay for a bit
        time.sleep(0.1)

except KeyboardInterrupt:
    led.value = False