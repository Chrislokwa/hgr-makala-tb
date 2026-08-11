# Suivi de la tuberculose - HGR Makala

Ce dépôt contient une application web Django destinée à soutenir la gestion du suivi des patients atteints de tuberculose à l’Hôpital Général de Référence de Makala, à Kinshasa, en République Démocratique du Congo.

Le projet a pour objectif de digitaliser les informations relatives aux patients, aux dossiers de traitement, aux rendez-vous, aux examens de laboratoire et au suivi thérapeutique, afin de réduire la dépendance aux registres papier et d’améliorer la traçabilité des soins.

## Contexte du projet

Dans un environnement hospitalier où la gestion manuelle des dossiers peut être lente, dispersée et vulnérable à la perte d’informations, ce système propose une base unique pour organiser les données médicales et administratives liées à la tuberculose.

Il s’inscrit dans une logique de:

- centralisation des dossiers patients;
- suivi simplifié des traitements;
- meilleure gestion des rendez-vous et des abandons de suivi;
- exploitation plus facile des données pour les rapports et indicateurs.

## Fonctionnalités principales

La version actuelle du projet couvre les modules suivants :

- gestion des utilisateurs et rôles via l’application d’authentification;
- enregistrement des patients;
- création de dossiers de traitement pour les cas de tuberculose;
- prise en charge des rendez-vous de suivi;
- suivi thérapeutique des patients;
- gestion des examens de laboratoire;
- module de statistiques et de consultation des données.

## Stack technique

Le projet est actuellement implémenté comme une application Django monolithique avec logique métier organisée par modules.

- Python 3.x
- Django 6
- Jinja2 (moteur de templates de l’application ; Django templates conservés uniquement pour l’interface d’administration)
- HTMX (interactions dynamiques sans rechargement complet, ex. recherche de patients / utilisateurs)
- Semantic UI
- PostgreSQL en base de données (configuration via le fichier `.env`)
- applications Django organisées par domaine : authentication, patients, laboratoire, stats

## Prérequis

- Python 3.10 ou plus
- pip
- un environnement virtuel recommandé
- PostgreSQL (serveur local en cours d’exécution)

## Installation

1. Cloner le dépôt
   ```bash
   git clone <url-du-dépôt>
   cd Suivi-tuberculose
   ```

2. Créer et activer un environnement virtuel
   ```bash
   python -m venv .venv
   ```
   Activation — Windows (PowerShell) :
   ```powershell
   .venv\Scripts\activate
   ```
   Activation — Linux / macOS :
   ```bash
   source .venv/bin/activate
   ```

3. Installer les dépendances
   ```bash
   pip install -r requirements.txt
   ```

4. Créer le fichier `.env`
   À la racine du projet, créer un fichier `.env` à partir du modèle ci-dessous :
   ```dotenv
   DB_NAME=hgr_makala_tb
   DB_USER=postgres
   DB_PASSWORD=<mot-de-passe>
   DB_HOST=localhost
   DB_PORT=5432
   ```
   Ce fichier est ignoré par git (il contient vos identifiants) et ne doit jamais être committé.

5. Créer la base de données PostgreSQL
   Avec un client `psql` et un utilisateur disposant des droits de création :
   ```bash
   psql -U postgres -c "CREATE DATABASE hgr_makala_tb;"
   ```
   Sous Windows, `psql` se trouve dans `C:\Program Files\PostgreSQL\<version>\bin\`.

6. Appliquer les migrations
   ```bash
   python manage.py migrate
   ```

7. (Optionnel) Charger les comptes de démonstration
   ```bash
   python manage.py seed_demo_users
   ```
   Cette commande crée 10 comptes de démonstration avec le mot de passe par défaut `demo`, dont un compte administrateur (`j.bongoy@hgr-makala.cd`). Elle est idempotente : réexécutée, elle met à jour les comptes existants.

8. Créer un superutilisateur
   ```bash
   python manage.py createsuperuser
   ```

9. Lancer l’application
   ```bash
   python manage.py runserver
   ```

L’application sera alors accessible sur http://127.0.0.1:8000/.

## Auteurs

Projet développé dans un cadre de formation / mise en œuvre pour l’amélioration du suivi de la tuberculose à l’HGR Makala.
