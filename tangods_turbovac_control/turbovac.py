from tango import DevState, Database
from tango.server import Device, attribute, command, device_property, GreenMode
from importlib.resources import files
from turboctl.ui.control_interface import ControlInterface
import time


class TurboVacControlController(Device):
    PUMP_SERIAL_PORT = device_property(
        dtype=str,
        doc="Serial port for either USB COM-PORT (default: /dev/ttyACM0) or RS485 interface (for vakupi: /dev/ttyAMA0)",
        default_value="/dev/ttyAMA0",
    )
    DEVICE_PUMP_ON = device_property(
        dtype=bool, doc="save of last set value", default_value=False
    )
    frequency = attribute(
        label="frequency",
        dtype=float,
        unit="Hz",
        format="%2.2f",
    )
    temperature = attribute(
        label="temperature",
        dtype=float,
        unit="C",
        format="%2.2f",
    )
    current = attribute(
        label="current",
        dtype=float,
        unit="A",
        format="%2.2f",
    )
    voltage = attribute(
        label="voltage",
        dtype=float,
        unit="V",
        format="%2.2f",
    )
    warnings = attribute(
        label="warnings",
        dtype=str,
    )
    error = attribute(
        label="error",
        dtype=str,
    )

    def write_pump_on(self, value):
        self._control_interface.status.pump_on = value
        # called once to instantly apply the change of pump_on
        self._control_interface.get_status()

    def read_frequency(self):
        return self._control_interface.status.frequency

    def read_temperature(self):
        return self._control_interface.status.temperature

    def read_current(self):
        return self._control_interface.status.current

    def read_voltage(self):
        return self._control_interface.status.voltage

    def dev_state(self):
        state = DevState.UNKNOWN
        status_codes = list(
            map(lambda x: int(x), self._control_interface.status.status_bits)
        )
        # see codes.StatusBits in turboctl.telegram
        if 0 in status_codes:
            state = DevState.INIT
        if 2 in status_codes:
            state = DevState.ON
        if 4 in status_codes or 5 in status_codes:
            state = DevState.MOVING
        if 11 in status_codes:
            state = DevState.RUNNING
        if 7 in status_codes or 13 in status_codes or 14 in status_codes:
            state = DevState.ALARM
        if 3 in status_codes:
            state = DevState.FAULT
        return state

    def dev_status(self):
        return ", ".join(
            map(lambda x: x.description, self._control_interface.status.status_bits)
        )

    def read_warnings(self):
        warnings_str = ""
        for status in self._control_interface.status.status_bits:
            if int(status) in [7, 13, 14]:
                warnings_str += f"{status.description}, "
        if warnings_str == "":
            warnings_str = "Clear"
        return warnings_str

    def read_error(self):
        error_str = "Clear"
        for status in self._control_interface.status.status_bits:
            if int(status) == 3:
                error_str = status.description
        return error_str

    @command
    def turn_off(self):
        self._control_interface.status.pump_on = False
        # to instantly send the command
        self._control_interface.get_status()
        # save the value for the next start
        self._db.put_device_property(self.get_name(), {"DEVICE_PUMP_ON": False})

    @command
    def turn_on(self):
        self._control_interface.status.pump_on = True
        # to instantly send the command
        self._control_interface.get_status()
        # save the value for the next start
        self._db.put_device_property(self.get_name(), {"DEVICE_PUMP_ON": True})

    @command
    def reset_error(self):
        self._control_interface.reset_error()
        # clear error forces pump to be switched off
        self._db.put_device_property(self.get_name(), {"DEVICE_PUMP_ON": False})

    def always_executed_hook(self):
        now = time.time()
        if now - self._last_status_query > 0.2:
            self._last_status_query = now
            self._control_interface.get_status()

    def init_device(self):
        Device.init_device(self)
        self.get_device_properties()
        # since we are not able to set pump_on default value to False before
        # the ControlInterface will be created and auto_update is running instantly
        # we need to firstly disable auto_update
        self._control_interface = ControlInterface(
            self.PUMP_SERIAL_PORT, auto_update=False
        )
        # then set the default value for pump_on to False
        self._control_interface.status.pump_on = self.DEVICE_PUMP_ON
        # ask once to avoid empty variables
        self._control_interface.get_status()
        self._last_status_query = time.time()
        self._db = Database()
        if not self.is_attribute_polled("State"):
            self.poll_attribute("State", 9500)

    def delete_device(self):
        # save on device close
        self._db.put_device_property(
            self.get_name(), {"DEVICE_PUMP_ON": self._control_interface.status.pump_on}
        )
        Device.delete_device(self)
