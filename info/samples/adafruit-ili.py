"""
Simple drawing program using the Adafruit display library.
"""

import xpt2046_circuitpython
import time
import busio
import digitalio
#from board import SCK, MOSI, MISO, D5, D6, D22, D23, D24, D25
import board
from adafruit_rgb_display import color565
import adafruit_rgb_display.ili9341 as ili9341


# Pin config
CS_PIN = board.D6
DC_PIN = board.D10
LED_PIN = board.D11
RST_PIN = board.D9

T_CS_PIN = board.D12
T_IRQ_PIN = board.D13

# Set up SPI bus using hardware SPI
spi = busio.SPI(clock=board.SCK, MOSI=board.MOSI, MISO=board.MISO)
# Turn on the LED backlight
led = digitalio.DigitalInOut(LED_PIN)
led.direction = digitalio.Direction.OUTPUT
led.value = True
# Create the ILI9341 display
display = ili9341.ILI9341(spi, cs=digitalio.DigitalInOut(CS_PIN),
                          dc=digitalio.DigitalInOut(DC_PIN), 
                          rst=digitalio.DigitalInOut(RST_PIN))
# Create touch controller
#  The Adafruit library changes the baudrate to 16M whenever it runs.
#  The touchscreen yields very inaccurate readings at this rate. We'll
#  bump it back down to 100K.
touch = xpt2046_circuitpython.Touch(
    spi, 
    cs = digitalio.DigitalInOut(T_CS_PIN),
    interrupt = digitalio.DigitalInOut(T_IRQ_PIN),
    force_baudrate = 100000
)
print("Touch controller initialized with size: {}x{}".format(touch.width, touch.height))
try:
    # Clear the screen
    display.fill(color565(0, 0, 0))
        
    while True:
        # Check if we have an interrupt signal
        if touch.is_pressed():
            # Get the coordinates for this touch.
            x, y = touch.get_coordinates()
            # The Y reading is flipped to what the Adafruit library expects.
            y = touch.height - y

            display.fill_rectangle(max(0, x - 10), max(0, y - 10), 20, 20, color565(255, 255, 255))

        # Delay for a bit
        time.sleep(0.1)

except KeyboardInterrupt:
    led.value = False