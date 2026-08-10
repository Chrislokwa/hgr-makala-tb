# AGENT.md

## 1. Mission

Tu es un agent de développement logiciel intervenant sur le projet :

**Suivi informatisé de la gestion de prise en charge des malades tuberculeux à l’Hôpital Général de Référence de Makala (HGR Makala).**

Ta mission est de contribuer au développement d’une application web fiable, sécurisée, maintenable et adaptée au fonctionnement réel du service de prise en charge de la tuberculose.

Le produit doit rester strictement aligné sur le rapport de projet, le cahier des charges, les besoins fonctionnels, le backlog et les modèles UML fournis dans le dépôt.

> **Principe directeur : le code doit implémenter le projet, pas inventer un nouveau projet.**

---

## 2. Source de vérité

Avant toute implémentation ou modification importante :

1. Lire les fichiers de spécification disponibles dans le dépôt.
2. Vérifier les besoins fonctionnels et les user stories concernés.
3. Vérifier les contraintes techniques et les rôles des utilisateurs.
4. Vérifier les modèles UML lorsqu’ils concernent la fonctionnalité.
5. Vérifier le code existant avant de créer une nouvelle abstraction.

En cas de contradiction entre une demande ponctuelle et une spécification existante :
- identifier explicitement la contradiction ;
- ne pas inventer une règle métier ;
- privilégier la spécification validée du projet ;
- signaler la contradiction avant une modification structurante.

Ne jamais considérer une hypothèse comme une exigence.

---

## 3. Périmètre fonctionnel

Le système couvre principalement :

- authentification et gestion des utilisateurs ;
- gestion des rôles et permissions ;
- admission et diagnostic initial ;
- gestion administrative des dossiers patients ;
- demandes et résultats d’examens de laboratoire ;
- suivi thérapeutique ;
- gestion des visites de contrôle ;
- programmation des rendez-vous ;
- consultation et recherche des dossiers ;
- historique des traitements et examens ;
- évaluation finale de la prise en charge ;
- statistiques et rapports.

### Hors périmètre

Ne pas implémenter sans validation explicite :

- gestion complète de l’hôpital ;
- prise en charge d’autres pathologies ;
- gestion complète de la pharmacie ;
- comptabilité ou gestion financière hospitalière ;
- réalisation d’actes médicaux ;
- fonctionnalités métier non prévues dans le cahier des charges.

Toute fonctionnalité supplémentaire doit être considérée comme une extension de périmètre, pas comme une amélioration anodine.

---

## 4. Acteurs et responsabilités métier

Les principaux acteurs sont :

### Administrateur
- gérer les comptes utilisateurs ;
- modifier les informations des utilisateurs ;
- attribuer les rôles ;
- désactiver les comptes ;
- contrôler les accès.

### Médecin
- créer un dossier provisoire de suspicion ;
- prescrire les examens ;
- consulter et interpréter les résultats ;
- confirmer ou infirmer le diagnostic ;
- modifier le traitement ;
- prescrire les examens de contrôle ;
- consulter l’historique ;
- effectuer l’évaluation finale ;
- décider de la poursuite ou de la clôture de la prise en charge.

### Infirmier
- finaliser l’admission administrative ;
- mettre à jour les informations administratives ;
- rechercher et consulter les dossiers autorisés ;
- enregistrer les visites de contrôle ;
- programmer les rendez-vous ;
- assurer le suivi de l’évolution thérapeutique selon les responsabilités prévues.

### Laborantin
- consulter les examens prescrits ;
- réaliser les analyses ;
- enregistrer les résultats ;
- conserver la traçabilité des examens.

### Agent du service statistique
- consulter les statistiques ;
- analyser les indicateurs du programme TB ;
- exporter les rapports.

---

## 5. Stack technique imposée par le projet

### Backend
- Python
- Django
- architecture monolithique Django/MVT

### Frontend
- Jinja2
- Semantic UI
- HTMX pour les interactions dynamiques sans rechargement complet lorsque pertinent
- Server-Sent Events (SSE) uniquement lorsque le besoin temps réel le justifie

### Base de données
- PostgreSQL
- pgAdmin 4 pour l’administration et l’inspection durant le développement

### Outils
- VS Code
- Git
- GitHub

Ne pas remplacer ces technologies par React, Vue, Angular, Node.js, MongoDB ou une architecture microservices sans décision explicite du responsable du projet.

---

## 6. Architecture

Le projet utilise une **architecture monolithique moderne orientée serveur**.

Principe général :

```text
Navigateur
    │
    ▼
Django
    ├── URLs / Routing
    ├── Views
    ├── Templates
    ├── Forms
    ├── Services / logique métier
    ├── Permissions / Authentification
    └── ORM
          │
          ▼
      PostgreSQL
```

### Règles d’architecture

- Les templates ne doivent pas contenir de logique métier complexe.
- Les vues doivent rester lisibles et ne pas devenir des blocs monolithiques.
- La logique métier réutilisable doit être isolée dans des services ou modules appropriés.
- Les accès aux données doivent passer par l’ORM Django sauf nécessité clairement justifiée.
- Les responsabilités doivent rester séparées.
- Éviter les dépendances circulaires entre applications Django.
- Ne pas introduire une architecture complexe simplement parce qu’elle semble plus « professionnelle ».

---

## 7. Structure Django recommandée

Adapter cette structure à l’état réel du dépôt plutôt que de réorganiser arbitrairement un projet existant.

```text
project/
├── manage.py
├── config/
│   ├── settings/
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── apps/
│   ├── accounts/
│   ├── patients/
│   ├── diagnosis/
│   ├── laboratory/
│   ├── treatment/
│   ├── appointments/
│   ├── reports/
│   └── statistics/
│
├── templates/
├── static/
├── media/
├── tests/
├── requirements/
├── docs/
├── .env.example
├── .gitignore
├── README.md
└── AGENT.md
```

Cette structure est une recommandation de séparation fonctionnelle. Elle ne doit pas être appliquée mécaniquement si le dépôt possède déjà une structure cohérente.

---

## 8. Règles métier critiques

### Dossier patient

Le système doit distinguer le dossier provisoire de suspicion et l’admission définitive.

Le médecin peut créer le dossier provisoire et prescrire l’examen initial.

Le système doit générer un **Numéro de Dossier Patient (NDP)** dès la création du dossier provisoire.

L’admission administrative définitive par l’infirmier dépend de la confirmation du diagnostic et de la disponibilité des résultats requis.

### Examens

- Le médecin prescrit les examens.
- Le laborantin consulte les examens prescrits.
- Le laborantin saisit les résultats.
- Le médecin consulte et interprète les résultats.
- Les résultats doivent rester associés au patient et à l’examen.
- Les résultats ne doivent pas être supprimés arbitrairement.
- L’historique doit être conservé.

### Traitement

- Le médecin est responsable de la prescription ou modification du traitement.
- Les modifications doivent être traçables.
- L’historique du traitement doit être conservé.

### Rendez-vous et visites

- L’infirmier programme les rendez-vous de suivi.
- L’infirmier enregistre les visites de contrôle.
- Les opérations doivent être liées au dossier patient.
- Les événements doivent être horodatés.

### Évaluation finale

L’évaluation finale relève du médecin.

Elle doit permettre de conserver la décision médicale et l’historique de la prise en charge.

Ne pas inventer de nouveaux résultats ou statuts médicaux sans validation du projet.

---

## 9. Sécurité et confidentialité

Le système manipule des données médicales sensibles.

La sécurité n’est donc pas une fonctionnalité « à faire plus tard ».

### Obligations

- authentification sécurisée ;
- autorisation basée sur les rôles ;
- permissions vérifiées côté serveur ;
- mots de passe gérés par les mécanismes sécurisés de Django ;
- protection CSRF ;
- validation des entrées utilisateur ;
- protection contre les accès directs non autorisés aux dossiers ;
- journalisation des opérations importantes ;
- conservation de l’historique ;
- sauvegardes régulières ;
- absence de données médicales sensibles dans les logs inutiles.

### Interdictions

Ne jamais :

- stocker un mot de passe en clair ;
- mettre des secrets dans Git ;
- contourner les permissions côté backend ;
- faire confiance uniquement aux contrôles de l’interface ;
- exposer inutilement des données médicales dans une réponse HTTP ;
- désactiver une protection Django pour « faire fonctionner » une fonctionnalité.

---

## 10. Autorisations

Toute opération sensible doit être contrôlée côté serveur.

Exemple conceptuel :

```text
Médecin
 ├── prescrire examen
 ├── interpréter résultat
 ├── modifier traitement
 └── évaluer prise en charge

Laborantin
 ├── consulter examens prescrits
 └── enregistrer résultats

Infirmier
 ├── finaliser admission
 ├── enregistrer visite
 └── programmer rendez-vous

Agent statistique
 ├── consulter statistiques
 └── exporter rapports

Administrateur
 └── gérer utilisateurs et droits
```

Ne jamais utiliser uniquement une condition dans le template comme mécanisme d’autorisation.

---

## 11. Modélisation et cohérence UML

Le développement doit rester cohérent avec les modèles UML du projet :

- diagrammes de cas d’utilisation ;
- diagramme de classes ;
- diagrammes de séquence ;
- diagramme de composants.

Lorsqu’une modification implique le modèle métier :

1. identifier les classes concernées ;
2. vérifier leurs relations ;
3. vérifier les multiplicités ;
4. vérifier les responsabilités ;
5. vérifier les interactions ;
6. mettre à jour la documentation UML si nécessaire.

Ne pas créer de modèle de données uniquement parce qu’un écran en a besoin.

Le modèle métier doit guider l’interface, et non l’inverse.

---

## 12. Modèles Django

### Principes

- Utiliser des relations Django explicites.
- Choisir soigneusement `ForeignKey`, `OneToOneField` et `ManyToManyField`.
- Définir les contraintes d’intégrité au niveau du modèle lorsque pertinent.
- Ajouter des index sur les champs réellement utilisés pour la recherche.
- Utiliser des choix (`choices`) lorsque le domaine impose un ensemble fermé de valeurs.
- Éviter les champs génériques ou JSON pour remplacer une modélisation relationnelle claire.
- Ne pas dupliquer inutilement les données.

### Données historiques

Les informations médicales importantes doivent conserver leur historique lorsqu’une modification est requise par le cahier des charges.

Éviter les suppressions physiques lorsqu’elles détruiraient une information nécessaire à la traçabilité.

---

## 13. Views, Forms et Services

### Views

Une view doit principalement :

1. recevoir la requête ;
2. vérifier les permissions ;
3. récupérer ou valider les données ;
4. appeler la logique métier appropriée ;
5. retourner une réponse.

Éviter les views de plusieurs centaines de lignes.

### Forms

Utiliser les Django Forms / ModelForms pour :

- validation ;
- nettoyage des données ;
- messages d’erreur ;
- cohérence des champs.

La validation métier critique doit rester côté serveur.

### Services

Utiliser une couche de service lorsque :

- une opération implique plusieurs modèles ;
- une transaction métier est complexe ;
- une logique doit être réutilisée ;
- la logique ne devrait pas vivre dans une view ou un template.

---

## 14. Transactions

Pour les opérations métier impliquant plusieurs écritures liées :

```python
from django.db import transaction

with transaction.atomic():
    ...
```

Utiliser les transactions lorsque l’intégrité de l'opération l’exige.

Un dossier médical ne doit pas se retrouver à moitié enregistré parce qu'une étape secondaire a échoué.

---

## 15. Templates et interface

L’interface doit être :

- simple ;
- claire ;
- professionnelle ;
- responsive ;
- adaptée au personnel hospitalier ;
- cohérente avec les rôles ;
- orientée vers l’efficacité opérationnelle.

### Semantic UI

- privilégier les classes utilitaires cohérentes ;
- éviter les styles inline inutiles ;
- factoriser les composants récurrents ;
- maintenir une hiérarchie visuelle claire.

### HTMX

Utiliser HTMX lorsqu'il permet de simplifier une interaction serveur sans introduire une SPA inutile.

Exemples pertinents :

- recherche de patient ;
- filtrage de listes ;
- affichage de résultats ;
- mise à jour partielle d’un tableau ;
- interactions de formulaire simples.

Ne pas utiliser HTMX partout par principe.

### SSE

Utiliser SSE uniquement pour des besoins réellement temps réel et clairement identifiés.

---

## 16. Recherche et dossiers patients

La recherche de patient est une fonctionnalité critique.

Elle doit :

- être rapide ;
- respecter les permissions ;
- utiliser des champs indexés lorsque nécessaire ;
- éviter les requêtes N+1 ;
- ne pas exposer de résultats à un utilisateur non autorisé.

Avant d'ajouter une recherche complexe :

1. identifier les champs recherchables ;
2. vérifier les besoins du cahier des charges ;
3. vérifier les performances ;
4. ajouter les index nécessaires si justifié.

---

## 17. Performance

Toujours surveiller les problèmes classiques Django :

- N+1 queries ;
- requêtes inutiles ;
- chargement excessif de relations ;
- absence d’index ;
- pagination manquante sur les listes volumineuses ;
- calculs lourds dans les templates.

Utiliser notamment lorsque pertinent :

```python
select_related()
prefetch_related()
```

Ne pas optimiser prématurément. Mesurer ou identifier un besoin réel avant d'ajouter de la complexité.

---

## 18. Statistiques et rapports

Les statistiques doivent être produites à partir des données réellement enregistrées dans le système.

Elles doivent notamment pouvoir couvrir les indicateurs prévus par le projet, tels que :

- nombre de cas enregistrés ;
- guérisons ;
- abandons ;
- rechutes ;
- évolution de la prise en charge.

Les rapports détaillés doivent être accessibles uniquement aux utilisateurs habilités.

Les exports prévus sont notamment :

- Excel ;
- PDF.

Ne pas créer de statistiques fictives pour remplir une interface de démonstration une fois le système connecté aux données réelles.

---

## 19. Tests

Chaque fonctionnalité importante doit être testée.

Priorité aux tests :

1. permissions et sécurité ;
2. règles métier ;
3. modèles et contraintes ;
4. formulaires et validations ;
5. views ;
6. intégrations entre modules ;
7. rendu/interface lorsque pertinent.

Exécuter les tests avant de considérer une fonctionnalité comme terminée.

Commande de référence :

```bash
python manage.py test
```

Si le dépôt utilise une autre commande de test, suivre la commande réellement configurée dans le projet.

---

## 20. Qualité du code

Principes prioritaires :

- KISS ;
- DRY ;
- SOLID lorsque pertinent ;
- séparation des responsabilités ;
- faible couplage ;
- forte cohésion ;
- lisibilité avant sophistication.

### Python

- respecter PEP 8 ;
- utiliser des noms explicites ;
- privilégier les fonctions courtes ;
- éviter les abstractions prématurées ;
- utiliser les type hints lorsqu’ils apportent une vraie valeur.

### Django

- respecter les conventions Django ;
- exploiter les mécanismes natifs avant d'ajouter une dépendance ;
- ne pas réimplémenter l’authentification ou les protections de sécurité existantes.

### Nommage

Le code utilise des noms techniques en anglais.

Exemples :

```text
Patient
Treatment
Appointment
LaboratoryExam
ClinicalEvolution
FinalEvaluation
User
```

Les libellés affichés à l'utilisateur peuvent être en français.

---

## 21. Dépendances

Avant d'ajouter une bibliothèque :

1. vérifier si Django ou une dépendance existante fournit déjà la fonctionnalité ;
2. vérifier si la bibliothèque est réellement nécessaire ;
3. vérifier sa maintenance et sa compatibilité ;
4. limiter les dépendances au strict nécessaire.

Ne pas ajouter une bibliothèque simplement parce qu’elle rend une tâche légèrement plus confortable.

Chaque dépendance est une petite dette technique qui vient réclamer son loyer plus tard.

---

## 22. Git

Utiliser Git pour conserver un historique propre.

### Commits

Les commits doivent :

- être atomiques ;
- décrire clairement l’intention ;
- éviter de mélanger plusieurs fonctionnalités ;
- ne pas contenir de secrets.

Exemples :

```text
feat: add patient provisional record workflow
feat: implement laboratory result entry
fix: enforce physician treatment permissions
test: add appointment permission tests
refactor: extract treatment service
docs: update setup instructions
```

Ne jamais committer :

- `.env` ;
- mots de passe ;
- clés API ;
- certificats privés ;
- données médicales réelles ;
- dumps de base contenant des données sensibles.

---

## 23. Workflow obligatoire de développement

Pour toute tâche non triviale :

### Étape 1 — Comprendre

Lire :

- la demande ;
- les fichiers concernés ;
- le code existant ;
- les modèles ;
- les tests ;
- la documentation pertinente.

### Étape 2 — Planifier

Identifier :

- les fichiers à modifier ;
- les nouveaux fichiers nécessaires ;
- les dépendances ;
- les risques ;
- les tests à ajouter.

### Étape 3 — Implémenter

Modifier uniquement ce qui est nécessaire.

Ne pas effectuer de refactorisation opportuniste sans rapport avec la tâche.

### Étape 4 — Vérifier

Lancer :

- les tests ;
- les vérifications Django ;
- les outils de lint/formatage disponibles ;
- les vérifications pertinentes à la fonctionnalité.

Exemples :

```bash
python manage.py check
python manage.py test
```

### Étape 5 — Relire

Avant de terminer :

- vérifier les permissions ;
- vérifier les erreurs ;
- vérifier les migrations ;
- vérifier les régressions ;
- vérifier les données exposées ;
- vérifier la cohérence avec le cahier des charges.

### Étape 6 — Résumer

Présenter clairement :

- ce qui a été modifié ;
- les tests exécutés ;
- les éventuels problèmes restants ;
- les décisions nécessitant validation.

---

## 24. Migrations

Toute modification de modèle doit être accompagnée de migrations appropriées.

Utiliser :

```bash
python manage.py makemigrations
python manage.py migrate
```

Ne jamais modifier manuellement une migration déjà appliquée en production sans raison extrêmement claire.

Avant une migration :

- comprendre son impact ;
- vérifier les données existantes ;
- éviter les opérations destructives non nécessaires.

---

## 25. Gestion des erreurs

Les erreurs doivent être :

- explicites ;
- compréhensibles ;
- traçables ;
- sûres.

Ne jamais exposer :

- stack traces ;
- secrets ;
- détails internes ;
- données médicales inutiles.

Ne pas utiliser :

```python
except Exception:
    pass
```

pour masquer un problème.

Une erreur silencieuse n'est pas une fonctionnalité. C'est juste un problème qui a appris à se cacher.

---

## 26. Données de développement

Utiliser uniquement des données fictives pour le développement et les tests.

Ne jamais intégrer dans le dépôt :

- noms réels de patients ;
- numéros de dossier réels ;
- résultats médicaux réels ;
- données personnelles réelles ;
- documents hospitaliers confidentiels.

---

## 27. Documentation

Toute décision technique importante doit être documentée lorsqu’elle influence :

- l’architecture ;
- le modèle de données ;
- la sécurité ;
- les workflows métier ;
- les dépendances ;
- le déploiement.

Le `README.md` doit expliquer aux développeurs humains comment installer et lancer le projet.

Ce fichier `AGENT.md` contient les règles et le contexte destinés principalement aux agents de développement.

---

## 28. Gestion de l'incertitude

Lorsque l'information manque :

- ne pas inventer ;
- chercher dans le dépôt ;
- chercher dans la documentation du projet ;
- vérifier le code existant ;
- utiliser la documentation officielle de la technologie si nécessaire.

Si l'ambiguïté concerne une règle métier médicale ou une décision de périmètre :

> **STOP → signaler l’ambiguïté → demander validation.**

Il vaut mieux une question précise qu'une fonctionnalité parfaitement codée mais fausse.

---

## 29. Non-régression

Avant toute modification :

- comprendre le comportement actuel ;
- identifier les dépendances ;
- préserver les fonctionnalités existantes.

Après modification :

- exécuter les tests ;
- vérifier les modules affectés ;
- vérifier les permissions ;
- vérifier les migrations ;
- vérifier les parcours métier concernés.

Ne pas déclarer une tâche terminée uniquement parce que « le code compile ».

---

## 30. Règle finale

Pour chaque contribution, respecter cette chaîne :

```text
Spécification
    ↓
Compréhension du besoin
    ↓
Modèle métier / UML
    ↓
Conception technique
    ↓
Implémentation
    ↓
Tests
    ↓
Vérification sécurité
    ↓
Validation fonctionnelle
    ↓
Documentation
```

**Priorités absolues :**

1. exactitude fonctionnelle ;
2. sécurité et confidentialité ;
3. intégrité des données ;
4. cohérence avec le projet ;
5. maintenabilité ;
6. performance ;
7. ergonomie ;
8. sophistication technique.

Le système doit rester simple, fiable et cohérent avec le besoin réel de l’HGR Makala.
