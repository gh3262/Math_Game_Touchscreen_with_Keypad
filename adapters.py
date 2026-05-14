class FilePersistenceAdapter:
    """Default file persistence backend for CircuitPython/CPython-compatible open()."""

    def open_read(self, file_path):
        return open(file_path, "r")

    def open_write(self, file_path):
        return open(file_path, "w")

    def open_append(self, file_path):
        return open(file_path, "a")


class DisplayIORendererAdapter:
    """Renderer backend that updates displayio labels/buttons with no-op guards."""

    def set_button_color(self, button, color):
        if button["fill_palette"][0] == color and button["label"].color == color:
            return
        button["fill_palette"][0] = color
        button["label"].color = color

    def set_button_text(self, button, text):
        if button["label"].text == text:
            return
        button["label"].text = text

    def set_label_text_if_changed(self, target_label, text):
        if target_label.text == text:
            return False
        target_label.text = text
        return True


class TouchInputAdapter:
    """Input backend that converts touchscreen samples into button hits."""

    def __init__(self, touchscreen, pressure_min, touch_to_pixel_fn, button_from_touch_fn):
        self.touchscreen = touchscreen
        self.pressure_min = pressure_min
        self.touch_to_pixel_fn = touch_to_pixel_fn
        self.button_from_touch_fn = button_from_touch_fn

    def read_touch_sample(self):
        if not self.touchscreen.touched:
            return None
        touch_sample = self.touchscreen.touch
        if touch_sample["pressure"] < self.pressure_min:
            return None
        return touch_sample

    def resolve_touch_to_button(self, touch_sample):
        if touch_sample is None:
            return 0, 0, None
        tx, ty = self.touch_to_pixel_fn(touch_sample["x"], touch_sample["y"])
        pressed = self.button_from_touch_fn(tx, ty)
        return tx, ty, pressed
