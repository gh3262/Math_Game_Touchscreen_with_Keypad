"""
Driver module for the XPT2046 chip communicating over SPI.

Authors:
    github.com/rdagger      Original MicroPython library
    github.com/Luca8991     Initial CircuitPython port
    github.com/humeman      Pure CircuitPython port, packaging, compatibility, examples, and docs
"""
from time import sleep
import digitalio
import busio

from .exceptions import ReadFailedException

class Touch:
    """Serial interface for XPT2046 Touch Screen Controller."""

    # Command constants from ILI9341 datasheet
    GET_X = 0b11010000  # X position
    GET_Y = 0b10010000  # Y position

    def __init__(
        self, 
        spi, 
        cs,
        interrupt=None,
        interrupt_pressed_value=False,
        width=240, 
        height=320,
        x_min=100,
        x_max=1900,
        y_min=100, 
        y_max=2100,
        force_baudrate=None
    ):
        """
        Initializes the touch screen controller.

        Args:
            spi (busio.SPI):  SPI interface for OLED
            cs (digitalio.DigitalInOut):  Chip select pin
            interrupt (Optional: digitalio.DigitalInOut): Interrupt pin
            interrupt_pressed_value (Optional: bool): Expected value of the interrupt pin when the 
                screen is touched. Only used if interrupt is provided.
            width (int): Width of LCD screen
            height (int): Height of LCD screen
            x_min (int): Minimum X coordinate (as provided by the display)
            x_max (int): Maximum X coordinate (as provided by the display)
            y_min (int): Minimum Y coordinate (as provided by the display)
            y_max (int): Maximum Y coordinate (as provided by the display)
            force_baudrate (Optional: int): If defined, the baudrate will be reset before TX over SPI. 
                This is helpful if you're using a library (ie: Adafruit's ILI library) that also changes
                the baudrate before communicating. Keep in mind that most of these XPT chips start 
                giving inaccurate readings beyond 1M, so I'd try to keep this around 100K if you need it.
        """
        # SPI
        self.spi = spi

        # Chip select pin
        self.cs = cs
        self.cs.direction = digitalio.Direction.OUTPUT
        self.cs.value = True

        # Interrupt pin. XPT2046 IRQ is typically active-low.
        self.interrupt = interrupt
        if self.interrupt is not None:
            self.interrupt.direction = digitalio.Direction.INPUT
            self.interrupt.pull = digitalio.Pull.UP
        self.interrupt_pressed_value = interrupt_pressed_value

        # Transmit data
        self.rx_buf = bytearray(3)
        self.tx_buf = bytearray(3)

        # Display parameters
        self.width = width
        self.height = height
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        self.x_multiplier = width / (x_max - x_min)
        self.x_add = x_min * -self.x_multiplier
        self.y_multiplier = height / (y_max - y_min)
        self.y_add = y_min * -self.y_multiplier

        # Baudrate override
        self.force_baudrate = force_baudrate

    def get_coordinates(
        self,
        reading_count=None,
        timeout=1
    ):
        """
        Reads coordinates from the display.
        
        Args:
            reading_count (Optional: int): Defines how many good readings to obtain from the XPT2046.
                If this is defined, readings will be obtained every 0.05s until the specified number
                of samples are obtained and the average will be returned.
            timeout (Optional: float): Only used if poll_for is defined. Defines the maximum time that 
                the screen should be polled for to get good samples before None is returned.
        Returns:
            Optional: Tuple[x: int, y: int]: X/Y coordinates, if a reading was able to be obtained.
        Raises:
            ReadFailedException: Unable to get a reading or timeout was reached
        """

        if reading_count is not None:
            buff = [[0, 0] for x in range(reading_count)]
            buffptr = 0  # Track current buffer position
            nsamples = 0  # Count samples
            c_time = 0
            while c_time <= timeout:
                if nsamples == reading_count:
                    meanx = sum([c[0] for c in buff]) // reading_count
                    meany = sum([c[1] for c in buff]) // reading_count
                    dev = sum([(c[0] - meanx)**2 +
                            (c[1] - meany)**2 for c in buff]) / reading_count
                    if dev <= 50:  # Deviation should be under margin of 50
                        return self._normalize(meanx, meany)
                # get a new value
                sample = self._raw_touch()  # get a touch
                if sample is None:
                    nsamples = 0    # Invalidate buff
                else:
                    buff[buffptr] = sample  # put in buff
                    buffptr = (buffptr + 1) % reading_count  # Incr, until rollover
                    nsamples = min(nsamples + 1, reading_count)  # Incr. until max

                sleep(.05)
                c_time += .05
            raise ReadFailedException(f"Read timed out after {c_time}s.")

        return self._normalize(*self._raw_touch())

    def is_pressed(
        self
    ):
        """
        Checks if the display is pressed.
        An interrupt pin must be specified during instantiation for this to work.

        Returns:
            bool: True if the display is actively being pressed
        Raises:
            ReadFailedException: Interrupt pin was not defined
        """
        if self.interrupt is None:
            raise ReadFailedException("An interrupt pin must be defined before this can be used.")

        return self.interrupt.value == self.interrupt_pressed_value

    def _raw_touch(
        self
    ):
        """
        Read raw X,Y touch values.

        Returns:
            tuple(int, int): X, Y
        Raises:
            ReadFailedException: Unable to get a valid reading
        """
        x = self._send_command(self.GET_X)
        y = self._send_command(self.GET_Y)
        if self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max:
            return (x, y)
        else:
            raise ReadFailedException(f"Out-of-bounds reading returned from LCD: x={x}, y={y}")

    def _normalize(
        self, 
        x, 
        y
    ):
        """
        Normalize XY values to match LCD screen.
        
        Args:
            x: int
            y: int
        Returns:
            Tuple[x: int, y: int]: Normalized XY values 
        """
        x = int(self.x_multiplier * x + self.x_add)
        y = int(self.y_multiplier * y + self.y_add)
        return x, y

    def _send_command(
        self, 
        command
    ):
        """
        Writes a command to the XT2046.

        Args:
            command (byte): XT2046 command code.
        Returns:
            int: 12 bit response
        Raises:
            ReadFailedException: Unable to get a reading or timeout was reached
        """
        if not self.spi.try_lock():
            raise ReadFailedException("Failed to lock SPI bus. Is it in use?")

        try:
            if self.force_baudrate is not None and self.spi.frequency != self.force_baudrate:
                self.spi.configure(baudrate = self.force_baudrate)

            self.tx_buf[0] = command
            self.cs.value = False
            try:
                self.spi.write_readinto(self.tx_buf, self.rx_buf)
            except Exception as e:
                raise ReadFailedException("SPI transfer failed.") from e
            return (self.rx_buf[1] << 4) | (self.rx_buf[2] >> 4)
        finally:
            self.cs.value = True
            self.spi.unlock()    