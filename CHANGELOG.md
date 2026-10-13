# Changelog

Numérotation : `AAAA.M.x` (stable) et `AAAA.M.xbN` (pré-version / pre-release).

## 2027.1.2

- Icône de l'intégration (`brand/icon.png`, versions claire et sombre) : l'icône s'affiche
  dans Home Assistant et HACS au lieu de « icon not available ».
- Validation HACS complète, sans exception (préparation à l'inclusion dans HACS par défaut).

## 2027.1.1 — version stable

- Première version stable (contenu de 2027.1.0b0).
- **Nouveau dossier `torque_pids/`** : PID Torque constructeur classés par marque
  (`renault`, `dacia`, `nissan`, `lada`, `autre`), en CAN et en ligne K, avec les fichiers de
  définitions Home Assistant. Source : base Renault DDT2000 de février 2021 — les modèles
  sortis après 2021 n'y figurent pas.

## 2027.1.0b0 — pré-version

Reprise complète de l'intégration (base JOHLC/Home-Assistant-Torque-OBDII).

### Nouveautés
- **Plusieurs véhicules sur un même téléphone** : aiguillage automatique selon le nom du profil Torque
  (`profileName`), avec apprentissage des identifiants numériques et alias modifiables dans les options.
- **PID à ignorer par véhicule** (options) : supprime les entités d'un PID d'une autre voiture
  (ex. `k2101, k2174`) et filtre ses valeurs.
- **PID perso à code partagé** (ex. bloc KWP `21 01`) : quand Torque envoie plusieurs fois la même clé,
  les valeurs sont séparées dans l'ordre des noms courts (`k2101_<nomcourt>`) et deviennent des
  capteurs distincts. Message dans le journal HA indiquant si la séparation a réussi.
- **Noms des capteurs en français**.
- `device_tracker` (position GPS), `binary_sensor` « Torque connecté », diagnostics.
- Tension affichée avec 2 décimales par défaut, filtrage des valeurs hors plage.

### Corrections
- Clés répétées dans la requête Torque : plus de perte silencieuse des valeurs.
- Métadonnées (`profileName`, `session`, `id`, `eml`) protégées si Torque les répète.

