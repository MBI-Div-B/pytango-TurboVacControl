from tango import AttrWriteType, DispLevel, DevState
from tango.server import Device, attribute, command, device_property, GreenMode
from importlib.resources import files
from turboctl.ui.control_interface import ControlInterface
import numpy as np
import asyncio


class TurboVacControlController(Device):
    PUMP_SERIAL_PORT = device_property(
        dtype=str,
        doc="Serial port for either USB COM-PORT (default: /dev/ttyACM0) or RS485 interface (for vakupi: /dev/ttyAMA0)",
        default_value="/dev/ttyAMA0",
    )
    PUMP_POLLING_PERIOD = device_property(
        dtype=int,
        doc="Polling period in secs",
        default_value="5",
    )
    pump_on = attribute(
        label="pump on",
        dtype=bool,
        access=AttrWriteType.READ_WRITE,
        hw_memorized=True,
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
    extra_status = attribute(
        label="status",
        dtype=(str,),
    )

    def read_pump_on(self):
        return self._control_interface.status.pump_on

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

    def read_extra_status(self):
        descriptions = (
            member.description for member in self._control_interface.status.status_bits
        )
        return descriptions

    def init_device(self):
        Device.init_device(self)
        self.set_state(DevState.INIT)
        self.get_device_properties()
        self._control_interface = ControlInterface(
            self.PUMP_SERIAL_PORT, auto_update=True
        )
        self._control_interface.status.pump_on = False
        self._control_interface.timestep = self.PUMP_POLLING_PERIOD
        self.set_state(DevState.ON)

    def delete_device(self):
        Device.delete_device(self)
