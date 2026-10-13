# PID Torque — Renault

> ℹ️ Base DDT2000 de **février 2021** : les modèles sortis après 2021 n'y figurent pas.
> ⚠️ Formules non testées sur chaque véhicule — vérifier les valeurs avant de s'y fier.

## Quel fichier pour quel moteur ?

| Type | Exemples de modèles | Fichiers |
|---|---|---|
| **CAN, essence** (≈ 2008 →) | Clio III/IV/V, Captur, Mégane III/IV, Scénic, Kangoo II, Twingo II/III, Fluence | `Renault_1_CAN_commun` + `Renault_2_CAN_essence` |
| **CAN, diesel dCi** | idem + Trafic III, Master III, Espace V, Talisman | `Renault_1_CAN_commun` + `Renault_3_CAN_diesel` |
| **CAN, essence « Hitachi »** (moteurs d'origine Nissan) | Koleos II, Kadjar, Talisman / Espace V 1.6 – 2.0 essence | `Renault_4_CAN_essence_Hitachi` |
| **Ligne K, essence Siemens** (Sirius / SIM32) | Clio II, Twingo I, Kangoo I, Mégane I/II, Thalia | `Renault_5_Kline_essence_Siemens` |
| **Ligne K, essence Sagem** (S2000 / S3000) | Clio II, Twingo I/II, Kangoo I, Mégane II 1.4 / 1.6 | `Renault_6_Kline_essence_Sagem` |
| **Ligne K, diesel Delphi** (DCM1.2 / DDCR, K9K) | Clio II/III, Kangoo, Mégane II, Modus 1.5 dCi | `Renault_7_Kline_diesel_Delphi` |
| **Ligne K, diesel Bosch** (EDC15 / EDC16) | Laguna II, Mégane II, Espace IV, Trafic II, Master II 1.9 / 2.0 / 2.2 / 2.5 dCi | `Renault_8_Kline_diesel_Bosch` |

Pour savoir quel calculateur équipe la voiture : DDT4all → choisir le projet du véhicule →
*Scanner* : le nom du calculateur moteur (EMS, Sirius, SIM32, S3000, DCM, EDC…) s'affiche.

## Contenu

- **CAN commun** : régime, vitesse, températures eau / huile / carburant / air, batterie,
  pressions atmosphérique et collecteur, couple, pédale, consigne ralenti, kilométrage, alternateur
- **CAN essence** : papillon, avance, temps d'injection, sondes O2, débit d'air, suralimentation (TCe), ratés cylindres 1–4
- **CAN diesel** : suralimentation + consigne, rail + consigne, débits, vanne EGR, FAP (suies, pression différentielle, régénération), température avant catalyseur
- **CAN Hitachi** : régime, vitesse, eau, huile, air, batterie, avance, injection, débit d'air, sonde O2 aval, correction de richesse, consigne ralenti
- **Ligne K** : régime, vitesse, températures, batterie, pression collecteur / suralimentation, sondes O2, avance, injection, rail (diesel) selon la famille
