# Système Informatisé de Suivi et de Prise en Charge des Malades Tuberculeux (HGR Makala)

Ce projet est une solution logicielle web conçue spécifiquement pour l'**Hôpital Général de Référence (HGR) de Makala** (Kinshasa, RDC). Il vise à informatiser, centraliser et optimiser l'ensemble du processus de suivi et de prise en charge thérapeutique des patients atteints de tuberculose.

---

## Contexte et Problématique

L'**Hôpital Général de Référence de Makala** (anciennement Sanatorium de Makala créé en 1956) fait face à des difficultés majeures liées à la gestion manuelle des dossiers de tuberculose sur registres papier :

* ⏱️ **Lenteur d'accès** aux historiques médicaux lors des consultations.

* 📁 **Risques de perte, détérioration ou falsification** des fiches papier.

* 🔄 **Lourdeur administrative** liée aux transferts physiques des fiches et bons de laboratoire portés par les patients eux-mêmes (risques de contagion).

* 📊 **Complexité d'extraction statistique** pour la production des rapports épidémiologiques destinés à la Direction et aux autorités sanitaires (PNLT / OMS).

---

## 🎯 Objectifs du Projet

### Objectif Général
Concevoir et mettre en œuvre un système informatisé sécurisé pour la gestion centralisée du suivi des malades tuberculeux au sein de l'HGR Makala.

### Objectifs Spécifiques
* 📝 **Informatiser l'enregistrement** des patients suspects et confirmés.

* 🔬 **Dématérialiser les demandes et résultats d'examens** de laboratoire (crachat/GeneXpert, etc.).

* 💊 **Tracer le suivi thérapeutique** (prescriptions, administration des médicaments, calendrier des prises).

* 📅 **Gérer les rendez-vous** et automatiser la détection des perdus de vue / abandons.

* 📈 **Générer automatiquement des indicateurs statistiques** et des rapports d'activité périodiques.

---

## Fonctionnalités Principales

# Module Fonctionnalités clés 

**Authentification & Sécurité** : Connexion sécurisée par rôles (RBAC), mots de passe chiffrés gestion des sessions et traçabilité globale (logs).

**Gestion des Patients** : Dossier Médical Électronique (DME) unique, enregistrement état civil, historiques, statut du patient (*En traitement*, *Guéri*, *Rechute*, *Perdu de vue*). 

**Consultations Médicales** : Saisie des observations cliniques, symptômes, diagnostics présomptifs et décisions médicales de prise en charge.

**Examens de Laboratoire** : Emission de bons d'examens électroniques par le médecin, saisie et validation des résultats par le laborantin.

**Suivi Thérapeutique** : Prescriptions des protocoles antituberculeux, suivi quotidien de l'administration des médicaments par l'infirmier.

**Rendez-vous & Contrôle** : Calendrier de suivi, relance des rendez-vous de contrôle crachat/radio, gestion des échéances.

**Statistiques & Rapports** : Tableau de bord décisionnel, calcul automatique des taux de guérison, exportation des rapports périodiques. |

---

## 🛠️ Architecture Technique

Le projet adopte une **architecture découplée Client-Serveur** (API REST + Single Page Application) :

```
┌────────────────────────────────────────┐
│             Client Web                 │
│      Svelte + Tailwind CSS             │
└──────────────────┬─────────────────────┘
                   │  HTTP / HTTPS (JSON)
                   ▼
┌────────────────────────────────────────┐
│        API Django REST Framework       │
│  (Python 3.11 / Authentication / RBAC) │
└─────────┬──────────────────────┬───────┘
          │                      │
          ▼                      ▼
┌──────────────────┐   ┌──────────────────┐
│   PostgreSQL     │   │   Redis / Celery │
│  (Base Relation) │   │ (Tâches/Rapports)│
└──────────────────┘   └──────────────────┘
```

* **Backend :** Python 3.11+, Django 5.x, Django REST Framework (DRF)

* **Frontend :** Svelte, Tailwind CSS, Vite

* **Base de données :** PostgreSQL 15+, pgAdmin 4

* **Tâches asynchrones & Cache :** Redis, Celery / Cron (génération automatique des rapports & sauvegardes)

* **Outils & Versioning :** Git, GitHub, VS Code

---

## 👥 Rôles et Droits d'Accès

Le système applique un contrôle d'accès basé sur les rôles (**RBAC**) :

**Administrateur :** Gestion des comptes utilisateurs, attribution des rôles, journalisation et configuration système.

**Médecin Traitant :** Consultation, diagnostic, prescription des examens et protocoles thérapeutiques, évaluation finale.

**Infirmier (Service Nursing) :** Enregistrement des patients, suivi de la prise de médicaments, gestion des rendez-vous.

**Laborantin :** Réception des demandes d'analyses, encodage et transmission des résultats de laboratoire.

**Agent du Service Statistique :** Consultation du tableau de bord, extraction et exportation des rapports périodiques.

---

## 📂 Structure du Projet

```bash
hgr-makala-tb/
├── backend/                  # Application Django API REST
│   ├── manage.py
│   ├── config/               # Settings Django, URLs principales & WSGI/ASGI
│   ├── authentication/       # Module de gestion des utilisateurs & rôles
│   ├── patients/             # Gestion des dossiers patients & statuts
│   ├── consultations/        # Consultations & observations médicales
│   ├── laboratory/           # Demandes & résultats d'analyses
│   ├── treatments/           # Prescriptions & suivi médicamenteux
│   ├── appointments/         # Calendrier & rendez-vous de suivi
│   └── statistics/           # Génération des rapports & exports

├── frontend/                 # Application Web Svelte
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── src/
│       ├── lib/              # Composants réutilisables & stores Svelte
│       ├── routes/           # Pages & navigation
│       └── services/         # Appels API REST (Fetch/Axios)

└── README.md
```

---

## ⚙️ Installation et Configuration

### Prérequis
* Python `3.10+` & `pip`
* Node.js `v18+` & `npm`
* PostgreSQL `v14+`
* Redis Server (optionnel pour la gestion du cache et Celery)

---

### 1. Backend (Django REST Framework)

1. **Cloner le projet :**
   ```bash
   git clone https://github.com/votre-organisation/hgr-makala-tb.git
   cd hgr-makala-tb/backend
   ```

2. **Créer et activer un environnement virtuel :**
   ```bash
   python -m venv venv
   # Sur Linux/macOS :
   source venv/bin/activate
   # Sur Windows :
   .env\Scriptsctivate
   ```

3. **Installer les dépendances Python :**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurer les variables d'environnement (`.env`) :**
   Créer un fichier `.env` dans le dossier `backend/` :
   ```env
   SECRET_KEY=votre_cle_secrete_django
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1

   DB_NAME=hgr_makala_tb_db
   DB_USER=postgres
   DB_PASSWORD=votre_mot_de_passe
   DB_HOST=localhost
   DB_PORT=5432
   ```

5. **Exécuter les migrations de base de données :**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Créer un superutilisateur (Administrateur) :**
   ```bash
   python manage.py createsuperuser
   ```

7. **Lancer le serveur de développement Backend :**
   ```bash
   python manage.py runserver
   ```
   L'API Backend sera accessible sur `http://127.0.0.1:8000/`.

---

### 2. Frontend (Svelte & Tailwind CSS)

1. **Naviguer dans le dossier frontend :**
   ```bash
   cd ../frontend
   ```

2. **Installer les dépendances Node.js :**
   ```bash
   npm install
   ```

3. **Lancer le serveur de développement Frontend :**
   ```bash
   npm run dev
   ```
   L'application Web sera accessible sur `http://localhost:5173/`.

---

## Organisation de l'Équipe & Méthodologie

* **Méthodologie :** Agile / Scrum (Sprints itératifs)
* **Cycle de développement :** 30 jours (Du 13 juillet au 3 août 2026)
* **Composition de l'Équipe :**
  * 👑 1 Chef de Projet
  * 🎨 2 Concepteurs (UML & UX/UI)
  * 💻 2 Développeurs (Fullstack / Backend / Frontend)

---

## 📄 Licence & Contact

Projet développé pour l'**Hôpital Général de Référence de Makala** (Commune de Selembao, Kinshasa, RDC) **Par TEAM 6 ENDGAME**.
