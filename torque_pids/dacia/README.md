# PID Torque — Dacia

PID constructeur (Renault / Dacia) à importer dans Torque Pro, extraits de la base de
diagnostic Renault DDT2000 (février 2021). Ils complètent les PID OBD standard.

> ⚠️ Formules issues des fichiers officiels des calculateurs, **non testées sur chaque
> véhicule**. Une version de calculateur peut différer : vérifier les valeurs (régime,
> température…) contre le tableau de bord avant de s'y fier.

## Quel fichier pour quelle Dacia ?

| Génération | Modèles | Moteur | Fichiers |
|---|---|---|---|
| **2ᵉ génération (2012 →)** — CAN | Logan II, Sandero II / III, Duster I ph2 / II, Dokker, Lodgy, Jogger | Essence 1.2 16V, SCe, TCe | `Dacia_1_CAN_commun` + `Dacia_2_CAN_essence` |
| | | Diesel 1.5 dCi (K9K) | `Dacia_1_CAN_commun` + `Dacia_3_CAN_diesel` |
| **1ʳᵉ génération (2004 → 2012)** — ligne K | Logan I, Sandero I, Duster I ph1 | Essence 1.4 / 1.6 8V (K7J/K7M), 1.6 16V (K4M) — Siemens Sirius 32/34 | `Dacia_4_Kline_essence_Sirius` |
| | | Diesel 1.5 dCi (K9K) — Delphi DCM1.2 | `Dacia_5_Kline_diesel_DCM12` |

Si une 1ʳᵉ génération récente ne répond pas avec le fichier ligne K, essayer les fichiers CAN
(certaines fins de série sont déjà en CAN).

## Contenu

| Fichier | PID |
|---|---|
| `Dacia_1_CAN_commun` | régime, vitesse, températures eau / huile / carburant / air, batterie, pressions atmosphérique et collecteur, couple, pédale, consigne ralenti, kilométrage, alternateur |
| `Dacia_2_CAN_essence` | papillon, avance, temps d'injection, sondes O2 amont / aval, débit d'air, suralimentation (TCe), ratés cylindres 1–4 |
| `Dacia_3_CAN_diesel` | suralimentation + consigne, pression rail + consigne, débits air / carburant, vanne EGR, FAP (suies, pression différentielle, régénération), température avant catalyseur |
| `Dacia_4_Kline_essence_Sirius` | régime, vitesse, eau, air, batterie, collecteur, sondes O2, avance, correction cliquetis, temps d'injection, richesse |
| `Dacia_5_Kline_diesel_DCM12` | régime, vitesse, eau, charge, suralimentation, atmosphérique, rail, batterie, air, carburant, pédale, débit injecté |

En-tête : `7E0` pour les fichiers CAN ; vide pour la ligne K (calculateur moteur par défaut).

## Installation

1. Copier le CSV dans *Téléchargements* sur le téléphone
2. Torque → Réglages → *Gérer les PIDs/Sondes supplémentaires* → ⋮ → *Importer* → choisir le fichier
3. Cocher les nouveaux PID dans *Enregistrement et envoi de données → Sélectionner quoi surveiller*
   (le moins possible : chaque PID ralentit le rafraîchissement, surtout en ligne K)

## Noms et unités dans Home Assistant

Copier le contenu de `torque_sensor_definitions_dacia.yaml` dans
`/config/torque_sensor_definitions.yaml`, puis redémarrer HA.

Les fichiers ligne K lisent plusieurs valeurs dans un même bloc (`21A9`, `21A0`…) :
l'intégration les sépare d'après le *ShortName* (`k21a9_rpm`, `k21a0_boost`…).
Fermer puis relancer Torque avant un trajet pour qu'il renvoie les noms.
