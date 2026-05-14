import board
import gc
import time
import rtc
import digitalio
import pwmio
import xpt2046_circuitpython
try:
    import adafruit_ds3231
except ImportError:
    adafruit_ds3231 = None
try:
    from adafruit_pcf8523.pcf8523 import PCF8523
except ImportError:
    PCF8523 = None
import storage
import displayio
import fourwire
import os
import adafruit_ili9341
import sdcardio
import random
import neopixel
try:
	import logic_core
	import game_engine
	from adapters import DisplayIORendererAdapter, FilePersistenceAdapter, TouchInputAdapter
except ImportError:
	print("Warning: Some imports failed. If you're running this on a host machine for testing, this is expected. If you're running on the target hardware, please check that all necessary libraries are included.")
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import label
from adafruit_displayio_layout.layouts.page_layout import PageLayout

PORTS = {
	"renderer": DisplayIORendererAdapter(),
	"persistence": FilePersistenceAdapter(),
	"input": None,
}

displayio.release_displays()

spi = board.SPI()
tft_cs = board.D6
tft_dc = board.D10
tft_rst = board.D9
sd_cs = board.D5
t_cs = board.D13
led_pin = board.D12

# Turn on TFT backlight.
led = digitalio.DigitalInOut(led_pin)
led.direction = digitalio.Direction.OUTPUT
led.value = True

display_width = 320
display_height = 240

# Touch calibration raw values measured at screen corners.
TOUCH_X_MIN = 265
TOUCH_Y_MIN = 165
TOUCH_X_MAX = 3775
TOUCH_Y_MAX = 3850
TOUCH_PRESSURE_MIN = 150
TOUCH_Y_CALIBRATION = 10  # touch panel reads ~10px high; subtract to align with screen
ACCURACY_WEIGHTING = .7
TIME_WEIGHTING = 1.0 - ACCURACY_WEIGHTING
MIN_AVG_TIME = 2.5
MAX_AVG_TIME = 5.0
SCORE_FILE_PATH = "/sd/scores.txt"
PLAYER_FILE_PATH = "/sd/players.txt"
PLAYER_TEMPLATE_FILE_PATHS = ("/sd/tplayers.txt", "/tplayers.txt", "tplayers.txt")

SCREEN_WIDTH = display_width
SCREEN_HEIGHT = display_height
DISPLAY_ROTATION = 0

FONT_PATHS = {
	"button": "/fonts/ComicSansMS-19.pcf",
	"small_button": "/fonts/ComicSansMS-15.pcf",
	"title": "/fonts/EffectsEighty-32.pcf",
	"result": "/fonts/Calibri-29.pcf",
	"question": "/fonts/Calibri-38.pcf",
	"score": "/fonts/Calibri-17.pcf",
	"top_list": "/fonts/ComicSansMS-14.pcf",
}
FONTS = {}
for font_key in FONT_PATHS:
	FONTS[font_key] = bitmap_font.load_font(FONT_PATHS[font_key])

BUTTON_FONT = FONTS["button"]
SMALL_BUTTON_FONT = FONTS["small_button"]
TITLE_FONT = FONTS["title"]
R_FONT = FONTS["result"]
Q_FONT = FONTS["question"]
SCORE_FONT = FONTS["score"]
TOP_LIST_FONT = FONTS["top_list"]
TITLE_TEXT = "Math Game"
QUESTION_TEXT = "Tap Start to Begin"
TOP_SCORE_PAGE_LIMIT = 10
PLAYER_BUTTON_LIMIT = 4
PLAYER_NAME_PAGE_SIZE = 3
PLAYER_LOAD_RETRY_COUNT = 3
PLAYER_LOAD_RETRY_DELAY = 0.2
SCORE_LOAD_RETRY_COUNT = 3
SCORE_LOAD_RETRY_DELAY = 0.2
PLAYER_LOAD_FAILURE_COOLDOWN = 3.0
SCORE_LOAD_FAILURE_COOLDOWN = 3.0
PLAYER_FILE_PATHS = (PLAYER_FILE_PATH, "/players.txt", "players.txt")
MAX_PLAYER_NAME_LENGTH = 8
NAME_ENTRY_PAGE_COUNT = 3
NAME_ENTRY_LETTER_PAGES = (
	(("B", "C", "D", "F"), ("G", "H", "J", "K")),
	(("L", "M", "N", "P"), ("Q", "R", "S", "T")),
	(("U", "V", "W", "X"), ("Y", "Z", "_", "")),
)
DEBUG_FLOW = False
DEBUG_HELPER_TRANSITIONS = False
DEBUG_RUNTIME_SNAPSHOT_INTERVAL = 2.0
RTC_TYPE = "ds3231"  # Set to "pcf8523" or "ds3231" to match the installed RTC chip
SD_MOUNT_BAUDRATES = (4000000, 2000000, 1000000, 400000)
SCORE_TYPES = ("Addition", "Subtraction", "Multiplication", "Mixed")
SCORE_TYPE_LABEL = {
	"Addition": "Addition",
	"Subtraction": "Subtract",
	"Multiplication": "Multiply",
	"Mixed": "Mixed",
}

# Touch debouncing/release tuning.
TOUCH_DEBOUNCE_PRESS_COUNT = 2
TOUCH_RELEASE_IDLE_COUNT = 2

# --- Entry type points (magic numbers) ---
POINTS_PER_MC_PROBLEM = 0.01
POINTS_PER_KB_PROBLEM = 0.025

# Named color palette for all game UI elements.
UI_COLORS = {
	"background": 0x777777,
	"button_inner": 0x555577,
	"title_text": 0x00FF88,
	"text_primary": 0xFFFFFF,
	"result_text": 0xFFFF00,
	"answer_buttons": (0xAAAAFF, 0x44FF44, 0xFFFF44, 0xFF8888),
	"quit_button": 0xFF8888,
	"next_button": 0x0088FF,
	"name_entry": {
		"nav_flash": 0xFFFF44,
		"backspace_flash": 0xFF8888,
		"enter_flash": 0x44FF44,
		"fixed_row": 0xFFBBBB,
		"changing_row": 0xAAAAFF,
		"header_text": 0xFFFFFF,
		"value_text": 0xFFFF00,
		"theme_header_text": 0x88FFFF,
		"theme_value_text": 0x00FF88,
	},
}

COLOR_BACKGROUND = UI_COLORS["background"]
COLOR_BUTTON_INNER = UI_COLORS["button_inner"]
COLOR_TITLE_TEXT = UI_COLORS["title_text"]
COLOR_TEXT_PRIMARY = UI_COLORS["text_primary"]
COLOR_RESULT_TEXT = UI_COLORS["result_text"]
COLOR_ANSWER_BUTTON_1 = UI_COLORS["answer_buttons"][0]
COLOR_ANSWER_BUTTON_2 = UI_COLORS["answer_buttons"][1]
COLOR_ANSWER_BUTTON_3 = UI_COLORS["answer_buttons"][2]
COLOR_ANSWER_BUTTON_4 = UI_COLORS["answer_buttons"][3]
COLOR_QUIT_BUTTON = UI_COLORS["quit_button"]
COLOR_NEXT_BUTTON = UI_COLORS["next_button"]
COLOR_BUTTON_PRESSED = COLOR_TEXT_PRIMARY
COLOR_NAME_ENTRY_NAV_FLASH = UI_COLORS["name_entry"]["nav_flash"]
COLOR_NAME_ENTRY_BACKSPACE_FLASH = UI_COLORS["name_entry"]["backspace_flash"]
COLOR_NAME_ENTRY_ENTER_FLASH = UI_COLORS["name_entry"]["enter_flash"]
COLOR_NAME_ENTRY_FIXED_ROW = UI_COLORS["name_entry"]["fixed_row"]
COLOR_NAME_ENTRY_CHANGING_ROW = UI_COLORS["name_entry"]["changing_row"]
COLOR_NAME_ENTRY_HEADER_TEXT = UI_COLORS["name_entry"]["header_text"]
COLOR_NAME_ENTRY_VALUE_TEXT = UI_COLORS["name_entry"]["value_text"]
COLOR_NAME_ENTRY_THEME_HEADER_TEXT = UI_COLORS["name_entry"]["theme_header_text"]
COLOR_NAME_ENTRY_THEME_VALUE_TEXT = UI_COLORS["name_entry"]["theme_value_text"]

ANSWER_BUTTON_COLORS = (
	COLOR_ANSWER_BUTTON_1,
	COLOR_ANSWER_BUTTON_2,
	COLOR_ANSWER_BUTTON_3,
	COLOR_ANSWER_BUTTON_4,
)

# Grouped UI layout values keep sizing/margins in one place.
UI_LAYOUT = {
	"top_button": {
		"width": 60,
		"height": 40,
		"margin": 5,
	},
	"answer_bar": {
		"height": 60,
		"count": 4,
		"start_x": 5,
		"bottom_margin": 35,
		"y_offset": 10,
	},
	"name_entry": {
		"text_height": 50,
		"button_width": 75,
		"button_height": 45,
		"columns": 4,
		"top_padding": 5,
	},
}

# Top button config.
TOP_BUTTON_WIDTH = UI_LAYOUT["top_button"]["width"]
TOP_BUTTON_HEIGHT = UI_LAYOUT["top_button"]["height"]
TOP_BUTTON_MARGIN = UI_LAYOUT["top_button"]["margin"]

# Bottom button bar config.
BUTTON_HEIGHT = UI_LAYOUT["answer_bar"]["height"]
BUTTON_COUNT = UI_LAYOUT["answer_bar"]["count"]
BUTTON_START_X = UI_LAYOUT["answer_bar"]["start_x"]
BUTTON_BOTTOM_MARGIN = UI_LAYOUT["answer_bar"]["bottom_margin"]
BUTTON_WIDTH = (SCREEN_WIDTH // BUTTON_COUNT) - 2
BUTTON_TOP = SCREEN_HEIGHT - BUTTON_HEIGHT - BUTTON_BOTTOM_MARGIN
ANSWER_BUTTON_Y_OFFSET = UI_LAYOUT["answer_bar"]["y_offset"]
ANSWER_BUTTON_TOP = BUTTON_TOP + ANSWER_BUTTON_Y_OFFSET
BUFFER_TOP = BUTTON_TOP + BUTTON_HEIGHT
NAME_ENTRY_TEXT_HEIGHT = UI_LAYOUT["name_entry"]["text_height"]
NAME_ENTRY_BUTTON_WIDTH = UI_LAYOUT["name_entry"]["button_width"]
NAME_ENTRY_BUTTON_HEIGHT = UI_LAYOUT["name_entry"]["button_height"]
NAME_ENTRY_GRID_X = (SCREEN_WIDTH - (NAME_ENTRY_BUTTON_WIDTH * UI_LAYOUT["name_entry"]["columns"])) // 2
NAME_ENTRY_GRID_Y = NAME_ENTRY_TEXT_HEIGHT + UI_LAYOUT["name_entry"]["top_padding"]

KB_KEYPAD_MARGIN_X = 20
KB_KEYPAD_COLUMNS = 4
KB_KEYPAD_ROWS = 3
KB_KEYPAD_GAP_X = 4
KB_KEYPAD_GAP_Y = 4
KB_KEYPAD_TOP = 85
KB_KEYPAD_BOTTOM = 220
KB_KEYPAD_BUTTON_WIDTH = (
	SCREEN_WIDTH
	- (2 * KB_KEYPAD_MARGIN_X)
	- ((KB_KEYPAD_COLUMNS - 1) * KB_KEYPAD_GAP_X)
) // KB_KEYPAD_COLUMNS
KB_KEYPAD_BUTTON_HEIGHT = (
	(KB_KEYPAD_BOTTOM - KB_KEYPAD_TOP)
	- ((KB_KEYPAD_ROWS - 1) * KB_KEYPAD_GAP_Y)
) // KB_KEYPAD_ROWS
KB_CORRECT_PAUSE_SECONDS = 0.5
KB_WRONG_PAUSE_SECONDS = 1.0
KB_ENTRY_MAX_DIGITS = 3


def debug_i2c_scan(i2c_bus):
	if not DEBUG_FLOW:
		return
	print("[I2C] Scanning bus...")
	while not i2c_bus.try_lock():
		pass
	try:
		addresses = i2c_bus.scan()
	finally:
		i2c_bus.unlock()
	if addresses:
		for addr in addresses:
			print("[I2C] Found device at 0x{:02X} ({})".format(addr, addr))
		print("[I2C] Scan complete. {} device(s) found.".format(len(addresses)))
	else:
		print("[I2C] Scan complete. No devices found.")


def create_sdcard_with_baudrate(baudrate):
	try:
		return sdcardio.SDCard(spi, sd_cs, baudrate=baudrate)
	except TypeError:
		# Older CircuitPython builds may not expose the baudrate keyword.
		return sdcardio.SDCard(spi, sd_cs)


def mount_sd_with_retries():
	last_error = ""
	for baudrate in SD_MOUNT_BAUDRATES:
		try:
			sdcard = create_sdcard_with_baudrate(baudrate)
			vfs = storage.VfsFat(sdcard)
			storage.mount(vfs, "/sd")
			return True, ""
		except Exception as exc:
			last_error = repr(exc)

	return False, last_error


def build_problem(a, b, operator):
	return logic_core.build_problem(a, b, operator)


def build_problem_set(operator, count=None):
	return logic_core.build_problem_set(operator, count)


def tag_problem_set(problem_set, operator_symbol):
	return logic_core.tag_problem_set(problem_set, operator_symbol)

def touch_to_pixel(raw_x, raw_y):
	"""Map normalized XPT2046 coordinates to display pixels."""
	x = display_width - raw_y
	y = display_height - raw_x - TOUCH_Y_CALIBRATION

	if x < 0:
		x = 0
	elif x >= display_width:
		x = display_width - 1

	if y < 0:
		y = 0
	elif y >= display_height:
		y = display_height - 1

	return x, y

def make_rect(x, y, width, height, color):
	"""Create a solid rectangle TileGrid using displayio primitives only."""
	bitmap = displayio.Bitmap(width, height, 1)
	palette = displayio.Palette(1)
	palette[0] = color
	return displayio.TileGrid(bitmap, pixel_shader=palette, x=x, y=y)


def make_rect_with_palette(x, y, width, height, color):
	"""Create a rectangle TileGrid and return it with its palette for fast recoloring."""
	bitmap = displayio.Bitmap(width, height, 1)
	palette = displayio.Palette(1)
	palette[0] = color
	return displayio.TileGrid(bitmap, pixel_shader=palette, x=x, y=y), palette


def add_button(parent_group, page_name, x, y, width, height, outline_color, text, font, name, role="action"):
	button_group = displayio.Group(x=x, y=y)
	button_fill, button_fill_palette = make_rect_with_palette(0, 0, width, height, outline_color)
	button_group.append(button_fill)
	button_group.append(make_rect(1, 1, width - 2, height - 2, COLOR_BUTTON_INNER))
	text_label = label.Label(
		font,
		text=text,
		color=outline_color,
	)
	text_label.anchor_point = (0.5, 0.5)
	text_label.anchored_position = (width // 2, height // 2)
	button_group.append(text_label)
	button = {
		"name": name,
		"role": role,
		"page": page_name,
		"x0": x,
		"x1": x + width,
		"y0": y,
		"y1": y + height,
		"width": width,
		"height": height,
		"group": button_group,
		"fill_palette": button_fill_palette,
		"label": text_label,
		"base_color": outline_color,
	}
	buttons.append(button)
	parent_group.append(button_group)
	return button

try:
	if "/sd" not in os.listdir("/"):
		mounted, mount_error = mount_sd_with_retries()
		if not mounted:
			raise OSError("SD mount failed after retries: {}".format(mount_error))
except Exception as exc:
	raise OSError("SD mount failed: {}".format(exc))

displaybus = fourwire.FourWire(
	spi, command=tft_dc, chip_select=tft_cs, reset=tft_rst)

display = adafruit_ili9341.ILI9341(
	displaybus, width=display_width, height=display_height, rotation=DISPLAY_ROTATION
)

game_page_layout = PageLayout(x=0, y=0)
game_page_group = displayio.Group()
game_kb_page_group = displayio.Group()
score_page_group = displayio.Group()
name_entry_page_group = displayio.Group()
game_page_layout.add_content(game_page_group, page_name="game_mc")
game_page_layout.add_content(game_kb_page_group, page_name="game_kb")
game_page_layout.add_content(score_page_group, page_name="score")
game_page_layout.add_content(name_entry_page_group, page_name="name_entry")
display.root_group = game_page_layout

i2c = board.I2C()

debug_i2c_scan(i2c)
xpt_cs = digitalio.DigitalInOut(t_cs)
ts_raw = xpt2046_circuitpython.Touch(
	spi,
	cs=xpt_cs,
	width=240,
	height=320,
	x_min=166,
	x_max=1960,
	y_min=162,
	y_max=1974,
	force_baudrate=100000,
)


class XPTTouchAdapter:
	"""Expose XPT2046 readings with the same interface expected by TouchInputAdapter."""

	def __init__(self, xpt_touch):
		self._xpt = xpt_touch
		self._last = None

	@property
	def touched(self):
		try:
			self._last = self._xpt.get_coordinates()
			return self._last is not None
		except Exception:
			self._last = None
			return False

	@property
	def touch(self):
		if self._last is None:
			return {"x": 0, "y": 0, "pressure": 0}
		return {"x": self._last[0], "y": self._last[1], "pressure": 1000}


ts = XPTTouchAdapter(ts_raw)

px = neopixel.NeoPixel(board.D24, 1, brightness=0.1, auto_write=True, pixel_order=neopixel.RGB)

AUDIO_LED_CONFIG = {
	"led": {
		"off": (0, 0, 0),
		"blue": (0, 0, 255),
		"green": (0, 255, 0),
		"red": (255, 0, 0),
		"yellow": (255, 128, 0),
		"magenta": (255, 0, 255),
		"feedback_off_seconds": 0.25,
	},
	"buzzer": {
		"startup_frequency": 440,
		"startup_duration": 0.5,
		"duty_cycle": 32768,
		"correct_frequency": 840,
		"correct_duration": 0.20,
		"wrong_frequency": 200,
		"wrong_duration": 1.0,
		"digit_frequency": 560,
		"digit_duration": 0.06,
		"skip_frequency": 500,
		"skip_beep_duration": 0.1,
		"skip_gap_duration": 0.06,
	},
}

LED_COLOR_OFF = AUDIO_LED_CONFIG["led"]["off"]
LED_COLOR_BLUE = AUDIO_LED_CONFIG["led"]["blue"]
LED_COLOR_GREEN = AUDIO_LED_CONFIG["led"]["green"]
LED_COLOR_RED = AUDIO_LED_CONFIG["led"]["red"]
LED_COLOR_YELLOW = AUDIO_LED_CONFIG["led"]["yellow"]
LED_COLOR_MAGENTA = AUDIO_LED_CONFIG["led"]["magenta"]
LED_FEEDBACK_OFF_SECONDS = AUDIO_LED_CONFIG["led"]["feedback_off_seconds"]
BUZZER_STARTUP_FREQUENCY = AUDIO_LED_CONFIG["buzzer"]["startup_frequency"]
BUZZER_STARTUP_DURATION = AUDIO_LED_CONFIG["buzzer"]["startup_duration"]
BUZZER_DUTY_CYCLE = AUDIO_LED_CONFIG["buzzer"]["duty_cycle"]
BUZZER_CORRECT_FREQUENCY = AUDIO_LED_CONFIG["buzzer"]["correct_frequency"]
BUZZER_CORRECT_DURATION = AUDIO_LED_CONFIG["buzzer"]["correct_duration"]
BUZZER_WRONG_FREQUENCY = AUDIO_LED_CONFIG["buzzer"]["wrong_frequency"]
BUZZER_WRONG_DURATION = AUDIO_LED_CONFIG["buzzer"]["wrong_duration"]
BUZZER_DIGIT_FREQUENCY = AUDIO_LED_CONFIG["buzzer"]["digit_frequency"]
BUZZER_DIGIT_DURATION = AUDIO_LED_CONFIG["buzzer"]["digit_duration"]
BUZZER_SKIP_FREQUENCY = AUDIO_LED_CONFIG["buzzer"]["skip_frequency"]
BUZZER_SKIP_BEEP_DURATION = AUDIO_LED_CONFIG["buzzer"]["skip_beep_duration"]
BUZZER_SKIP_GAP_DURATION = AUDIO_LED_CONFIG["buzzer"]["skip_gap_duration"]

DEFAULT_RTC_DATETIME = time.struct_time((2026, 1, 1, 12, 0, 0, 3, -1, -1))
system_rtc = rtc.RTC()
crt = None
buzzer_tx = None
buzzer_pattern = ()
buzzer_pattern_index = 0
buzzer_step_deadline = 0.0

try:
	buzzer_tx = pwmio.PWMOut(board.TX, duty_cycle=0, frequency=BUZZER_STARTUP_FREQUENCY, variable_frequency=True)
except Exception as exc:
	print("Buzzer TX PWM init failed:", exc)

if RTC_TYPE == "ds3231" and adafruit_ds3231 is not None:
	try:
		crt = adafruit_ds3231.DS3231(i2c)
		system_rtc.datetime = crt.datetime
		print("DS3231 RTC initialized. Date and time:", system_rtc.datetime)
	except Exception as exc:
		print("DS3231 init failed:", exc)
		crt = None
elif RTC_TYPE == "pcf8523" and PCF8523 is not None:
	try:
		crt = PCF8523(i2c)
		system_rtc.datetime = crt.datetime
		print("PCF8523 RTC initialized. Date and time:", system_rtc.datetime)
	except Exception as exc:
		print("PCF8523 init failed:", exc)
		crt = None
else:
	print("RTC_TYPE '{}' not recognized or library missing.".format(RTC_TYPE))

if crt is None:
	system_rtc.datetime = DEFAULT_RTC_DATETIME
	print("Using fallback time:", system_rtc.datetime)

if False:  # change to True if you want to set the time!
	#                     year, mon, date, hour, min, sec, wday, yday, isdst
	t = time.struct_time((2026, 5, 13, 10, 50, 00, 3, -1, -1))
	# you must set year, mon, date, hour, min, sec and weekday
	# yearday is not supported, isdst can be set but we don't do anything with it at this time
	print("Setting time to:", t)
	system_rtc.datetime = t
	if crt is not None:
		crt.datetime = t

def set_status_led(color):
	global led_flash_active, led_flash_deadline, led_flash_color
	led_flash_active = False
	led_flash_deadline = 0.0
	led_flash_color = color
	px[0] = color


def flash_status_led(color, off_seconds=LED_FEEDBACK_OFF_SECONDS):
	global led_flash_active, led_flash_deadline, led_flash_color
	led_flash_color = color
	led_flash_active = True
	led_flash_deadline = time.monotonic() + off_seconds
	px[0] = LED_COLOR_OFF


def update_status_led():
	global led_flash_active
	if not led_flash_active:
		return
	if time.monotonic() < led_flash_deadline:
		return
	led_flash_active = False
	px[0] = led_flash_color


def stop_buzzer():
	global buzzer_pattern, buzzer_pattern_index, buzzer_step_deadline
	if buzzer_tx is not None:
		buzzer_tx.duty_cycle = 0
	buzzer_pattern = ()
	buzzer_pattern_index = 0
	buzzer_step_deadline = 0.0


def start_buzzer_tone(frequency):
	if buzzer_tx is None:
		return False

	buzzer_tx.frequency = frequency
	buzzer_tx.duty_cycle = BUZZER_DUTY_CYCLE
	return True


def advance_buzzer_pattern():
	global buzzer_pattern, buzzer_pattern_index, buzzer_step_deadline
	if buzzer_pattern_index >= len(buzzer_pattern):
		stop_buzzer()
		return

	frequency, duration = buzzer_pattern[buzzer_pattern_index]
	buzzer_pattern_index += 1
	if frequency is None or frequency <= 0:
		if buzzer_tx is not None:
			buzzer_tx.duty_cycle = 0
	else:
		start_buzzer_tone(frequency)
	buzzer_step_deadline = time.monotonic() + duration


def play_buzzer_pattern(pattern):
	global buzzer_pattern, buzzer_pattern_index, buzzer_step_deadline
	if buzzer_tx is None:
		return

	buzzer_pattern = pattern
	buzzer_pattern_index = 0
	buzzer_step_deadline = 0.0
	advance_buzzer_pattern()


def update_buzzer():
	if not buzzer_pattern:
		return
	if time.monotonic() >= buzzer_step_deadline:
		advance_buzzer_pattern()


def play_buzzer_tone(frequency, duration):
	if not start_buzzer_tone(frequency):
		return
	time.sleep(duration)

	stop_buzzer()


set_status_led(LED_COLOR_RED)

addition = build_problem_set("+")
multiplication = build_problem_set("*")
subtraction = build_problem_set("-")
addition_mixed = tag_problem_set(addition, "+")
subtraction_mixed = tag_problem_set(subtraction, "-")
multiplication_mixed = tag_problem_set(multiplication, "*")

# Full-screen background.
game_page_group.append(make_rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_BACKGROUND))
game_kb_page_group.append(make_rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_BACKGROUND))
score_page_group.append(make_rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_BACKGROUND))
name_entry_page_group.append(make_rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_BACKGROUND))

title_label = label.Label(
	TITLE_FONT,
	text=TITLE_TEXT,
	color=COLOR_TITLE_TEXT,
)
title_label.anchor_point = (0.5, 0.0)
title_label.anchored_position = (SCREEN_WIDTH // 2, 5)
game_page_group.append(title_label)

game_kb_title_label = label.Label(
	TITLE_FONT,
	text=TITLE_TEXT,
	color=COLOR_TITLE_TEXT,
)
game_kb_title_label.anchor_point = (0.5, 0.0)
game_kb_title_label.anchored_position = (SCREEN_WIDTH // 2, 5)
game_kb_page_group.append(game_kb_title_label)

question_label = label.Label(
	Q_FONT,
	text=QUESTION_TEXT,
	color=COLOR_TEXT_PRIMARY,
)
question_label.anchor_point = (0.5, 0.5)
question_label.anchored_position = (SCREEN_WIDTH // 2, 70)
game_page_group.append(question_label)

game_kb_question_label = label.Label(
	Q_FONT,
	text=QUESTION_TEXT,
	color=COLOR_TEXT_PRIMARY,
)
game_kb_question_label.anchor_point = (0.5, 0.5)
game_kb_question_label.anchored_position = (SCREEN_WIDTH // 3, 61)
game_kb_page_group.append(game_kb_question_label)

game_kb_entry_label = label.Label(
	Q_FONT,
	text="",
	color=COLOR_RESULT_TEXT,
)
game_kb_entry_label.anchor_point = (0.5, 0.5)
game_kb_entry_label.anchored_position = ((SCREEN_WIDTH * 2) // 3, 61)
game_kb_page_group.append(game_kb_entry_label)

result_label = label.Label(
	R_FONT,
	text="Your answer is...",
	color=COLOR_RESULT_TEXT,
)
result_label.anchor_point = (0.5, 0.5)
result_label.anchored_position = (SCREEN_WIDTH // 2, 110)
game_page_group.append(result_label)

game_kb_result_label = label.Label(
	R_FONT,
	text="Your answer is...",
	color=COLOR_RESULT_TEXT,
)
game_kb_result_label.anchor_point = (0.5, 0.5)
game_kb_result_label.anchored_position = (SCREEN_WIDTH // 2, 110)
game_kb_page_group.append(game_kb_result_label)

score_title_label = label.Label(
	TITLE_FONT,
	text="Score",
	color=COLOR_TITLE_TEXT,
)
score_title_label.anchor_point = (0.5, 0.0)
score_title_label.anchored_position = (SCREEN_WIDTH // 2, 5)
score_page_group.append(score_title_label)

score_question_label = label.Label(
	SCORE_FONT,
	text="",
	color=COLOR_TEXT_PRIMARY,
)
score_question_label.anchor_point = (0.0, 0.0)
score_question_label.anchored_position = (5, 48)
score_page_group.append(score_question_label)

score_result_label = label.Label(
	SCORE_FONT,
	text="",
	color=COLOR_RESULT_TEXT,
)
score_result_label.anchor_point = (0.0, 0.0)
score_result_label.anchored_position = (5, 68)
score_page_group.append(score_result_label)

name_entry_instruction_label = label.Label(
	SCORE_FONT,
	text="Enter new name",
	color=COLOR_NAME_ENTRY_HEADER_TEXT,
)
name_entry_instruction_label.anchor_point = (0.5, 0.0)
name_entry_instruction_label.anchored_position = (SCREEN_WIDTH // 2, 6)
name_entry_page_group.append(name_entry_instruction_label)

name_entry_value_label = label.Label(
	BUTTON_FONT,
	text="_",
	color=COLOR_NAME_ENTRY_VALUE_TEXT,
)
name_entry_value_label.anchor_point = (0.5, 0.0)
name_entry_value_label.anchored_position = (SCREEN_WIDTH // 2, 24)
name_entry_page_group.append(name_entry_value_label)


# Draw four buttons along the bottom.
button_colors = ANSWER_BUTTON_COLORS
buttons = []
answer_buttons = []
name_entry_buttons = []
game_kb_keypad_buttons = []

quit_button = add_button(
	game_page_group,
	"game_mc",
	TOP_BUTTON_MARGIN,
	TOP_BUTTON_MARGIN,
	TOP_BUTTON_WIDTH,
	TOP_BUTTON_HEIGHT,
	COLOR_QUIT_BUTTON,
	"Start",
	SMALL_BUTTON_FONT,
	"Quit",
	"quit",
)
game_kb_quit_button = add_button(
	game_kb_page_group,
	"game_kb",
	TOP_BUTTON_MARGIN,
	TOP_BUTTON_MARGIN,
	TOP_BUTTON_WIDTH,
	TOP_BUTTON_HEIGHT,
	COLOR_QUIT_BUTTON,
	"Start",
	SMALL_BUTTON_FONT,
	"KB Quit",
	"quit",
)
next_button = add_button(
	game_page_group,
	"game_mc",
	SCREEN_WIDTH - TOP_BUTTON_MARGIN - TOP_BUTTON_WIDTH,
	TOP_BUTTON_MARGIN,
	TOP_BUTTON_WIDTH,
	TOP_BUTTON_HEIGHT,
	COLOR_NEXT_BUTTON,
	"Next",
	SMALL_BUTTON_FONT,
	"Next",
	"next",
)
game_kb_next_button = add_button(
	game_kb_page_group,
	"game_kb",
	SCREEN_WIDTH - TOP_BUTTON_MARGIN - TOP_BUTTON_WIDTH,
	TOP_BUTTON_MARGIN,
	TOP_BUTTON_WIDTH,
	TOP_BUTTON_HEIGHT,
	COLOR_NEXT_BUTTON,
	"Next",
	SMALL_BUTTON_FONT,
	"KB Next",
	"next",
)

game_kb_keypad_layout = (
	("1", "2", "3", "BkSp"),
	("4", "5", "6", "Enter"),
	("7", "8", "9", "0"),
)
for row in range(KB_KEYPAD_ROWS):
	for col in range(KB_KEYPAD_COLUMNS):
		button_text = game_kb_keypad_layout[row][col]
		button_color = COLOR_ANSWER_BUTTON_1
		if button_text == "BkSp":
			button_color = COLOR_ANSWER_BUTTON_3
		elif button_text == "Enter":
			button_color = COLOR_ANSWER_BUTTON_2

		keypad_button = add_button(
			game_kb_page_group,
			"game_kb",
			KB_KEYPAD_MARGIN_X + (col * (KB_KEYPAD_BUTTON_WIDTH + KB_KEYPAD_GAP_X)),
			KB_KEYPAD_TOP + (row * (KB_KEYPAD_BUTTON_HEIGHT + KB_KEYPAD_GAP_Y)),
			KB_KEYPAD_BUTTON_WIDTH,
			KB_KEYPAD_BUTTON_HEIGHT,
			button_color,
			button_text,
			SMALL_BUTTON_FONT,
			"KB {}".format(button_text),
			"kb_entry",
		)
		game_kb_keypad_buttons.append(keypad_button)

for i in range(BUTTON_COUNT):
	x = BUTTON_START_X + (i * BUTTON_WIDTH)
	answer_button = add_button(
		game_page_group,
		"game_mc",
		x,
		ANSWER_BUTTON_TOP,
		BUTTON_WIDTH,
		BUTTON_HEIGHT,
		button_colors[i],
		"",
		BUTTON_FONT,
		"Button {}".format(i + 1),
		"answer",
	)
	answer_buttons.append(answer_button)

score_quit_button = add_button(
	score_page_group,
	"score",
	TOP_BUTTON_MARGIN,
	TOP_BUTTON_MARGIN,
	TOP_BUTTON_WIDTH,
	TOP_BUTTON_HEIGHT,
	COLOR_QUIT_BUTTON,
	"Start",
	SMALL_BUTTON_FONT,
	"Score Quit",
	"quit",
)
score_next_button = add_button(
	score_page_group,
	"score",
	SCREEN_WIDTH - TOP_BUTTON_MARGIN - TOP_BUTTON_WIDTH,
	TOP_BUTTON_MARGIN,
	TOP_BUTTON_WIDTH,
	TOP_BUTTON_HEIGHT,
	COLOR_NEXT_BUTTON,
	"Next",
	SMALL_BUTTON_FONT,
	"Score Next",
	"next",
)

name_entry_button_labels = (
	"LAST", "BkSp", "ENTER", "NEXT",
	"A", "E", "I", "O",
	"", "", "", "",
	"", "", "", "",
)
for i in range(len(name_entry_button_labels)):
	row = i // 4
	col = i % 4
	if row < 2:
		row_color = COLOR_NAME_ENTRY_FIXED_ROW
	else:
		row_color = COLOR_NAME_ENTRY_CHANGING_ROW
	name_entry_button = add_button(
		name_entry_page_group,
		"name_entry",
		NAME_ENTRY_GRID_X + (col * NAME_ENTRY_BUTTON_WIDTH),
		NAME_ENTRY_GRID_Y + (row * NAME_ENTRY_BUTTON_HEIGHT),
		NAME_ENTRY_BUTTON_WIDTH,
		NAME_ENTRY_BUTTON_HEIGHT,
		row_color,
		name_entry_button_labels[i],
		SMALL_BUTTON_FONT,
		"Name Entry {}".format(i + 1),
		"name_entry",
	)
	name_entry_buttons.append(name_entry_button)

# Two score labels in the bottom buffer.
buffer_top_y = BUFFER_TOP + 5
buffer_bottom_y = BUFFER_TOP + 20
left_column_x = 5
right_column_x = (SCREEN_WIDTH // 2) + 5

total_time_label = label.Label(
	SCORE_FONT,
	text="time 00:00",
	color=COLOR_TEXT_PRIMARY,
)
total_time_label.anchor_point = (0.0, 0.0)
total_time_label.anchored_position = (left_column_x, buffer_bottom_y)
game_page_group.append(total_time_label)

game_kb_total_time_label = label.Label(
	SCORE_FONT,
	text="time 00:00",
	color=COLOR_TEXT_PRIMARY,
)
game_kb_total_time_label.anchor_point = (0.0, 0.0)
game_kb_total_time_label.anchored_position = (left_column_x, buffer_bottom_y)
game_kb_page_group.append(game_kb_total_time_label)

nbr_q_label = label.Label(
	SCORE_FONT,
	text="0 / 0 / 0",
	color=COLOR_TEXT_PRIMARY,
)
nbr_q_label.anchor_point = (0.0, 0.0)
nbr_q_label.anchored_position = (right_column_x, buffer_bottom_y)
game_page_group.append(nbr_q_label)

game_kb_nbr_q_label = label.Label(
	SCORE_FONT,
	text="0 / 0 / 0",
	color=COLOR_TEXT_PRIMARY,
)
game_kb_nbr_q_label.anchor_point = (0.0, 0.0)
game_kb_nbr_q_label.anchored_position = (right_column_x, buffer_bottom_y)
game_kb_page_group.append(game_kb_nbr_q_label)

game_time_label = label.Label(
	SCORE_FONT,
	text="13:00",
	color=COLOR_TEXT_PRIMARY,
)
game_time_label.anchor_point = (1.0, 0.0)
game_time_label.anchored_position = (display.width - 5, buffer_bottom_y)
game_page_group.append(game_time_label)

game_kb_game_time_label = label.Label(
	SCORE_FONT,
	text="13:00",
	color=COLOR_TEXT_PRIMARY,
)
game_kb_game_time_label.anchor_point = (1.0, 0.0)
game_kb_game_time_label.anchored_position = (display.width - 5, buffer_bottom_y)
game_kb_page_group.append(game_kb_game_time_label)

time_label = label.Label(
	SCORE_FONT,
	text="13:00",
	color=COLOR_TEXT_PRIMARY,
)
time_label.anchor_point = (1.0, 0.0)
time_label.anchored_position = (display.width - 5, buffer_bottom_y)
score_page_group.append(time_label)

comparison_labels = []
for i in range(8):
	line_label = label.Label(
		SCORE_FONT,
		text="",
		color=COLOR_TEXT_PRIMARY,
	)
	line_label.anchor_point = (0.0, 0.0)
	if i % 2 == 0:
		line_label.anchored_position = (5, 72 + (i * 18))
		line_label.color = COLOR_RESULT_TEXT
	else:
		line_label.anchored_position = (20, 72 + (i * 18))
		line_label.color = COLOR_TEXT_PRIMARY
	comparison_labels.append(line_label)
	score_page_group.append(line_label)

top_score_labels = []
for i in range(TOP_SCORE_PAGE_LIMIT):
	line_label = label.Label(
		TOP_LIST_FONT,
		text="",
		color=COLOR_TEXT_PRIMARY,
	)
	line_label.anchor_point = (0.0, 0.0)
	line_label.anchored_position = (5, 75 + (i * 15))
	top_score_labels.append(line_label)
	score_page_group.append(line_label)

game_page_layout.show_page("game_mc")


def set_button_color(button, color):
	"""Update button color without allocating new display objects."""
	PORTS["renderer"].set_button_color(button, color)


def pressed_button_color(button):
	if button["role"] != "name_entry":
		return COLOR_BUTTON_PRESSED

	button_text = button["label"].text
	if button_text == "ENTER":
		return COLOR_NAME_ENTRY_ENTER_FLASH
	if button_text == "BkSp":
		return COLOR_NAME_ENTRY_BACKSPACE_FLASH
	if button_text in ("LAST", "NEXT"):
		return COLOR_NAME_ENTRY_NAV_FLASH
	return COLOR_BUTTON_PRESSED


def set_button_text(button, text):
	PORTS["renderer"].set_button_text(button, text)


def set_label_text_if_changed(target_label, text):
	return PORTS["renderer"].set_label_text_if_changed(target_label, text)


def open_text_read(file_path):
	return PORTS["persistence"].open_read(file_path)


def open_text_write(file_path):
	return PORTS["persistence"].open_write(file_path)


def open_text_append(file_path):
	return PORTS["persistence"].open_append(file_path)


def set_name_entry_top_line_colors(header_color, value_color):
	"""Set colors for the top two lines on the name-entry page."""
	name_entry_instruction_label.color = header_color
	name_entry_value_label.color = value_color


def set_name_entry_grid_row_colors(fixed_row_color, changing_row_color):
	"""Set colors for fixed (rows 1-2) and changing (rows 3-4) name-entry grid rows."""
	for i in range(len(name_entry_buttons)):
		row = i // 4
		if row < 2:
			row_color = fixed_row_color
		else:
			row_color = changing_row_color
		button = name_entry_buttons[i]
		button["base_color"] = row_color
		set_button_color(button, row_color)


def apply_page_theme(page_name):
	"""Apply per-page visual theme tweaks."""
	if page_name == "name_entry":
		set_name_entry_top_line_colors(
			COLOR_NAME_ENTRY_THEME_HEADER_TEXT,
			COLOR_NAME_ENTRY_THEME_VALUE_TEXT,
		)
		set_name_entry_grid_row_colors(
			COLOR_NAME_ENTRY_FIXED_ROW,
			COLOR_NAME_ENTRY_CHANGING_ROW,
		)
	else:
		set_name_entry_top_line_colors(
			COLOR_NAME_ENTRY_HEADER_TEXT,
			COLOR_NAME_ENTRY_VALUE_TEXT,
		)


def format_time_for_label(dt):
	hour_24 = dt[3]
	minute = dt[4]
	suffix = "am"
	if hour_24 >= 12:
		suffix = "pm"
	hour_12 = hour_24 % 12
	if hour_12 == 0:
		hour_12 = 12
	return "{}:{:02d} {}".format(hour_12, minute, suffix)


def update_clock_label(force=False):
	global last_clock_update
	now = time.monotonic()
	if force or (now - last_clock_update) >= 5.0:
		last_clock_update = now
		formatted_time = format_time_for_label(system_rtc.datetime)
		set_label_text_if_changed(time_label, formatted_time)
		set_label_text_if_changed(game_time_label, formatted_time)
		set_label_text_if_changed(game_kb_game_time_label, formatted_time)


def clear_comparison_labels():
	for line_label in comparison_labels:
		if line_label.text:
			line_label.text = ""


def clear_top_score_labels():
	for line_label in top_score_labels:
		if line_label.text:
			line_label.text = ""


def configure_comparison_labels_for_ranking():
	for i in range(len(comparison_labels)):
		line_label = comparison_labels[i]
		line_label.anchor_point = (0.0, 0.0)
		if i % 2 == 0:
			line_label.anchored_position = (5, 72 + (i * 18))
			line_label.color = COLOR_RESULT_TEXT
		else:
			line_label.anchored_position = (20, 72 + (i * 18))
			line_label.color = COLOR_TEXT_PRIMARY


def configure_comparison_labels_for_summary():
	for i in range(len(comparison_labels)):
		line_label = comparison_labels[i]
		line_label.anchor_point = (0.0, 0.0)
		line_label.anchored_position = (5, 88 + (i * 18))
		line_label.color = COLOR_TEXT_PRIMARY


def friendly_score_timestamp(raw_text):
	if not raw_text or len(raw_text) != 13 or raw_text[8] != "_":
		return "-"
	try:
		month = int(raw_text[4:6])
		day = int(raw_text[6:8])
		hour_24 = int(raw_text[9:11])
		minute = int(raw_text[11:13])
	except ValueError:
		return "-"
	suffix = "am"
	if hour_24 >= 12:
		suffix = "pm"
	hour_12 = hour_24 % 12
	if hour_12 == 0:
		hour_12 = 12
	return "{}:{:02d} {} {}/{}".format(hour_12, minute, suffix, month, day)


def score_type_label(score_type):
	return SCORE_TYPE_LABEL.get(score_type, score_type)


def set_score_detail_text(text):
	score_result_label.anchor_point = (0.0, 0.0)
	score_result_label.anchored_position = (5, 68)
	set_label_text_if_changed(score_result_label, text)


def set_score_next_text(text):
	score_result_label.anchor_point = (1.0, 0.0)
	score_result_label.anchored_position = (SCREEN_WIDTH - 5, 48)
	set_label_text_if_changed(score_result_label, text)


def debug_flow(message):
	if not DEBUG_FLOW:
		return
	try:
		free_memory = gc.mem_free()
		allocated_memory = gc.mem_alloc()
		memory_status = "free={} alloc={}".format(free_memory, allocated_memory)
	except AttributeError:
		memory_status = "memory=n/a"
	print(
		"[FLOW] {} | page={} game_started={} mode_select={} selecting_count={} selecting_name={} post_active={} post_page={} start_top_active={} start_top_page={} | {}".format(
			message,
			current_page_name,
			game_started,
			mode_select_active,
			selecting_problem_count,
			selecting_score_name,
			post_score_status_active,
			post_score_page_index,
			start_screen_top_scores_active,
			start_screen_top_score_index,
			memory_status,
		)
	)


def debug_helper_transition(message):
	if not DEBUG_HELPER_TRANSITIONS:
		return
	print("[HELPER] {}".format(message))


def emit_runtime_snapshot_if_due():
	global last_runtime_snapshot_time
	if not DEBUG_FLOW:
		return
	now = time.monotonic()
	if now - last_runtime_snapshot_time < DEBUG_RUNTIME_SNAPSHOT_INTERVAL:
		return
	last_runtime_snapshot_time = now
	state = runtime_state_snapshot()
	print(
		"[STATE] page={} started={} mode={} name_sel={} count_sel={} q={}/{} attempts={} correct={} skipped={} touch_rel={} pending={} idle={}".format(
			state["current_page_name"],
			state["game_started"],
			state["mode_select_active"],
			state["selecting_score_name"],
			state["selecting_problem_count"],
			state["current_problem_position"],
			state["question_order_length"],
			state["total_attempts"],
			state["total_correct"],
			state["total_skipped"],
			state["touch_release_required"],
			state["pending_press_count"],
			state["no_touch_count"],
		)
	)


def show_game_page():
	global current_page_name
	game_page_layout.show_page("game_mc")
	current_page_name = "game_mc"
	apply_page_theme(current_page_name)


def show_game_kb_page():
	global current_page_name
	game_page_layout.show_page("game_kb")
	current_page_name = "game_kb"
	apply_page_theme(current_page_name)


def show_score_page():
	global current_page_name
	game_page_layout.show_page("score")
	current_page_name = "score"
	apply_page_theme(current_page_name)


def show_name_entry_page_only():
	global current_page_name
	game_page_layout.show_page("name_entry")
	current_page_name = "name_entry"
	apply_page_theme(current_page_name)


def display_operator_symbol(operator_symbol):
	if operator_symbol == "*":
		return "x"
	return operator_symbol


def problem_text(problem):
	operator_symbol = current_operator_symbol
	if len(problem) > 6:
		operator_symbol = problem[6]
	return "{} {} {} = ".format(problem[0], display_operator_symbol(operator_symbol), problem[1])


def shuffle_in_place(items):
	for i in range(len(items) - 1, 0, -1):
		j = random.randrange(i + 1)
		items[i], items[j] = items[j], items[i]


def random_subset_from_pool(pool, count):
	pool_size = len(pool)
	if count >= pool_size:
		selected_items = list(pool)
		shuffle_in_place(selected_items)
		return selected_items

	selected_indexes = list(range(pool_size))
	for i in range(count):
		j = i + random.randrange(pool_size - i)
		selected_indexes[i], selected_indexes[j] = selected_indexes[j], selected_indexes[i]

	selected_items = []
	for i in range(count):
		selected_items.append(pool[selected_indexes[i]])
	return selected_items


def random_index_order(pool_size, count):
	if count > pool_size:
		count = pool_size

	selected_indexes = list(range(pool_size))
	for i in range(count):
		j = i + random.randrange(pool_size - i)
		selected_indexes[i], selected_indexes[j] = selected_indexes[j], selected_indexes[i]
	return selected_indexes[:count]


def update_elapsed_display(total_seconds):
	minutes = total_seconds // 60
	seconds = total_seconds % 60
	set_label_text_if_changed(total_time_label, "time {:02d}:{:02d}".format(minutes, seconds))
	set_label_text_if_changed(game_kb_total_time_label, "time {:02d}:{:02d}".format(minutes, seconds))


def reset_game_timer():
	global game_start_time, last_elapsed_second
	game_start_time = time.monotonic()
	last_elapsed_second = -1
	update_elapsed_display(0)
	update_score_displays(0)


def update_game_timer():
	global last_elapsed_second
	if not game_started:
		return
	elapsed_seconds = int(time.monotonic() - game_start_time)
	if elapsed_seconds != last_elapsed_second:
		last_elapsed_second = elapsed_seconds
		update_elapsed_display(elapsed_seconds)
		update_score_displays(elapsed_seconds)


def update_score_displays(elapsed_seconds=None):
	if elapsed_seconds is None:
		if game_started:
			elapsed_seconds = int(time.monotonic() - game_start_time)
		else:
			elapsed_seconds = max(last_elapsed_second, 0)

	set_label_text_if_changed(
		nbr_q_label,
		"{} / {} / {}".format(total_correct, total_attempts - total_skipped, total_skipped),
	)
	set_label_text_if_changed(
		game_kb_nbr_q_label,
		"{} / {} / {}".format(total_correct, total_attempts - total_skipped, total_skipped),
	)


def update_attempts_display():
	update_score_displays()


def current_elapsed_seconds():
	if game_started:
		return int(time.monotonic() - game_start_time)
	return max(last_elapsed_second, 0)


def average_time_seconds(elapsed_seconds):
	if total_correct <= 0:
		return 0.0
	return elapsed_seconds / total_correct


def percent_correct_value():
	effective_attempts = total_attempts + (0.5 * total_skipped)
	if effective_attempts <= 0:
		return 0.0
	return (total_correct * 100.0) / effective_attempts


def parse_score_line(line):
	return logic_core.parse_score_line(line)



score_entries_cache = None
score_entries_cache_loaded = False
score_math_cache = {}
score_entries_next_retry_time = 0.0
player_names_next_retry_time = 0.0


def invalidate_score_cache(game_type=None):
	global score_entries_cache, score_entries_cache_loaded, score_math_cache, score_entries_next_retry_time
	if game_type is None:
		score_entries_cache = None
		score_entries_cache_loaded = False
		score_math_cache = {}
		score_entries_next_retry_time = 0.0
		return
	score_math_cache.pop(game_type, None)


def load_score_entries(force_reload=False):
	global score_entries_cache, score_entries_cache_loaded, score_math_cache, score_entries_next_retry_time
	if score_entries_cache is not None and score_entries_cache_loaded and not force_reload:
		return score_entries_cache

	now = time.monotonic()
	if not force_reload and now < score_entries_next_retry_time:
		if score_entries_cache is not None:
			return score_entries_cache
		return []

	entries = []
	loaded = False
	for _ in range(SCORE_LOAD_RETRY_COUNT):
		try:
			entries = []
			with open_text_read(SCORE_FILE_PATH) as score_file:
				for raw_line in score_file:
					line = raw_line.strip()
					if not line:
						continue
					entry = parse_score_line(line)
					if entry is not None:
						entries.append(entry)
			loaded = True
			break
		except OSError:
			time.sleep(SCORE_LOAD_RETRY_DELAY)

	if not loaded:
		score_entries_next_retry_time = now + SCORE_LOAD_FAILURE_COOLDOWN
		if score_entries_cache is not None and not force_reload:
			return score_entries_cache
		print("Score history unavailable from:", SCORE_FILE_PATH)
		return []

	score_entries_cache = entries
	score_entries_cache_loaded = True
	score_math_cache = {}
	score_entries_next_retry_time = 0.0
	return score_entries_cache


def unique_player_names_from_scores(limit=None):
	entries = load_score_entries()
	names = []
	seen_names = set()
	for entry in entries:
		player_name = entry["player"]
		if player_name in seen_names:
			continue
		seen_names.add(player_name)
		names.append(player_name)
		if limit is not None and len(names) >= limit:
			break
	return names


def load_player_names(limit=PLAYER_BUTTON_LIMIT):
	global player_names_cache, player_names_next_retry_time
	names = []
	loaded_path = ""
	now = time.monotonic()

	if now < player_names_next_retry_time:
		if len(player_names_cache) > 0:
			if limit is None:
				return player_names_cache[:]
			return player_names_cache[:limit]
		return unique_player_names_from_scores(limit)

	for _ in range(PLAYER_LOAD_RETRY_COUNT):
		names = []
		for player_path in PLAYER_FILE_PATHS:
			try:
				with open_text_read(player_path) as players_file:
					for raw_line in players_file:
						name = raw_line.strip()
						if not name:
							continue
						names.append(name)
						if limit is not None and len(names) >= limit:
							break
				loaded_path = player_path
				break
			except OSError:
				continue
		if loaded_path:
			break
		time.sleep(PLAYER_LOAD_RETRY_DELAY)

	if loaded_path and len(names) > 0:
		print("Loaded player list from:", loaded_path)
		player_names_cache = names[:]
		player_names_next_retry_time = 0.0
	else:
		player_names_next_retry_time = now + PLAYER_LOAD_FAILURE_COOLDOWN
		names = unique_player_names_from_scores(limit)
		if len(names) > 0:
			print("Loaded player list from deduplicated scores")
			player_names_cache = names[:]
		elif len(player_names_cache) > 0:
			if limit is None:
				names = player_names_cache[:]
			else:
				names = player_names_cache[:limit]
			print("Using cached player list")
		else:
			print("Player list missing. Tried:", PLAYER_FILE_PATHS)

	return names


def first_existing_file_path(file_paths):
	for file_path in file_paths:
		try:
			with open_text_read(file_path):
				pass
			return file_path
		except OSError:
			continue
	return ""


def timestamped_archive_path(file_path, timestamp_text):
	slash_index = file_path.rfind("/")
	directory_path = ""
	file_name = file_path
	if slash_index >= 0:
		directory_path = file_path[:slash_index + 1]
		file_name = file_path[slash_index + 1:]
	dot_index = file_name.rfind(".")
	if dot_index <= 0:
		return "{}{}_{}".format(directory_path, file_name, timestamp_text)
	return "{}{}_{}{}".format(
		directory_path,
		file_name[:dot_index],
		timestamp_text,
		file_name[dot_index:],
	)


def archive_file_with_timestamp(file_path, timestamp_text):
	archive_path = timestamped_archive_path(file_path, timestamp_text)
	try:
		os.rename(file_path, archive_path)
		print("Archived {} to {}".format(file_path, archive_path))
		return archive_path
	except OSError as exc:
		print("Archive skipped for {}: {}".format(file_path, exc))
		return ""


def read_text_file(file_path):
	with open_text_read(file_path) as source_file:
		return source_file.read()


def write_text_file(file_path, text):
	with open_text_write(file_path) as target_file:
		target_file.write(text)


def restore_archived_file(archive_path, live_path):
	if not archive_path:
		return False
	try:
		os.rename(archive_path, live_path)
		print("Restored {} to {}".format(archive_path, live_path))
		return True
	except OSError as exc:
		print("Restore failed for {}: {}".format(live_path, exc))
		return False


def load_player_template_for_reset():
	template_path = first_existing_file_path(PLAYER_TEMPLATE_FILE_PATHS)
	if not template_path:
		print("Player template missing. Tried:", PLAYER_TEMPLATE_FILE_PATHS)
		return "", ""

	try:
		return template_path, read_text_file(template_path)
	except OSError as exc:
		print("Unable to read player template {}: {}".format(template_path, exc))
		return "", ""


def prepare_reset_archive_paths(timestamp_text):
	score_existing_path = first_existing_file_path((SCORE_FILE_PATH,))
	score_archive_path = ""
	if score_existing_path:
		score_archive_path = timestamped_archive_path(score_existing_path, timestamp_text)
		if first_existing_file_path((score_archive_path,)):
			print("Score archive already exists:", score_archive_path)
			return False, "", "", "", ""

	existing_player_path = first_existing_file_path(PLAYER_FILE_PATHS)
	player_archive_path = ""
	if existing_player_path:
		player_archive_path = timestamped_archive_path(existing_player_path, timestamp_text)
		if first_existing_file_path((player_archive_path,)):
			print("Player archive already exists:", player_archive_path)
			return False, "", "", "", ""

	return True, score_existing_path, existing_player_path, score_archive_path, player_archive_path


def backup_reset_files(score_existing_path, existing_player_path, timestamp_text):
	score_archive_path = ""
	if score_existing_path:
		score_archive_path = archive_file_with_timestamp(score_existing_path, timestamp_text)
		if not score_archive_path or not first_existing_file_path((score_archive_path,)):
			print("Unable to confirm score backup")
			return False, "", ""

	player_archive_path = ""
	if existing_player_path:
		player_archive_path = archive_file_with_timestamp(existing_player_path, timestamp_text)
		if not player_archive_path or not first_existing_file_path((player_archive_path,)):
			print("Unable to confirm player backup")
			if score_archive_path:
				restore_archived_file(score_archive_path, SCORE_FILE_PATH)
			return False, "", ""

	return True, score_archive_path, player_archive_path


def rollback_reset_files(score_archive_path, player_archive_path, existing_player_path):
	if score_archive_path:
		restore_archived_file(score_archive_path, SCORE_FILE_PATH)
	if player_archive_path:
		restore_archived_file(player_archive_path, existing_player_path)


def reset_saved_files():
	global player_names_cache, selectable_player_names, current_player_name
	timestamp_text = format_score_timestamp(system_rtc.datetime)
	template_path, template_text = load_player_template_for_reset()
	if not template_path:
		return False

	paths_ok, score_existing_path, existing_player_path, _unused_score_archive_path, _unused_player_archive_path = prepare_reset_archive_paths(timestamp_text)
	if not paths_ok:
		return False

	backups_ok, score_archive_path, player_archive_path = backup_reset_files(
		score_existing_path,
		existing_player_path,
		timestamp_text,
	)
	if not backups_ok:
		return False

	try:
		write_text_file(PLAYER_FILE_PATH, template_text)
		write_text_file(SCORE_FILE_PATH, "")
	except OSError as exc:
		print("Unable to reset saved files:", exc)
		rollback_reset_files(score_archive_path, player_archive_path, existing_player_path)
		return False

	player_names_cache = []
	selectable_player_names = []
	current_player_name = ""
	invalidate_score_cache()
	player_names_cache = load_player_names(None)
	print("Reset player and score files from template:", template_path)
	return True


def find_existing_player_name(candidate_name):
	candidate_upper = candidate_name.strip().upper()
	if not candidate_upper:
		return ""
	for existing_name in load_player_names(None):
		if existing_name.strip().upper() == candidate_upper:
			return existing_name
	return ""


def append_player_name(name_text):
	global player_names_cache
	if not name_text:
		return False

	for player_path in PLAYER_FILE_PATHS:
		try:
			separator = ""
			try:
				with open_text_read(player_path) as players_file:
					existing_text = players_file.read()
				if existing_text and not existing_text.endswith("\n"):
					separator = "\n"
			except OSError:
				separator = ""
			with open_text_append(player_path) as players_file:
				players_file.write("{}{}\n".format(separator, name_text))
			if name_text not in player_names_cache:
				player_names_cache.append(name_text)
			print("Saved player name to:", player_path)
			return True
		except OSError:
			continue

	print("Unable to write player list. Tried:", PLAYER_FILE_PATHS)
	return False


def update_player_name_buttons():
	start_index = player_name_page_index * PLAYER_NAME_PAGE_SIZE
	for i in range(PLAYER_NAME_PAGE_SIZE):
		name_index = start_index + i
		name_text = ""
		if name_index < len(selectable_player_names):
			name_text = selectable_player_names[name_index]
		set_button_text(answer_buttons[i], name_text)

	if start_index + PLAYER_NAME_PAGE_SIZE < len(selectable_player_names):
		set_button_text(answer_buttons[3], "More")
	else:
		set_button_text(answer_buttons[3], "NEW")


def advance_player_name_page():
	global player_name_page_index
	if len(selectable_player_names) <= PLAYER_NAME_PAGE_SIZE:
		return
	page_count = (len(selectable_player_names) + PLAYER_NAME_PAGE_SIZE - 1) // PLAYER_NAME_PAGE_SIZE
	player_name_page_index += 1
	if player_name_page_index >= page_count:
		player_name_page_index = 0
	update_player_name_buttons()


def update_name_entry_buttons():
	page_letters = NAME_ENTRY_LETTER_PAGES[name_entry_letter_page]
	labels = (
		"LAST", "BkSp", "ENTER", "NEXT",
		"A", "E", "I", "O",
		page_letters[0][0], page_letters[0][1], page_letters[0][2], page_letters[0][3],
		page_letters[1][0], page_letters[1][1], page_letters[1][2], page_letters[1][3],
	)
	for i in range(len(name_entry_buttons)):
		set_button_text(name_entry_buttons[i], labels[i])


def update_name_entry_display():
	if name_entry_message:
		name_entry_instruction_label.text = name_entry_message
	else:
		name_entry_instruction_label.text = "Tap letters, then ENTER"
	display_text = manual_name_value
	if len(display_text) < MAX_PLAYER_NAME_LENGTH:
		display_text += "_"
	if not display_text:
		display_text = "_"
	name_entry_value_label.text = display_text


def show_name_entry_page():
	global manual_name_value, name_entry_letter_page, name_entry_message
	manual_name_value = ""
	name_entry_letter_page = 0
	name_entry_message = ""
	show_name_entry_page_only()
	update_name_entry_buttons()
	update_name_entry_display()
	reset_button_colors()


def finish_manual_name_entry():
	global current_player_name, selecting_score_name, manual_name_value, name_entry_message
	name_text = manual_name_value.strip().upper()
	if not name_text:
		name_entry_message = "Enter at least 1 letter"
		update_name_entry_display()
		return

	if name_text == "RESET":
		if not reset_saved_files():
			name_entry_message = "Reset failed"
			update_name_entry_display()
			return
		selecting_score_name = True
		manual_name_value = ""
		name_entry_message = ""
		show_name_choices_for_score("Files reset. Tap NEW if needed")
		return

	existing_name = find_existing_player_name(name_text)
	if existing_name:
		current_player_name = existing_name
	else:
		if not append_player_name(name_text):
			name_entry_message = "Unable to save name"
			update_name_entry_display()
			return
		current_player_name = name_text

	selecting_score_name = False
	manual_name_value = ""
	name_entry_message = ""
	show_entry_type_choices()


def refresh_name_entry_controls():
	update_name_entry_buttons()
	update_name_entry_display()


def handle_name_entry_navigation(choice_text):
	global name_entry_letter_page, name_entry_message
	if choice_text == "LAST":
		name_entry_letter_page = (name_entry_letter_page - 1) % NAME_ENTRY_PAGE_COUNT
		name_entry_message = ""
		refresh_name_entry_controls()
		return True
	if choice_text == "NEXT":
		name_entry_letter_page = (name_entry_letter_page + 1) % NAME_ENTRY_PAGE_COUNT
		name_entry_message = ""
		refresh_name_entry_controls()
		return True
	return False


def handle_name_entry_edit(choice_text):
	global manual_name_value, name_entry_message
	if choice_text == "BkSp":
		manual_name_value = manual_name_value[:-1]
		name_entry_message = ""
		update_name_entry_display()
		return True
	if not choice_text:
		return True
	if len(manual_name_value) >= MAX_PLAYER_NAME_LENGTH:
		name_entry_message = "Max {} letters".format(MAX_PLAYER_NAME_LENGTH)
		update_name_entry_display()
		return True
	manual_name_value += choice_text
	name_entry_message = ""
	update_name_entry_display()
	return True


def handle_name_entry_choice(choice_text):
	if handle_name_entry_navigation(choice_text):
		return
	if choice_text == "ENTER":
		finish_manual_name_entry()
		return
	handle_name_entry_edit(choice_text)


def category_time_bounds(score_entries, game_type):
	return logic_core.category_time_bounds(score_entries, game_type, MIN_AVG_TIME, MAX_AVG_TIME)


def normalized_time_score(avg_time_value, min_time, max_time):
	return logic_core.normalized_time_score(avg_time_value, min_time, max_time)


def composite_score(percent_correct, avg_time_value, min_time, max_time):
	return logic_core.composite_score(
		percent_correct,
		avg_time_value,
		min_time,
		max_time,
		ACCURACY_WEIGHTING,
		TIME_WEIGHTING,
	)


def cached_score_math(game_type):
	global score_math_cache
	cached = score_math_cache.get(game_type)
	if cached is not None:
		return cached

	all_entries = load_score_entries()
	min_time, max_time = category_time_bounds(all_entries, game_type)

	scored_entries = []
	for entry in all_entries:
		if entry["type"] != game_type:
			continue
		scored_entry = dict(entry)
		scored_entry["norm_time"] = normalized_time_score(entry["avg_time"], min_time, max_time)
		scored_entry["score"] = composite_score(
			entry["pct_correct"],
			entry["avg_time"],
			min_time,
			max_time,
		)
		scored_entries.append(scored_entry)

	scored_entries.sort(key=lambda entry: entry["score"], reverse=True)
	cached = {
		"type": game_type,
		"min_time": min_time,
		"max_time": max_time,
		"entries": scored_entries,
	}
	score_math_cache[game_type] = cached
	return cached


def compile_scores_with_math(game_type, candidate_entry=None):
	cached = cached_score_math(game_type)
	min_time = cached["min_time"]
	max_time = cached["max_time"]

	candidate_scored = None
	if candidate_entry is not None:
		candidate_scored = dict(candidate_entry)
		candidate_scored["norm_time"] = normalized_time_score(candidate_entry["avg_time"], min_time, max_time)
		candidate_scored["score"] = composite_score(
			candidate_entry["pct_correct"],
			candidate_entry["avg_time"],
			min_time,
			max_time,
		)

	return {
		"type": game_type,
		"min_time": min_time,
		"max_time": max_time,
		"entries": cached["entries"],
		"candidate": candidate_scored,
	}


def format_score_timestamp(dt):
	return logic_core.format_score_timestamp(dt)


def append_score_entry(score_entry):
	global score_entries_cache, score_entries_cache_loaded
	if score_entry is None:
		return False
	timestamp_text = format_score_timestamp(system_rtc.datetime)
	score_entry["timestamp"] = timestamp_text
	# Determine entry mode: 'mc' for multiple choice, 'kb' for keyboard
	entry_mode = "mc"
	if "entry_type" in score_entry:
		if score_entry["entry_type"].lower().startswith("k"):  # "Keys" or "Keyboard"
			entry_mode = "kb"
	line = "{}, {}, {}, {}, {:.3f}, {:.3f}%, {}, {}\n".format(
		score_entry["player"],
		score_entry["type"],
		score_entry["nbr_q"],
		score_entry["nbr_skipped"],
		score_entry["avg_time"],
		score_entry["pct_correct"],
		timestamp_text,
		entry_mode,
	)
	try:
		with open_text_append(SCORE_FILE_PATH) as score_file:
			score_file.write(line)
		if score_entries_cache is None or not score_entries_cache_loaded:
			score_entries_cache = []
			score_entries_cache_loaded = True
		score_entries_cache.append(dict(score_entry))
		invalidate_score_cache(score_entry["type"])
		print("Saved score:", line)
		return True
	except Exception as exc:
		print("Unable to write {}:".format(SCORE_FILE_PATH), exc)
		return False


def player_best_entry(game_type, player_name):
	score_math = compile_scores_with_math(game_type)
	best_entry = None
	for entry in score_math["entries"]:
		if entry["player"] != player_name:
			continue
		if best_entry is None or entry["score"] > best_entry["score"]:
			best_entry = entry
	return best_entry


def rank_for_entry(entries, candidate_score):
	rank = 1
	for entry in entries:
		if entry["score"] > candidate_score:
			rank += 1
	return rank


def comparison_line_for_type(game_type, player_name, current_entry):
	candidate_entry = None
	if current_entry is not None and current_entry["type"] == game_type:
		candidate_entry = current_entry
	else:
		candidate_entry = player_best_entry(game_type, player_name)

	score_math = compile_scores_with_math(game_type, candidate_entry)
	entries = score_math["entries"]

	type_label = score_type_label(game_type)
	if len(type_label) > 8:
		type_label = type_label[:8]
	top_entry = None
	if entries:
		top_entry = entries[0]

	if candidate_entry is None or score_math["candidate"] is None:
		first_line = "{}: You N/A".format(type_label)
		if top_entry is None:
			return first_line, "No saved scores yet"
		return first_line, "#1 is {} {}".format(
			top_entry["player"][:8],
			friendly_score_timestamp(top_entry.get("timestamp", "")),
		)

	candidate_percent = score_math["candidate"]["score"] * 100.0
	rank = rank_for_entry(entries, score_math["candidate"]["score"])
	first_line = "{}: You {:4.1f}% - #{}".format(type_label, candidate_percent, rank)

	if top_entry is None:
		return first_line, "No saved scores yet"

	if top_entry["player"] == player_name and rank == 1:
		if current_entry is not None and current_entry["type"] == game_type and top_entry.get("timestamp", "") == current_entry.get("timestamp", ""):
			return first_line, "You have the top score just now"
		return first_line, "You have the top score {}".format(
			friendly_score_timestamp(top_entry.get("timestamp", ""))
		)

	return first_line, "#1 is {} {}".format(
		top_entry["player"][:8],
		friendly_score_timestamp(top_entry.get("timestamp", "")),
	)


def top_score_lines_for_type(game_type, limit=TOP_SCORE_PAGE_LIMIT):
	score_math = compile_scores_with_math(game_type)
	entries = score_math["entries"]
	if len(entries) == 0:
		return ["No saved scores for {}".format(game_type)]

	lines = []
	count = min(limit, len(entries))
	for i in range(count):
		entry = entries[i]
		timestamp_text = entry.get("timestamp", "")
		timestamp_text = friendly_score_timestamp(timestamp_text)
		name_text = entry["player"]
		if len(name_text) > 7:
			name_text = name_text[:7]
		lines.append(
			"#{:2d} - {:7s}  {:4.1f}%    {}".format(
				i + 1,
				name_text,
				entry["score"] * 100.0,
				timestamp_text,
			)
		)
	return lines


def player_totals_lines(limit=TOP_SCORE_PAGE_LIMIT):
	entries = load_score_entries()
	if len(entries) == 0:
		return ["No saved scores yet"]

	player_totals = {}
	for entry in entries:
		player_name = entry["player"]
		entry_mode = entry.get("entry_mode", "mc")
		n_problems = entry["nbr_q"] - entry["nbr_skipped"]
		if player_name not in player_totals:
			player_totals[player_name] = {
				"games": 0,
				"problems": 0,
				"points": 0.0,
			}
		player_totals[player_name]["games"] += 1
		player_totals[player_name]["problems"] += n_problems
		if entry_mode == "kb":
			player_totals[player_name]["points"] += n_problems * POINTS_PER_KB_PROBLEM
		else:
			player_totals[player_name]["points"] += n_problems * POINTS_PER_MC_PROBLEM

	ordered_names = list(player_totals.keys())
	ordered_names.sort(
		key=lambda name: (
			-player_totals[name]["games"],
			-player_totals[name]["problems"],
			name,
		)
	)

	lines = []
	count = min(limit, len(ordered_names))
	for i in range(count):
		name = ordered_names[i]
		games_played = player_totals[name]["games"]
		problems_played = player_totals[name]["problems"]
		points = player_totals[name]["points"]
		game_word = "Game" if games_played == 1 else "Games"
		problem_word = "Problem" if problems_played == 1 else "Problems"
		lines.append(
			"{}: {} {} - {} {}  Pts: {:.2f}".format(
				name[:8],
				games_played,
				game_word,
				problems_played,
				problem_word,
				points,
			)
		)
	return lines


def is_leap_year(year):
	if year % 400 == 0:
		return True
	if year % 100 == 0:
		return False
	return (year % 4) == 0


def previous_calendar_day(year, month, day):
	if day > 1:
		return year, month, day - 1

	month -= 1
	if month < 1:
		year -= 1
		month = 12

	if month in (1, 3, 5, 7, 8, 10, 12):
		max_day = 31
	elif month in (4, 6, 9, 11):
		max_day = 30
	else:
		if is_leap_year(year):
			max_day = 29
		else:
			max_day = 28

	return year, month, max_day


def date_text_from_timestamp(raw_text):
	if not raw_text or len(raw_text) < 8:
		return ""
	date_text = raw_text[:8]
	for c in date_text:
		if c < "0" or c > "9":
			return ""
	return date_text


def player_recent_totals_lines(limit=TOP_SCORE_PAGE_LIMIT):
	entries = load_score_entries()
	if len(entries) == 0:
		return ["No saved scores yet"]

	today = system_rtc.datetime
	today_text = "{:04d}{:02d}{:02d}".format(today[0], today[1], today[2])
	y_year, y_month, y_day = previous_calendar_day(today[0], today[1], today[2])
	yesterday_text = "{:04d}{:02d}{:02d}".format(y_year, y_month, y_day)

	player_totals = {}
	for entry in entries:
		entry_date = date_text_from_timestamp(entry.get("timestamp", ""))
		if entry_date != today_text and entry_date != yesterday_text:
			continue

		player_name = entry["player"]
		entry_mode = entry.get("entry_mode", "mc")
		n_problems = entry["nbr_q"] - entry["nbr_skipped"]
		if player_name not in player_totals:
			player_totals[player_name] = {
				"games": 0,
				"problems": 0,
				"points": 0.0,
			}
		player_totals[player_name]["games"] += 1
		player_totals[player_name]["problems"] += n_problems
		if entry_mode == "kb":
			player_totals[player_name]["points"] += n_problems * POINTS_PER_KB_PROBLEM
		else:
			player_totals[player_name]["points"] += n_problems * POINTS_PER_MC_PROBLEM

	if len(player_totals) == 0:
		return ["No scores for today/yesterday"]

	ordered_names = list(player_totals.keys())
	ordered_names.sort(
		key=lambda name: (
			-player_totals[name]["games"],
			-player_totals[name]["problems"],
			name,
		)
	)

	lines = []
	count = min(limit, len(ordered_names))
	for i in range(count):
		name = ordered_names[i]
		games_played = player_totals[name]["games"]
		problems_played = player_totals[name]["problems"]
		points = player_totals[name]["points"]
		game_word = "Game" if games_played == 1 else "Games"
		problem_word = "Problem" if problems_played == 1 else "Problems"
		lines.append(
			"{}: {} {} - {} {}  Pts: {:.2f}".format(
				name[:8],
				games_played,
				game_word,
				problems_played,
				problem_word,
				points,
			)
		)
	return lines


def show_post_score_summary(player_name, current_entry, saved, candidate_composite_score, high_score_status=""):
	global post_score_status_active, post_score_page_index, post_score_player_name, post_score_current_entry
	debug_flow("show_post_score_summary")
	show_score_page()
	clear_comparison_labels()
	clear_top_score_labels()
	configure_comparison_labels_for_summary()
	post_score_player_name = player_name
	post_score_current_entry = current_entry
	post_score_status_active = True
	post_score_page_index = 1
	wrong_answers = total_attempts - total_correct
	if wrong_answers < 0:
		wrong_answers = 0
	set_label_text_if_changed(score_title_label, "Game Result")
	score_question_label.anchor_point = (0.0, 0.0)
	score_question_label.anchored_position = (5, 68)
	score_question_label.color = COLOR_TEXT_PRIMARY
	set_label_text_if_changed(
		score_question_label,
		"{} Score for {}:".format(player_name, score_type_label(current_entry["type"])),
	)
	score_result_label.color = COLOR_RESULT_TEXT
	set_score_next_text("Next: Ranking")
	comparison_labels[0].text = "Problems: {} / Skipped: {} / Wrong: {}".format(
		current_entry["nbr_q"] - current_entry["nbr_skipped"],
		current_entry["nbr_skipped"],
		wrong_answers,
	)
	comparison_labels[1].text = "Accuracy Score: {:.0f}%".format(current_entry["pct_correct"])
	comparison_labels[2].text = "Average Time: {:.1f}s".format(current_entry["avg_time"])
	comparison_labels[3].color = COLOR_RESULT_TEXT
	comparison_labels[3].text = "Composite Score: {:.1f}%".format(candidate_composite_score * 100.0)
	if high_score_status == "new":
		comparison_labels[4].color = COLOR_RESULT_TEXT
		comparison_labels[4].text = "NEW HIGH SCORE!"
	elif high_score_status == "tie":
		comparison_labels[4].color = COLOR_RESULT_TEXT
		comparison_labels[4].text = "HIGH SCORE TIE!"
	if saved:
		set_status_led(LED_COLOR_BLUE)
	else:
		set_status_led(LED_COLOR_MAGENTA)
		comparison_labels[5].color = COLOR_RESULT_TEXT
		comparison_labels[5].text = "Save Failed"


def show_post_score_comparison_page():
	global post_score_page_index
	debug_flow("show_post_score_comparison_page")
	show_score_page()
	clear_answer_choices()
	reset_button_colors()
	clear_top_score_labels()
	configure_comparison_labels_for_ranking()
	set_label_text_if_changed(score_title_label, "Your Ranking")
	score_question_label.anchor_point = (0.0, 0.0)
	score_question_label.anchored_position = (5, 48)
	set_label_text_if_changed(score_question_label, "{} across all types".format(post_score_player_name))
	score_question_label.color = COLOR_TEXT_PRIMARY
	set_score_next_text("Next: Top Scores")
	score_result_label.color = COLOR_RESULT_TEXT
	for i in range(4):
		game_type = SCORE_TYPES[i]
		line_1, line_2 = comparison_line_for_type(
			game_type,
			post_score_player_name,
			post_score_current_entry,
		)
		comparison_labels[i * 2].text = line_1
		comparison_labels[(i * 2) + 1].text = line_2
	post_score_page_index = 2


def show_post_score_top_scores_page():
	global post_score_page_index
	debug_flow("show_post_score_top_scores_page")
	show_score_page()
	clear_answer_choices()
	reset_button_colors()
	clear_comparison_labels()
	configure_comparison_labels_for_ranking()
	top_lines = top_score_lines_for_type(post_score_current_entry["type"])
	type_label = score_type_label(post_score_current_entry["type"])
	set_label_text_if_changed(score_title_label, "Top Scores")
	score_question_label.anchor_point = (0.0, 0.0)
	score_question_label.anchored_position = (5, 48)
	set_label_text_if_changed(score_question_label, "{} Top {}".format(type_label, TOP_SCORE_PAGE_LIMIT))
	score_question_label.color = COLOR_TEXT_PRIMARY
	set_score_next_text("Next: Home")
	score_result_label.color = COLOR_RESULT_TEXT
	for i in range(TOP_SCORE_PAGE_LIMIT):
		if i < len(top_lines):
			top_score_labels[i].text = top_lines[i]
		else:
			top_score_labels[i].text = ""
	post_score_page_index = 3


def show_start_screen_top_scores_page(score_type_index=0):
	global game_started, mode_select_active, selecting_problem_count, selecting_score_name
	global post_score_status_active, post_score_page_index
	global start_screen_top_scores_active, start_screen_top_score_index
	show_score_page()
	game_started = False
	mode_select_active = False
	selecting_problem_count = False
	selecting_score_name = False
	post_score_status_active = False
	post_score_page_index = 0
	start_screen_top_scores_active = True
	start_screen_top_score_index = score_type_index
	clear_answer_choices()
	reset_button_colors()
	clear_comparison_labels()
	configure_comparison_labels_for_ranking()
	set_button_text(score_quit_button, "Start")
	set_button_text(score_next_button, "Next")
	score_question_label.anchor_point = (0.0, 0.0)
	score_question_label.anchored_position = (5, 48)
	score_question_label.color = COLOR_TEXT_PRIMARY
	score_result_label.color = COLOR_RESULT_TEXT

	title_text, question_text, next_text, top_lines = start_screen_scores_page_content(score_type_index)
	set_label_text_if_changed(score_title_label, title_text)
	set_label_text_if_changed(score_question_label, question_text)
	set_score_next_text(next_text)
	render_top_score_lines(top_lines)


def start_screen_scores_page_content(score_type_index):
	totals_page_index = len(SCORE_TYPES)

	if score_type_index < len(SCORE_TYPES):
		game_type = SCORE_TYPES[score_type_index]
		type_label = score_type_label(game_type)
		title_text = "Top Scores"
		question_text = "{} Top {}".format(type_label, TOP_SCORE_PAGE_LIMIT)
		top_lines = top_score_lines_for_type(game_type)
		if score_type_index < len(SCORE_TYPES) - 1:
			next_label = score_type_label(SCORE_TYPES[score_type_index + 1])
			next_text = "Next: {}".format(next_label)
		else:
			next_text = "Next: Totals"
		return title_text, question_text, next_text, top_lines

	if score_type_index == totals_page_index:
		return (
			"Player Totals",
			"Games/Problems Played",
			"Next: Last 2 Days",
			player_totals_lines(TOP_SCORE_PAGE_LIMIT),
		)

	return (
		"Last 2 Days",
		"Combined Games/Problems",
		"Next: Home",
		player_recent_totals_lines(TOP_SCORE_PAGE_LIMIT),
	)


def render_top_score_lines(top_lines):
	for i in range(TOP_SCORE_PAGE_LIMIT):
		if i < len(top_lines):
			set_label_text_if_changed(top_score_labels[i], top_lines[i])
		else:
			set_label_text_if_changed(top_score_labels[i], "")


def advance_start_screen_top_scores_page():
	if start_screen_top_score_index >= len(SCORE_TYPES) + 1:
		show_title_screen()
		return
	show_start_screen_top_scores_page(start_screen_top_score_index + 1)


def show_name_choices_for_score(status_message="Tap NEW if not listed"):
	global game_started, mode_select_active, selecting_entry_type, selecting_problem_count, selecting_score_name, post_score_status_active, post_score_page_index, selectable_player_names, player_name_page_index, start_screen_top_scores_active
	show_game_page()
	game_started = False
	mode_select_active = True
	selecting_entry_type = False
	selecting_problem_count = False
	selecting_score_name = True
	post_score_status_active = False
	post_score_page_index = 0
	start_screen_top_scores_active = False
	clear_comparison_labels()
	clear_top_score_labels()
	set_label_text_if_changed(title_label, TITLE_TEXT)
	set_button_text(quit_button, "Start")
	set_button_text(next_button, "Back")
	set_label_text_if_changed(question_label, "Choose Player Name")
	set_label_text_if_changed(result_label, status_message)
	selectable_player_names = load_player_names(None)
	player_name_page_index = 0
	update_player_name_buttons()
	reset_button_colors()


def show_entry_type_choices():
	global game_started, mode_select_active, selecting_entry_type, selecting_problem_count, selecting_score_name, post_score_status_active, post_score_page_index, start_screen_top_scores_active
	show_game_page()
	game_started = False
	mode_select_active = True
	selecting_entry_type = True
	selecting_problem_count = False
	selecting_score_name = False
	post_score_status_active = False
	post_score_page_index = 0
	start_screen_top_scores_active = False
	clear_comparison_labels()
	clear_top_score_labels()
	set_label_text_if_changed(title_label, TITLE_TEXT)
	set_button_text(quit_button, "Start")
	set_button_text(next_button, "Next")
	set_label_text_if_changed(question_label, "Entry Type?")
	set_label_text_if_changed(result_label, "")
	set_button_text(answer_buttons[0], "Choice")
	set_button_text(answer_buttons[1], "Keys")
	set_button_text(answer_buttons[2], "")
	set_button_text(answer_buttons[3], "")
	reset_button_colors()


def finish_completed_game():
	global game_started, mode_select_active, selecting_problem_count, selecting_score_name
	debug_flow("finish_completed_game")
	game_started = False
	mode_select_active = False
	selecting_problem_count = False
	set_label_text_if_changed(question_label, "")
	set_label_text_if_changed(result_label, "")
	clear_answer_choices()
	reset_button_colors()
	if not current_player_name:
		show_name_choices_for_score()
		return
	elapsed_seconds = current_elapsed_seconds()
	current_entry = build_current_game_entry(elapsed_seconds)
	score_math = compile_scores_with_math(current_entry["type"], current_entry)
	candidate_composite_score, high_score_status = evaluate_high_score_status(score_math)
	saved = append_score_entry(current_entry)
	selecting_score_name = False
	show_post_score_summary(current_player_name, current_entry, saved, candidate_composite_score, high_score_status)


def build_current_game_entry(elapsed_seconds):
	current_entry = {
		"player": current_player_name,
		"type": current_game_type,
		"nbr_q": len(question_order),
		"nbr_skipped": total_skipped,
		"avg_time": average_time_seconds(elapsed_seconds),
		"pct_correct": percent_correct_value(),
	}
	current_entry["timestamp"] = format_score_timestamp(system_rtc.datetime)
	return current_entry


def evaluate_high_score_status(score_math):
	candidate_composite_score = 0.0
	high_score_status = ""
	if score_math["candidate"] is None:
		return candidate_composite_score, high_score_status

	candidate_composite_score = score_math["candidate"]["score"]
	if len(score_math["entries"]) == 0:
		high_score_status = "new"
	elif candidate_composite_score > score_math["entries"][0]["score"]:
		high_score_status = "new"
	elif candidate_composite_score == score_math["entries"][0]["score"]:
		high_score_status = "tie"

	return candidate_composite_score, high_score_status


def current_mode_select_state():
	return game_engine.initial_mode_select_state(
		selecting_score_name=selecting_score_name,
		selecting_entry_type=selecting_entry_type,
		selecting_problem_count=selecting_problem_count,
		current_game_type=current_game_type,
		current_operator_symbol=current_operator_symbol,
		problem_count_target=problem_count_target,
		current_player_name=current_player_name,
	)


def current_gameplay_state():
	return game_engine.initial_gameplay_state(
		game_started=game_started,
		current_problem_position=current_problem_position,
		question_order_length=len(question_order),
		total_attempts=total_attempts,
		total_correct=total_correct,
		total_skipped=total_skipped,
		current_correct_answer=current_correct_answer,
	)


def current_post_score_state():
	return game_engine.initial_post_score_state(
		post_score_status_active=post_score_status_active,
		post_score_page_index=post_score_page_index,
	)


def current_start_screen_scores_state():
	return game_engine.initial_start_screen_scores_state(
		start_screen_top_scores_active=start_screen_top_scores_active,
		start_screen_top_score_index=start_screen_top_score_index,
	)


def runtime_state_snapshot():
	return {
		"game_started": game_started,
		"mode_select_active": mode_select_active,
		"selecting_entry_type": selecting_entry_type,
		"selecting_score_name": selecting_score_name,
		"selecting_problem_count": selecting_problem_count,
		"post_score_status_active": post_score_status_active,
		"start_screen_top_scores_active": start_screen_top_scores_active,
		"current_page_name": current_page_name,
		"current_game_type": current_game_type,
		"problem_count_target": problem_count_target,
		"current_problem_position": current_problem_position,
		"question_order_length": len(question_order),
		"total_attempts": total_attempts,
		"total_correct": total_correct,
		"total_skipped": total_skipped,
		"pending_press_count": pending_press_count,
		"no_touch_count": no_touch_count,
		"touch_release_required": touch_release_required,
	}


def choose_player_name(choice_text):
	global selecting_score_name, current_player_name
	reducer_result = game_engine.handle_mode_select_event(
		current_mode_select_state(),
		"player_name_choice",
		choice_text,
		selectable_player_names,
	)
	action = reducer_result["intent"]
	next_state = reducer_result["state"]

	if action == "advance_page":
		advance_player_name_page()
		return
	if action == "show_name_entry":
		show_name_entry_page()
		return
	if action != "select_player":
		return
	current_player_name = next_state["current_player_name"]
	selecting_score_name = next_state["selecting_score_name"]
	show_entry_type_choices()


def reset_score_counters():
	global total_attempts, total_correct, total_skipped
	total_attempts = 0
	total_correct = 0
	total_skipped = 0
	update_attempts_display()


def set_answer_choices(problem):
	choices = list(problem[2:6])
	shuffle_in_place(choices)
	for i in range(BUTTON_COUNT):
		set_button_text(answer_buttons[i], str(choices[i]))


def clear_answer_choices():
	for answer_button in answer_buttons:
		set_button_text(answer_button, "")


def kb_entry_display_text():
	if kb_answer_text:
		return kb_answer_text
	return "_"


def refresh_kb_entry_label():
	set_label_text_if_changed(game_kb_entry_label, kb_entry_display_text())


def clear_kb_entry():
	global kb_answer_text
	kb_answer_text = ""
	refresh_kb_entry_label()


def append_kb_digit(digit_text):
	global kb_answer_text
	if len(kb_answer_text) >= KB_ENTRY_MAX_DIGITS:
		return
	kb_answer_text += digit_text
	refresh_kb_entry_label()


def backspace_kb_digit():
	global kb_answer_text
	if kb_answer_text:
		kb_answer_text = kb_answer_text[:-1]
	refresh_kb_entry_label()


def reset_button_colors():
	for button in buttons:
		set_button_color(button, button["base_color"])


def show_current_problem():
	global current_correct_answer
	problem = active_questions[question_order[current_problem_position]]
	problem_line = problem_text(problem)
	if current_entry_type == "Keys":
		set_label_text_if_changed(game_kb_question_label, problem_line)
		set_label_text_if_changed(game_kb_result_label, "")
		clear_kb_entry()
	else:
		set_label_text_if_changed(question_label, problem_line)
	current_correct_answer = problem[2]
	reset_button_colors()
	if current_entry_type != "Keys":
		set_answer_choices(problem)


def handle_kb_submit_answer():
	global total_attempts, total_correct, current_problem_position
	if not kb_answer_text:
		refresh_kb_entry_label()
		return False

	try:
		chosen_value = int(kb_answer_text)
	except ValueError:
		clear_kb_entry()
		return False

	total_attempts += 1
	if chosen_value == current_correct_answer:
		debug_helper_transition("kb answer -> correct {}".format(chosen_value))
		play_buzzer_pattern(((BUZZER_CORRECT_FREQUENCY, BUZZER_CORRECT_DURATION),))
		flash_status_led(LED_COLOR_GREEN)
		total_correct += 1
		update_attempts_display()
		time.sleep(KB_CORRECT_PAUSE_SECONDS)
		current_problem_position += 1
		if current_problem_position >= len(question_order):
			finish_completed_game()
			return True
		show_current_problem()
		return True

	debug_helper_transition("kb answer -> wrong {}".format(chosen_value))
	play_buzzer_pattern(((BUZZER_WRONG_FREQUENCY, BUZZER_WRONG_DURATION),))
	flash_status_led(LED_COLOR_RED)
	update_attempts_display()
	time.sleep(KB_WRONG_PAUSE_SECONDS)
	clear_kb_entry()
	return False


def handle_kb_entry_press(pressed):
	if current_entry_type != "Keys":
		return False
	button_text = pressed["label"].text
	if not button_text:
		return False
	if button_text == "BkSp":
		backspace_kb_digit()
		return False
	if button_text == "Enter":
		return handle_kb_submit_answer()
	if button_text in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
		play_buzzer_pattern(((BUZZER_DIGIT_FREQUENCY, BUZZER_DIGIT_DURATION),))
		append_kb_digit(button_text)
		return False
	return False


def end_game(message="Game Over"):
	global game_started, mode_select_active, selecting_problem_count
	game_started = False
	mode_select_active = False
	selecting_problem_count = False
	set_button_text(quit_button, "Start")
	set_button_text(game_kb_quit_button, "Start")
	set_button_text(game_kb_next_button, "Next")
	set_label_text_if_changed(question_label, message)
	set_label_text_if_changed(game_kb_question_label, message)
	set_label_text_if_changed(result_label, "")
	set_label_text_if_changed(game_kb_result_label, "")
	clear_kb_entry()
	clear_answer_choices()
	reset_button_colors()


def start_game():
	global game_started, current_problem_position, mode_select_active, selecting_problem_count, active_questions
	if current_entry_type == "Keys":
		show_game_kb_page()
	else:
		show_game_page()
	if current_game_type == "Mixed":
		selected_questions = []
		max_mixed_questions = len(addition_mixed) + len(subtraction_mixed) + len(multiplication_mixed)
		mixed_count = min(problem_count_target, max_mixed_questions)
		base_count = mixed_count // 3
		extra_count = mixed_count % 3
		category_specs = (addition_mixed, subtraction_mixed, multiplication_mixed)
		for i in range(len(category_specs)):
			take_count = base_count
			if i < extra_count:
				take_count += 1
			selected_questions.extend(random_subset_from_pool(category_specs[i], take_count))
		shuffle_in_place(selected_questions)
		active_questions = selected_questions

	if not active_questions:
		end_game("No problems")
		return
	game_started = True
	mode_select_active = False
	selecting_problem_count = False
	set_label_text_if_changed(result_label, "")
	reset_game_timer()
	reset_score_counters()
	question_count = min(problem_count_target, len(active_questions))
	question_order[:] = random_index_order(len(active_questions), question_count)
	current_problem_position = 0
	set_button_text(quit_button, "Quit")
	set_button_text(next_button, "Next")
	set_button_text(game_kb_quit_button, "Quit")
	set_button_text(game_kb_next_button, "Next")
	clear_comparison_labels()
	clear_top_score_labels()
	set_status_led(LED_COLOR_OFF)
	show_current_problem()
	reset_button_colors()


def show_problem_type_choices():
	global game_started, mode_select_active, selecting_entry_type, selecting_problem_count, selecting_score_name, post_score_status_active, post_score_page_index, name_entry_message, start_screen_top_scores_active
	show_game_page()
	game_started = False
	mode_select_active = True
	selecting_entry_type = False
	selecting_problem_count = False
	selecting_score_name = False
	post_score_status_active = False
	post_score_page_index = 0
	start_screen_top_scores_active = False
	name_entry_message = ""
	clear_comparison_labels()
	clear_top_score_labels()
	set_label_text_if_changed(title_label, TITLE_TEXT)
	set_button_text(quit_button, "Start")
	set_button_text(next_button, "Next")
	set_label_text_if_changed(question_label, "Problem Type?")
	set_label_text_if_changed(result_label, "")
	set_button_text(answer_buttons[0], "Add")
	set_button_text(answer_buttons[1], "Subtract")
	set_button_text(answer_buttons[2], "Multiply")
	set_button_text(answer_buttons[3], "Mixed")
	reset_button_colors()


def show_problem_count_choices():
	global game_started, mode_select_active, selecting_problem_count, selecting_score_name, post_score_status_active, post_score_page_index, start_screen_top_scores_active
	show_game_page()
	game_started = False
	mode_select_active = True
	selecting_problem_count = True
	selecting_score_name = False
	post_score_status_active = False
	post_score_page_index = 0
	start_screen_top_scores_active = False
	clear_comparison_labels()
	clear_top_score_labels()
	set_button_text(quit_button, "Start")
	set_button_text(next_button, "Next")
	set_label_text_if_changed(question_label, "Nbr Problems?")
	set_label_text_if_changed(result_label, "")
	set_button_text(answer_buttons[0], "10")
	set_button_text(answer_buttons[1], "20")
	set_button_text(answer_buttons[2], "35")
	set_button_text(answer_buttons[3], "50")
	reset_button_colors()


def show_title_screen(reset_title=True):
	global game_started, mode_select_active, selecting_entry_type, selecting_problem_count, selecting_score_name, post_score_status_active, post_score_page_index, post_score_player_name, post_score_current_entry, current_player_name, current_entry_type, kb_answer_text, manual_name_value, name_entry_letter_page, name_entry_message, start_screen_top_scores_active, start_screen_top_score_index
	show_game_page()
	game_started = False
	mode_select_active = False
	selecting_entry_type = False
	selecting_problem_count = False
	selecting_score_name = False
	post_score_status_active = False
	post_score_page_index = 0
	start_screen_top_scores_active = False
	start_screen_top_score_index = 0
	post_score_player_name = ""
	post_score_current_entry = None
	current_player_name = ""
	current_entry_type = "Choice"
	kb_answer_text = ""
	manual_name_value = ""
	name_entry_letter_page = 0
	name_entry_message = ""
	if reset_title:
		set_label_text_if_changed(title_label, TITLE_TEXT)
	set_button_text(quit_button, "Start")
	set_button_text(next_button, "Next")
	set_label_text_if_changed(question_label, QUESTION_TEXT)
	set_label_text_if_changed(result_label, "")
	set_label_text_if_changed(score_title_label, "Score")
	set_label_text_if_changed(score_question_label, "")
	set_score_detail_text("")
	clear_comparison_labels()
	clear_top_score_labels()
	reset_score_counters()
	clear_answer_choices()
	reset_button_colors()


def choose_problem_type(choice_text):
	global active_questions, current_operator_symbol, current_game_type, selecting_problem_count, selecting_score_name
	reducer_result = game_engine.handle_mode_select_event(
		current_mode_select_state(),
		"problem_type_choice",
		choice_text,
	)
	if reducer_result["intent"] != "show_problem_count_choices":
		return

	next_state = reducer_result["state"]
	data = reducer_result.get("data")
	if isinstance(data, dict):
		# Support both legacy wrapper shape {"selection": {...}} and raw selection dict.
		selection = data.get("selection") if "selection" in data else data
	else:
		selection = data
	if selection is None:
		return

	question_bank = selection["question_bank"]
	if question_bank == "addition":
		active_questions = addition
	elif question_bank == "subtraction":
		active_questions = subtraction
	elif question_bank == "multiplication":
		active_questions = multiplication
	else:
		active_questions = []

	current_operator_symbol = next_state["current_operator_symbol"]
	current_game_type = next_state["current_game_type"]
	selecting_problem_count = next_state["selecting_problem_count"]
	selecting_score_name = next_state["selecting_score_name"]
	set_label_text_if_changed(title_label, selection["title"])
	show_problem_count_choices()


def choose_problem_count(choice_text):
	global problem_count_target, selecting_problem_count
	reducer_result = game_engine.handle_mode_select_event(
		current_mode_select_state(),
		"problem_count_choice",
		choice_text,
	)
	if reducer_result["intent"] != "start_game":
		return
	next_state = reducer_result["state"]
	problem_count_target = next_state["problem_count_target"]
	selecting_problem_count = next_state["selecting_problem_count"]
	start_game()


def button_from_touch(x, y):
	for button in buttons:
		if button["page"] != current_page_name:
			continue
		if button["x0"] <= x < button["x1"] and button["y0"] <= y < button["y1"]:
			return button
	return None


def initialize_input_adapter():
	PORTS["input"] = TouchInputAdapter(ts, TOUCH_PRESSURE_MIN, touch_to_pixel, button_from_touch)


def read_filtered_touch():
	if PORTS["input"] is not None:
		return PORTS["input"].read_touch_sample()

	touch = None
	if ts.touched:
		touch_sample = ts.touch
		if touch_sample["pressure"] >= TOUCH_PRESSURE_MIN:
			touch = touch_sample
	return touch


def resolve_touch_press(touch):
	if PORTS["input"] is not None:
		return PORTS["input"].resolve_touch_to_button(touch)
	tx, ty = touch_to_pixel(touch["x"], touch["y"])
	pressed = button_from_touch(tx, ty)
	return tx, ty, pressed


def update_pending_press_state(pressed):
	global pending_pressed, pending_press_count
	next_pending_press_count, clear_pending_pressed, set_pending_pressed = game_engine.route_pending_press_state(
		pressed is not None,
		pressed is pending_pressed,
		pending_press_count,
	)
	pending_press_count = next_pending_press_count
	if clear_pending_pressed:
		pending_pressed = None
	elif set_pending_pressed:
		pending_pressed = pressed


def handle_quit_intent(intent, debug_context=""):
	if intent == "prompt_choose_player":
		debug_helper_transition("quit -> selecting_score_name prompt")
		set_label_text_if_changed(result_label, "Choose player to continue")
		return False
	if intent == "show_name_choices":
		if debug_context:
			debug_helper_transition("quit -> name choices ({})".format(debug_context))
		else:
			debug_helper_transition("quit -> name choices")
		show_name_choices_for_score()
		return True
	if intent == "show_title_screen":
		debug_helper_transition("quit -> title screen (in game)")
		show_title_screen()
		return True
	return False


def handle_next_intent(intent, data=None):
	if intent == "show_title_screen":
		show_title_screen()
		return True
	if intent == "show_start_scores_page":
		if data is None:
			return False
		if isinstance(data, dict):
			next_index = data.get("next_index")
		else:
			next_index = data
		if next_index is None:
			return False
		show_start_screen_top_scores_page(next_index)
		return True
	if intent == "show_ranking_page":
		show_post_score_comparison_page()
		return True
	if intent == "show_top_scores_page":
		show_post_score_top_scores_page()
		return True
	return False


def handle_gameplay_next_intent(intent, next_state):
	global total_skipped, current_problem_position
	set_status_led(LED_COLOR_YELLOW)
	play_buzzer_pattern(
		(
			(BUZZER_SKIP_FREQUENCY, BUZZER_SKIP_BEEP_DURATION),
			(None, BUZZER_SKIP_GAP_DURATION),
			(BUZZER_SKIP_FREQUENCY, BUZZER_SKIP_BEEP_DURATION),
		)
	)
	total_skipped = next_state["total_skipped"]
	update_attempts_display()
	current_problem_position = next_state["current_problem_position"]
	if intent == "finish_game":
		finish_completed_game()
		return True
	set_label_text_if_changed(result_label, "")
	set_label_text_if_changed(game_kb_result_label, "")
	show_current_problem()
	return True


def handle_quit_press():
	reducer_result = game_engine.handle_mode_select_event(
		current_mode_select_state(),
		"quit_pressed_mode_select",
	)
	if selecting_score_name:
		return handle_quit_intent(reducer_result["intent"])
	if start_screen_top_scores_active:
		reducer_result = game_engine.handle_start_screen_scores_event(
			current_start_screen_scores_state(),
			"quit_pressed_start_screen_scores",
		)
		return handle_quit_intent(reducer_result["intent"], "from top scores")
	if post_score_status_active:
		reducer_result = game_engine.handle_post_score_event(
			current_post_score_state(),
			"quit_pressed_post_score",
		)
		return handle_quit_intent(reducer_result["intent"], "from post score")
	if game_started:
		reducer_result = game_engine.handle_gameplay_event(
			current_gameplay_state(),
			"quit_pressed_in_game",
		)
		return handle_quit_intent(reducer_result["intent"])
	return handle_quit_intent(reducer_result["intent"])


def handle_next_press():
	global total_skipped, current_problem_position
	debug_flow("Next pressed")
	debug_helper_transition("next pressed")
	if selecting_score_name:
		reducer_result = game_engine.handle_mode_select_event(
			current_mode_select_state(),
			"next_pressed_mode_select",
		)
		if reducer_result["intent"] != "show_title_screen":
			return False
		debug_flow("Next branch: selecting_score_name")
		debug_helper_transition("next -> title screen (selecting name)")
		return handle_next_intent(reducer_result["intent"], reducer_result.get("data"))
	if start_screen_top_scores_active:
		reducer_result = game_engine.handle_start_screen_scores_event(
			current_start_screen_scores_state(),
			"next_pressed_start_screen_scores",
			len(SCORE_TYPES),
		)
		if reducer_result["intent"] == "ignore":
			return False
		debug_flow("Next branch: start_screen_top_scores_active")
		debug_helper_transition("next -> advance start top scores page")
		return handle_next_intent(reducer_result["intent"], reducer_result.get("data"))
	if game_started:
		reducer_result = game_engine.handle_gameplay_event(
			current_gameplay_state(),
			"next_pressed_in_game",
		)
		if reducer_result["intent"] == "ignore":
			return False
		debug_flow("Next branch: game_started")
		debug_helper_transition("next -> skip current problem")
		return handle_gameplay_next_intent(reducer_result["intent"], reducer_result["state"])
	if post_score_status_active:
		reducer_result = game_engine.handle_post_score_event(
			current_post_score_state(),
			"next_pressed_post_score",
		)
		if reducer_result["intent"] == "ignore":
			return False
		debug_flow("Next branch: post_score_status_active")
		debug_helper_transition("next -> post score page flow")
		if reducer_result["intent"] == "show_ranking_page":
			debug_flow("Advancing to ranking page")
			debug_helper_transition("next -> ranking page")
		elif reducer_result["intent"] == "show_top_scores_page":
			debug_flow("Advancing to top scores page")
			debug_helper_transition("next -> top scores page")
		elif reducer_result["intent"] == "show_title_screen":
			debug_flow("Advancing to title screen")
			debug_helper_transition("next -> title screen")
		return handle_next_intent(reducer_result["intent"], reducer_result.get("data"))
	debug_helper_transition("next -> start screen top scores page 0")
	show_start_screen_top_scores_page(0)
	return True


def handle_name_entry_press(pressed):
	choice_text = pressed["label"].text
	if choice_text:
		play_buzzer_pattern(((BUZZER_DIGIT_FREQUENCY, BUZZER_DIGIT_DURATION),))
		debug_helper_transition("name_entry -> {}".format(choice_text))
		starting_page = current_page_name
		handle_name_entry_choice(choice_text)
		return current_page_name != starting_page
	return False


def handle_mode_select_answer_intent(intent, choice_text):
	global current_entry_type
	if intent == "choose_entry_type":
		debug_helper_transition("mode_select answer -> choose entry type {}".format(choice_text))
		current_entry_type = choice_text
		show_problem_type_choices()
		return True
	if intent == "choose_player_name":
		debug_helper_transition("mode_select answer -> choose player {}".format(choice_text))
		choose_player_name(choice_text)
		return True
	if intent == "choose_problem_count":
		debug_helper_transition("mode_select answer -> choose problem count {}".format(choice_text))
		choose_problem_count(choice_text)
		return True
	if intent == "choose_problem_type":
		debug_helper_transition("mode_select answer -> choose problem type {}".format(choice_text))
		choose_problem_type(choice_text)
		return True
	return False


def handle_mode_select_answer_press(pressed):
	choice_text = pressed["label"].text
	if not choice_text:
		return False
	reducer_result = game_engine.handle_mode_select_event(
		current_mode_select_state(),
		"answer_pressed_mode_select",
		choice_text,
	)
	if reducer_result["intent"] == "ignore":
		return False
	return handle_mode_select_answer_intent(reducer_result["intent"], choice_text)


def handle_gameplay_answer_intent(intent, next_state, chosen_value):
	global total_attempts, total_correct, current_problem_position
	total_attempts = next_state["total_attempts"]

	if intent in ("show_current_problem_correct", "finish_game_correct"):
		debug_helper_transition("game answer -> correct {}".format(chosen_value))
		play_buzzer_pattern(((BUZZER_CORRECT_FREQUENCY, BUZZER_CORRECT_DURATION),))
		flash_status_led(LED_COLOR_GREEN)
		total_correct = next_state["total_correct"]
		update_attempts_display()
		current_problem_position = next_state["current_problem_position"]
		if intent == "finish_game_correct":
			finish_completed_game()
			return True
		show_current_problem()
		return True

	if intent == "wrong_answer":
		debug_helper_transition("game answer -> wrong {}".format(chosen_value))
		play_buzzer_pattern(((BUZZER_WRONG_FREQUENCY, BUZZER_WRONG_DURATION),))
		flash_status_led(LED_COLOR_RED)
		update_attempts_display()
		return False

	return False


def handle_game_answer_press(pressed):
	chosen_text = pressed["label"].text
	if not chosen_text:
		return False
	chosen_value = int(chosen_text)
	reducer_result = game_engine.handle_gameplay_event(
		current_gameplay_state(),
		"answer_selected",
		chosen_value,
	)
	if reducer_result["intent"] == "ignore":
		return False
	return handle_gameplay_answer_intent(
		reducer_result["intent"],
		reducer_result["state"],
		chosen_value,
	)


def dispatch_pressed_action(pressed):
	debug_helper_transition("dispatch role={}".format(pressed["role"]))
	intent = game_engine.route_pressed_action(
		pressed["role"],
		mode_select_active=mode_select_active,
		game_started=game_started,
	)
	if intent == "handle_quit":
		return handle_quit_press()
	if intent == "handle_next":
		return handle_next_press()
	if intent == "handle_name_entry":
		return handle_name_entry_press(pressed)
	if intent == "handle_kb_entry":
		return handle_kb_entry_press(pressed)
	if intent == "handle_mode_select_answer":
		return handle_mode_select_answer_press(pressed)
	if intent == "handle_game_answer":
		return handle_game_answer_press(pressed)
	return False


def process_debounced_press(pressed, tx, ty):
	global last_pressed, touch_release_required, pending_pressed, pending_press_count
	accept_press = game_engine.route_debounced_press(
		pressed is not None,
		pressed is last_pressed,
		pending_press_count,
		TOUCH_DEBOUNCE_PRESS_COUNT,
	)
	if not accept_press:
		return

	screen_changed = False
	if last_pressed is not None:
		set_button_color(last_pressed, last_pressed["base_color"])

	set_button_color(pressed, pressed_button_color(pressed))
	debug_helper_transition("debounced press accepted {}".format(pressed["name"]))
	try:
		memory_text = "free={} alloc={}".format(gc.mem_free(), gc.mem_alloc())
	except AttributeError:
		memory_text = "memory=n/a"
	print("{} pressed at ({}, {}) | {}".format(pressed["name"], tx, ty, memory_text))
	screen_changed = dispatch_pressed_action(pressed)

	if screen_changed:
		last_pressed = None
	else:
		last_pressed = pressed
	touch_release_required = True
	pending_pressed = None
	pending_press_count = 0


def handle_no_touch_state():
	global touch_release_required, pending_pressed, pending_press_count, no_touch_count, last_pressed
	clear_touch_release_required, next_no_touch_count, clear_last_pressed = game_engine.route_no_touch_state(
		touch_release_required,
		last_pressed is not None,
		no_touch_count,
		TOUCH_RELEASE_IDLE_COUNT,
	)
	if clear_touch_release_required:
		debug_helper_transition("touch released")
		touch_release_required = False
	pending_pressed = None
	pending_press_count = 0
	no_touch_count = next_no_touch_count
	if clear_last_pressed:
		debug_helper_transition("release button highlight {}".format(last_pressed["name"]))
		set_button_color(last_pressed, last_pressed["base_color"])
		last_pressed = None


def dispatch_touch_cycle_intent(intent, touch):
	global pending_pressed, pending_press_count, no_touch_count
	if intent == "wait_for_touch_release":
		pending_pressed = None
		pending_press_count = 0
		no_touch_count = 0
		return

	if intent == "process_touch":
		no_touch_count = 0
		#print(gc.mem_free())
		tx, ty, pressed = resolve_touch_press(touch)
		update_pending_press_state(pressed)
		process_debounced_press(pressed, tx, ty)
		return

	handle_no_touch_state()


def initialize_runtime_startup():
	global player_names_cache
	initialize_input_adapter()
	update_clock_label(True)
	player_names_cache = load_player_names(None)
	set_status_led(LED_COLOR_BLUE)
	play_buzzer_tone(BUZZER_STARTUP_FREQUENCY, BUZZER_STARTUP_DURATION)


def run_main_loop_iteration():
	update_game_timer()
	update_clock_label()
	update_status_led()
	update_buzzer()
	touch = read_filtered_touch()
	intent = game_engine.route_touch_cycle_state(
		touch is not None,
		touch_release_required,
	)
	dispatch_touch_cycle_intent(intent, touch)
	# emit_runtime_snapshot_if_due()
	time.sleep(0.05)


def run_main_loop():
	while True:
		run_main_loop_iteration()


game_started = False
mode_select_active = False
selecting_entry_type = False
selecting_problem_count = False
selecting_score_name = False
active_questions = addition
current_operator_symbol = "+"
current_game_type = "Addition"
current_entry_type = "Choice"
kb_answer_text = ""
problem_count_target = 10
question_order = []
current_problem_position = 0
current_correct_answer = None
game_start_time = 0.0
last_elapsed_second = -1
total_attempts = 0
total_correct = 0
total_skipped = 0
selectable_player_names = []
player_names_cache = []
player_name_page_index = 0
current_player_name = ""
post_score_status_active = False
post_score_page_index = 0
post_score_player_name = ""
post_score_current_entry = None
start_screen_top_scores_active = False
start_screen_top_score_index = 0
manual_name_value = ""
name_entry_letter_page = 0
name_entry_message = ""
current_page_name = "game_mc"
last_pressed = None
pending_pressed = None
pending_press_count = 0
no_touch_count = 0
touch_release_required = False
last_clock_update = -5.0
led_flash_active = False
led_flash_deadline = 0.0
led_flash_color = LED_COLOR_OFF
last_runtime_snapshot_time = -999.0

initialize_runtime_startup()
run_main_loop()
