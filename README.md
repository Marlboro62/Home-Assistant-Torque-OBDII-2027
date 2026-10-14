# Torque OBD-II pour Home Assistant

[![Release](https://img.shields.io/github/v/release/Marlboro62/Home-Assistant-Torque-OBDII-2027?include_prereleases&label=version)](https://github.com/Marlboro62/Home-Assistant-Torque-OBDII-2027/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Validate](https://github.com/Marlboro62/Home-Assistant-Torque-OBDII-2027/actions/workflows/validate.yml/badge.svg)](https://github.com/Marlboro62/Home-Assistant-Torque-OBDII-2027/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/github/license/Marlboro62/Home-Assistant-Torque-OBDII-2027)](LICENSE)

Intégration personnalisée qui reçoit les données OBD-II envoyées par l'application Android
[Torque Pro](https://torque-bhp.com/) et les transforme en capteurs Home Assistant
(un appareil par véhicule).

> Version retravaillée et étendue de [JOHLC/Home-Assistant-Torque-OBDII](https://github.com/JOHLC/Home-Assistant-Torque-OBDII).

*English summary [below](#english).*

## Fonctionnalités

- Un appareil par véhicule, avec sa propre URL : `/api/torque-<nom-du-vehicule>`
- **Plusieurs voitures sur un même téléphone** : le véhicule est choisi selon le profil Torque
- **PID à ignorer** par véhicule (options de l'intégration)
- **PID perso à code partagé** (ex. bloc `21 01`) séparés en capteurs distincts
- Position GPS (`device_tracker`), état « Torque connecté », diagnostics
- Définitions de capteurs personnalisables via `/config/torque_sensor_definitions.yaml`
- **PID Torque prêts à l'emploi** par constructeur : Renault, Dacia, Nissan, Lada, autres ([`torque_pids`](torque_pids))

## Installation

### HACS (recommandé)

[![Ouvrir dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Marlboro62&repository=Home-Assistant-Torque-OBDII-2027&category=integration)

Ou manuellement :
1. HACS → ⋮ → **Dépôts personnalisés**
2. URL : `https://github.com/Marlboro62/Home-Assistant-Torque-OBDII-2027` — catégorie **Intégration**
3. Installer **Torque OBD-II**, puis redémarrer Home Assistant
4. Pour les pré-versions (`…b0`) : activer l'interrupteur *Pre-release* du dépôt dans HACS

### Manuelle
Copier `custom_components/torque_obd` dans `/config/custom_components/`, puis redémarrer.

## Configuration

[![Ajouter l'intégration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=torque_obd)

1. Paramètres → Appareils et services → **Ajouter une intégration** → *Torque OBD-II*
2. Nom du véhicule = **nom exact du profil Torque** (ex. `Ma voiture`)
3. Dans Torque Pro → Réglages → *Enregistrement et envoi de données* :
   - **Envoyer au serveur web** : activé
   - **URL du serveur Web** : `http://<ip-ha>:8123/api/torque-<nom-du-vehicule>`
     (ou l'adresse externe en HTTPS)
   - **Email utilisateur** : laisser vide
   - **Sélectionner quoi surveiller** : cocher les PID à envoyer (les moins possible)

Plusieurs voitures sur un téléphone : créer un profil Torque par voiture, avec le même nom
que le véhicule dans HA. Une seule URL suffit, l'aiguillage se fait par le profil.

### Options du véhicule (roue dentée)
- **Profils Torque** : noms / identifiants de profil associés au véhicule (appris automatiquement)
- **PID à ignorer** : ex. `k2101, k2174, k2176` — les entités correspondantes sont supprimées

## Définitions personnalisées

Noms, unités, icônes et limites de vos PID (standards ou perso mode 21/22…) se définissent dans
`/config/torque_sensor_definitions.yaml` (modèle : `custom_components/torque_obd/torque_sensor_definitions.yaml.example`).
Redémarrer HA après modification. La clé est `k` + le code *ModeAndPID* de Torque, en minuscules.

```yaml
# PID perso mode 22 (ModeAndPID 222005)
k222005:
  name: Tension batterie (calculateur)
  unit: V
  icon: mdi:car-battery
  device_class: voltage
  state_class: measurement
  min: 8          # valeurs hors plage ignorées
  max: 16
  precision: 2    # décimales affichées

# Surcharger un PID standard (vitesse, 0x0D)
kd:
  name: Vitesse compteur
  unit: km/h
  device_class: speed
  state_class: measurement
```

## PID Torque fournis

Le dossier [`torque_pids`](torque_pids) contient des PID constructeur prêts à importer dans Torque,
classés par marque, avec les définitions Home Assistant correspondantes :

| Dossier | Constructeur |
|---|---|
| [`renault`](torque_pids/renault) | Renault — CAN (essence, diesel, Hitachi) et ligne K (Siemens, Sagem, Delphi, Bosch) |
| [`dacia`](torque_pids/dacia) | Dacia — Logan, Sandero, Duster, Dokker, Lodgy |
| [`nissan`](torque_pids/nissan) | Nissan — moteurs Nissan et moteurs Renault |
| [`lada`](torque_pids/lada) | Lada — Largus, Vesta / XRAY à moteur Renault |
| [`autre`](torque_pids/autre) | Alpine A110, Mercedes Citan, Renault Samsung |

> ℹ️ Source : base de diagnostic Renault DDT2000 de **février 2021**. Les modèles sortis
> **après 2021** n'y figurent pas.

## PID perso à code partagé

Quand plusieurs PID perso lisent la même réponse (ex. un bloc `21 01` dont on extrait
plusieurs octets), Torque envoie la même clé `k2101` une fois par PID. L'intégration les
sépare dans l'ordre de leurs **noms courts** (*ShortName* du CSV Torque) : chaque valeur
devient `k2101_<nomcourt>` en minuscules, sans espaces ni symboles.
Si seuls certains de ces PID sont cochés pour l'envoi, Torque transmet quand même les noms
de tous : les valeurs reçues sont associées aux premiers noms, dans l'ordre.

```yaml
# PID Torque : ShortName "OilTemp" et "Boost", ModeAndPID 2101
k2101_oiltemp:
  name: Température huile
  unit: °C
  device_class: temperature
  state_class: measurement
k2101_boost:
  name: Pression suralimentation
  unit: mbar
  device_class: pressure
  state_class: measurement
```

Le journal HA indique au début du trajet si la séparation a réussi
(`k2101 reçu N fois -> séparé en …`) ou si Torque n'a envoyé qu'une valeur.
Astuce : fermer puis relancer Torque avant le trajet pour qu'il renvoie les noms.

## Dépannage
- Journal HA : rechercher `torque_obd` (Paramètres → Système → Journaux)
- Aucune donnée : vérifier l'URL dans Torque et que le profil porte le nom du véhicule
- Rafraîchissement lent : réduire le nombre de PID dans « Sélectionner quoi surveiller »
- Diagnostics : Paramètres → Appareils et services → *Torque OBD-II* → ⋮ du véhicule → *Télécharger les diagnostics*

---

## English

Custom Home Assistant integration receiving OBD-II data from the **Torque Pro** Android app.

**Features**: one device per vehicle (`/api/torque-<vehicle-name>`), several vehicles on one
phone (routed by Torque profile name), per-vehicle ignored PIDs, splitting of custom PIDs
sharing the same request (e.g. `2101` → `k2101_<shortname>`), GPS `device_tracker`,
ready-made Torque PID files per manufacturer — Renault, Dacia, Nissan, Lada, others (`torque_pids`, from the Renault DDT2000 database of February 2021; later models are not included),
"Torque connected" binary sensor, diagnostics, custom definitions in
`/config/torque_sensor_definitions.yaml`.

**Install**: HACS → Custom repositories → `https://github.com/Marlboro62/Home-Assistant-Torque-OBDII-2027`
(category *Integration*), install, restart. Enable beta versions for pre-releases.

**Setup**: add the *Torque OBD-II* integration, use the exact Torque profile name as vehicle
name, then in Torque Pro → Settings → Data Logging & Upload set the web server URL to
`http://<ha-ip>:8123/api/torque-<vehicle-name>` and leave the email empty.

---

## Crédits
- Base : [JOHLC/Home-Assistant-Torque-OBDII](https://github.com/JOHLC/Home-Assistant-Torque-OBDII)
- Torque Pro : Ian Hawkins

## Licence
MIT — voir [`LICENSE`](LICENSE) (licence du projet d'origine conservée, © JOHLC).

## Soutenir
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/marlboro62)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/nothing_one)
