# coding: utf-8
import atexit
import glob
import os
import select
import sys

JS_EVENT_BUTTON = 0x01  # pressed/released
JS_EVENT_AXIS = 0x02  # joystick moved
JS_EVENT_INIT = 0x80

JS_BUTTON_RELEASE = 0x00
JS_BUTTON_PRESS = 0x01

# Arrows (directional keys)
DIR_ARROW_UP = 'U'
DIR_ARROW_RIGHT = 'R'
DIR_ARROW_DOWN = 'D'
DIR_ARROW_LEFT = 'L'

# MK: key map
# ML: multilaser joystick (tested on a JS028 and JS030 joypad)
KM_ML_TRIANGLE = 0
KM_ML_CIRCLE = 1
KM_ML_X = 2
KM_ML_SQUARE = 3
KM_ML_L1 = 4
KM_ML_R1 = 5
KM_ML_L2 = 6
KM_ML_R2 = 7
KM_ML_SELECT = 8
KM_ML_START = 9
KM_ML_L3 = 10
KM_ML_R3 = 11

# Analog off
KM_ML_ARROW_AXIS_X = 0
KM_ML_ARROW_AXIS_Y = 1

# Analog on
KM_ML_LEFT_STICK_AXIS_X = 0
KM_ML_LEFT_STICK_AXIS_Y = 1
KM_ML_RIGHT_STICK_AXIS_X = 2
KM_ML_RIGHT_STICK_AXIS_Y = 3
KM_ML_ARROWA_AXIS_X = 4
KM_ML_ARROWA_AXIS_Y = 5


class JoystickEvent:
    """Represent a Joystick event."""

    def __init__(self, raw_8_bytes_data):
        """raw_8_bytes_data must be a string."""
        assert len(raw_8_bytes_data) == 8, 'Invalid size of data'
        self.time = raw_8_bytes_data[:4]
        self.value = int.from_bytes(
            raw_8_bytes_data[4:6],
            sys.byteorder, signed=True)
        self.type = ord(raw_8_bytes_data[6:7])
        self.number = ord(raw_8_bytes_data[7:8])
        self.direction = self.get_direction()

    def get_direction(self):
        """Get which arrow button key was pressed."""
        x_axis = [KM_ML_ARROW_AXIS_X,
                  KM_ML_LEFT_STICK_AXIS_X,
                  KM_ML_RIGHT_STICK_AXIS_X,
                  KM_ML_ARROWA_AXIS_X]

        y_axis = [KM_ML_ARROW_AXIS_Y,
                  KM_ML_LEFT_STICK_AXIS_Y,
                  KM_ML_RIGHT_STICK_AXIS_Y,
                  KM_ML_ARROWA_AXIS_Y]

        if self.type == JS_EVENT_AXIS:
            if (self.number in x_axis) and (self.value < 0):
                return DIR_ARROW_LEFT
            elif (self.number in x_axis) and (self.value > 0):
                return DIR_ARROW_RIGHT

            if (self.number in y_axis) and (self.value < 0):
                return DIR_ARROW_UP
            elif (self.number in y_axis) and (self.value > 0):
                return DIR_ARROW_DOWN


class Joystick:
    """Represent a Joystick."""

    ANY = 0
    BUTTON_PRESS = 1
    BUTTON_RELEASE = 2
    ARROW_PRESS = 3
    ARROW_RELEASE = 4

    def __init__(self, timeout=0.1, device_path=None, verbose=False):
        """If you want make blocking set timeout to None."""
        self.timeout = timeout
        self.verbose = verbose
        if not device_path:
            # getting the first device found
            devices = self.get_joystick_devices()
            if devices:
                device_path = devices[0]
        self.device_file = None
        if device_path and os.path.exists(device_path):
            self.device_file = open(device_path, 'rb')
            atexit.register(self.device_file.close)
        self.function_map = {
            Joystick.ANY: list(),
            Joystick.BUTTON_PRESS: list(),
            Joystick.BUTTON_RELEASE: list(),
            Joystick.ARROW_PRESS: list(),
            Joystick.ARROW_RELEASE: list()
        }

    def get_joystick_devices(self):
        """Return a list of joystick devices path."""
        return glob.glob('/dev/input/js[0-9]')

    def bind(self, event_type, func, operation=None):
        """Bind a function to a Joystick event.

        Arguments:
            event_type: The event type must be one of:
                Joystick.ANY, Joystick.BUTTON_PRESS,
                Joystick.BUTTON_RELEASE
            func: a function that will be executed when event occurs.
                It must receive a JoystickEvent object as argument
            operation: a string representing if the function
                will be placed in a list with others or if must
                be the only function to be executed when function
                occurs. If '+' the function will be one more
                function to be executed.

                If operation='None' then all previous functions
                will be deleted and just 'func' function will be
                executed.

                If operation='-' the function 'func' will be removed
                from execution list
        """
        assert operation in (None, '+', '-'), 'Invalid operation'
        assert event_type in (
            Joystick.ANY,
            Joystick.BUTTON_PRESS, Joystick.BUTTON_RELEASE,
            Joystick.ARROW_PRESS, Joystick.ARROW_RELEASE)
        if operation is None:
            self.function_map[event_type] = list()
        list_func = self.function_map[event_type].append
        if list_func == '-':
            list_func = self.function_map[event_type].remove
        list_func(func)

    def connected(self):
        """Return True if Joystick was found."""
        return bool(self.device_file)

    def process_events(self):
        """Verify if exists some joystick event and call binds."""
        read, write, error = select.select(
            [self.device_file.fileno()], [], [], self.timeout)
        # get all pending events
        while read:
            # each event has 8 bytes
            event = JoystickEvent(self.device_file.read(8))
            if self.verbose:
                print('\nType: %d\nNumber: %d\nValue: %d\nDirection: %s\n' % (
                    event.type, event.number, event.value, event.direction))
            # running events
            for func in self.function_map.get(Joystick.ANY):
                func(event)

            if event.type == JS_EVENT_BUTTON:
                key = None
                button = event.value
                if button == JS_BUTTON_RELEASE:
                    key = Joystick.BUTTON_RELEASE
                elif button == JS_BUTTON_PRESS:
                    key = Joystick.BUTTON_PRESS
                if key:
                    for func in self.function_map[key]:
                        func(event)
            elif event.type == JS_EVENT_AXIS:
                key = Joystick.ARROW_RELEASE
                if event.value:
                    key = Joystick.ARROW_PRESS
                for func in self.function_map[key]:
                    func(event)

            read, write, error = select.select(
                [self.device_file.fileno()], [], [], self.timeout)


if __name__ == '__main__':
    def on_button_press(event):
        if event.number == KM_ML_X:
            print('ok')

    joystick = Joystick(timeout=1, verbose=True)
    joystick.bind(Joystick.BUTTON_PRESS, on_button_press)
    if joystick.connected():
        while True:
            joystick.process_events()
    else:
        print('Device not found')
