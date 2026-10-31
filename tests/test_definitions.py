"""Définitions des capteurs éditées dans les options du véhicule (sans YAML ni redémarrage)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.torque_obd.const import (
    CONF_MULTI_NAMES,
    CONF_SENSOR_DEFINITIONS,
    DOMAIN,
    definition_to_raw,
    prepare_definition,
)

PID = "k222001"


async def _setup(hass: HomeAssistant, options: dict | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="renault", title="Renault",
        data={"vehicle_name": "Renault"}, options=options or {},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _send(hass_client, **values) -> None:
    client = await hass_client()
    resp = await client.get("/api/torque-renault", params={"session": "1", "id": "tel", **values})
    assert resp.status == 200


def _entity_id(hass: HomeAssistant, entry: MockConfigEntry, key: str = PID) -> str:
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_{entry.entry_id}_{key}")
    assert entity_id
    return entity_id


async def _edit(hass: HomeAssistant, entry: MockConfigEntry, pid: str, **fields):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "pick_pid"})
    assert result["step_id"] == "pick_pid"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"pid": pid})
    assert result["step_id"] == "edit_definition"
    return await hass.config_entries.options.async_configure(result["flow_id"], fields)


def test_prepare_definition() -> None:
    prepared = prepare_definition(PID, {"name": "Eau", "device_class": "temperature", "state_class": "measurement"})
    assert prepared["device_class"] is SensorDeviceClass.TEMPERATURE
    assert prepared["state_class"] is SensorStateClass.MEASUREMENT
    assert prepared["icon"] == "mdi:car-info"
    assert prepare_definition(PID, {"unit": "°C"}) is None  # sans nom
    assert prepare_definition(PID, "texte") is None
    assert definition_to_raw(prepared) == {
        "name": "Eau", "icon": "mdi:car-info", "device_class": "temperature", "state_class": "measurement",
    }


async def test_definition_editee_appliquee_sans_redemarrage(hass: HomeAssistant, hass_client_no_auth) -> None:
    entry = await _setup(hass)
    await _send(hass_client_no_auth, **{PID: "85"})
    await hass.async_block_till_done()
    entity_id = _entity_id(hass, entry)
    assert hass.states.get(entity_id).state == "85.0"

    result = await _edit(
        hass, entry, PID, name="Température eau", unit="°C", device_class="temperature",
        state_class="measurement", min=-40, max=130, precision=0,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert entry.options[CONF_SENSOR_DEFINITIONS][PID] == {
        "name": "Température eau", "unit": "°C", "device_class": "temperature",
        "state_class": "measurement", "min": -40, "max": 130, "precision": 0,
    }
    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get(entity_id)
    assert state.attributes["unit_of_measurement"] == "°C"
    assert state.attributes["friendly_name"] == "Renault Température eau"
    assert state.state == "85.0"  # valeur restaurée après le rechargement

    # 255 (calculateur sans donnée) dépasse le max : ignoré
    await _send(hass_client_no_auth, **{PID: "255"})
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "85.0"


async def test_saisie_invalide(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "pick_pid"})
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"pid": "zz?"})
    assert result["errors"] == {"pid": "invalid_pid"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"pid": "222001"})
    assert result["step_id"] == "edit_definition"
    assert result["description_placeholders"] == {"pid": PID}
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"name": "X", "min": 10, "max": 5})
    assert result["errors"] == {"max": "min_above_max"}


async def test_noms_appris_sans_rechargement(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    runtime = entry.runtime_data
    hass.config_entries.async_update_entry(entry, options={**entry.options, CONF_MULTI_NAMES: {"k2101": {"short": ["a", "b"]}}})
    await hass.async_block_till_done()
    assert entry.runtime_data is runtime  # pas de rechargement pour les noms appris


async def test_import_export_suppression(hass: HomeAssistant, hass_client_no_auth) -> None:
    with open(hass.config.path("torque_sensor_definitions.yaml"), "w", encoding="utf-8") as file:
        file.write(
            "k222001:\n  name: Laguna - Eau\n  unit: °C\n  max: 130\n"
            "k2101_slktemp33:\n  name: SLK - Huile\n"
        )
    entry = await _setup(hass)
    await _send(hass_client_no_auth, **{PID: "85"})
    await hass.async_block_till_done()

    # Import : seulement les PID reçus de ce véhicule (pas le PID de la SLK)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "import_yaml"})
    assert result["description_placeholders"]["count"] == "2"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"only_received": True, "overwrite": False})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_SENSOR_DEFINITIONS] == {PID: {"name": "Laguna - Eau", "unit": "°C", "max": 130}}

    # Export
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "export_yaml"})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "exported"
    with open(hass.config.path("torque_sensor_definitions_renault.yaml"), encoding="utf-8") as file:
        assert "Laguna - Eau" in file.read()

    # Suppression : le capteur reprend la définition commune (YAML)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "delete_definitions"})
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"pids": [PID]})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_SENSOR_DEFINITIONS] == {}
    assert hass.states.get(_entity_id(hass, entry)).attributes["friendly_name"] == "Renault Laguna - Eau"


async def test_profils_inchanges(hass: HomeAssistant) -> None:
    entry = await _setup(hass, {CONF_SENSOR_DEFINITIONS: {PID: {"name": "Eau"}}})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "profiles"})
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"profile_aliases": "1966413", "ignored_pids": "2174, k2176"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["ignored_pids"] == ["k2174", "k2176"]
    assert entry.options["profile_aliases"] == ["1966413"]
    assert entry.options[CONF_SENSOR_DEFINITIONS] == {PID: {"name": "Eau"}}  # conservées
