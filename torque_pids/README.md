# PID Torque par constructeur

Fichiers CSV à importer dans **Torque Pro** pour lire les données constructeur (au-delà des
PID OBD standard), avec pour chaque dossier le fichier de définitions Home Assistant
(noms, unités, icônes).

| Dossier | Constructeur |
|---|---|
| [`renault`](renault) | Renault |
| [`dacia`](dacia) | Dacia |
| [`nissan`](nissan) | Nissan |
| [`lada`](lada) | Lada |
| [`autre`](autre) | Alpine, Mercedes Citan (Daimler), Renault Samsung |

> ℹ️ **Source : base de diagnostic Renault DDT2000 datée de février 2021.**
> Les modèles sortis **après 2021** (ex. Dacia Jogger, nouveau Duster, Renault Austral,
> Mégane E-Tech…) **ne figurent pas** dans cette base : leurs calculateurs peuvent ne pas
> répondre ou répondre avec d'autres formules.

> ⚠️ Formules extraites des fichiers officiels des calculateurs, **non testées sur chaque
> véhicule**. Toujours comparer les premières valeurs (régime, température…) avec le
> tableau de bord.

## Principe

- **CAN (environ 2008 / 2012 →)** : codes de lecture `22xxxx` communs à la plupart des
  calculateurs moteur Renault / Dacia / Nissan / Lada récents. En-tête `7E0`.
  Fichier « commun » + fichier « essence » ou « diesel » selon le moteur.
- **Ligne K (avant ~2008 / 2012)** : blocs `21xx` propres à chaque famille de calculateur
  (Siemens, Sagem, Delphi, Bosch). Plusieurs valeurs par bloc : l'intégration les sépare
  (`k21a0_<nomcourt>`). En-tête vide.
- Calculateurs récents en CAN 29 bits (modèles 2018 →) : si rien ne répond avec `7E0`,
  essayer l'en-tête `DA10F1` (protocole ISO 15765-4 CAN 29 bits).

## Installation

1. Copier le CSV dans *Téléchargements* sur le téléphone
2. Torque → Réglages → *Gérer les PIDs/Sondes supplémentaires* → ⋮ → *Importer*
3. Cocher les PID voulus dans *Enregistrement et envoi de données → Sélectionner quoi surveiller*
   (le moins possible, surtout en ligne K : chaque PID ralentit le rafraîchissement)
4. Copier le contenu du `torque_sensor_definitions_<dossier>.yaml` dans
   `/config/torque_sensor_definitions.yaml`, puis redémarrer Home Assistant
