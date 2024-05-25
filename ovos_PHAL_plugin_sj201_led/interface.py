import abc
import os
import time

import neopixel
from RPi import GPIO

GPIO.setmode(GPIO.BCM)  # Use BCM pins D4 = GPIO #4
GPIO.setwarnings(False)  # shh!


class LedPin:
    """taken from https://github.com/adafruit/Adafruit_Blinka/blob/main/src/adafruit_blinka/microcontroller/bcm283x/pin.py
    no need to drag the whole dependency"""

    IN = 0
    OUT = 1
    LOW = 0
    HIGH = 1
    PULL_NONE = 0
    PULL_UP = 1
    PULL_DOWN = 2

    id = None
    _value = LOW
    _mode = IN

    def __init__(self, bcm_number=12):
        self.id = bcm_number

    def __repr__(self):
        return str(self.id)

    def __eq__(self, other):
        return self.id == other

    def init(self, mode=IN, pull=None):
        """Initialize the Pin"""
        if mode is not None:
            if mode == self.IN:
                self._mode = self.IN
                GPIO.setup(self.id, GPIO.IN)
            elif mode == self.OUT:
                self._mode = self.OUT
                GPIO.setup(self.id, GPIO.OUT)
            else:
                raise RuntimeError("Invalid mode for pin: %s" % self.id)
        if pull is not None:
            if self._mode != self.IN:
                raise RuntimeError("Cannot set pull resistor on output")
            if pull == self.PULL_UP:
                GPIO.setup(self.id, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            elif pull == self.PULL_DOWN:
                GPIO.setup(self.id, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            else:
                raise RuntimeError("Invalid pull for pin: %s" % self.id)

    def value(self, val=None):
        """Set or return the Pin Value"""
        if val is not None:
            if val == self.LOW:
                self._value = val
                GPIO.output(self.id, val)
            elif val == self.HIGH:
                self._value = val
                GPIO.output(self.id, val)
            else:
                raise RuntimeError("Invalid value for pin")
            return None
        return GPIO.input(self.id)


class AbstractLedInterface:
    num_pixels = 12

    @abc.abstractmethod
    def setColor(self, pixel, colors):
        pass

    def wheel(self, pos):
        # Input a value 0 to 255 to get a color value.
        # The colours are a transition r - g - b - back to r.
        if pos < 0 or pos > 255:
            return (0, 0, 0)
        if pos < 85:
            return (255 - pos * 3, pos * 3, 0)
        if pos < 170:
            pos -= 85
            return (0, 255 - pos * 3, pos * 3)
        pos -= 170
        return (pos * 3, 0, 255 - pos * 3)

    def rainbow_cycle(self, wait=0):
        for j in range(255):
            for i in range(self.num_pixels):
                rc_index = (i * 256 // self.num_pixels) + j
                colors = self.wheel(rc_index & 255)
                self.setColor(i, colors)
                time.sleep(wait)

    def color_chase(self, color, wait=0.2):
        for i in range(self.num_pixels):
            self.setColor(i, color)
            time.sleep(wait)

    def turn_off(self):
        self.color_chase((0, 0, 0), 0)


class SJ201DevKitInterface(AbstractLedInterface):
    DeviceAddr = 0x04
    current_rgb = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    def setColor(self, pixel, colors):
        assert pixel < 12
        redVal = colors[0]
        greenVal = colors[1]
        blueVal = colors[2]

        SJ201DevKitInterface.current_rgb[pixel] = (redVal, greenVal, blueVal)

        commandOS = "i2cset -a -y 1  %d %d %d %d %d i " % (
            self.DeviceAddr,
            pixel,
            redVal,
            greenVal,
            blueVal)

        # print(commandOS)
        os.system(commandOS)


class SJ201Interface(AbstractLedInterface):
    current_rgb = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    def __init__(self, brightness=0.6):
        self.brightness = brightness
        self.pixels = neopixel.NeoPixel(
            LedPin(12),
            self.num_pixels,
            brightness=self.brightness,
            auto_write=False,
            pixel_order=neopixel.GRB
        )

    def setColor(self, pixel, colors):
        assert pixel < 12
        red_val = colors[0]
        green_val = colors[1]
        blue_val = colors[2]

        self.pixels[pixel] = (red_val, green_val, blue_val)
        self.pixels.show()
        SJ201Interface.current_rgb[pixel] = (red_val, green_val, blue_val)
