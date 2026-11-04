"""Diagnostics : téléchargeable depuis la page de l'intégration (⋮ → Télécharger les diagnostics)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import TorqueConfigEntry
from .const import CONF_EMAIL, CONF_ROUTED_DEVICES, CONF_WEBHOOK_ID, PID_GPS_LATITUDE, PID_GPS_LONGITUDE

# Identifiants Torque des téléphones (id, routed_devices), webhook, e-mail et position : masqués
TO_REDACT = {
    CONF_EMAIL, CONF_ROUTED_DEVICES, CONF_WEBHOOK_ID,
    "eml", "id", "lat", "lon", PID_GPS_LATITUDE, PID_GPS_LONGITUDE,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TorqueConfigEntry
) -> dict[str, Any]:
    """Dernier payload reçu (dont les unités defaultUnit/userUnit) et noms de PID."""
    runtime = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": async_redact_data(dict(entry.options), TO_REDACT),
        "last_seen": runtime.last_seen.isoformat() if runtime.last_seen else None,
        "request_count": runtime.request_count,
        "torque_profile": runtime.profile_name,
        "pid_names": runtime.sensor_names,
        "last_payload": async_redact_data(dict(sorted(runtime.data.items())), TO_REDACT),
    }
