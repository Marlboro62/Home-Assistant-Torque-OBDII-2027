"""The Torque OBD-II integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import logging
import re
import time
from typing import Any, Callable

from aiohttp import web

from homeassistant.components import persistent_notification
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import (
    CONF_EMAIL,
    CONF_AMBIGUOUS_PROFILES,
    CONF_PROFILE_ALIASES,
    CONF_IGNORED_PIDS,
    CONF_MULTI_NAMES,
    CONF_ROUTED_DEVICES,
    PENDING_MAX_ITEMS,
    PENDING_TIMEOUT_SECONDS,
    SESSION_TTL_SECONDS,
    CONF_VEHICLE_NAME,
    DOMAIN,
    SIGNAL_UPDATE,
    load_sensor_definitions,
    normalize_pid,
    vehicle_slug,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_NAME_PREFIXES = (("userFullName", "full_name"), ("userShortName", "short_name"))


@dataclass
class TorqueRuntimeData:
    """Données d'exécution d'un véhicule (une par config entry)."""

    vehicle_name: str
    email: str
    slug: str
    api_path: str
    data: dict[str, Any] = field(default_factory=dict)
    sensor_names: dict[str, dict[str, str | None]] = field(default_factory=dict)
    last_seen: datetime | None = None
    request_count: int = 0
    profile_name: str | None = None
    # Renseigné par la plateforme sensor : crée les capteurs des nouveaux PID
    add_new_sensors: Callable[[dict[str, Any]], None] | None = None
    # PID perso partageant un même code (ex. "21 01") : noms dans l'ordre d'envoi
    multi_names: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    multi_logged: set[str] = field(default_factory=set)

    def payload_name(self, normalized_pid: str) -> str | None:
        """Nom envoyé par Torque pour ce PID (nom complet en priorité)."""
        names = self.sensor_names.get(normalized_pid)
        if not names:
            return None
        return names.get("full_name") or names.get("short_name")


type TorqueConfigEntry = ConfigEntry[TorqueRuntimeData]


def entry_aliases(entry: ConfigEntry) -> list[str]:
    """Identifiants de profil Torque associés à ce véhicule (minuscules)."""
    raw = entry.options.get(CONF_PROFILE_ALIASES, [])
    if isinstance(raw, str):
        raw = raw.split(",")
    return [str(a).strip().lower() for a in raw if str(a).strip()]


def entry_ignored_pids(entry: ConfigEntry) -> set[str]:
    """PID que ce véhicule doit ignorer (ex. PID d'une autre voiture)."""
    raw = entry.options.get(CONF_IGNORED_PIDS, [])
    if isinstance(raw, str):
        raw = raw.split(",")
    return {normalize_pid(str(p).strip().lower()) for p in raw if str(p).strip()}


def _query_to_dict(query: Any) -> dict[str, Any]:
    """MultiDict -> dict. Une clé répétée (ex. k2101 envoyée une fois par PID
    perso "21 01") devient une liste au lieu d'être réduite à sa 1re valeur."""
    out: dict[str, Any] = {}
    for key in query.keys():
        if key in out:
            continue
        values = query.getall(key)
        out[key] = values[0] if len(values) == 1 else list(values)
    return out


def _short_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _base_pid(key: str) -> str:
    """k2101_oiltemp -> k2101 (clé d'origine Torque)."""
    return normalize_pid(key.split("_", 1)[0])


def _extract_name(value: Any) -> str | None:
    """Torque peut envoyer une chaîne ou une liste de chaînes."""
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


async def async_setup_entry(hass: HomeAssistant, entry: TorqueConfigEntry) -> bool:
    """Set up Torque OBD-II from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {"slugs": {}})

    # Définitions (défauts + YAML utilisateur), chargées une seule fois
    if "sensor_definitions" not in domain_data:
        domain_data["sensor_definitions"] = await hass.async_add_executor_job(
            load_sensor_definitions, hass
        )
        _LOGGER.debug("Loaded %d sensor definitions", len(domain_data["sensor_definitions"]))

    # Une seule vue HTTP pour tous les véhicules : /api/torque-{slug}
    # (une vue aiohttp ne peut pas être retirée ; l'enregistrer une seule fois
    # évite les doublons de routes à chaque rechargement de l'intégration)
    if not domain_data.get("view_registered"):
        hass.http.register_view(TorqueView(hass))
        domain_data["view_registered"] = True

    vehicle_name = entry.data[CONF_VEHICLE_NAME]
    slug = vehicle_slug(vehicle_name)
    runtime = TorqueRuntimeData(
        vehicle_name=vehicle_name,
        email=(entry.data.get(CONF_EMAIL) or "").strip().lower(),
        slug=slug,
        api_path=f"/api/torque-{slug}",
        multi_names={
            k: dict(v) for k, v in (entry.options.get(CONF_MULTI_NAMES) or {}).items()
        },
    )
    entry.runtime_data = runtime
    domain_data["slugs"][slug] = entry
    _LOGGER.info("Torque OBD-II '%s' listening on %s", vehicle_name, runtime.api_path)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TorqueConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN]["slugs"].pop(entry.runtime_data.slug, None)
    return unload_ok


class TorqueView(HomeAssistantView):
    """Reçoit les envois de Torque Pro pour tous les véhicules configurés.

    Aiguillage (l'URL d'envoi de Torque est commune à tous les profils) :
      1. profileName = nom d'un véhicule HA, ou alias de profil connu ;
      2. sinon, la session Torque (champ "session") déjà associée à un véhicule ;
      3. sinon, pour un téléphone qui utilise l'aiguillage par profil (déjà vu
         avec un nom reconnu), les envois sont mis en attente pour cette session
         jusqu'à ce qu'un nom de profil reconnu arrive ; les autres téléphones
         passent directement par leur URL. Les identifiants inconnus vus entre-temps
         (ex. "1966413…") sont alors appris comme alias de ce véhicule ;
      4. sans session (ou téléphone n'utilisant pas les profils) : véhicule de l'URL ;
         attente expirée (profil inconnu) : données ignorées + notification.
    """

    url = "/api/torque-{slug}"
    name = "api:torque_obd"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the view."""
        self.hass = hass
        self._warned_slugs: set[str] = set()
        self._session_entry: dict[str, tuple[str, float, str | None]] = {}
        self._pending: dict[str, dict[str, Any]] = {}
        self._ambiguous: set[str] = set()
        self._notified_profiles: set[str] = set()

    async def get(self, request: web.Request, slug: str) -> web.Response:
        """Torque envoie par défaut en GET (query string)."""
        return self._process(slug, _query_to_dict(request.query))

    async def post(self, request: web.Request, slug: str) -> web.Response:
        """Envoi en POST (formulaire)."""
        return self._process(slug, _query_to_dict(await request.post()))

    # ------------------------------------------------------------------ routage
    def _entries(self) -> dict[str, TorqueConfigEntry]:
        return self.hass.data[DOMAIN]["slugs"]

    def _by_id(self, entry_id: str) -> TorqueConfigEntry | None:
        for entry in self._entries().values():
            if entry.entry_id == entry_id:
                return entry
        return None

    def _resolve_profile(
        self, profile: str
    ) -> tuple[TorqueConfigEntry | None, str | None]:
        """Nom de profil Torque -> (véhicule, alias utilisé ou None si nom exact)."""
        if not profile:
            return None, None
        entries = self._entries()
        wanted = vehicle_slug(profile)
        if (entry := entries.get(wanted)) is not None:
            return entry, None
        # Nom affiché modifié par l'utilisateur (titre de l'intégration ou de l'appareil)
        dev_reg = dr.async_get(self.hass)
        for entry in entries.values():
            names = {entry.title}
            device = dev_reg.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
            if device is not None:
                names |= {device.name or "", device.name_by_user or ""}
            if wanted in {vehicle_slug(n) for n in names if n}:
                return entry, None
        # Nom du véhicule contenu comme mot(s) entier(s) dans le profil Torque, ou
        # l'inverse (ex. "Ma VOITURE" -> "Voiture", profil "Voiture" -> "Ma voiture").
        # Uniquement si un seul véhicule correspond.
        words = [w for w in wanted.replace("_", "-").split("-") if w]
        matches = []
        for entry in entries.values():
            names = {entry.runtime_data.vehicle_name, entry.title}
            device = dev_reg.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
            if device is not None:
                names |= {device.name or "", device.name_by_user or ""}
            for name in names:
                sub = [w for w in vehicle_slug(name).replace("_", "-").split("-") if w]
                # nom du véhicule contenu dans le profil, ou profil contenu dans le nom
                if sub and (
                    any(words[i : i + len(sub)] == sub for i in range(len(words)))
                    or any(sub[i : i + len(words)] == words for i in range(len(sub)))
                ):
                    matches.append(entry)
                    break
        if len(matches) == 1:
            return matches[0], None
        key = profile.strip().lower()
        if self._is_ambiguous(key):
            return None, None
        for entry in entries.values():
            if key in entry_aliases(entry):
                return entry, key
        return None, None

    def _is_ambiguous(self, key: str) -> bool:
        if key in self._ambiguous:
            return True
        return any(
            key in other.options.get(CONF_AMBIGUOUS_PROFILES, [])
            for other in self._entries().values()
        )

    def _mark_ambiguous(self, aliases: set[str]) -> None:
        """Mémorise (dans les options de chaque véhicule) des identifiants ambigus."""
        self._ambiguous |= aliases
        for other in self._entries().values():
            amb = set(other.options.get(CONF_AMBIGUOUS_PROFILES, [])) | aliases
            self.hass.config_entries.async_update_entry(
                other,
                options={
                    **other.options,
                    CONF_PROFILE_ALIASES: sorted(set(entry_aliases(other)) - aliases),
                    CONF_AMBIGUOUS_PROFILES: sorted(amb),
                },
            )

    def _is_routed(self, device: str) -> bool:
        """Téléphone ayant déjà envoyé un nom de profil reconnu."""
        return any(
            device in entry.options.get(CONF_ROUTED_DEVICES, [])
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        )

    def _mark_routed(self, entry: TorqueConfigEntry, device: str) -> None:
        """Mémorise qu'un téléphone utilise l'aiguillage par profil."""
        if self._is_routed(device):
            return
        devices = sorted(set(entry.options.get(CONF_ROUTED_DEVICES, [])) | {device})
        self.hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_ROUTED_DEVICES: devices}
        )

    def _is_disabled_vehicle(self, profile: str) -> bool:
        """Vrai si le profil désigne un véhicule HA désactivé (ses données sont ignorées)."""
        wanted = vehicle_slug(profile)
        key = profile.strip().lower()
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.disabled_by is None:
                continue
            names = {entry.title, str(entry.data.get(CONF_VEHICLE_NAME, ""))}
            if wanted in {vehicle_slug(n) for n in names if n} or key in entry_aliases(entry):
                return True
        return False

    def _forget_alias(self, entry: TorqueConfigEntry, alias: str) -> None:
        """Retire un alias devenu ambigu."""
        self._mark_ambiguous({alias})
        _LOGGER.warning(
            "Identifiant de profil Torque %s utilisé par plusieurs véhicules : "
            "ignoré désormais (attente du vrai nom de profil)",
            alias,
        )

    def _learn_aliases(self, entry: TorqueConfigEntry, profiles: set[str]) -> None:
        """Mémorise (dans les options) les identifiants de profil inconnus."""
        new = {p.strip().lower() for p in profiles if p.strip()}
        new -= set(entry_aliases(entry))
        new -= {vehicle_slug(entry.runtime_data.vehicle_name)}
        new = {p for p in new if not self._is_ambiguous(p)}
        # Un identifiant vu sur deux véhicules différents n'est pas fiable :
        # on le retire partout et on ne l'utilisera plus pour aiguiller.
        for other in self._entries().values():
            if other is entry:
                continue
            clash = new & set(entry_aliases(other))
            if clash:
                new -= clash
                self._mark_ambiguous(clash)
                _LOGGER.warning(
                    "Identifiant de profil Torque %s commun à plusieurs véhicules : "
                    "ignoré pour l'aiguillage (attente du vrai nom de profil)",
                    ", ".join(sorted(clash)),
                )
        if not new:
            return
        aliases = sorted(set(entry_aliases(entry)) | new)
        self.hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_PROFILE_ALIASES: aliases}
        )
        _LOGGER.info(
            "Profil(s) Torque %s associé(s) au véhicule '%s'",
            ", ".join(sorted(new)),
            entry.runtime_data.vehicle_name,
        )

    def _prune(self, now: float) -> list[tuple[str, dict[str, Any]]]:
        """Nettoie les sessions anciennes ; renvoie les envois en attente expirés."""
        for session, (_eid, ts, _alias) in list(self._session_entry.items()):
            if now - ts > SESSION_TTL_SECONDS:
                del self._session_entry[session]
        expired: list[tuple[str, dict[str, Any]]] = []
        for session, pend in list(self._pending.items()):
            if now - pend["since"] > PENDING_TIMEOUT_SECONDS:
                # Téléphone multi-profils dont le profil ne correspond à aucun
                # véhicule : on N'ENVOIE PAS au véhicule de l'URL (ce serait
                # mélanger deux voitures). Les données sont ignorées et
                # l'utilisateur est prévenu une fois par nom de profil.
                del self._pending[session]
                self._notify_unknown_profiles(pend["profiles"])
        return expired

    def _notify_unknown_profiles(self, profiles: set[str]) -> None:
        names = sorted(p for p in profiles if any(c.isalpha() for c in p)) or ["(inconnu)"]
        key = ",".join(names)
        if key in self._notified_profiles:
            return
        self._notified_profiles.add(key)
        _LOGGER.warning(
            "Profil(s) Torque %s sans véhicule HA correspondant : données ignorées",
            key,
        )
        persistent_notification.async_create(
            self.hass,
            (
                f"Torque envoie des données avec le profil **{', '.join(names)}**, "
                "mais aucun véhicule de l'intégration Torque OBD-II ne porte ce nom. "
                "Ces données sont ignorées (elles ne sont pas mélangées à un autre "
                "véhicule).\n\nAjoutez un véhicule portant exactement ce nom "
                "(Paramètres → Appareils et services → Torque OBD-II → Ajouter un "
                "appareil), ou renommez le profil dans Torque Pro."
            ),
            title="Torque OBD-II : profil non reconnu",
            notification_id=f"torque_obd_profile_{vehicle_slug(names[0]) or 'inconnu'}",
        )

    def _process(self, slug: str, data: dict[str, Any]) -> web.Response:
        """Traite un envoi. Répond toujours « OK! » : sinon Torque réessaie en boucle."""
        try:
            now = time.monotonic()
            for old_slug, old_data in self._prune(now):
                self._deliver(self._entries().get(old_slug), old_slug, old_data)

            # Une clé répétée devient une liste (_query_to_dict) : on garde la 1re valeur
            for meta in ("profileName", "session", "id", "eml"):
                if isinstance(data.get(meta), list):
                    data[meta] = data[meta][0]
            profile = str(data.get("profileName", "")).strip()
            session = str(data.get("session", "")).strip()

            entry, via_alias = self._resolve_profile(profile)
            by_profile = entry is not None
            if entry is None and profile and self._is_disabled_vehicle(profile):
                return web.Response(text="OK!")  # véhicule désactivé : on ignore
            bound = self._session_entry.get(session) if session else None
            if bound is not None:
                bound_entry = self._by_id(bound[0])
                if entry is None:
                    entry, via_alias = bound_entry, bound[2]
                elif via_alias is None and bound[2] and bound_entry is not entry:
                    # La session avait démarré sur un alias qui désignait un autre
                    # véhicule : cet alias est commun aux deux, on l'abandonne.
                    if bound_entry is not None:
                        self._forget_alias(bound_entry, bound[2])

            device = str(data.get("id", "")).strip()
            if by_profile and device:
                self._mark_routed(entry, device)

            if entry is None:
                # Mise en attente réservée aux téléphones qui utilisent l'aiguillage
                # par profil (déjà vus avec un nom de profil reconnu). Tout autre
                # téléphone (ex. celui d'un ami avec sa propre URL) est traité
                # immédiatement, via son URL, comme avant.
                if not session or not device or not self._is_routed(device):
                    self._deliver(self._entries().get(slug), slug, data)
                    return web.Response(text="OK!")
                pend = self._pending.setdefault(
                    session, {"since": now, "items": [], "profiles": set()}
                )
                if profile:
                    pend["profiles"].add(profile)
                pend["items"].append((slug, data))
                del pend["items"][:-PENDING_MAX_ITEMS]
                return web.Response(text="OK!")

            if session:
                self._session_entry[session] = (entry.entry_id, now, via_alias)
                if (pend := self._pending.pop(session, None)) is not None:
                    self._learn_aliases(entry, pend["profiles"])
                    for _old_slug, old_data in pend["items"]:
                        self._deliver(entry, slug, old_data)
            self._deliver(entry, slug, data)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Erreur lors du traitement des données Torque (%s)", slug)
        return web.Response(text="OK!")

    # ------------------------------------------------- PID perso à code partagé
    def _expand_multi(self, entry: TorqueConfigEntry, data: dict[str, Any]) -> dict[str, Any]:
        """Sépare les PID perso qui partagent un même code (ex. plusieurs PID "21 01").

        Torque envoie alors la même clé (k2101) une fois par PID, dans l'ordre de
        sa liste, et les noms (userShortName2101…) dans des requêtes à part, dans
        le même ordre. Chaque valeur devient k2101_<nom court> (ex. k2101_oiltemp).
        """
        runtime = entry.runtime_data
        changed = False
        for key, value in data.items():
            if not (isinstance(value, list) and len(value) > 1):
                continue
            for prefix, fld in (
                ("userShortName", "short"),
                ("userFullName", "full"),
                ("userUnit", "unit"),
            ):
                if key.startswith(prefix) and len(key) > len(prefix):
                    base = normalize_pid("k" + key[len(prefix):])
                    names = [str(v).strip() for v in value]
                    if runtime.multi_names.get(base, {}).get(fld) != names:
                        runtime.multi_names.setdefault(base, {})[fld] = names
                        changed = fld != "unit"
                    break
        if changed:
            self.hass.config_entries.async_update_entry(
                entry,
                options={**entry.options, CONF_MULTI_NAMES: runtime.multi_names},
            )

        out: dict[str, Any] = {}
        for key, value in data.items():
            if not key.startswith("k"):
                out[key] = value
                continue
            base = normalize_pid(key)
            known = runtime.multi_names.get(base, {})
            shorts = known.get("short") or []
            if isinstance(value, list):
                tag = f"{base}:{len(value)}"
                if shorts and len(value) <= len(shorts):
                    # Torque envoie les noms de TOUS les PID perso du code (ex. 44),
                    # ceux sélectionnés pour l'envoi en tête et dans le même ordre
                    # que les valeurs (ex. 15) : on associe les N premiers noms.
                    names = shorts[: len(value)]
                    fulls = known.get("full") or []
                    seen: set[str] = set()
                    for i, (short, val) in enumerate(zip(names, value, strict=True)):
                        sk = f"{base}_{_short_slug(short) or i}"
                        if sk in seen:
                            sk = f"{sk}{i}"
                        seen.add(sk)
                        out[sk] = val
                        if i < len(fulls) and fulls[i]:
                            runtime.sensor_names.setdefault(sk, {})["full_name"] = fulls[i]
                    if tag not in runtime.multi_logged:
                        runtime.multi_logged.add(tag)
                        _LOGGER.warning(
                            "Torque '%s' : %s reçu %d fois (%d noms connus) -> séparé en %s",
                            runtime.vehicle_name, key, len(value), len(shorts),
                            ", ".join(f"{base}_{_short_slug(s)}" for s in names),
                        )
                else:
                    out[key] = value[-1]
                    if tag not in runtime.multi_logged:
                        runtime.multi_logged.add(tag)
                        if not shorts and len(set(map(str, value))) == 1:
                            # Clé répétée à l'identique (ex. GPS) : rien à séparer
                            _LOGGER.debug(
                                "Torque '%s' : %s reçu %d fois (valeurs identiques)",
                                runtime.vehicle_name, key, len(value),
                            )
                        else:
                            _LOGGER.warning(
                                "Torque '%s' : %s reçu %d fois mais %d nom(s) connu(s) "
                                "(noms envoyés en début de trajet) : valeurs non séparées "
                                "pour l'instant. Valeurs reçues : %s",
                                runtime.vehicle_name, key, len(value), len(shorts), value,
                            )
                continue
            out[key] = value
            if len(shorts) > 1 and f"{base}:single" not in runtime.multi_logged:
                runtime.multi_logged.add(f"{base}:single")
                _LOGGER.warning(
                    "Torque '%s' : %d PID perso partagent le code %s mais Torque "
                    "n'envoie qu'UNE valeur (%s). Séparation impossible. "
                    "Clés reçues dans cet envoi : %s",
                    runtime.vehicle_name, len(shorts), key, value,
                    ", ".join(sorted(data))[:1500],
                )
        return out

    # --------------------------------------------------------------- traitement
    def _deliver(
        self, entry: TorqueConfigEntry | None, slug: str, data: dict[str, Any]
    ) -> None:
        """Applique un envoi à un véhicule."""
        if entry is None:
            if slug not in self._warned_slugs:
                self._warned_slugs.add(slug)
                _LOGGER.warning(
                    "Données Torque reçues sur /api/torque-%s mais aucun véhicule "
                    "ne correspond. Vérifiez l'URL configurée dans Torque Pro",
                    slug,
                )
            return

        runtime = entry.runtime_data

        # PID ignorés pour ce véhicule (PID d'une autre voiture cochés dans Torque)
        if ignored := entry_ignored_pids(entry):
            data = {
                k: v
                for k, v in data.items()
                if not (
                    (k.startswith("k") and _base_pid(k) in ignored)
                    or any(
                        k.startswith(pfx) and normalize_pid("k" + k[len(pfx):]) in ignored
                        for pfx, _ in _NAME_PREFIXES
                    )
                )
            }

        # Filtrage optionnel par e-mail : uniquement si Torque l'envoie
        eml = str(data.get("eml", "")).strip().lower()
        if runtime.email and eml and eml != runtime.email:
            _LOGGER.debug("Envoi ignoré pour '%s' : e-mail %s non autorisé", runtime.vehicle_name, eml)
            return

        data = self._expand_multi(entry, data)

        if profile := data.get("profileName"):
            runtime.profile_name = str(profile)
        runtime.last_seen = dt_util.utcnow()
        runtime.request_count += 1

        # Torque envoie les noms (userFullName…) dans des requêtes à part
        has_values = False
        for key, value in data.items():
            if key.startswith("k"):
                has_values = True
                continue
            for prefix, field_name in _NAME_PREFIXES:
                if key.startswith(prefix) and len(key) > len(prefix):
                    name = _extract_name(value)
                    if name:
                        pid = normalize_pid("k" + key[len(prefix):])
                        runtime.sensor_names.setdefault(pid, {})[field_name] = name
                    break

        # On conserve les métadonnées utiles au diagnostic (units, profil…)
        runtime.data.update(data)

        if has_values and runtime.add_new_sensors is not None:
            runtime.add_new_sensors(data)

        async_dispatcher_send(self.hass, SIGNAL_UPDATE.format(entry.entry_id), data)
