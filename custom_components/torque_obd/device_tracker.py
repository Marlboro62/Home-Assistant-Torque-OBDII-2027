"""Position GPS du véhicule (téléphone Torque) sous forme de device_tracker."""
from __future__ import annotations

import math
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import TorqueConfigEntry, TorqueRuntimeData
from .const import (
    DOMAIN,
    PID_GPS_ACCURACY,
    PID_GPS_ALTITUDE,
    PID_GPS_LATITUDE,
    PID_GPS_LONGITUDE,
    SIGNAL_UPDATE,
)
from .sensor import vehicle_device_info


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TorqueConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the vehicle tracker."""
    async_add_entities([TorqueTracker(entry.entry_id, entry.runtime_data)])


class TorqueTracker(TrackerEntity, RestoreEntity):
    """Suit la position GPS envoyée par Torque (kff1006 / kff1005)."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = "Position"
    _attr_icon = "mdi:car"

    def __init__(self, entry_id: str, runtime: TorqueRuntimeData) -> None:
        """Initialize."""
        self._entry_id = entry_id
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_tracker"
        self._attr_device_info = vehicle_device_info(entry_id, runtime.vehicle_name)
        self._lat: float | None = None
        self._lon: float | None = None
        self._accuracy: float = 0
        self._altitude: float | None = None

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        return self._lat

    @property
    def longitude(self) -> float | None:
        return self._lon

    @property
    def location_accuracy(self) -> int:
        return int(round(self._accuracy))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return {"altitude": self._altitude} if self._altitude is not None else None

    async def async_added_to_hass(self) -> None:
        """Restaure la dernière position connue (véhicule garé)."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            self._lat = _to_float(state.attributes.get("latitude"))
            self._lon = _to_float(state.attributes.get("longitude"))
            self._accuracy = _to_float(state.attributes.get("gps_accuracy")) or 0
            self._altitude = _to_float(state.attributes.get("altitude"))
        if self._lat is None:
            self._seed_from_sensors()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE.format(self._entry_id), self._handle_update
            )
        )

    @callback
    def _seed_from_sensors(self) -> None:
        """Première installation : reprend la dernière position des capteurs lat/lon."""
        ent_reg = er.async_get(self.hass)
        coords: list[float | None] = []
        for pid in (PID_GPS_LATITUDE, PID_GPS_LONGITUDE):
            entity_id = ent_reg.async_get_entity_id(
                "sensor", DOMAIN, f"{DOMAIN}_{self._entry_id}_{pid}"
            )
            state = self.hass.states.get(entity_id) if entity_id else None
            coords.append(_to_float(state.state) if state else None)
        lat, lon = coords
        if lat is not None and lon is not None and (lat, lon) != (0, 0):
            self._lat, self._lon = lat, lon

    @callback
    def _handle_update(self, data: dict[str, Any]) -> None:
        lat = _to_float(data.get(PID_GPS_LATITUDE))
        lon = _to_float(data.get(PID_GPS_LONGITUDE))
        # Pas de fix GPS : Torque envoie 0/0 ou rien
        if lat is None or lon is None or (lat == 0 and lon == 0):
            return
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return
        accuracy = _to_float(data.get(PID_GPS_ACCURACY)) or 0
        altitude = _to_float(data.get(PID_GPS_ALTITUDE))
        if (lat, lon) == (self._lat, self._lon):
            return
        self._lat, self._lon, self._accuracy = lat, lon, accuracy
        if altitude is not None:
            self._altitude = round(altitude)
        self.async_write_ha_state()
