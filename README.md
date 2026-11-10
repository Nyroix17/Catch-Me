# Catch-Me

**Catch-Me** est un jeu de réflexe développé en Python avec Pygame. Le principe est de cliquer sur des cibles qui apparaissent à l'écran afin de gagner des points, améliorer ses performances et débloquer du contenu.

Le projet a évolué à travers plusieurs versions : d'un jeu local simple à une application connectée à un serveur, avec gestion des comptes, progression sauvegardée et fonctionnalités en ligne.

---

## Sommaire

- [Présentation](#présentation)
- [Fonctionnalités](#fonctionnalités)
- [Les différentes versions](#les-différentes-versions)
- [Architecture technique](#architecture-technique)
- [Organisation du dépôt](#organisation-du-dépôt)
- [Installation et lancement](#installation-et-lancement)
- [Commandes](#commandes)
- [Sécurité et fonctionnement du serveur](#sécurité-et-fonctionnement-du-serveur)
- [État du développement](#état-du-développement)
- [Utilisation du code](#utilisation-du-code)

## Présentation

Catch-Me est un jeu dans lequel le joueur doit cliquer sur des cibles pour obtenir des points.

Au fil des versions, plusieurs systèmes ont été ajoutés :
- Différents niveaux de difficulté.
- Une boutique avec des améliorations.
- Des skins et des éléments personnalisables.
- Des comptes utilisateurs.
- Un système de classement.
- Une progression sauvegardée en ligne.
- Des missions quotidiennes et des récompenses.

## Fonctionnalités

### Modes de jeu

La version 1.1 propose trois modes :

| Mode | Objectif |
|---|---|
| Classique | Obtenir le meilleur score en 30 secondes. |
| Challenge | Atteindre 30 cibles le plus rapidement possible. |
| Survie | Survivre avec 3 vies face à une difficulté progressive. |

### Difficultés

Le jeu propose cinq niveaux de difficulté :

- Easy
- Medium
- Hard
- Impossible
- Demonic

La difficulté influence notamment le comportement et la vitesse des cibles.

### Boutique et progression

Le jeu intègre plusieurs améliorations achetables avec les points gagnés :

- **Ralentisseur :** réduit la vitesse des cibles.
- **Aide :** permet de bénéficier de boutons supplémentaires.
- **Multiplicateur :** augmente les points obtenus.
- **Skins :** modifient l'apparence des éléments du jeu.

Les améliorations disposent de plusieurs niveaux et de conditions de déblocage.

### Système de progression en ligne

La version connectée propose notamment :

- Création de compte et connexion.
- Sauvegarde de la progression.
- Gestion des améliorations et des thèmes.
- Classements.
- Missions quotidiennes.
- Caisses avec plusieurs niveaux de rareté.
- Série de connexion et récompenses.

### Personnalisation

Le jeu possède plusieurs thèmes visuels.

Les ressources d'un thème peuvent comprendre :
- Un arrière-plan.
- Une image de bouton.
- Une ou plusieurs images de cible.
- Des animations sous forme de spritesheet.
- Des effets sonores.

Les ressources sont organisées dans des dossiers séparés pour chaque thème.

## Les différentes versions

### Version 1 — Jeu local

Première version du projet.

Cette version constitue la base du gameplay :
- Création de boutons et de cibles.
- Gestion des clics.
- Gestion du score.
- Choix de la difficulté.
- Menu principal.
- Boutique d'améliorations.

**Technologies :** Python, Pygame, Tkinter et SQLite.

### Version 2 — Ajout des fonctionnalités en ligne

Cette version enrichit le jeu avec une première communication entre le client et un serveur.

Fonctionnalités présentes dans le code :
- Interface de connexion.
- Création de compte.
- Communication HTTP avec le serveur.
- Récupération des informations du joueur.
- Synchronisation de la progression et des achats.
- Consultation d'un classement.

**Technologies :** Python, Pygame, Tkinter, Requests et HTTP.

### Version 3 — Client-serveur

Cette version apporte une évolution importante de l'architecture du projet.

Le jeu communique avec une API afin de gérer les comptes et la progression des joueurs.

Fonctionnalités :
- Interface de jeu redimensionnable.
- Modes Classique, Challenge et Survie.
- Gestion des combos.
- Cibles spéciales et bombes.
- Boutique et améliorations.
- Thèmes personnalisables.
- Missions quotidiennes.
- Caisses et récompenses.
- Classements par mode et classement général.
- Connexion et sauvegarde de la progression.

**Technologies :** Python, Pygame, Requests, FastAPI, SQLite, Uvicorn et bcrypt.

### Serveur — Version 1.2

Le serveur possède sa propre application et gère les fonctionnalités nécessitant une validation centralisée.

Ses principales responsabilités sont :
- Inscription et authentification.
- Gestion des sessions.
- Gestion des données des joueurs.
- Validation des résultats des parties.
- Calcul des points et des récompenses.
- Gestion des achats et des thèmes.
- Gestion des missions et des caisses.
- Gestion des classements.
- Stockage des données dans SQLite.

Le serveur vérifie les résultats envoyés par le client afin de limiter les scores impossibles ou les achats non autorisés.

## Architecture technique

Le projet repose sur une architecture client-serveur pour sa troisième version.

```text
             CLIENT
        Python / Pygame
               |
               |
        Requêtes HTTP
               |
               v
              API
         FastAPI / Python
               |
               v
            SQLite
       Données des joueurs
```

**Client :**
- Affichage du jeu et gestion des interactions.
- Gestion des menus et des événements.
- Envoi des requêtes au serveur.
- Affichage des informations récupérées.

**Serveur :**
- Traitement des requêtes.
- Authentification des joueurs.
- Validation des parties et des achats.
- Gestion de la progression.
- Accès à la base de données.

**Base de données :**

SQLite est utilisée pour conserver les informations nécessaires au fonctionnement du jeu.

## Organisation du dépôt

```text
Catch-Me/
│
├── README.md
│
├── versions/
│   ├── v1-originale/
│   │   └── mon_jeux.py
│   │
│   ├── v2-enrichie/
│   │   └── mon_jeux.py
│   │
│   └── v3-client-serveur/
│       ├── CatchMe.py
│       ├── requirements.txt
│       ├── LISEZ-MOI.txt
│       └── themes/
│
├── serveur/
│   ├── main.py
│   ├── requirements.txt
│   └── INSTALLATION.txt
│
├── screenshots/
│
└── docs/
```

## Installation et lancement

### Version 1

Installer les dépendances :

```bash
pip install pygame
```

Lancer le jeu :

```bash
python mon_jeux.py
```

### Version 3 — Client

Se placer dans le dossier du client :

```bash
cd versions/v3-client-serveur
```

Installer les dépendances :

```bash
pip install -r requirements.txt
```

Lancer le jeu :

```bash
python CatchMe.py
```

Le dossier `themes` doit rester à côté du fichier `CatchMe.py`.

Une connexion au serveur est nécessaire pour utiliser les fonctionnalités liées aux comptes et à la progression en ligne.

### Serveur

Se placer dans le dossier du serveur :

```bash
cd serveur
```

Installer les dépendances :

```bash
pip install -r requirements.txt
```

Lancer le serveur en local :

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

La base de données `catchme.db` est créée ou mise à jour automatiquement au démarrage.

Pour une utilisation à distance, le serveur doit être accessible par une configuration réseau adaptée, notamment HTTPS.

## Commandes

| Touche | Action |
|---|---|
| ESC | Mettre en pause ou revenir en arrière |
| F11 | Activer ou désactiver le plein écran |
| F10 | Activer ou désactiver le son |
| Souris | Interagir avec les menus et les cibles |

## Sécurité et fonctionnement du serveur

La version 1.2 du serveur intègre plusieurs mécanismes de sécurité :

- Les mots de passe sont stockés sous forme d'empreintes bcrypt.
- Les jetons de session sont aléatoires et expirent.
- Seule l'empreinte des jetons est conservée.
- Les tentatives de connexion et d'inscription sont limitées.
- Les entrées sont vérifiées.
- Les requêtes SQL sont paramétrées.
- Les scores et les achats sont validés côté serveur.

Le serveur conserve la responsabilité des règles importantes du jeu afin de ne pas faire entièrement confiance aux informations envoyées par le client.

## État du développement

Catch-Me est un projet en évolution.

Les différentes versions permettent de suivre les étapes de son développement, depuis le premier gameplay local jusqu'à l'architecture client-serveur.

Certaines fonctionnalités et améliorations restent susceptibles d'évoluer.

## Utilisation du code

Ce dépôt est publié à des fins de présentation et de consultation.

Tous droits réservés. Aucune autorisation n'est accordée pour réutiliser, modifier, redistribuer ou exploiter commercialement le code source sans autorisation écrite préalable, sous réserve des droits et conditions applicables, notamment ceux des plateformes utilisées pour héberger le projet.

Pour toute autre utilisation, une autorisation préalable est nécessaire.
