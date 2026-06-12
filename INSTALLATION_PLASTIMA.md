

1. [Prérequis](#1-prérequis)
2. [Étape 1 — Installer WSL2](#étape-1--installer-wsl2)
3. [Étape 2 — Installer Docker Desktop](#étape-2--installer-docker-desktop)
4. [Étape 3 — Configurer Docker Desktop](#étape-3--configurer-docker-desktop)
5. [Étape 4 — Décompresser le projet](#étape-4--décompresser-le-projet)
6. [Étape 5 — Configurer le fichier `.env`](#étape-5--configurer-le-fichier-env)
7. [Étape 6 — Premier démarrage Docker](#étape-6--premier-démarrage-docker)
8. [Étape 7 — Vérifier que tout fonctionne](#étape-7--vérifier-que-tout-fonctionne)
9. [Étape 8 — Connexion à l'application](#étape-8--connexion-à-lapplication)
10. [Étape 9 — Configurer la sauvegarde automatique hebdomadaire](#étape-9--configurer-la-sauvegarde-automatique-hebdomadaire)
11. [Étape 10 — Démarrage automatique au boot Windows](#étape-10--démarrage-automatique-au-boot-windows)
12. [Utilisation au quotidien](#utilisation-au-quotidien)
13. [Restaurer une sauvegarde](#restaurer-une-sauvegarde)
14. [Dépannage](#dépannage)

---

## 1. Prérequis

Avant de commencer l'installation, vérifier que le PC satisfait ces conditions :

| Élément | Minimum |
|---|---|
| Système d'exploitation | Windows 10 (build 19044+) ou Windows 11 |
| Architecture | 64 bits |
| Mémoire RAM | 8 Go (16 Go recommandés) |
| Espace disque libre | 80 Go |
| Connexion Internet | Stable, débit décent (les téléchargements totalisent environ 1,5 Go) |
| Droits administrateur | Oui, pour l'installation de WSL2 et Docker |

Fichiers fournis par le développeur :

- L'archive ZIP **`legaleye_livraison.zip`** (environ 400 Mo)

- Ce guide **`INSTALLATION_PLASTIMA.md`**

---

## Étape 1 — Installer WSL2

**WSL2** (Windows Subsystem for Linux) est une couche Linux intégrée à Windows. Docker en a besoin pour faire tourner les conteneurs. Il s'installe en une seule commande.

### Procédure

1. Faire **clic droit sur le menu Démarrer** (icône Windows en bas à gauche)
2. Choisir **« Terminal (administrateur) »** ou **« Windows PowerShell (admin) »**
3. Valider l'invite « Voulez-vous autoriser cette application... » par **Oui**
4. Dans la fenêtre PowerShell, taper :

```powershell
wsl --install
```

5. Attendre la fin du téléchargement et de l'installation (3 à 5 minutes)
6. **Redémarrer le PC** quand demandé

> **Note** : après le redémarrage, une fenêtre Ubuntu peut s'ouvrir automatiquement et demander un nom d'utilisateur Linux. **Ne pas la remplir, la fermer.** L'installation ne nécessite pas la création d'un compte utilisateur Linux.

### Vérification

Après le redémarrage, ouvrir PowerShell (sans privilèges admin cette fois) et taper :

```powershell
wsl --status
```

Le résultat doit afficher quelque chose comme :

```
Version WSL par défaut : 2
Kernel version : 5.x.x
```

Si la commande répond, **passer à l'étape 2**.

---

## Étape 2 — Installer Docker Desktop

### Téléchargement

1. Ouvrir un navigateur (Chrome, Edge, Firefox)
2. Aller sur : **https://www.docker.com/products/docker-desktop/**
3. Cliquer sur **« Download for Windows »**
4. Sauvegarder `Docker Desktop Installer.exe` (environ 600 Mo)

### Installation

1. Double-cliquer sur **`Docker Desktop Installer.exe`**
2. Sur l'écran de configuration, cocher :
   - ✅ **« Use WSL 2 instead of Hyper-V »**
   - ✅ **« Add shortcut to desktop »**
3. Cliquer **« OK »**
4. Attendre la fin de l'installation (5 à 10 minutes)
5. **Redémarrer le PC** quand demandé

### Premier lancement

1. Double-cliquer sur l'icône **Docker Desktop** sur le bureau
2. Accepter la licence (gratuite pour usage commercial < 250 employés)
3. Cliquer **« Skip »** lorsqu'un compte Docker est proposé (facultatif)
4. Attendre que la **baleine** apparaisse dans la barre des tâches en bas à droite
5. Quand la baleine devient **fixe (non animée)**, Docker est prêt

---

## Étape 3 — Configurer Docker Desktop

Cette étape réserve assez de mémoire pour les conteneurs et le pipeline de machine learning.

1. Clic sur l'icône **Docker Desktop** (baleine)
2. Cliquer sur **⚙️ Settings** (engrenage en haut à droite)
3. Aller dans **Resources → Advanced**
4. Régler :
   - **CPUs** : 4 minimum
   - **Memory** : **6 Go minimum** (8 Go conseillé)
   - **Disk image size** : 80 Go minimum
5. Cliquer **« Apply & Restart »**
6. Aller dans **General**
7. Cocher **« Start Docker Desktop when you log in »**
8. Cliquer **« Apply & Restart »**

> Le démarrage automatique au login Windows est important : si le PC redémarre, Docker se relance tout seul et l'application LegalEye redevient accessible sans intervention.

---

## Étape 4 — Décompresser le projet

### Créer le dossier de destination

Ouvrir PowerShell (non-admin) et taper :

```powershell
mkdir C:\Apps
```

### Transférer le ZIP

Copier le fichier **`legaleye_livraison.zip`** (fourni par le développeur, sur clé USB ou OneDrive) dans `C:\` à la racine du disque.

### Décompresser

Dans PowerShell, taper :

```powershell
Expand-Archive -Path "C:\legaleye_livraison.zip" -DestinationPath "C:\Apps\"
```

Cela crée le dossier **`C:\Apps\legaleye\`** avec tout le projet à l'intérieur.

### Vérifier

```powershell
cd C:\Apps\legaleye
dir
```

On doit voir au minimum les éléments suivants :

```
backend/
frontend/
ml/
modeles/
scraping/
scripts/
database/
docker-compose.yml
.env.example
README.md
```

> **Important** : le chemin doit être **exactement** `C:\Apps\legaleye\` sans accent ni espace. Ne pas placer le projet dans un dossier au nom contenant des caractères spéciaux.

---

## Étape 5 — Configurer le fichier `.env`

Le fichier `.env` contient les mots de passe de la base et la clé de sécurité. **Ce fichier est sensible et ne doit jamais être partagé.**

### Créer le fichier `.env` à partir du template

Dans PowerShell, depuis `C:\Apps\legaleye` :

```powershell
copy .env.example .env
notepad .env
```

Notepad s'ouvre avec le fichier `.env`. Effacer tout son contenu (Ctrl+A, Suppr) et coller le contenu fourni par le développeur (déjà préparé avec les mots de passe finaux). Ce contenu ressemble à :

```dotenv
# Base de données MySQL
DB_USER=legaleye
DB_PASSWORD=<mot de passe fort fourni par le développeur>
DB_HOST=db
DB_PORT=3306
DB_NAME=bo_watch

MYSQL_DATABASE=bo_watch
MYSQL_USER=legaleye
MYSQL_PASSWORD=<même valeur que DB_PASSWORD>
MYSQL_ROOT_PASSWORD=<autre mot de passe fort>

# Sécurité JWT
SECRET_KEY=<chaîne aléatoire de 64 caractères>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Frontend
FRONTEND_URL=http://localhost

# Modèles ML
SEUIL_SIMILARITE=0.80

# Environnement
ENV=production
DEBUG=false

# Scraping
SCRAPER_ENABLED=true
CONTACT_EMAIL=contact@plastima.ma
MAX_ESSAIS_VIDES=10
DELAI_ENTRE_REQUETES=1.0

# Logs et timezone
LOG_LEVEL=INFO
TZ=Africa/Casablanca
```

Sauvegarder avec **Ctrl+S**, puis fermer Notepad.

> **Sécurité** : ces mots de passe ne seront jamais à taper par l'utilisateur Plastima. Ils sont lus automatiquement par Docker. Le seul mot de passe à mémoriser est celui du compte `admin@plastima.ma` qui sert à se connecter à l'application.

---

## Étape 6 — Premier démarrage Docker

Cette étape construit les conteneurs et lance le système. **Compter 15 à 20 minutes** pour la première fois (téléchargement des images Docker et build des composants).

Depuis `C:\Apps\legaleye` :

```powershell
docker compose up -d --build
```

Pendant l'attente, Docker effectue ces opérations en arrière-plan :

1. Téléchargement de l'image MySQL 9.1
2. Téléchargement de l'image Python 3.11
3. Téléchargement de l'image Node.js et Nginx
4. Compilation du frontend React (npm install + npm run build)
5. Installation des dépendances Python (FastAPI, PyTorch CPU, Transformers, scikit-learn, etc.)
6. Copie des modèles de machine learning dans l'image
7. Démarrage des trois conteneurs
8. Import automatique des données de démonstration (685 partenaires + utilisateurs)



## Étape 7 — Vérifier que tout fonctionne

### Vérifier l'état des conteneurs

```powershell
docker compose ps
```

Le résultat doit montrer **trois conteneurs** avec le statut **`Up X minutes (healthy)`** :

```
NAME                STATUS                  PORTS
legaleye-db         Up X minutes (healthy)  3306/tcp
legaleye-backend    Up X minutes (healthy)  8000/tcp
legaleye-frontend   Up X minutes (healthy)  0.0.0.0:80->80/tcp
```



### Vérifier les données importées

```powershell
docker compose exec db mysql -u root -p<MYSQL_ROOT_PASSWORD> bo_watch -e "SELECT COUNT(*) AS partenaires FROM tier; SELECT COUNT(*) AS utilisateurs FROM user;"
```

Remplacer `<MYSQL_ROOT_PASSWORD>` par la valeur du `.env`. Le résultat doit afficher environ **685 partenaires** et **3 utilisateurs**.


## Étape 8 — Connexion à l'application

1. Ouvrir un navigateur (Chrome, Edge, Firefox) sur **http://localhost**
2. La page de **connexion LegalEye** s'affiche
3. Se connecter avec les identifiants figurant sur la **carte de connexion** fournie par le développeur :

```
Email    : admin@plastima.ma
Mot de passe : <mot de passe fourni>
```

4. Le **tableau de bord** s'ouvre avec les KPIs et la liste des alertes
5. **Changer le mot de passe** à la première connexion via le menu profil

### Tests fonctionnels rapides

Vérifier ces six fonctions :

| Test | Résultat attendu |
|---|---|
| Login | Dashboard s'affiche |
| Menu Alertes → cliquer sur une alerte | La capture annotée du PDF s'affiche dans la page de détail |
| Bouton « Vérifier sur DirectInfo » | Ouvre directinfo.ma dans un nouvel onglet |
| Menu Bulletins | Liste des bulletins traités s'affiche |
| Menu Tiers (partenaires) | Liste des 685 partenaires |
| Dashboard → Exporter un rapport PDF | Téléchargement d'un PDF aux couleurs Heritage |

Si les six tests passent, **le système est opérationnel**.

---

## Étape 9 — Configurer la sauvegarde automatique hebdomadaire

Pour protéger la base de données contre une perte (panne disque, ransomware, fausse manipulation), un script PowerShell réalise une sauvegarde **chaque dimanche soir à 22h00**. Les sauvegardes sont conservées pendant **6 mois** (182 jours) puis supprimées automatiquement.

### 9.1 — Tester le script manuellement

Avant d'automatiser, vérifier que le script fonctionne :

```powershell
cd C:\Apps\legaleye
powershell -ExecutionPolicy Bypass -File .\scripts\backup_legaleye.ps1
```

Le résultat attendu :

```
Sauvegarde hebdomadaire -> C:\Apps\legaleye\backups\legaleye_2026_sem23_20260605_143022.sql.gz
[OK] Sauvegarde : C:\Apps\legaleye\backups\legaleye_2026_sem23_20260605_143022.sql.gz (1,23 Mo)
[OK] Semaine 23 de 2026

Sauvegardes conservees : 1
Espace total           : 1,23 Mo
Retention              : 182 jours (~26 semaines)
```

Vérifier qu'un fichier `.sql.gz` est apparu dans `C:\Apps\legaleye\backups\`.

### 9.2 — Créer la tâche planifiée Windows

#### Ouvrir le Planificateur de tâches

Trois méthodes possibles :

| Méthode | Action |
|---|---|
| Raccourci clavier | Touche Windows + R → taper `taskschd.msc` → Entrée |
| Recherche | Touche Windows → taper `planificateur` → cliquer sur le résultat |
| PowerShell | Taper `taskschd.msc` puis Entrée |

#### Créer la tâche

1. Dans la fenêtre du Planificateur, clic sur **« Bibliothèque du Planificateur de tâches »** à gauche
2. Dans le **volet droit (Actions)**, cliquer sur **« Créer une tâche... »** (pas « Tâche de base »)

#### Onglet **Général**

| Champ | Valeur |
|---|---|
| Nom | `LegalEye - Sauvegarde hebdomadaire` |
| Description | `Sauvegarde automatique de la base MySQL chaque dimanche soir` |
| Cocher | ✅ « Exécuter même si l'utilisateur n'est pas connecté » |
| Cocher | ✅ « Exécuter avec les autorisations maximales » |
| Configurer pour | Windows 10 (ou Windows 11 selon l'OS) |

#### Onglet **Déclencheurs** → Bouton **« Nouveau... »**

| Champ | Valeur |
|---|---|
| Commencer la tâche | **Selon une planification** |
| Type de planification | **Hebdomadaire** |
| Démarrer le | (date du prochain dimanche) |
| Heure | **22:00:00** |
| Toutes les | **1 semaine(s)** |
| Jours | Cocher uniquement **Dimanche** |
| Cocher | ✅ Activé |

Cliquer **OK**.

#### Onglet **Actions** → Bouton **« Nouveau... »**

| Champ | Valeur |
|---|---|
| Action | **Démarrer un programme** |
| Programme/script | `powershell.exe` |
| Ajouter des arguments | `-ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Apps\legaleye\scripts\backup_legaleye.ps1"` |
| Commencer dans | `C:\Apps\legaleye` |

Cliquer **OK**.

#### Onglet **Conditions**

| Option | État |
|---|---|
| Démarrer uniquement si l'ordinateur est sur secteur | ❌ Décocher (utile sur portable) |
| Sortir l'ordinateur du mode veille pour exécuter cette tâche | ✅ Cocher |

#### Onglet **Paramètres**

| Option | État |
|---|---|
| Exécuter la tâche dès que possible si un démarrage planifié est manqué | ✅ Cocher |
| Si la tâche échoue, redémarrer toutes les 1 heure (3 tentatives) | ✅ Cocher |

Cliquer **OK** pour valider la création. Windows demande le mot de passe du compte utilisateur. Le saisir.

### 9.3 — Tester la tâche immédiatement

1. Dans la liste des tâches, repérer **« LegalEye - Sauvegarde hebdomadaire »**
2. **Clic droit** dessus → **« Exécuter »**
3. Quelques secondes plus tard, vérifier qu'un fichier `.sql.gz` est apparu dans `C:\Apps\legaleye\backups\`
4. Si oui, **la sauvegarde automatique est opérationnelle**

### 9.4 — Comprendre la rétention

À tout moment, le dossier `C:\Apps\legaleye\backups\` contient au maximum **26 sauvegardes** (une par semaine sur les 6 derniers mois). Les sauvegardes plus anciennes sont supprimées automatiquement par le script à chaque nouvelle exécution.

Pour modifier la durée de rétention, éditer le script `scripts/backup_legaleye.ps1` et changer la ligne :

```powershell
$RetentionDays = 182   # 6 mois par défaut
```

Valeurs possibles :

| Valeur | Conservation |
|---|---|
| 90 | 3 mois (~13 sauvegardes) |
| 182 | 6 mois (~26 sauvegardes) — défaut |
| 365 | 1 an (~52 sauvegardes) |
| 730 | 2 ans (~104 sauvegardes) |

---

## Étape 10 — Démarrage automatique au boot Windows

Cette étape, déjà partiellement configurée à l'étape 3, garantit qu'après un redémarrage du PC, **tout repart automatiquement** sans intervention.

### Vérifier Docker Desktop

1. Ouvrir Docker Desktop → **Settings** → **General**
2. Vérifier que **« Start Docker Desktop when you log in »** est coché
3. Sinon, cocher et **« Apply & Restart »**

### Vérifier le redémarrage automatique des conteneurs

Dans le fichier `docker-compose.yml`, chaque service inclut la directive :

```yaml
restart: unless-stopped
```

Cela signifie que les trois conteneurs (`db`, `backend`, `frontend`) redémarrent automatiquement après un reboot, **sauf si l'utilisateur les a arrêtés manuellement**.

### Test de simulation d'un redémarrage

Pour vérifier que le système supporte un redémarrage complet :

```powershell
# 1. Couper proprement Docker
docker compose stop

# 2. Relancer
docker compose start

# 3. Attendre 30 secondes puis vérifier
docker compose ps
```

Les trois conteneurs doivent être à nouveau `Up (healthy)`.

---

## Utilisation au quotidien

Une fois l'installation terminée, **rien à faire au quotidien**. L'application tourne en arrière-plan, le scraping s'exécute automatiquement lundi 06h00 et jeudi 18h00, et la sauvegarde s'exécute chaque dimanche 22h00.

### Commandes utiles à mémoriser

| Action | Commande |
|---|---|
| Voir l'état des conteneurs | `docker compose ps` |
| Voir les logs du backend | `docker compose logs -f backend` |
| Redémarrer un service | `docker compose restart backend` |
| Arrêter le système | `docker compose stop` |
| Relancer le système | `docker compose start` |
| Faire une sauvegarde manuelle | `powershell -ExecutionPolicy Bypass -File .\scripts\backup_legaleye.ps1` |

### Accès à l'application

- URL : **http://localhost**
- Compte admin : **admin@plastima.ma** (mot de passe défini après la première connexion)

---

## Restaurer une sauvegarde

En cas de besoin (perte de données, erreur manuelle, corruption), restaurer une sauvegarde précédente avec le script dédié.

### Lister les sauvegardes disponibles

```powershell
dir C:\Apps\legaleye\backups
```

### Restaurer une sauvegarde précise

```powershell
cd C:\Apps\legaleye
powershell -ExecutionPolicy Bypass -File .\scripts\restore_legaleye.ps1 -File "C:\Apps\legaleye\backups\legaleye_2026_sem23_20260605_143022.sql.gz"
```

Le script demande une **confirmation explicite** (taper `OUI`) avant d'écraser la base courante. Une fois validé, la restauration prend environ 1 minute.

---

### Mot de passe administrateur perdu

Pour réinitialiser le mot de passe d'un utilisateur :

```powershell
docker compose exec backend python -c "
from database import SessionLocal
from models import User
from passlib.hash import bcrypt
db = SessionLocal()
u = db.query(User).filter(User.email == 'admin@plastima.ma').first()
if u:
    u.password_hash = bcrypt.hash('NouveauMotDePasse2026')
    db.commit()
    print('Mot de passe modifié')
"
```

Adapter l'email et le nouveau mot de passe.

### Tout réinitialiser et recommencer (cas extrême)

> ⚠️ **Cette opération efface toutes les données. À ne faire qu'après une sauvegarde manuelle.**

```powershell
cd C:\Apps\legaleye
docker compose down -v
docker compose up -d --build
```

---