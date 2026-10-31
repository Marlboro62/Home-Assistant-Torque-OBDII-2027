"""Config flow for Torque OBD-II integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol
import yaml

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigFlowResult as FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    CONF_EMAIL,
    CONF_IGNORED_PIDS,
    CONF_PROFILE_ALIASES,
    CONF_SENSOR_DEFINITIONS,
    CONF_VEHICLE_NAME,
    DEFINITION_FIELDS,
    DOMAIN,
    SENSOR_DEFINITIONS_FILE,
    definition_to_raw,
    normalize_pid,
    read_custom_definitions_file,
    vehicle_slug,
    write_vehicle_definitions_file,
)

_LOGGER = logging.getLogger(__name__)

# Clé de PID Torque : k + code hexadécimal, éventuellement suivi d'un nom court (k2101_oiltemp)
PID_KEY = re.compile(r"^k[0-9a-f]+(_[a-z0-9]+)?$")
# Unités proposées dans la liste (une autre peut être saisie)
COMMON_UNITS = ["°C", "%", "V", "A", "W", "kW", "km", "km/h", "rpm", "bar", "mbar", "kPa", "psi",
                "L", "L/h", "L/100km", "kg/h", "g/s", "mg/cp", "N·m", "ms", "µs", "s", "°", "°vil", "lambda"]


def is_pid_key(key: str) -> bool:
    """Clé de valeur Torque (k…), hors métadonnées."""
    return bool(PID_KEY.match(key.lower()))

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VEHICLE_NAME): cv.string,
        vol.Optional(CONF_EMAIL): cv.string,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.
    
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    _LOGGER.debug("Validating config flow input for vehicle '%s'", data.get(CONF_VEHICLE_NAME, "Unknown"))
    
    # Validate vehicle name
    vehicle_name = data[CONF_VEHICLE_NAME].strip()
    if not vehicle_name:
        _LOGGER.warning("Validation failed: Vehicle name is empty")
        raise ValueError("Vehicle name cannot be empty")
    
    # Validate that vehicle name is alphanumeric with spaces, dashes, or underscores only
    if not re.match(r'^[a-zA-Z0-9 _-]+$', vehicle_name):
        _LOGGER.warning("Validation failed: Vehicle name '%s' contains invalid characters", vehicle_name)
        raise ValueError("Vehicle name contains invalid characters")
    
    _LOGGER.debug("Vehicle name '%s' validated successfully", vehicle_name)
    
    # Validate email format if provided
    if CONF_EMAIL in data and data[CONF_EMAIL]:
        email = data[CONF_EMAIL]
        
        # Basic email validation: must have @ and . with reasonable structure
        if "@" not in email or "." not in email:
            _LOGGER.warning("Validation failed: Email '%s' has invalid format", email)
            raise ValueError("Invalid email format")
        
        # Check that @ comes before the last .
        at_pos = email.rfind("@")
        dot_pos = email.rfind(".")
        if at_pos >= dot_pos or at_pos == 0 or dot_pos == len(email) - 1:
            _LOGGER.warning("Validation failed: Email '%s' has invalid format", email)
            raise ValueError("Invalid email format")
        
        # Check there's content on both sides of @
        parts = email.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            _LOGGER.warning("Validation failed: Email '%s' has invalid format", email)
            raise ValueError("Invalid email format")
        
        _LOGGER.debug("Email '%s' validated successfully", email)
    
    _LOGGER.debug("All validation checks passed for vehicle '%s'", vehicle_name)
    
    # Return info to be stored in the config entry
    return {"title": vehicle_name}


class TorqueConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Torque OBD-II."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> TorqueOptionsFlow:
        """Options : identifiants de profil Torque de ce véhicule."""
        return TorqueOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        _LOGGER.debug("Starting Torque OBD-II config flow (user step)")
        errors: dict[str, str] = {}
        
        if user_input is not None:
            _LOGGER.debug("Processing user input for vehicle '%s'", user_input.get(CONF_VEHICLE_NAME, "Unknown"))
            try:
                info = await validate_input(self.hass, user_input)
                if user_input.get(CONF_EMAIL):
                    user_input[CONF_EMAIL] = user_input[CONF_EMAIL].strip()
            except ValueError as err:
                if "Vehicle name" in str(err):
                    _LOGGER.warning("Config flow validation error: %s", err)
                    errors["base"] = "invalid_vehicle_name"
                else:
                    _LOGGER.warning("Config flow validation error: %s", err)
                    errors["base"] = "invalid_email"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during config flow validation")
                errors["base"] = "unknown"
            else:
                # Check if already configured - use vehicle name as unique identifier
                # Normalize vehicle name for unique_id (same as URL: lowercase, spaces to dashes)
                # Même règle que l'URL : deux noms donnant la même URL sont refusés
                user_input[CONF_VEHICLE_NAME] = user_input[CONF_VEHICLE_NAME].strip()
                normalized_name = vehicle_slug(user_input[CONF_VEHICLE_NAME])
                _LOGGER.debug("Setting unique_id to normalized vehicle name: %s", normalized_name)
                await self.async_set_unique_id(normalized_name)
                self._abort_if_unique_id_configured()
                
                _LOGGER.info("Creating config entry for vehicle '%s'", info["title"])
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class TorqueOptionsFlow(config_entries.OptionsFlow):
    """Options d'un véhicule : profils Torque, PID ignorés et définitions de ses capteurs."""

    def __init__(self) -> None:
        """Initialize."""
        self._pid: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Menu des options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["profiles", "pick_pid", "delete_definitions", "import_yaml", "export_yaml"],
        )

    # ------------------------------------------------------------------ profils
    async def async_step_profiles(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Profils Torque et PID à ignorer : listes séparées par des virgules."""
        if user_input is not None:
            aliases = sorted(
                {
                    a.strip().lower()
                    for a in user_input.get(CONF_PROFILE_ALIASES, "").split(",")
                    if a.strip()
                }
            )
            ignored = sorted(
                {
                    normalize_pid(p.strip().lower() if p.strip().lower().startswith("k") else "k" + p.strip().lower())
                    for p in user_input.get(CONF_IGNORED_PIDS, "").split(",")
                    if p.strip()
                }
            )
            # Supprime les entités déjà créées pour les PID désormais ignorés
            if ignored:
                ent_reg = er.async_get(self.hass)
                for ent in er.async_entries_for_config_entry(ent_reg, self.config_entry.entry_id):
                    prefix = f"{DOMAIN}_{self.config_entry.entry_id}_"
                    if not ent.unique_id.startswith(prefix):
                        continue
                    key = ent.unique_id[len(prefix):]
                    # k2101_oiltemp -> k2101 (PID perso séparés)
                    if key.startswith("k") and normalize_pid(key.split("_", 1)[0]) in ignored:
                        ent_reg.async_remove(ent.entity_id)
            return self._save(**{CONF_PROFILE_ALIASES: aliases, CONF_IGNORED_PIDS: ignored})

        current = self.config_entry.options.get(CONF_PROFILE_ALIASES, [])
        if isinstance(current, str):
            current = current.split(",")
        cur_ign = self.config_entry.options.get(CONF_IGNORED_PIDS, [])
        if isinstance(cur_ign, str):
            cur_ign = cur_ign.split(",")
        return self.async_show_form(
            step_id="profiles",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PROFILE_ALIASES, default=", ".join(current)): cv.string,
                    vol.Optional(CONF_IGNORED_PIDS, default=", ".join(cur_ign)): cv.string,
                }
            ),
        )

    # ------------------------------------------------------------- définitions
    def _definitions(self) -> dict[str, dict[str, Any]]:
        """Définitions propres au véhicule (options), sous forme brute."""
        raw = self.config_entry.options.get(CONF_SENSOR_DEFINITIONS) or {}
        return {normalize_pid(str(pid)): dict(d) for pid, d in raw.items() if isinstance(d, dict)}

    def _known_pids(self) -> dict[str, str]:
        """PID de ce véhicule -> libellé « clé — nom = dernière valeur » pour la liste de choix."""
        entry = self.config_entry
        own = self._definitions()
        shared: dict[str, dict[str, Any]] = self.hass.data.get(DOMAIN, {}).get("sensor_definitions", {})
        last: dict[str, Any] = {}
        runtime = getattr(entry, "runtime_data", None)
        if runtime is not None:
            last = {normalize_pid(k): v for k, v in runtime.data.items() if is_pid_key(k)}

        pids: dict[str, str | None] = {pid: None for pid in last}
        prefix = f"{DOMAIN}_{entry.entry_id}_"
        ent_reg = er.async_get(self.hass)
        for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
            if ent.domain == "sensor" and ent.unique_id.startswith(prefix):
                key = ent.unique_id[len(prefix):]
                if is_pid_key(key):
                    pids[normalize_pid(key)] = ent.original_name
        for pid in own:
            pids.setdefault(pid, None)

        labels: dict[str, str] = {}
        for pid in sorted(pids):
            name = (own.get(pid) or shared.get(pid) or {}).get("name") or pids[pid]
            label = pid + (f" — {name}" if name else "")
            if pid in last:
                label += f" = {last[pid]}"
            if pid in own:
                label += " ✎"
            labels[pid] = label
        return labels

    async def async_step_pick_pid(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Choix du PID à définir : liste des PID du véhicule, ou clé saisie."""
        errors: dict[str, str] = {}
        if user_input is not None:
            pid = str(user_input["pid"]).strip().lower().replace(" ", "")
            if pid and not pid.startswith("k"):
                pid = "k" + pid
            if not PID_KEY.match(pid):
                errors["pid"] = "invalid_pid"
            else:
                self._pid = normalize_pid(pid)
                return await self.async_step_edit_definition()

        options = [
            selector.SelectOptionDict(value=pid, label=label)
            for pid, label in self._known_pids().items()
        ]
        return self.async_show_form(
            step_id="pick_pid",
            data_schema=vol.Schema(
                {
                    vol.Required("pid"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            custom_value=True,
                            sort=False,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_edit_definition(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Nom, unité, icône, classes, bornes et décimales d'un PID."""
        assert self._pid is not None
        pid = self._pid
        errors: dict[str, str] = {}
        if user_input is not None:
            raw = {field: user_input.get(field) for field in DEFINITION_FIELDS}
            raw["name"] = str(raw.get("name") or "").strip()
            for field in ("unit", "icon", "device_class", "state_class"):
                raw[field] = str(raw.get(field) or "").strip() or None
            if raw.get("precision") is not None:
                raw["precision"] = int(raw["precision"])
            if not raw["name"]:
                errors["name"] = "name_required"
            elif raw.get("min") is not None and raw.get("max") is not None and raw["min"] > raw["max"]:
                errors["max"] = "min_above_max"
            else:
                definitions = self._definitions()
                definitions[pid] = {k: v for k, v in raw.items() if v is not None}
                return self._save(**{CONF_SENSOR_DEFINITIONS: definitions})

        current = self._definitions().get(pid)
        if current is None:
            # Pas encore défini pour ce véhicule : on part de la définition partagée (défauts + YAML)
            shared = self.hass.data.get(DOMAIN, {}).get("sensor_definitions", {}).get(pid)
            current = definition_to_raw(shared) if shared else {}
        if user_input is not None:
            current = {k: v for k, v in user_input.items() if v not in (None, "")}

        def opt(field: str) -> vol.Optional:
            value = current.get(field)
            return vol.Optional(field, description={"suggested_value": value} if value is not None else None)

        number = selector.NumberSelector(
            selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX, step="any")
        )
        return self.async_show_form(
            step_id="edit_definition",
            data_schema=vol.Schema(
                {
                    vol.Required("name", default=current.get("name", "")): selector.TextSelector(),
                    opt("unit"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=COMMON_UNITS, custom_value=True, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    ),
                    opt("icon"): selector.IconSelector(),
                    opt("device_class"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=sorted(c.value for c in SensorDeviceClass),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    opt("state_class"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[c.value for c in SensorStateClass],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    opt("min"): number,
                    opt("max"): number,
                    opt("precision"): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=6, step=1, mode=selector.NumberSelectorMode.BOX)
                    ),
                }
            ),
            description_placeholders={"pid": pid},
            errors=errors,
        )

    async def async_step_delete_definitions(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Retire des définitions du véhicule : les capteurs reprennent la définition partagée."""
        definitions = self._definitions()
        if not definitions:
            return self.async_abort(reason="no_definitions")
        if user_input is not None:
            for pid in user_input.get("pids", []):
                definitions.pop(pid, None)
            return self._save(**{CONF_SENSOR_DEFINITIONS: definitions})
        return self.async_show_form(
            step_id="delete_definitions",
            data_schema=vol.Schema(
                {
                    vol.Required("pids"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=pid, label=f"{pid} — {d.get('name')}")
                                for pid, d in sorted(definitions.items())
                            ],
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_import_yaml(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Reprend les définitions de torque_sensor_definitions.yaml dans ce véhicule."""
        try:
            file_definitions = await self.hass.async_add_executor_job(read_custom_definitions_file, self.hass)
        except (yaml.YAMLError, OSError) as err:
            _LOGGER.warning("Lecture de %s impossible : %s", SENSOR_DEFINITIONS_FILE, err)
            return self.async_abort(reason="yaml_invalid")
        if not file_definitions:
            return self.async_abort(reason="yaml_missing")

        if user_input is not None:
            known = set(self._known_pids())
            definitions = self._definitions()
            imported = 0
            for pid, definition in file_definitions.items():
                if user_input.get("only_received") and pid not in known:
                    continue
                if pid in definitions and not user_input.get("overwrite"):
                    continue
                definitions[pid] = {k: definition[k] for k in DEFINITION_FIELDS if definition.get(k) is not None}
                imported += 1
            _LOGGER.info("%d définition(s) importée(s) pour '%s'", imported, self.config_entry.title)
            return self._save(**{CONF_SENSOR_DEFINITIONS: definitions})

        return self.async_show_form(
            step_id="import_yaml",
            data_schema=vol.Schema(
                {
                    vol.Optional("only_received", default=True): selector.BooleanSelector(),
                    vol.Optional("overwrite", default=False): selector.BooleanSelector(),
                }
            ),
            description_placeholders={"count": str(len(file_definitions)), "file": SENSOR_DEFINITIONS_FILE},
        )

    async def async_step_export_yaml(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Écrit les définitions du véhicule dans /config/torque_sensor_definitions_<véhicule>.yaml."""
        definitions = self._definitions()
        if not definitions:
            return self.async_abort(reason="no_definitions")
        path = await self.hass.async_add_executor_job(
            write_vehicle_definitions_file,
            self.hass,
            vehicle_slug(self.config_entry.data[CONF_VEHICLE_NAME]),
            definitions,
        )
        return self.async_abort(reason="exported", description_placeholders={"path": path})

    def _save(self, **changes: Any) -> FlowResult:
        """Enregistre les options modifiées en gardant les autres (noms appris, alias…)."""
        return self.async_create_entry(data={**self.config_entry.options, **changes})
