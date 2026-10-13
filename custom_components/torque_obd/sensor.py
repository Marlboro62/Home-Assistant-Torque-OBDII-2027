"""Capteurs Torque OBD-II."""
from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.network import NoURLAvailableError, get_url

from . import TorqueConfigEntry, TorqueRuntimeData
from .const import (
    ATTRIBUTE_FIELDS,
    DOMAIN,
    METADATA_FIELD_PREFIXES,
    SIGNAL_UPDATE,
    normalize_pid,
)

_LOGGER = logging.getLogger(__name__)

GENERIC_DEFINITION: dict[str, Any] = {
    "unit": None,
    "icon": "mdi:car-info",
    "device_class": None,
    "state_class": None,
}


def vehicle_device_info(entry_id: str, vehicle_name: str) -> DeviceInfo:
    """DeviceInfo commun à toutes les entités d'un véhicule."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=vehicle_name,
        manufacturer="Torque Pro",
        model="OBD-II",
    )


def _is_sensor_key(key: str) -> bool:
    """Vrai si la clé du payload est une valeur de PID (k…)."""
    if not key.startswith("k") or key in ATTRIBUTE_FIELDS:
        return False
    return not any(key.startswith(prefix) for prefix in METADATA_FIELD_PREFIXES)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TorqueConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les capteurs restaurés puis ceux découverts à la volée."""
    runtime = entry.runtime_data
    definitions: dict[str, dict[str, Any]] = hass.data[DOMAIN]["sensor_definitions"]
    known: set[str] = set()  # PID normalisés déjà créés

    def build(raw_key: str, name: str | None, initial: Any = None) -> TorqueSensor:
        norm = normalize_pid(raw_key)
        known_def = definitions.get(norm)
        definition = {**GENERIC_DEFINITION, **(known_def or {})}
        # PID connu : le nom FR de const.py / du YAML fait foi (il suit les corrections).
        # PID inconnu : nom envoyé par Torque, sinon ancien nom, sinon "PID kxx".
        if not known_def:
            definition["name"] = name or f"PID {raw_key}"
        known.add(norm)
        return TorqueSensor(entry.entry_id, runtime, raw_key, definition, initial)

    entities: list[SensorEntity] = [TorqueAPIEndpointSensor(entry.entry_id, runtime)]

    # --- Restauration des capteurs déjà connus (registre des entités) ---
    prefix = f"{DOMAIN}_{entry.entry_id}_"
    ent_reg = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if reg_entry.domain != "sensor" or not reg_entry.unique_id.startswith(prefix):
            continue
        raw_key = reg_entry.unique_id[len(prefix):]
        if not raw_key.startswith("k") or normalize_pid(raw_key) in known:
            continue
        # Anciennes versions : nom stocké sous la forme "<véhicule> <capteur>"
        name = reg_entry.original_name
        if name and name.startswith(f"{runtime.vehicle_name} "):
            name = name[len(runtime.vehicle_name) + 1:]
        entities.append(build(raw_key, name))

    async_add_entities(entities)

    @callback
    def add_new_sensors(data: dict[str, Any]) -> None:
        """Appelé par la vue HTTP avant le dispatch : crée les PID inconnus."""
        new = [
            build(key, runtime.payload_name(normalize_pid(key)), value)
            for key, value in data.items()
            if _is_sensor_key(key) and normalize_pid(key) not in known
        ]
        if new:
            async_add_entities(new)
            _LOGGER.info("%d nouveau(x) capteur(s) pour '%s'", len(new), runtime.vehicle_name)

    runtime.add_new_sensors = add_new_sensors

    @callback
    def _detach() -> None:
        runtime.add_new_sensors = None

    entry.async_on_unload(_detach)


class TorqueSensor(RestoreSensor):
    """Capteur OBD-II alimenté par les envois de Torque."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        entry_id: str,
        runtime: TorqueRuntimeData,
        key: str,
        definition: dict[str, Any],
        initial: Any = None,
    ) -> None:
        """Initialize."""
        self._entry_id = entry_id
        self._key = key  # clé brute envoyée par Torque (ex : "kd")
        self._norm_key = normalize_pid(key)  # clé normalisée (ex : "k0d")

        self._attr_name = definition["name"]
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{key}"
        self._attr_device_info = vehicle_device_info(entry_id, runtime.vehicle_name)
        self._attr_native_unit_of_measurement = definition.get("unit")
        self._attr_icon = definition.get("icon") or "mdi:car-info"
        self._attr_device_class = definition.get("device_class")
        self._attr_state_class = definition.get("state_class")
        if definition.get("precision") is not None:
            self._attr_suggested_display_precision = definition["precision"]
        elif self._attr_device_class == SensorDeviceClass.VOLTAGE:
            # HA arrondit les volts à l'unité par défaut : 0,45 V -> "0 V"
            self._attr_suggested_display_precision = 2
        # Attribut statique : n'alourdit pas l'historique
        self._attr_extra_state_attributes = {"pid": key}

        # Un capteur avec unité / classe doit rester numérique, sinon HA lève une erreur
        # Bornes de plausibilité : Torque envoie parfois des valeurs sentinelles
        # (ex. -3057 psi sur le turbo quand le PID n'est pas lu)
        self._min = definition.get("min")
        self._max = definition.get("max")
        self._numeric_only = any(
            (self._attr_native_unit_of_measurement, self._attr_device_class, self._attr_state_class)
        )
        self._attr_native_value = self._parse(initial) if initial is not None else None

    def _parse(self, value: Any) -> float | str | None:
        """Convertit une valeur Torque ; None si invalide."""
        try:
            number = float(value)
        except (TypeError, ValueError):
            if self._numeric_only:
                return None
            text = str(value).strip()
            return text[:255] or None
        if not math.isfinite(number):
            return None
        if (self._min is not None and number < self._min) or (
            self._max is not None and number > self._max
        ):
            return None
        return number

    async def async_added_to_hass(self) -> None:
        """Restaure la dernière valeur puis écoute les envois."""
        await super().async_added_to_hass()
        if self._attr_native_value is None:
            restored: Any = None
            if (last := await self.async_get_last_sensor_data()) is not None:
                restored = last.native_value
            elif (state := await self.async_get_last_state()) is not None:
                # Données issues de l'ancienne version (RestoreEntity)
                restored = state.state
            if restored not in (None, "unknown", "unavailable"):
                self._attr_native_value = self._parse(restored)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE.format(self._entry_id), self._handle_update
            )
        )

    @callback
    def _handle_update(self, data: dict[str, Any]) -> None:
        """Met à jour l'état si ce PID est présent et a changé."""
        if self._key in data:
            raw = data[self._key]
        elif self._norm_key in data:
            raw = data[self._norm_key]
        else:
            return
        value = self._parse(raw)
        if value is None:
            _LOGGER.debug("Valeur invalide ignorée pour %s : %r", self.entity_id, raw)
            return
        if value == self._attr_native_value:
            return  # aucun changement : on évite un événement d'état inutile
        self._attr_native_value = value
        self.async_write_ha_state()


class TorqueAPIEndpointSensor(SensorEntity):
    """URL à saisir dans Torque Pro (Réglages → Journalisation → URL Webserver)."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = "URL Torque"
    _attr_icon = "mdi:api"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry_id: str, runtime: TorqueRuntimeData) -> None:
        """Initialize."""
        self._runtime = runtime
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_api_endpoint"
        self._attr_device_info = vehicle_device_info(entry_id, runtime.vehicle_name)

    async def async_added_to_hass(self) -> None:
        """Construit les URL interne et externe."""
        path = self._runtime.api_path
        urls: dict[str, str] = {}
        for label, kwargs in (
            ("url_externe", {"allow_internal": False}),
            ("url_interne", {"allow_external": False}),
        ):
            try:
                urls[label] = f"{get_url(self.hass, **kwargs)}{path}"
            except NoURLAvailableError:
                pass
        self._attr_native_value = (
            urls.get("url_externe") or urls.get("url_interne") or f"http://IP_HA:8123{path}"
        )
        self._attr_extra_state_attributes = urls
        self.async_write_ha_state()
