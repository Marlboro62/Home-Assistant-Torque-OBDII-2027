"""Constants for the Torque OBD-II integration."""
from __future__ import annotations

import logging
import os
from typing import Any, Final

import yaml

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolume,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "torque_obd"

# Custom sensor definitions file
SENSOR_DEFINITIONS_FILE: Final = "torque_sensor_definitions.yaml"

# Configuration
CONF_EMAIL: Final = "email"
CONF_VEHICLE_NAME: Final = "vehicle_name"
CONF_PROFILE_ALIASES: Final = "profile_aliases"
CONF_IGNORED_PIDS: Final = "ignored_pids"
# Noms (dans l'ordre) des PID perso partageant un même code (ex. 9 PID "21 01")
CONF_MULTI_NAMES: Final = "multi_pid_names"
CONF_AMBIGUOUS_PROFILES: Final = "ambiguous_profiles"
CONF_ROUTED_DEVICES: Final = "routed_devices"

# Aiguillage par profil Torque
PENDING_TIMEOUT_SECONDS: Final = 600  # attente max d'un nom de profil reconnu
PENDING_MAX_ITEMS: Final = 300  # envois gardés en attente par session
SESSION_TTL_SECONDS: Final = 6 * 3600  # durée de mémorisation session -> véhicule

# Durée sans données au-delà de laquelle Torque est considéré déconnecté
DATA_TIMEOUT_SECONDS: Final = 120

# PID GPS utilisés pour le device_tracker
PID_GPS_LATITUDE: Final = "kff1006"
PID_GPS_LONGITUDE: Final = "kff1005"
PID_GPS_ACCURACY: Final = "kff1239"
PID_GPS_ALTITUDE: Final = "kff1010"
PID_GPS_SPEED: Final = "kff1001"

# Signaux dispatcher
SIGNAL_UPDATE: Final = DOMAIN + "_{}_update"

# Décimales affichées par défaut selon l'unité, quand la définition n'en précise pas
# (évite "27,4509803921569 %"). Une clé "precision" dans la définition reste prioritaire.
DEFAULT_PRECISION_BY_UNIT: Final[dict[str, int]] = {
    "%": 1,
    "°C": 1,
    "°F": 1,
    "°": 1,
    "V": 2,
    "RPM": 0,
    "rpm": 0,
    "km/h": 0,
    "mph": 0,
    "km": 1,
    "mi": 1,
    "m": 1,
    "s": 0,
    "min": 0,
    "kPa": 0,
    "Pa": 0,
    "psi": 1,
    "bar": 2,
    "mbar": 0,
    "g": 0,
    "g/s": 2,
    "g/km": 0,
    "mg/stroke": 2,
    "L": 2,
    "L/h": 2,
    "mL/min": 1,
    "km/L": 1,
    "L/100km": 1,
    "mpg": 1,
    "Nm": 0,
    "N·m": 0,
    "W": 0,
    "kg/h": 1,
    "ms": 2,
    "µs": 0,
    "μs": 0,
    "°vil": 1,
    "mg/cp": 0,
    "hp": 1,
    "kW": 1,
}

# Nombre de chiffres hex des PID OBD-II standard (0x00-0xFF)
STANDARD_PID_HEX_LENGTH: Final = 2


def normalize_pid(pid: str) -> str:
    """Normalise un PID Torque (k5 -> k05, kd -> k0d). Unique source de vérité."""
    pid = pid.lower()
    if not pid.startswith("k"):
        return pid
    hex_part = pid[1:]
    if not hex_part:
        return pid
    try:
        int(hex_part, 16)
    except ValueError:
        return pid
    if len(hex_part) < STANDARD_PID_HEX_LENGTH:
        hex_part = hex_part.zfill(STANDARD_PID_HEX_LENGTH)
    return f"k{hex_part}"


def vehicle_slug(vehicle_name: str) -> str:
    """Nom de véhicule -> segment d'URL (même règle partout)."""
    slug = vehicle_name.strip().lower().replace(" ", "-")
    return "".join(c for c in slug if c.isalnum() or c in "-_")

# Sensor definitions
# Maps Torque parameter names to Home Assistant sensor attributes
# NOTE: These are FALLBACK definitions. Sensor names should preferably come from
# Torque payload (userFullName{PID} or userShortName{PID}) when available.
# Units are in METRIC format as Torque typically sends metric values regardless of app settings:
# - Temperature: Celsius (°C)
# - Speed: Kilometers per hour (km/h)
# - Distance: Kilometers (km)
# - Volume: Liters (L)
# - Pressure: Kilopascals (kPa)
# Note: While Torque usually sends metric values, this may vary by version or configuration.
SENSOR_DEFINITIONS: Final = {
    # Basic OBD-II sensors (0x00-0x1F)
    "k03": {
        "name": "Statut du carburant",
        "unit": None,
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": None,
    },
    "k04": {
        "name": "Charge moteur",
        "unit": PERCENTAGE,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k05": {
        "name": "Température du liquide de refroidissement",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:coolant-temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k06": {
        "name": "Correction carburant banc 1 court terme",
        "unit": PERCENTAGE,
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k07": {
        "name": "Correction carburant banc 1 long terme",
        "unit": PERCENTAGE,
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k08": {
        "name": "Correction carburant banc 2 court terme",
        "unit": PERCENTAGE,
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k09": {
        "name": "Correction carburant banc 2 long terme",
        "unit": PERCENTAGE,
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k0a": {
        "name": "Pression carburant",
        "unit": "kPa",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k0b": {
        "name": "Pression du collecteur d'admission",
        "unit": "kPa",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "min": 0,
        "max": 400,
    },
    "k0c": {
        "name": "Régime moteur",
        "unit": "RPM",
        "icon": "mdi:engine",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "precision": 0,
    },
    "k0d": {
        "name": "Vitesse du véhicule",
        "unit": UnitOfSpeed.KILOMETERS_PER_HOUR,
        "icon": "mdi:speedometer",
        "device_class": SensorDeviceClass.SPEED,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k0e": {
        "name": "Avance à l'allumage",
        "unit": "°",
        "icon": "mdi:clock-fast",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "min": -64,
        "max": 63,
    },
    "k0f": {
        "name": "Température d'air d'admission",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:air-filter",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k10": {
        "name": "Débit massique d'air",
        "unit": "g/s",
        "icon": "mdi:air-filter",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k11": {
        "name": "Position des gaz",
        "unit": PERCENTAGE,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k12": {
        "name": "Statut de l'air",
        "unit": None,
        "icon": "mdi:air-filter",
        "device_class": None,
        "state_class": None,
    },
    "k14": {
        "name": "Correction carburant banc 1 capteur 1",
        "unit": PERCENTAGE,
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k15": {
        "name": "Correction carburant banc 1 capteur 2",
        "unit": PERCENTAGE,
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k16": {
        "name": "Correction carburant banc 1 capteur 3",
        "unit": PERCENTAGE,
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k17": {
        "name": "Correction carburant banc 1 capteur 4",
        "unit": PERCENTAGE,
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k18": {
        "name": "Correction carburant banc 2 capteur 1",
        "unit": PERCENTAGE,
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k19": {
        "name": "Correction carburant banc 2 capteur 2",
        "unit": PERCENTAGE,
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k1a": {
        "name": "Correction carburant banc 2 capteur 3",
        "unit": PERCENTAGE,
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k1b": {
        "name": "Correction carburant banc 2 capteur 4",
        "unit": PERCENTAGE,
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k1f": {
        "name": "Durée de fonctionnement depuis le démarrage",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    # OBD-II sensors (0x20-0x3F)
    "k21": {
        "name": "Distance parcourue avec voyant MIL/CEL allumé",
        "unit": "km",
        "icon": "mdi:map-marker-distance",
        "device_class": SensorDeviceClass.DISTANCE,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "k22": {
        "name": "Pression rampe carburant (relative au vide du collecteur)",
        "unit": "kPa",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k23": {
        "name": "Pression rampe carburant",
        "unit": "kPa",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k24": {
        "name": "Rapport d'équivalence capteur O2 n°1",
        "unit": None,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k25": {
        "name": "Rapport d'équivalence capteur O2 n°2",
        "unit": None,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k26": {
        "name": "Rapport d'équivalence capteur O2 n°3",
        "unit": None,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k27": {
        "name": "Rapport d'équivalence capteur O2 n°4",
        "unit": None,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k28": {
        "name": "Rapport d'équivalence capteur O2 n°5",
        "unit": None,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k29": {
        "name": "Rapport d'équivalence capteur O2 n°6",
        "unit": None,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k2a": {
        "name": "Rapport d'équivalence capteur O2 n°7",
        "unit": None,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k2b": {
        "name": "Rapport d'équivalence capteur O2 n°8",
        "unit": None,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k2c": {
        "name": "EGR commandée",
        "unit": PERCENTAGE,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k2d": {
        "name": "Erreur EGR",
        "unit": PERCENTAGE,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k2f": {
        "name": "Niveau de carburant",
        "unit": PERCENTAGE,
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k31": {
        "name": "Distance parcourue depuis remise à zéro des codes",
        "unit": "km",
        "icon": "mdi:map-marker-distance",
        "device_class": SensorDeviceClass.DISTANCE,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "k32": {
        "name": "Pression vapeur système EVAP",
        "unit": "kPa",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k33": {
        "name": "Pression barométrique",
        "unit": "kPa",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k34": {
        "name": "Rapport d'équivalence capteur O2 n°1 (alternatif)",
        "unit": None,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k3c": {
        "name": "Température catalyseur (banc 1 capteur 1)",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:coolant-temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k3d": {
        "name": "Température catalyseur (banc 2 capteur 1)",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:coolant-temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k3e": {
        "name": "Température catalyseur (banc 1 capteur 2)",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:coolant-temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k3f": {
        "name": "Température catalyseur (banc 2 capteur 2)",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:coolant-temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    # OBD-II sensors (0x40-0x5F)
    "k42": {
        "name": "Tension (module de contrôle)",
        "unit": "V",
        "icon": "mdi:car-battery",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k43": {
        "name": "Charge moteur (absolue)",
        "unit": PERCENTAGE,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k44": {
        "name": "Rapport d'équivalence commandé (lambda)",
        "unit": None,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k45": {
        "name": "Position relative des gaz",
        "unit": PERCENTAGE,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k46": {
        "name": "Température de l'air ambiant",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k47": {
        "name": "Position absolue des gaz B",
        "unit": PERCENTAGE,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k49": {
        "name": "Position pédale d'accélérateur D",
        "unit": PERCENTAGE,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k4a": {
        "name": "Position pédale d'accélérateur E",
        "unit": PERCENTAGE,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k4b": {
        "name": "Position pédale d'accélérateur F",
        "unit": PERCENTAGE,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k52": {
        "name": "Taux d'éthanol dans le carburant",
        "unit": PERCENTAGE,
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k5a": {
        "name": "Position relative de la pédale d'accélérateur",
        "unit": PERCENTAGE,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k5c": {
        "name": "Température d'huile moteur",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:oil-temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    # OBD-II sensors (0x60+)
    "k78": {
        "name": "Température des gaz d'échappement 1",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k79": {
        "name": "Température des gaz d'échappement 2",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "ka6": {
        "name": "Odomètre",
        "unit": "km",
        "icon": "mdi:counter",
        "device_class": SensorDeviceClass.DISTANCE,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "kb4": {
        "name": "Température de boîte de vitesses (méthode 2)",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    # -------------------------------------------------------------------------
    # PID standard SAE J1979 (mode 01) complémentaires
    # -------------------------------------------------------------------------
    "k1c": {
        "name": "Norme OBD du véhicule",
        "unit": None,
        "icon": "mdi:certificate",
        "device_class": None,
        "state_class": None,
    },
    "k1e": {
        "name": "Statut prise de force (PTO)",
        "unit": None,
        "icon": "mdi:power-plug",
        "device_class": None,
        "state_class": None,
    },
    "k2e": {
        "name": "Purge EVAP commandée",
        "unit": PERCENTAGE,
        "icon": "mdi:gas-cylinder",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k30": {
        "name": "Démarrages à chaud depuis effacement des codes",
        "unit": None,
        "icon": "mdi:counter",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "precision": 0,
    },
    "k48": {
        "name": "Position absolue des gaz C",
        "unit": PERCENTAGE,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k4c": {
        "name": "Commande actionneur papillon",
        "unit": PERCENTAGE,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k4d": {
        "name": "Durée de fonctionnement avec voyant MIL allumé",
        "unit": "min",
        "icon": "mdi:timer-alert",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "k4e": {
        "name": "Durée depuis effacement des codes défaut",
        "unit": "min",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "k51": {
        "name": "Type de carburant",
        "unit": None,
        "icon": "mdi:gas-station",
        "device_class": None,
        "state_class": None,
    },
    "k53": {
        "name": "Pression vapeur EVAP absolue",
        "unit": "kPa",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k54": {
        "name": "Pression vapeur EVAP",
        "unit": "Pa",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k59": {
        "name": "Pression rampe carburant (absolue)",
        "unit": "kPa",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k5b": {
        "name": "Durée de vie restante batterie hybride",
        "unit": PERCENTAGE,
        "icon": "mdi:battery-heart-variant",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k5d": {
        "name": "Calage de l'injection",
        "unit": "°",
        "icon": "mdi:clock-fast",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k5e": {
        "name": "Débit carburant moteur (OBD)",
        "unit": "L/h",
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k61": {
        "name": "Couple demandé par le conducteur",
        "unit": PERCENTAGE,
        "icon": "mdi:engine",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k62": {
        "name": "Couple moteur réel",
        "unit": PERCENTAGE,
        "icon": "mdi:engine",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k63": {
        "name": "Couple moteur de référence",
        "unit": "Nm",
        "icon": "mdi:engine",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k66": {
        "name": "Débit massique d'air (capteur MAF)",
        "unit": "g/s",
        "icon": "mdi:air-filter",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k67": {
        "name": "Température liquide de refroidissement (capteur)",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:coolant-temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k68": {
        "name": "Température d'air d'admission (capteur)",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:air-filter",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k6b": {
        "name": "Température EGR",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k70": {
        "name": "Pression de suralimentation (contrôle)",
        "unit": "kPa",
        "icon": "mdi:turbine",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k73": {
        "name": "Pression des gaz d'échappement",
        "unit": "kPa",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k7a": {
        "name": "Pression différentielle FAP (banc 1)",
        "unit": "kPa",
        "icon": "mdi:air-filter",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k7b": {
        "name": "Pression différentielle FAP (banc 2)",
        "unit": "kPa",
        "icon": "mdi:air-filter",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k7c": {
        "name": "Température du FAP",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer-high",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k84": {
        "name": "Température surface collecteur",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k8e": {
        "name": "Couple de friction moteur",
        "unit": PERCENTAGE,
        "icon": "mdi:engine",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "ka2": {
        "name": "Débit carburant par cylindre",
        "unit": "mg/stroke",
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "ka4": {
        "name": "Rapport de boîte engagé",
        "unit": None,
        "icon": "mdi:car-shift-pattern",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "precision": 0,
    },
    "ka5": {
        "name": "Dosage AdBlue (DEF) commandé",
        "unit": PERCENTAGE,
        "icon": "mdi:water",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    # Torque custom PIDs (kff*)
    "kff1001": {
        "name": "Vitesse GPS",
        "unit": UnitOfSpeed.KILOMETERS_PER_HOUR,
        "icon": "mdi:map-marker-distance",
        "device_class": SensorDeviceClass.SPEED,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1005": {
        "name": "Longitude GPS",
        "unit": "°",
        "precision": 6,
        "icon": "mdi:crosshairs-gps",
        "device_class": None,
        "state_class": None,
    },
    "kff1006": {
        "name": "Latitude GPS",
        "unit": "°",
        "precision": 6,
        "icon": "mdi:crosshairs-gps",
        "device_class": None,
        "state_class": None,
    },
    "kff1010": {
        "name": "Altitude GPS",
        "unit": "m",
        "icon": "mdi:elevation-rise",
        "device_class": SensorDeviceClass.DISTANCE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1201": {
        "name": "Miles par gallon (instantané)",
        "unit": "mpg",
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "min": 0,
        "max": 511,
    },
    "kff1202": {
        "name": "Jauge de suralimentation turbo et dépression",
        "unit": "psi",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "min": -15,
        "max": 60,
    },
    "kff1203": {
        "name": "Kilomètres par litre (instantané)",
        "unit": "km/L",
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1204": {
        "name": "Distance du trajet",
        "unit": "km",
        "icon": "mdi:map-marker-distance",
        "device_class": SensorDeviceClass.DISTANCE,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "kff1205": {
        "name": "MPG moyen du trajet",
        "unit": "mpg",
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "min": 0,
        "max": 511,
    },
    "kff1206": {
        "name": "KPL moyen du trajet",
        "unit": "km/L",
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1207": {
        "name": "Litres aux 100 km (instantané)",
        "unit": "L/100km",
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1208": {
        "name": "Litres/100 km moyen du trajet",
        "unit": "L/100km",
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff120c": {
        "name": "Distance du trajet (profil véhicule)",
        "unit": "km",
        "icon": "mdi:map-marker-distance",
        "device_class": SensorDeviceClass.DISTANCE,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "kff1214": {
        "name": "Tension O2 banc 1 capteur 1",
        "unit": "V",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1215": {
        "name": "Tension O2 banc 1 capteur 2",
        "unit": "V",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1216": {
        "name": "Tension O2 banc 1 capteur 3",
        "unit": "V",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1217": {
        "name": "Tension O2 banc 1 capteur 4",
        "unit": "V",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1218": {
        "name": "Tension O2 banc 2 capteur 1",
        "unit": "V",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1219": {
        "name": "Tension O2 banc 2 capteur 2",
        "unit": "V",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff121a": {
        "name": "Tension O2 banc 2 capteur 3",
        "unit": "V",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff121b": {
        "name": "Tension O2 banc 2 capteur 4",
        "unit": "V",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1220": {
        "name": "Capteur d'accélération (axe X)",
        "unit": "g",
        "icon": "mdi:car-speed-limiter",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1221": {
        "name": "Capteur d'accélération (axe Y)",
        "unit": "g",
        "icon": "mdi:car-speed-limiter",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1222": {
        "name": "Capteur d'accélération (axe Z)",
        "unit": "g",
        "icon": "mdi:car-speed-limiter",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1223": {
        "name": "Capteur d'accélération (total)",
        "unit": "g",
        "icon": "mdi:car-speed-limiter",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1225": {
        "name": "Couple moteur",
        "unit": "Nm",
        "icon": "mdi:engine",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1226": {
        "name": "Puissance aux roues (ch)",
        "unit": "hp",
        "icon": "mdi:engine",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff122d": {
        "name": "Temps 0-60 mph",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": None,
    },
    "kff122e": {
        "name": "Temps 0-100 km/h",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": None,
    },
    "kff122f": {
        "name": "Temps sur 1/4 de mile",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": None,
    },
    "kff1230": {
        "name": "Temps sur 1/8 de mile",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": None,
    },
    "kff1237": {
        "name": "Différence de vitesse GPS vs OBD",
        "unit": UnitOfSpeed.KILOMETERS_PER_HOUR,
        "icon": "mdi:speedometer",
        "device_class": SensorDeviceClass.SPEED,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1238": {
        "name": "Tension (adaptateur OBD)",
        "unit": "V",
        "icon": "mdi:car-battery",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1239": {
        "name": "Précision GPS",
        "unit": "m",
        "icon": "mdi:crosshairs-gps",
        "device_class": SensorDeviceClass.DISTANCE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff123a": {
        "name": "Satellites GPS",
        "unit": None,
        "icon": "mdi:satellite-variant",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "precision": 0,
        "min": 0,
        "max": 99,
    },
    "kff123b": {
        "name": "Cap GPS",
        "unit": "°",
        "precision": 0,
        "icon": "mdi:compass",
        "device_class": None,
        "state_class": None,
    },
    "kff1240": {
        "name": "Tension large bande capteur O2 n°1",
        "unit": "V",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1241": {
        "name": "Tension large bande capteur O2 n°2",
        "unit": "V",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1242": {
        "name": "Tension large bande capteur O2 n°3",
        "unit": "V",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1243": {
        "name": "Tension large bande capteur O2 n°4",
        "unit": "V",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1244": {
        "name": "Tension large bande capteur O2 n°5",
        "unit": "V",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1245": {
        "name": "Tension large bande capteur O2 n°6",
        "unit": "V",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1246": {
        "name": "Tension large bande capteur O2 n°7",
        "unit": "V",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1247": {
        "name": "Tension large bande capteur O2 n°8",
        "unit": "V",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1249": {
        "name": "Rapport air/carburant (mesuré)",
        "unit": None,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff124a": {
        "name": "Inclinaison (x)",
        "unit": "°",
        "icon": "mdi:axis-arrow",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff124b": {
        "name": "Inclinaison (y)",
        "unit": "°",
        "icon": "mdi:axis-arrow",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff124c": {
        "name": "Inclinaison (z)",
        "unit": "°",
        "icon": "mdi:axis-arrow",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff124d": {
        "name": "Rapport air/carburant (commandé)",
        "unit": None,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff124f": {
        "name": "Temps 0-200 km/h",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": None,
    },
    "kff1257": {
        "name": "CO₂ en g/km (instantané)",
        "unit": "g/km",
        "icon": "mdi:molecule-co2",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1258": {
        "name": "CO₂ en g/km (moyen)",
        "unit": "g/km",
        "icon": "mdi:molecule-co2",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff125a": {
        "name": "Débit carburant par minute",
        "unit": "mL/min",
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff125c": {
        "name": "Coût carburant (trajet)",
        "unit": None,
        "precision": 2,
        "icon": "mdi:currency-usd",
        "device_class": None,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "kff125d": {
        "name": "Débit carburant par heure",
        "unit": "L/h",
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff125e": {
        "name": "Temps 60-120 mph",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": None,
    },
    "kff125f": {
        "name": "Temps 60-80 mph",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": None,
    },
    "kff1260": {
        "name": "Temps 40-60 mph",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": None,
    },
    "kff1261": {
        "name": "Temps 80-100 mph",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": None,
    },
    "kff1263": {
        "name": "Vitesse moyenne du trajet (en mouvement uniquement)",
        "unit": UnitOfSpeed.KILOMETERS_PER_HOUR,
        "icon": "mdi:speedometer",
        "device_class": SensorDeviceClass.SPEED,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1264": {
        "name": "Temps 100-0 km/h",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": None,
    },
    "kff1265": {
        "name": "Temps 60-0 mph",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": None,
    },
    "kff1266": {
        "name": "Durée du trajet (depuis le départ)",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "kff1267": {
        "name": "Durée du trajet (à l'arrêt)",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "kff1268": {
        "name": "Durée du trajet (en mouvement)",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "kff1269": {
        "name": "Rendement volumétrique (calculé)",
        "unit": PERCENTAGE,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff126a": {
        "name": "Distance avant panne sèche (estimée)",
        "unit": "km",
        "icon": "mdi:map-marker-distance",
        "device_class": SensorDeviceClass.DISTANCE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff126b": {
        "name": "Carburant restant (calculé depuis le profil véhicule)",
        "unit": PERCENTAGE,
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff126d": {
        "name": "Coût par km (instantané)",
        "unit": None,
        "icon": "mdi:currency-eur",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff126e": {
        "name": "Coût par km (trajet)",
        "unit": None,
        "icon": "mdi:currency-eur",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1270": {
        "name": "Baromètre (sur appareil Android)",
        "unit": "kPa",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1271": {
        "name": "Carburant utilisé (trajet)",
        "unit": UnitOfVolume.LITERS,
        "icon": "mdi:fuel",
        "device_class": SensorDeviceClass.VOLUME,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "kff1272": {
        "name": "Vitesse moyenne du trajet (à l'arrêt ou en mouvement)",
        "unit": UnitOfSpeed.KILOMETERS_PER_HOUR,
        "icon": "mdi:speedometer",
        "device_class": SensorDeviceClass.SPEED,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1273": {
        "name": "Puissance moteur en kW (aux roues)",
        "unit": "kW",
        "icon": "mdi:engine",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1275": {
        "name": "Temps 80-120 km/h",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": None,
    },
    "kff1276": {
        "name": "Temps 60-130 mph",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": None,
    },
    "kff1277": {
        "name": "Temps 0-30 mph",
        "unit": "s",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": None,
    },
# Ajouts pour les capteurs KFF manquants
    "kff12b6": {
        "name": "Consommation Totale (Session)",
        "unit": "g",
        "icon": "mdi:fuel",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1280": {
        "name": "Chrono 100-200 km/h",
        "unit": "s",
        "icon": "mdi:timer-outline",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff129a": {
        "name": "Batterie du téléphone",
        "unit": PERCENTAGE,
        "icon": "mdi:cellphone-charging",
        "device_class": SensorDeviceClass.BATTERY,
        "state_class": SensorStateClass.MEASUREMENT,
        "min": 0,
        "max": 100,
    },
    "kff1296": {
        "name": "Part du trajet en ville",
        "unit": PERCENTAGE,
        "icon": "mdi:city",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "min": 0,
        "max": 100,
    },
    "kff1297": {
        "name": "Part du trajet sur route/autoroute",
        "unit": PERCENTAGE,
        "icon": "mdi:highway",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "min": 0,
        "max": 100,
    },
    "kff1298": {
        "name": "Part du trajet au ralenti",
        "unit": PERCENTAGE,
        "icon": "mdi:car-clock",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "min": 0,
        "max": 100,
    },    
    "kff5201": {
        "name": "Miles par gallon (moyenne long terme)",
        "unit": "mpg",
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "min": 0,
        "max": 511,
    },
    "kff5202": {
        "name": "Kilomètres par litre (moyenne long terme)",
        "unit": "km/L",
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff5203": {
        "name": "Litres aux 100 km (moyenne long terme)",
        "unit": "L/100km",
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kfe1805": {
        "name": "Température de boîte de vitesses (méthode 1)",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "kff1007": {
        "name": "Cap GPS (bearing)",
        "unit": "°",
        "precision": 0,
        "icon": "mdi:compass-outline",
        "device_class": None,
        "state_class": None,
    },	    
    # Ford-specific extended PIDs
    "k221e1c": {
        "name": "Température boîte de vitesses Ford",
        "unit": UnitOfTemperature.FAHRENHEIT,
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k2203ca": {
        "name": "Température d'air d'admission Ford IAT2 (méthode 2)",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:air-filter",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k222813": {
        "name": "Pression pneu avant côté conducteur Ford",
        "unit": "psi",
        "icon": "mdi:car-tire-alert",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k222814": {
        "name": "Pression pneu avant côté passager Ford",
        "unit": "psi",
        "icon": "mdi:car-tire-alert",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k222815": {
        "name": "Pression pneu arrière côté conducteur Ford",
        "unit": "psi",
        "icon": "mdi:car-tire-alert",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "k222816": {
        "name": "Pression pneu arrière côté passager Ford",
        "unit": "psi",
        "icon": "mdi:car-tire-alert",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
}
# Additional attributes to store but not create sensors for
ATTRIBUTE_FIELDS: Final = [
    "eml",  # Email address (vehicle identifier)
    "time",  # Timestamp
    "session",  # Session ID
    "id",  # Device ID
    "v",  # App version
]

# Patterns for fields that should not create sensors
# These are metadata fields from Torque
METADATA_FIELD_PREFIXES: Final = [
    "profile",  # Vehicle profile data (profileName, profileFuelType, etc.)
    "userUnit",  # User-configured units (DO NOT USE - frequently wrong)
    "defaultUnit",  # Default units (DO NOT USE - frequently wrong)
    "userShortName",  # Short names for PIDs (used for sensor naming)
    "userFullName",  # Full names for PIDs (used for sensor naming)
]


def load_sensor_definitions(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Load sensor definitions from YAML file if it exists, merge with defaults.
    
    Args:
        hass: Home Assistant instance
        
    Returns:
        Dictionary of sensor definitions (defaults merged with user customizations)
    """
    # Start with default definitions
    definitions = SENSOR_DEFINITIONS.copy()
    
    # Path to the custom sensor definitions file in the config directory
    config_path = hass.config.path(SENSOR_DEFINITIONS_FILE)
    
    if not os.path.isfile(config_path):
        _LOGGER.debug(
            "No custom sensor definitions file found at %s. Using defaults only.",
            config_path
        )
        return definitions
    
    try:
        _LOGGER.info("Loading custom sensor definitions from %s", config_path)
        with open(config_path, "r", encoding="utf-8") as file:
            custom_definitions = yaml.safe_load(file)
        
        if not custom_definitions:
            _LOGGER.warning(
                "Custom sensor definitions file at %s is empty or invalid. Using defaults only.",
                config_path
            )
            return definitions
        
        if not isinstance(custom_definitions, dict):
            _LOGGER.error(
                "Custom sensor definitions file at %s must contain a dictionary. Using defaults only.",
                config_path
            )
            return definitions
        
        # Merge custom definitions with defaults
        # Custom definitions override defaults
        merged_count = 0
        new_count = 0
        
        for raw_pid, definition in custom_definitions.items():
            # Normalisation : "kd" dans le YAML doit surcharger "k0d" des défauts
            pid = normalize_pid(str(raw_pid))
            if not isinstance(definition, dict):
                _LOGGER.warning(
                    "Invalid definition for PID '%s' in custom sensor definitions. Skipping.",
                    pid
                )
                continue
            
            # Validate required fields
            if "name" not in definition:
                _LOGGER.warning(
                    "PID '%s' in custom sensor definitions missing required 'name' field. Skipping.",
                    pid
                )
                continue
            
            # Convert string class names to actual classes if needed
            definition_copy = definition.copy()
            
            # Handle device_class
            if "device_class" in definition_copy:
                device_class = definition_copy["device_class"]
                if isinstance(device_class, str) and device_class:
                    # Try to convert string to SensorDeviceClass
                    # Use getattr with None default to safely check for attribute
                    class_attr = getattr(SensorDeviceClass, device_class.upper(), None)
                    if class_attr is not None:
                        definition_copy["device_class"] = class_attr
                    else:
                        _LOGGER.warning(
                            "Unknown device_class '%s' for PID '%s'. Setting to None.",
                            device_class,
                            pid
                        )
                        definition_copy["device_class"] = None
            
            # Handle state_class
            if "state_class" in definition_copy:
                state_class = definition_copy["state_class"]
                if isinstance(state_class, str) and state_class:
                    # Try to convert string to SensorStateClass
                    # Use getattr with None default to safely check for attribute
                    class_attr = getattr(SensorStateClass, state_class.upper(), None)
                    if class_attr is not None:
                        definition_copy["state_class"] = class_attr
                    else:
                        _LOGGER.warning(
                            "Unknown state_class '%s' for PID '%s'. Setting to None.",
                            state_class,
                            pid
                        )
                        definition_copy["state_class"] = None
            
            # Add defaults for optional fields if not present
            definition_copy.setdefault("unit", None)
            definition_copy.setdefault("icon", "mdi:car-info")
            definition_copy.setdefault("device_class", None)
            definition_copy.setdefault("state_class", None)
            
            # Track if this is new or override
            if pid in definitions:
                merged_count += 1
                _LOGGER.debug("Overriding default definition for PID '%s'", pid)
            else:
                new_count += 1
                _LOGGER.debug("Adding new custom definition for PID '%s'", pid)
            
            definitions[pid] = definition_copy
        
        _LOGGER.info(
            "Loaded custom sensor definitions: %d overrides, %d new PIDs",
            merged_count,
            new_count
        )
        
    except yaml.YAMLError as err:
        _LOGGER.error(
            "Error parsing custom sensor definitions file at %s: %s. Using defaults only.",
            config_path,
            err,
            exc_info=True
        )
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.error(
            "Unexpected error loading custom sensor definitions from %s: %s. Using defaults only.",
            config_path,
            err,
            exc_info=True
        )
    
    return definitions