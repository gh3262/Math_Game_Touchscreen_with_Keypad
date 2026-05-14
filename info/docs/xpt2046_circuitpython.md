# module: xpt2046_circuitpython

## Touch
### Touch(spi, cs, interrupt, interrupt_pressed_value, width, height, x_min, x_max, y_min, y_max, force_baudrate)
Constructs a new XPT2046 touchscreen reader.
* **Args:**
    * spi (*busio.SPI*): SPI interface for OLED
    * cs (*digitalio.DigitalInOut*): Chip select pin
    * interrupt (*Optional: digitalio.DigitalInOut*) = `None`: Interrupt pin
    * interrupt_pressed_value (*Optional: bool*) = `False`: Expected value of the interrupt pin when the screen is touched. Only used if interrupt is provided.
    * width (*int*) = `240`: Width of LCD screen
    * height (*int*) = `320`: Height of LCD screen
    * x_min (*int*) = `100`: Minimum X coordinate (as provided by the display)
    * x_max (*int*) = `1900`: Maximum X coordinate (as provided by the display)
    * y_min (*int*) = `100`: Minimum Y coordinate (as provided by the display)
    * y_max (*int*) = `2100`: Maximum Y coordinate (as provided by the display)
    * force_baudrate (*Optional: int*) = `None`: If defined, the baudrate will be reset before TX over SPI. 
        * This is helpful if you're using a library (ie: Adafruit's ILI library) that also changes the baudrate before communicating. Keep in mind that most of these XPT chips start giving inaccurate readings beyond 1M, so I'd try to keep this around 100K if you need it.
* **Sample:**
    ```py
    import xpt2046_circuitpython
    from board import SCK, MOSI, MISO, D6, D22
    spi = busio.SPI(clock=SCK, MOSI=MOSI, MISO=MISO)

    # Create a basic touch controller
    touch = xpt2046_circuitpython.Touch(
        spi, 
        cs = digitalio.DigitalInOut(D6)
    )

    # Create a touch controller with interrupt handling and a forced 100K baudrate
    touch = xpt2046_circuitpython.Touch(
        spi, 
        cs = digitalio.DigitalInOut(D6),
        interrupt = digitalio.DigitalInOut(D22),
        force_baudrate = 100000
    )
    ```
---
### .get_coordinates(reading_count, timeout)
Reads (normalized) coordinates from the display. By default, this returns just one reading.
* **Args:**
    * reading_count (*Optional: int*) = `None`: Defines how many good readings to obtain from the XPT2046.
        * If this is defined, readings will be obtained every 0.05s until the specified number of samples are obtained and the average will be returned.
    * timeout (*Optional: float*) = `1`: Only used if poll_for is defined. Defines the maximum time that the screen should be polled for to get good samples before None is returned.
* **Returns:**
    * *Optional: Tuple[x: int, y: int]*: X/Y coordinates, if a reading was able to be obtained.
* **Raises:**
    * *ReadFailedException*: Unable to get a reading or timeout was reached
* **Sample:**
    ```py
    # Read one sample
    x, y = touch.get_coordinates()

    # Get a more accurate sample (average 5 samples together)
    x, y = touch.get_coordinates(reading_count = 5, timeout = 1)
    ```
---
### .is_pressed()
Checks if the display is pressed.
An interrupt pin must be specified during instantiation for this to work.
* **Returns:**
    * *bool*: True if the display is actively being pressed
* **Raises:**
    * *ReadFailedException*: Interrupt pin was not defined
---
## ReadFailedException
Exception for read failures.
* **Sample:**
    ```py
    import xpt2046_circuitpython

    try:
        touch.get_coordinates(reading_count = 5, timeout = 0.5)

    except xpt2046_circuitpython.ReadFailedException as e:
        print("Couldn't read coordinates!")
    ```