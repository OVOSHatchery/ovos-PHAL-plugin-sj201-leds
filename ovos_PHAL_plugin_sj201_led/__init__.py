##########################################################################
# sj201-reset-led
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
##########################################################################

import os
import time
from threading import Event
from os.path import exists

from ovos_bus_client.message import Message
from ovos_plugin_manager.phal import PHALPlugin
from ovos_utils.log import LOG
from ovos_PHAL.detection import is_mycroft_sj201

RED = (255, 0, 0)
YELLOW = (255, 150, 0)
GREEN = (0, 255, 0)
CYAN = (0, 255, 255)
BLUE = (0, 0, 255)
PURPLE = (180, 0, 255)
BLACK = (0, 0, 0)

I2C_PLATFORM_FILE = "/etc/OpenVoiceOS/i2c_platform"


class SJ201Interface:
    DeviceAddr = 0x04
    num_pixels = 12
    current_rgb = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    def setColor(self, pixel, colors):
        assert pixel < 12
        redVal = colors[0]
        greenVal = colors[1]
        blueVal = colors[2]

        SJ201Interface.current_rgb[pixel] = (redVal, greenVal, blueVal)

        commandOS = "i2cset -a -y 1  %d %d %d %d %d i " % (
            self.DeviceAddr,
            pixel,
            redVal,
            greenVal,
            blueVal)

        # print(commandOS)
        os.system(commandOS)

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
        self.color_chase(BLACK, 0)


class MycroftSJ201Validator:
    @staticmethod
    def validate(config=None):
        # If the user enabled the plugin no need to go further
        if config.get("enabled"):
            return True
        # Check for a file created by ovos-i2csound
        # https://github.com/OpenVoiceOS/ovos-i2csound/blob/dev/ovos-i2csound#L76
        LOG.debug(f"checking file {I2C_PLATFORM_FILE}")
        if exists(I2C_PLATFORM_FILE):
            with open(I2C_PLATFORM_FILE) as f:
                platform = f.readline().strip().lower()
            if platform == "SJ201V6":
                return True
        # Try a direct hardware check
        if is_mycroft_sj201():
            LOG.debug("direct hardware check")
            return True
        LOG.debug("no validation")
        return False


class MycroftSJ201(PHALPlugin):
    validator = MycroftSJ201Validator

    def __init__(self, bus=None, config=None):
        super().__init__(bus=bus, name="ovos-PHAL-plugin-sj201-leds", config=config)
        self.stopped = Event()
        self.config = config or {
            "default_color": "red"
        }

        self.sj = SJ201Interface()

        self.speaking = False
        self.listening = False

        self._init_animation()

        self.bus.on("mycroft.internet.connected", self.on_display_reset)
        self.bus.on("mycroft.stop", self.on_display_reset)

    @property
    def default_color(self):
        color = self.config.get("default_color", "red")
        if color == "red":
            color = RED
        elif color == "green":
            color = GREEN
        elif color == "yellow":
            color = YELLOW
        elif color == "cyan":
            color = CYAN
        elif color == "blue":
            color = BLUE
        elif color == "purple":
            color = PURPLE
        else:
            LOG.error(f"invalid color: '{color}', defaulting to red")
            color = RED
            # TODO - allow using rgb in config
        return color

    def _init_animation(self):
        self.sj.color_chase(self.default_color, 0)
        time.sleep(1)
        self.sj.turn_off()

    def _check_services_ready(self):
        """Report if all specified services are ready.

        services (iterable): service names to check.
        """
        services = {k: False for k in ["skills",  # ovos-core
                                       "audio",  # ovos-audio
                                       "voice"  # ovos-dinkum-listener
                                       ]}

        for ser, rdy in services.items():
            if rdy:
                # already reported ready
                continue
            response = self.bus.wait_for_response(
                Message(f'mycroft.{ser}.is_ready',
                        context={"source": "sj201-leds", "destination": "skills"}))
            if response and response.data['status']:
                services[ser] = True
        return all([services[ser] for ser in services])

    def handle_get_color(self, message):
        """Get the eye RGB color for all pixels
        Returns:
           (list) list of (r,g,b) tuples for each eye pixel
        """
        self.bus.emit(message.reply("enclosure.eyes.rgb",
                      {"pixels": self.sj.current_rgb}))

    # Audio Events
    def on_record_begin(self, message=None):
        # NOTE: ignore self._mouth_events, listening should ALWAYS be obvious
        self.listening = True
        self.on_listen()

    def on_record_end(self, message=None):
        self.listening = False
        self.on_system_reset(message)

    def on_audio_output_start(self, message=None):
        self.speaking = True
        self.on_talk()

    def on_audio_output_end(self, message=None):
        self.speaking = False
        self.on_system_reset(message)

    def on_awake(self, message=None):
        ''' on wakeup animation
        triggered by "mycroft.awoken"
        '''
        self._init_animation()  # TODO - dedicated animation

    def on_sleep(self, message=None):
        ''' on naptime animation
        triggered by "recognizer_loop:sleep"
        '''
        self._init_animation()  # TODO - dedicated animation

    def on_reset(self, message=None):
        """The enclosure should restore itself to a started state.
        Typically this would be represented by the eyes being 'open'
        and the mouth reset to its default (smile or blank).
        triggered by "enclosure.reset"
        """
        self.sj.turn_off()

    # System Events
    def on_no_internet(self, message=None):
        """
        triggered by "enclosure.notify.no_internet"
        """
        # TODO - dedicated animation

    def on_system_reset(self, message=None):
        """The enclosure hardware should reset any CPUs, etc.
        triggered by "enclosure.system.reset"
        """
        self.sj.turn_off()

    def on_system_blink(self, message=None):
        """The 'eyes' should blink the given number of times.
        triggered by "enclosure.system.blink"

        Args:
            times (int): number of times to blink
        """
        n = int(message.data.get("times", 1))
        for i in range(n):
            self.sj.color_chase(self.default_color, wait=0)
            time.sleep(1)
            self.sj.turn_off()

    # Eyes messages
    def on_eyes_on(self, message=None):
        """Illuminate or show the eyes.
        triggered by "enclosure.eyes.on"
        """
        self.sj.color_chase(self.default_color, wait=0)

    def on_eyes_off(self, message=None):
        """Turn off or hide the eyes.
        triggered by "enclosure.eyes.off"
        """
        self.sj.turn_off()

    def on_eyes_fill(self, message=None):
        """triggered by "enclosure.eyes.fill" """
        # TODO

    def on_eyes_blink(self, message=None):
        """Make the eyes blink
        triggered by "enclosure.eyes.blink"
        Args:
            side (str): 'r', 'l', or 'b' for 'right', 'left' or 'both'
        """
        # TODO

    def on_eyes_narrow(self, message=None):
        """Make the eyes look narrow, like a squint
        triggered by "enclosure.eyes.narrow"
        """
        # TODO

    def on_eyes_look(self, message=None):
        """Make the eyes look to the given side
        triggered by "enclosure.eyes.look"
        Args:
            side (str): 'r' for right
                        'l' for left
                        'u' for up
                        'd' for down
                        'c' for crossed
        """
        # TODO

    def on_eyes_color(self, message=None):
        """Change the eye color to the given RGB color
        triggered by "enclosure.eyes.color"
        Args:
            r (int): 0-255, red value
            g (int): 0-255, green value
            b (int): 0-255, blue value
        """
        r = int(message.data.get("r", 0))
        g = int(message.data.get("g", 0))
        b = int(message.data.get("b", 0))
        self.sj.color_chase((r, g, b), wait=0)

    def on_eyes_brightness(self, message=None):
        """Set the brightness of the eyes in the display.
        triggered by "enclosure.eyes.brightness"
        Args:
            level (int): 1-30, bigger numbers being brighter
        """
        # TODO

    def on_eyes_reset(self, message=None):
        """Restore the eyes to their default (ready) state
        triggered by "enclosure.eyes.reset".
        """
        self.sj.turn_off()

    def on_eyes_timed_spin(self, message=None):
        """Make the eyes 'roll' for the given time.
        triggered by "enclosure.eyes.timedspin"
        Args:
            length (int): duration in milliseconds of roll, None = forever
        """
        l = message.data.get("length", 10)
        for i in range(l):
            self.sj.color_chase(self.default_color, wait=0.01)

    def on_eyes_volume(self, message=None):
        """Indicate the volume using the eyes
        triggered by "enclosure.eyes.volume"
        Args:
            volume (int): 0 to 11
        """
        v = message.data.get("volume")
        for n in range(v):
            self.sj.setColor(n, self.default_color)

    def on_eyes_spin(self, message=None):
        """
        triggered by "enclosure.eyes.spin"
        """
        self.sj.color_chase(self.default_color)

    def on_eyes_set_pixel(self, message=None):
        """
        triggered by "enclosure.eyes.set_pixel"
        """
        idx = 0
        r, g, b = 255, 255, 255
        if message and message.data:
            idx = int(message.data.get("idx", idx))
            r = int(message.data.get("r", r))
            g = int(message.data.get("g", g))
            b = int(message.data.get("b", b))
        self.sj.setColor(idx, (r, g, b))

    # Display (faceplate) messages
    def on_display_reset(self, message=None):
        """Restore the mouth display to normal (blank)
        triggered by "enclosure.mouth.reset" / "recognizer_loop:record_end"
        """
        self.sj.turn_off()

    def on_talk(self, message=None):
        """Show a generic 'talking' animation for non-synched speech
        triggered by "enclosure.mouth.talk"
        """
        self.sj.color_chase(self.default_color,
                            0.1)  # TODO dedicated animation

    def on_think(self, message=None):
        """Show a 'thinking' image or animation
        triggered by "enclosure.mouth.think"
        """
        # TODO

    def on_listen(self, message=None):
        """Show a 'thinking' image or animation
        triggered by "enclosure.mouth.listen" / "recognizer_loop:record_begin"
        """
        # TODO

    def on_smile(self, message=None):
        """Show a 'smile' image or animation
        triggered by "enclosure.mouth.smile"
        """
        # TODO

    def on_weather_display(self, message=None):
        """Show a the temperature and a weather icon

        triggered by "enclosure.weather.display"

        Args:
            img_code (char): one of the following icon codes
                         0 = sunny
                         1 = partly cloudy
                         2 = cloudy
                         3 = light rain
                         4 = raining
                         5 = stormy
                         6 = snowing
                         7 = wind/mist
            temp (int): the temperature (either C or F, not indicated)
        """
        if message and message.data:
            # Convert img_code to icon
            img_code = message.data.get("img_code", None)
            icon = None
            if img_code == 0:
                # sunny
                pass  # TODO
            elif img_code == 1:
                # partly cloudy
                pass  # TODO
            elif img_code == 2:
                # cloudy
                pass  # TODO
            elif img_code == 3:
                # light rain
                pass  # TODO
            elif img_code == 4:
                # raining
                pass  # TODO
            elif img_code == 5:
                # storming
                pass  # TODO
            elif img_code == 6:
                # snowing
                pass  # TODO
            elif img_code == 7:
                # wind/mist
                pass  # TODO
