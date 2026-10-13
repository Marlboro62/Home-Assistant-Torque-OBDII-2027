"""Capteur binaire de connexion Torque (données reçues récemment)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import TorqueConfigEntry, TorqueRuntimeData
from .const import DATA_TIMEOUT_SECONDS, DOMAIN, SIGNAL_UPDATE
from .sensor import vehicle_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TorqueConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the connectivity binary sensor."""
    async_add_entities([TorqueConnectedSensor(entry.entry_id, entry.runtime_data)])


class TorqueConnectedSensor(BinarySensorEntity):
    """ON tant que Torque envoie des données (moteur/app actifs)."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = "Torque connecté"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry_id: str, runtime: TorqueRuntimeData) -> None:
        """Initialize."""
        self._entry_id = entry_id
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_connected"
        self._attr_device_info = vehicle_device_info(entry_id, runtime.vehicle_name)
        self._attr_is_on = False
        self._cancel_timer: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        """Écoute les envois Torque."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE.format(self._entry_id), self._handle_update
            )
        )
        self.async_on_remove(self._cancel)

    @callback
    def _cancel(self) -> None:
        if self._cancel_timer is not None:
            self._cancel_timer()
            self._cancel_timer = None

    @callback
    def _handle_update(self, _data: dict[str, Any]) -> None:
        """Repousse le délai d'expiration à chaque envoi."""
        self._cancel()
        self._cancel_timer = async_call_later(self.hass, DATA_TIMEOUT_SECONDS, self._expired)
        if not self._attr_is_on:
            self._attr_is_on = True
            self.async_write_ha_state()

    @callback
    def _expired(self, _now: Any) -> None:
        self._cancel_timer = None
        self._attr_is_on = False
        self.async_write_ha_state()
