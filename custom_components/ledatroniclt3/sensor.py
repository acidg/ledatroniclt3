"""
Support for getting temperature and state from LEDATronic LT3 Wifi devices.

configuration.yaml:

sensors:
    - platform: ledatroniclt3
      host: 192.168.178.222

"""
import logging
import socket
import datetime
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_PORT, CONF_HOST, TEMP_CELSIUS, PERCENTAGE
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import (
    ConfigType,
    HomeAssistantType,
)
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_HOST): cv.string,
    }
)


class LedatronicComm:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.current_temp = None
        self.upper_temp = None
        self.center_temp = None
        self.lower_temp = None
        self.forerun_temp = None
        self.pump = None
        self.current_state = None
        self.current_valve_pos_target = None
        self.current_valve_pos_actual = None
        self.last_update = None

    def update(self):
        # update at most every 10 seconds
        if self.last_update != None and (
            datetime.datetime.now() - self.last_update
        ) < datetime.timedelta(seconds=30):
            return

        self.last_update = datetime.datetime.now()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.host, self.port))

            # Try up to 5 times
            for x in range(5):
                content = s.recv(1024)
                if len(content) != 43:
                    continue

                s.close()

                self.current_temp = int.from_bytes(content[2:4], byteorder="big")
                self.current_valve_pos_target = content[4]
                self.current_valve_pos_actual = content[5]

                stateVal = content[6]
                if stateVal == 0:
                    self.current_state = "Bereit"
                elif stateVal == 2:
                    self.current_state = "Anheizen"
                elif stateVal == 3 or stateVal == 4:
                    self.current_state = "Heizbetrieb"
                elif stateVal == 7 or stateVal == 8:
                    self.current_state = "Grundglut"
                elif stateVal == 97:
                    self.current_state = "Heizfehler"
                elif stateVal == 98:
                    self.current_state = "Tür offen"
                else:
                    self.current_state = "Unbekannter Status: " + str(stateVal)

                self.lower_temp = content[36]
                self.center_temp = content[37]
                self.upper_temp = content[38]
                self.forerun_temp = content[39]
                self.pump = False if content[40] == 0 else True

            _LOGGER.error("Failed to parse data from socket after 5 tries!")
        finally:
            s.close()


def setup_platform(
    hass: HomeAssistantType, config: ConfigType, add_entities, discovery_info=None
):
    """Set up the LEDATRONIC LT3 Wifi sensors."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    comm = LedatronicComm(host, port)

    add_entities(
        [
            LedatronicTemperatureSensor(comm),
            LedatronicStateSensor(comm),
            LedatronicValveSensor(comm),
            LedatronicUpperTemperatureSensor(comm),
            LedatronicCenterTemperatureSensor(comm),
            LedatronicLowerTemperatureSensor(comm),
            LedatronicForerunTemperatureSensor(comm),
            LedatronicPumpSensor(comm),
        ]
    )


class LedatronicSensor(Entity):
    def __init__(self, comm, name):
        """Initialize the sensor."""
        self._name = name
        self.comm = comm

    @property
    def name(self):
        return self._name

    def update(self):
        """Retrieve latest state."""
        try:
            self.comm.update()
        except Exception as exception:
            _LOGGER.exception("Failed to get LEDATRONIC LT3 Wifi state: %s" % exception)


class LedatronicTemperatureSensor(LedatronicSensor):
    def __init__(self, comm):
        super().__init__(comm, "ledatronic_brennraum_temp")

    @property
    def state(self):
        return self.comm.current_temp

    @property
    def unit_of_measurement(self):
        return TEMP_CELSIUS


class LedatronicStateSensor(LedatronicSensor):
    def __init__(self, comm):
        super().__init__(comm, "ledatronic_status")

    @property
    def state(self):
        """Return the current state of the entity."""
        return self.comm.current_state


class LedatronicValveSensor(LedatronicSensor):
    def __init__(self, comm):
        super().__init__(comm, "ledatronic_valve")

    @property
    def state(self):
        return self.comm.current_valve_pos_target

    @property
    def unit_of_measurement(self):
        return PERCENTAGE

    @property
    def device_state_attributes(self):
        """Show Device Attributes."""
        return {"Actual Position": self.comm.current_valve_pos_actual}


class LedatronicUpperTemperatureSensor(LedatronicSensor):
    def __init__(self, comm):
        super().__init__(comm, "ledatronic_speicher_temp_oben")

    @property
    def state(self):
        return self.comm.upper_temp

    @property
    def unit_of_measurement(self):
        return TEMP_CELSIUS


class LedatronicCenterTemperatureSensor(LedatronicSensor):
    def __init__(self, comm):
        super().__init__(comm, "ledatronic_speicher_temp_mitte")

    @property
    def state(self):
        return self.comm.center_temp

    @property
    def unit_of_measurement(self):
        return TEMP_CELSIUS


class LedatronicLowerTemperatureSensor(LedatronicSensor):
    def __init__(self, comm):
        super().__init__(comm, "ledatronic_speicher_temp_unten")

    @property
    def state(self):
        return self.comm.lower_temp

    @property
    def unit_of_measurement(self):
        return TEMP_CELSIUS


class LedatronicForerunTemperatureSensor(LedatronicSensor):
    def __init__(self, comm):
        super().__init__(comm, "ledatronic_vorlauf_temp")

    @property
    def state(self):
        return self.comm.forerun_temp

    @property
    def unit_of_measurement(self):
        return TEMP_CELSIUS


class LedatronicPumpSensor(LedatronicSensor):
    def __init__(self, comm):
        super().__init__(comm, "ledatronic_pumpe")

    @property
    def state(self):
        return self.comm.pump

    @property
    def unit_of_measurement(self):
        return TEMP_CELSIUS
