# Catch-Me

Catch-Me est un jeu de réflexe développé en Python avec Pygame. Le principe est simple : cliquer sur des cibles qui apparaissent à l'écran pour marquer des points, avec différents modes de jeu et niveaux de difficulté.

Le projet a évolué au fil de plusieurs versions, depuis une première version locale jusqu'à une architecture client-serveur avec gestion de comptes et sauvegarde des données.

## Présentation du projet

- **Langage principal :** Python
- **Bibliothèque graphique :** Pygame
- **Communication client-serveur :** HTTP avec Requests et FastAPI
- **Base de données :** SQLite
- **Serveur :** FastAPI et Uvicorn
- **Environnement de test du serveur :** Linux Mint

## Fonctionnalités

Selon la version utilisée, le jeu propose notamment :

- Un mode classique avec une durée limitée.
- Un mode défi où il faut atteindre un nombre de cibles le plus rapidement possible.
- Un mode survie avec un nombre de vies limité et une difficulté progressive.
- Un système de score et de progression.
- Des missions quotidiennes.
- Des caisses et des thèmes personnalisables.
- Une gestion de comptes et une sauvegarde en ligne dans la version client-serveur.

## Les différentes versions

### Version 1 — Jeu local

Première version du projet, développée individuellement.

Elle contient :
- L'interface graphique du jeu.
- La gestion des événements et des clics.
- La logique principale du jeu.
- Plusieurs modes de jeu.
- La gestion de la difficulté et des scores.

**Technologies :** Python, Pygame.

### Version 2 — Version enrichie

Cette version reprend le jeu initial et ajoute progressivement de nouvelles fonctionnalités.

Le développement a été réalisé avec une combinaison de programmation personnelle et d'assistance par intelligence artificielle.

**Technologies :** Python, Pygame.

### Version 3 — Architecture client-serveur

Cette version introduit une communication entre le jeu et un serveur distant.

Elle comprend notamment :
- Un serveur développé avec FastAPI.
- Une base de données SQLite.
- Une gestion des comptes utilisateurs.
- Des échanges entre le client et le serveur via HTTP.
- Une sauvegarde de certaines données en ligne.

Cette partie du projet a été développée avec une assistance importante de l'intelligence artificielle. Le mode multijoueur reste en cours de développement.

**Technologies :** Python, Pygame, FastAPI, Uvicorn, SQLite, Requests.

## Organisation du dépôt

```text
Catch-Me/
│
├── README.md
│
├── versions/
│   ├── v1-originale/
│   ├── v2-enrichie/
│   └── v3-client-serveur/
│
├── serveur/
│
├── screenshots/
│
└── docs/
```

Les dossiers permettent de retrouver les différentes étapes du développement. Chaque version possède ses propres fichiers et sa documentation lorsque celle-ci est disponible.

## Lancer le projet

Les instructions de lancement peuvent varier selon la version.

Pour la version locale, il faut disposer de Python et installer les dépendances nécessaires, notamment Pygame.

Pour la version client-serveur, il faut également installer les dépendances du serveur et démarrer celui-ci avant de lancer un client compatible.

Consulter les fichiers `README` ou `LISEZ-MOI` présents dans les dossiers des versions pour connaître les instructions précises.

## État du projet

Le projet est toujours en évolution. La version client-serveur est en cours de développement, notamment concernant les fonctionnalités multijoueurs.

## Utilisation du code

Ce dépôt est publié à des fins de présentation et de consultation.

Tous droits réservés. Aucune autorisation n'est accordée pour réutiliser, modifier, redistribuer ou exploiter commercialement le code source sans autorisation écrite préalable, sous réserve des droits et conditions applicables, notamment ceux des plateformes utilisées pour héberger le projet.

Pour toute autre utilisation, une autorisation préalable est nécessaire.
