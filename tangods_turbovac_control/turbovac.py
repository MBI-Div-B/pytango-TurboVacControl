from tango import DevState, Database, DeviceProxy
from tango.server import Device, attribute, command, device_property, GreenMode
from importlib.resources import files
from turboctl.ui.control_interface import ControlInterface
import time


class TurboVacControlController(Device):
    Port = device_property(
        dtype=str,
        doc="Serial port for either USB COM-PORT (default: /dev/ttyACM0) or RS485 interface (for vakupi: /dev/ttyAMA0)",
        default_value="/dev/ttyAMA0",
    )
    Pressure_device_FQDN = device_property(
        dtype=str, doc="Tango device which indicates pressure in the evacuated volume"
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
        if 4 in status_codes or 5 in status_codes:
            state = DevState.MOVING
        if 2 in status_codes:
            state = DevState.RUNNING
        if 11 in status_codes:
            state = DevState.ON
        if 7 in status_codes or 13 in status_codes or 14 in status_codes:
            state = DevState.ALARM
        if 3 in status_codes:
            state = DevState.FAULT
        return state

    def dev_status(self):
        return "\n".join(
            map(lambda x: x.description, self._control_interface.status.status_bits)
        )

    @command
    def turn_off(self):
        self._control_interface.status.pump_on = False
        # to instantly send the command
        self._control_interface.apply_state()

    @command
    def turn_on(self):
        self._control_interface.status.pump_on = True
        # to instantly send the command
        self._control_interface.apply_state()

    @command
    def reset_error(self):
        # clear error forces pump to be switched off
        self._control_interface.reset_error()

    def always_executed_hook(self):
        now = time.time()
        if now - self._last_status_query > 0.2:
            self._last_status_query = now
            self._control_interface.get_status()
            self._control_interface.apply_state()

    def init_device(self):
        Device.init_device(self)
        self.get_device_properties()
        # since we are not able to set pump_on default value to False before
        # the ControlInterface will be created and auto_update is running instantly
        # we need to firstly disable auto_update
        self._control_interface = ControlInterface(self.Port, auto_update=False)
        self.init_dynamic_attributes()
        # then set the default value for pump_on to False
        # ask once to avoid empty variables
        self._control_interface.get_status()
        self._last_status_query = time.time()
        self._db = Database()
        if not self.is_attribute_polled("State"):
            self.poll_attribute("State", 9500)

    def init_dynamic_attributes(self):
        if self.Pressure_device_FQDN is not None:
            try:
                self.pressure_proxy = DeviceProxy(self.Pressure_device_FQDN)
                self.pressure_proxy.ping()
            except:
                self.info_stream(
                    f"Could not connect to pressure device {self.Pressure_device_FQDN}"
                )
            else:
                self.add_attribute(
                    attribute(
                        name="pressure",
                        label="pressure",
                        dtype=float,
                        format="%7.3e",
                        unit="mbar",
                        fget=self.get_pressure,
                    )
                )

    def get_pressure(self, attr_name):
        return self.pressure_proxy.pressure

    def delete_device(self):
        Device.delete_device(self)
