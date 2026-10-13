# PID Torque — Nissan

> ℹ️ Base DDT2000 de **février 2021** : les modèles sortis après 2021 n'y figurent pas.
> La base ne couvre que les Nissan partageant l'électronique Renault (Micra, Note, Juke,
> Qashqai, X-Trail, Navara, Leaf…). ⚠️ Formules non testées sur chaque véhicule.

| Moteur | Fichiers |
|---|---|
| **Moteur Nissan** (HR / MR / QR, calculateur Hitachi) | `Nissan_1_CAN_moteur_Nissan` |
| **Moteur Renault** (1.5 dCi K9K, 1.2 / 1.3 TCe, 1.6 dCi…) | `Nissan_2_CAN_commun_moteur_Renault` + `Nissan_3_CAN_essence_moteur_Renault` ou `Nissan_4_CAN_diesel_moteur_Renault` |

En-tête `7E0`. Sur les modèles récents en CAN 29 bits, essayer `DA10F1` si rien ne répond.
