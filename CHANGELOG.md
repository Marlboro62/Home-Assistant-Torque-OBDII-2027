# Changelog

Numérotation : `AAAA.M.x` (stable) et `AAAA.M.xbN` (pré-version / pre-release).

## 2027.2.1b3

- **Accéléromètre** : les axes X/Y/Z et le total s'affichaient arrondis à l'entier (`-1 g`, `0 g`),
  car l'unité `g` (grammes) est réglée à 0 décimale. Ils sont maintenant affichés avec 2 décimales.

## 2027.2.1b2

- Début de trajet manqué : véhicule reconnu à ses PID propres (voir 2027.2.1b1).

## 2027.2.1b1

- **Trajet en cours au redémarrage de Home Assistant** : Torque n'envoie le nom du profil (le véhicule)
  qu'au démarrage du trajet. Après un redémarrage de HA en cours de route, un téléphone à plusieurs
  profils voyait le reste du trajet ignoré, avec la notification « profil non reconnu : **(inconnu)** ».
  L'association session → véhicule est maintenant enregistrée (`.storage/torque_obd.sessions`, écrite à
  l'arrêt de HA, gardée 6 h) : le trajet continue sur le bon véhicule.
- Si le début du trajet n'a vraiment pas été reçu (pas de réseau au démarrage, par exemple), la
  notification s'intitule **« début de trajet manqué »** et explique la cause, au lieu de parler d'un
  profil inconnu. Les données restent ignorées pour ne pas mélanger deux véhicules.
- **Début de trajet manqué** (HA arrêté quand le trajet démarre, cas du 04/11) : le véhicule est
  reconnu à ses **PID propres** (PID perso qu'aucun autre véhicule n'a, ex. les PID Laguna). Les PID
  communs (GPS, accéléromètre, PID standard) ne comptent pas : sans PID propre, rien n'est deviné.
- Tests : session conservée au redémarrage, notification sans nom de profil, véhicule reconnu à ses PID.

## 2027.2.0

Version stable : reprend la pré-version 2027.2.0b1 (webhook privé par véhicule, diagnostics masqués), testée sur une installation réelle (migration de deux véhicules, avertissements dans les Réparations, affichage de l'adresse, nouvelles adresses saisies dans Torque Pro).

## 2027.2.0b1

Sécurité (revue HACS) : **l'adresse d'envoi devient un webhook privé**.

- ⚠️ **Changement à faire dans Torque Pro** : l'ancienne adresse `/api/torque-<véhicule>` ne demandait
  aucune authentification. Quiconque pouvait joindre Home Assistant pouvait déplacer le
  `device_tracker` du véhicule, écrire n'importe quelle valeur de capteur, créer des entités, modifier
  les options enregistrées ou publier des notifications. Elle est **supprimée**.
- Chaque véhicule reçoit un **webhook Home Assistant à identifiant aléatoire** (`webhook.async_generate_id`).
  L'adresse complète s'affiche à la fin de l'ajout du véhicule, puis dans ses options
  (**Adresse à saisir dans Torque Pro**). Option **Créer une nouvelle adresse** si elle a fuité.
- **Migration automatique** des véhicules existants (version 1 → 2) : adresse privée créée et
  avertissement dans **Paramètres → Réparations**, qui disparaît une fois l'adresse affichée.
- L'entité « URL Torque » est **supprimée** : elle exposait l'adresse à tous les utilisateurs.
- **Diagnostics** : les options passent aussi par `async_redact_data` ; `routed_devices` (identifiants
  Torque des téléphones) et l'identifiant du webhook sont masqués.
- Tests : réception GET et POST par webhook, ancienne adresse supprimée, migration, nouvelle adresse,
  aucune adresse dans les entités, diagnostics masqués.

## 2027.1.8b1

- Journal : le message « N PID perso partagent le code … mais Torque n'envoie qu'UNE valeur.
  Séparation impossible » n'est plus un avertissement. Ce cas est sans conséquence (la valeur
  reste sur sa clé d'origine) : il est noté en information, avec les noms des PID concernés
  et la marche à suivre (cocher tous ces PID pour l'envoi, ou supprimer le doublon dans Torque).

## 2027.1.7

Version stable : reprend la pré-version 2027.1.7b1, testée sur une installation réelle (import des
définitions YAML d'un véhicule, modification d'une unité appliquée sans redémarrage).

## 2027.1.7b1

- Nouveau : **définitions des capteurs éditables dans Home Assistant**, par véhicule. Le menu des
  options (roue dentée) propose :
  - **Ajouter ou modifier la définition d'un capteur** : choix du PID dans la liste de ceux reçus
    (avec leur dernière valeur), puis nom, unité, icône, classes, min / max et décimales ;
  - **Supprimer des définitions** : le capteur reprend la définition commune ;
  - **Importer** depuis `torque_sensor_definitions.yaml` (tout, ou seulement les PID reçus du véhicule) ;
  - **Exporter** dans `/config/torque_sensor_definitions_<véhicule>.yaml`.
- Les définitions d'un véhicule priment sur le fichier YAML, qui reste lu comme avant.
- Une définition modifiée recharge le véhicule : **plus besoin de redémarrer Home Assistant**.
  Les noms appris et les autres options ne déclenchent pas de rechargement.
- Tests automatiques du formulaire d'options et des définitions (`tests/`), lancés par la CI.

## 2027.1.6

- Décimales par défaut ajoutées pour d'autres unités courantes des PID perso :
  N·m, W, kg/h, ms, µs, °vil, mg/cp (ex. « 1,21875 N·m » devient « 1 N·m »).

## 2027.1.5

- Correction : séparation des PID perso à code partagé quand seuls certains sont envoyés.
  Torque transmet les noms de tous les PID du code (ex. 44 PID `21 01`) mais seulement les
  valeurs des PID sélectionnés (ex. 15), dans le même ordre : les valeurs sont désormais
  associées aux premiers noms au lieu de rester non séparées.
- Clés répétées avec des valeurs identiques (ex. GPS `kff1005`) : plus d'avertissement dans le journal.

## 2027.1.4

- Correction : latitude et longitude GPS de nouveau affichées avec 6 décimales
  (la 2027.1.3 les arrondissait à 1 décimale, par exemple 49,4°). Cap GPS sans décimale.

## 2027.1.3

- Nombre de décimales affichées par défaut selon l'unité (%, L/h, kW, km, s…) :
  fini les valeurs du type « 27,4509803921569 % ». Le coût du trajet s'affiche avec 2 décimales.
- Une clé `precision` dans `torque_sensor_definitions.yaml` reste prioritaire, tout comme
  le réglage d'affichage choisi dans les paramètres d'une entité.

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

