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
- SQLite pour l’environnement de développement
- applications Django organisées par domaine : authentication, patients, laboratoire, stats

## Prérequis

- Python 3.10 ou plus
- pip
- un environnement virtuel recommandé

## Installation

1. Cloner le dépôt
   ```bash
   git clone <url-du-dépôt>
   cd Suivi-tuberculose
   ```

2. Créer et activer un environnement virtuel
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Installer les dépendances
   ```bash
   pip install -r requirements.txt
   ```

4. Appliquer les migrations
   ```bash
   python manage.py migrate
   ```

5. Créer un superutilisateur
   ```bash
   python manage.py createsuperuser
   ```

6. Lancer l’application
   ```bash
   python manage.py runserver
   ```

L’application sera alors accessible sur http://127.0.0.1:8000/.

## Auteurs

Projet développé dans un cadre de formation / mise en œuvre pour l’amélioration du suivi de la tuberculose à l’HGR Makala.
