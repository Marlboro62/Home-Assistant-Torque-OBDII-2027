# Torque OBD-II pour Home Assistant

Intégration personnalisée qui reçoit les données OBD-II envoyées par l'application Android
[Torque Pro](https://torque-bhp.com/) et les transforme en capteurs Home Assistant
(un appareil par véhicule).

> Version retravaillée et étendue de [JOHLC/Home-Assistant-Torque-OBDII](https://github.com/JOHLC/Home-Assistant-Torque-OBDII).

## Fonctionnalités

- Un appareil par véhicule, avec sa propre URL : `/api/torque-<nom-du-vehicule>`
- **Plusieurs voitures sur un même téléphone** : le véhicule est choisi selon le profil Torque
- **PID à ignorer** par véhicule (options de l'intégration)
- **PID perso à code partagé** (ex. bloc `21 01`) séparés en capteurs distincts
- Position GPS (`device_tracker`), état « Torque connecté », diagnostics
- Définitions de capteurs personnalisables via `/config/torque_sensor_definitions.yaml`

## Installation

### HACS (recommandé)
1. HACS → ⋮ → **Dépôts personnalisés**
2. URL : `https://github.com/Marlboro62/Home-Assistant-Torque-OBDII-2027` — catégorie **Intégration**
3. Installer **Torque OBD-II**, puis redémarrer Home Assistant
4. Pour les pré-versions (`…b0`) : activer « Afficher les versions bêta » dans HACS

### Manuelle
Copier `custom_components/torque_obd` dans `/config/custom_components/`, puis redémarrer.

## Configuration

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
Noms, unités et icônes de vos PID perso (mode 21/22…) : copier
`custom_components/torque_obd/torque_sensor_definitions.yaml.example` vers
`/config/torque_sensor_definitions.yaml`, l'adapter, puis redémarrer HA.

## PID perso à code partagé
Si plusieurs PID perso utilisent la même requête (ex. `2101`), Torque envoie la même clé
plusieurs fois. L'intégration les sépare dans l'ordre de leurs noms courts : la clé devient
`k2101_<nomcourt>` (ex. `k2101_oiltemp`), utilisable dans le fichier de définitions.

## Dépannage
- Journal HA : rechercher `torque_obd` (Paramètres → Système → Journaux)
- Aucune donnée : vérifier l'URL dans Torque et que le profil porte le nom du véhicule
- Diagnostics : page de l'appareil → ⋮ → *Télécharger les diagnostics*

## Crédits
- Base : [JOHLC/Home-Assistant-Torque-OBDII](https://github.com/JOHLC/Home-Assistant-Torque-OBDII)
- Torque Pro : Ian Hawkins

## Licence
MIT — voir `LICENSE` (licence du projet d'origine conservée, © JOHLC).

## Soutenir
[Buy Me a Coffee](https://buymeacoffee.com/marlboro62) · [Ko-fi](https://ko-fi.com/nothing_one)
