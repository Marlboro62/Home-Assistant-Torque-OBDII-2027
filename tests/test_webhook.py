"""Réception par webhook : adresse secrète par véhicule, migration de l'ancienne adresse, diagnostics."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.torque_obd.const import CONF_ROUTED_DEVICES, CONF_WEBHOOK_ID, DOMAIN
from custom_components.torque_obd.diagnostics import async_get_config_entry_diagnostics

PID = "k5"  # température du liquide de refroidissement


async def _setup(hass: HomeAssistant, **kwargs) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="laguna", title="Laguna",
        **{"version": 2, "data": {"vehicle_name": "Laguna", CONF_WEBHOOK_ID: "hook_laguna"}, **kwargs},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _pid_entity(hass: HomeAssistant, entry: MockConfigEntry) -> str | None:
    return er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_{entry.entry_id}_{PID}")


async def test_webhook_get_and_post(hass: HomeAssistant, hass_client_no_auth) -> None:
    """Les envois GET et POST sur l'adresse du webhook créent et mettent à jour les capteurs."""
    entry = await _setup(hass)
    client = await hass_client_no_auth()
    resp = await client.get("/api/webhook/hook_laguna", params={"session": "1", "id": "tel", PID: "87"})
    assert resp.status == 200
    assert await resp.text() == "OK!"
    await hass.async_block_till_done()
    entity_id = _pid_entity(hass, entry)
    assert entity_id and float(hass.states.get(entity_id).state) == 87

    resp = await client.post("/api/webhook/hook_laguna", data={"session": "1", "id": "tel", PID: "91"})
    assert resp.status == 200
    await hass.async_block_till_done()
    assert float(hass.states.get(entity_id).state) == 91


async def test_old_unauthenticated_path_is_gone(hass: HomeAssistant, hass_client_no_auth) -> None:
    """L'ancienne adresse /api/torque-<véhicule> n'existe plus ; un webhook inconnu ne crée rien."""
    entry = await _setup(hass)
    client = await hass_client_no_auth()
    resp = await client.get("/api/torque-laguna", params={"session": "1", "id": "tel", PID: "50"})
    assert resp.status in (401, 404)
    await client.get("/api/webhook/mauvais_identifiant", params={"session": "1", "id": "tel", PID: "50"})
    await hass.async_block_till_done()
    assert _pid_entity(hass, entry) is None


async def test_unload_unregisters_webhook(hass: HomeAssistant, hass_client_no_auth) -> None:
    """Véhicule déchargé : son webhook ne reçoit plus rien."""
    entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    client = await hass_client_no_auth()
    await client.get("/api/webhook/hook_laguna", params={"session": "1", "id": "tel", PID: "50"})
    await hass.async_block_till_done()
    assert _pid_entity(hass, entry) is None


async def test_migration_creates_webhook_and_issue(hass: HomeAssistant) -> None:
    """Version 1 (ancienne adresse) -> 2 : identifiant de webhook créé, avertissement dans les Réparations."""
    entry = await _setup(hass, version=1, data={"vehicle_name": "Laguna"})
    assert entry.version == 2
    webhook_id = entry.data[CONF_WEBHOOK_ID]
    assert len(webhook_id) >= 32
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"webhook_url_{entry.entry_id}")
    assert issue is not None and issue.translation_key == "webhook_url_changed"

    # Afficher l'adresse depuis les options retire l'avertissement
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "torque_url"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "torque_url"
    assert webhook_id in result["description_placeholders"]["url"]
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"webhook_url_{entry.entry_id}") is None


async def test_new_url_replaces_webhook(hass: HomeAssistant, hass_client_no_auth) -> None:
    """Nouvelle adresse : l'ancienne cesse de fonctionner, la nouvelle reçoit les données."""
    entry = await _setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "new_url"})
    assert result["step_id"] == "new_url"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    await hass.async_block_till_done()
    new_id = entry.data[CONF_WEBHOOK_ID]
    assert new_id != "hook_laguna" and new_id in result["description_placeholders"]["url"]

    client = await hass_client_no_auth()
    await client.get("/api/webhook/hook_laguna", params={"session": "1", "id": "tel", PID: "50"})
    await hass.async_block_till_done()
    assert _pid_entity(hass, entry) is None
    await client.get(f"/api/webhook/{new_id}", params={"session": "1", "id": "tel", PID: "60"})
    await hass.async_block_till_done()
    assert float(hass.states.get(_pid_entity(hass, entry)).state) == 60


async def test_config_flow_generates_webhook(hass: HomeAssistant) -> None:
    """Nouveau véhicule : identifiant de webhook aléatoire et adresse affichée à la fin."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"vehicle_name": "SLK"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    webhook_id = result["data"][CONF_WEBHOOK_ID]
    assert len(webhook_id) >= 32
    assert webhook_id in result["description_placeholders"]["url"]
    assert result["result"].version == 2


async def test_no_url_entity(hass: HomeAssistant) -> None:
    """L'adresse n'est exposée dans aucune entité (lisible par tous les utilisateurs)."""
    entry = await _setup(hass)
    for state in hass.states.async_all():
        assert entry.data[CONF_WEBHOOK_ID] not in str(state.state)
        assert entry.data[CONF_WEBHOOK_ID] not in str(state.attributes)


async def test_diagnostics_redacted(hass: HomeAssistant) -> None:
    """Diagnostics : identifiants des téléphones et webhook masqués, y compris dans les options."""
    entry = await _setup(hass, options={CONF_ROUTED_DEVICES: ["a1b2c3"], "profile_aliases": ["laguna"]})
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = str(diag)
    assert "a1b2c3" not in text
    assert "hook_laguna" not in text
    assert diag["options"][CONF_ROUTED_DEVICES] == "**REDACTED**"
    assert diag["entry"][CONF_WEBHOOK_ID] == "**REDACTED**"


async def test_session_survives_restart(hass: HomeAssistant, hass_client_no_auth, hass_storage) -> None:
    """Trajet en cours au redémarrage de HA : la session enregistrée garde son véhicule."""
    import time

    hass_storage[f"{DOMAIN}.sessions"] = {
        "version": 1, "minor_version": 1, "key": f"{DOMAIN}.sessions",
        "data": {"s1": ["slk_id", time.time() - 60, None]},
    }
    routed = {CONF_ROUTED_DEVICES: ["tel"]}
    for entry_id, name in (("laguna_id", "Laguna"), ("slk_id", "SLK")):
        MockConfigEntry(
            domain=DOMAIN, unique_id=name.lower(), title=name, entry_id=entry_id, version=2,
            data={"vehicle_name": name, CONF_WEBHOOK_ID: f"hook_{name.lower()}"}, options=routed,
        ).add_to_hass(hass)
    assert await hass.config_entries.async_setup("laguna_id")
    await hass.async_block_till_done()

    client = await hass_client_no_auth()
    # Sans nom de profil, envoyé sur l'adresse de la Laguna : la session désigne la SLK
    await client.get("/api/webhook/hook_laguna", params={"session": "s1", "id": "tel", PID: "70"})
    await hass.async_block_till_done()
    reg = er.async_get(hass)
    assert reg.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_slk_id_{PID}") is not None
    assert reg.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_laguna_id_{PID}") is None


async def test_missing_profile_notification(hass: HomeAssistant) -> None:
    """Aucun nom de profil reçu : message « début de trajet manqué », pas « (inconnu) »."""
    from homeassistant.components import persistent_notification

    await _setup(hass)
    router = hass.data[DOMAIN]["router"]
    router._notify_unknown_profiles({"1966413"})
    router._notify_unknown_profiles(set())
    notes = persistent_notification._async_get_or_create_notifications(hass)
    assert list(notes) == ["torque_obd_profile_missing"]
    assert "(inconnu)" not in notes["torque_obd_profile_missing"]["message"]
