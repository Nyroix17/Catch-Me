"""
Serveur Catch-Me 1.2 (FastAPI + SQLite)

Sécurité :
  - les mots de passe ne sont JAMAIS stockés : seulement leur empreinte bcrypt ;
  - les jetons de connexion sont aléatoires, expirent, et seule leur empreinte est stockée ;
  - le serveur décide de tout : prix, achats, points, récompenses. Le jeu ne peut pas
    envoyer "mon score vaut X" ni "je possède tel bonus" ;
  - limite d'essais de connexion et d'inscriptions ;
  - toutes les entrées sont vérifiées, toutes les requêtes SQL sont paramétrées.

Jeu :
  - trois modes de jeu (Classique, Challenge, Survie) : le jeu annonce le début d'un run,
    puis envoie son résultat ;
    le serveur vérifie la durée et refuse un score impossible ;
  - classements par mode (semaine ou tous temps) et classement général ;
  - caisses de 4 raretés, missions du jour par difficulté, série de connexion :
    tout est tiré et compté ici.

Installation :   pip install fastapi uvicorn bcrypt
Lancement :      uvicorn main:app --host 127.0.0.1 --port 8000
                 (derrière ton tunnel HTTPS, comme avant)

La base catchme.db est créée (ou mise à jour) toute seule au lancement, à côté de ce fichier.
"""
import hashlib
import math
import os
import random
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from collections import deque
from contextlib import contextmanager

import bcrypt
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# ==============================
# REGLAGES
# ==============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("CATCHME_DB", os.path.join(BASE_DIR, "catchme.db"))  # chemin absolu

# Numéro de version minimum du jeu. Le jeu envoie le sien à la connexion ; s'il est plus
# petit, la connexion est refusée avec un message qui demande de se mettre à jour.
# À augmenter (ici ET dans le jeu, VERSION_JEU) quand une mise à jour rend l'ancien jeu incompatible.
VERSION_JEU_MIN = 2

SESSION_JOURS = 30          # durée de vie d'une connexion
SESSIONS_MAX = 5            # connexions simultanées par joueur (les plus vieilles sautent)
BCRYPT_COUT = 12            # plus c'est haut, plus casser un mot de passe volé est long
# True si le serveur n'est joignable QUE par ton tunnel / proxy : l'adresse du joueur est
# alors lue dans l'en-tête ajouté par le proxy. Mets False si le port est ouvert en direct.
PROXY_DE_CONFIANCE = True

# ==============================
# REGLES DU JEU (le serveur fait foi)
# ==============================
BASE_POINTS = {"easy": 1, "medium": 2, "hard": 5, "impossible": 15, "demonic": 50}
MULTIPLICATEURS = (1, 1.5, 2, 3)        # selon le niveau "multi" (0 à 3)
MULTIPLICATEURS_EASY = (1, 2, 2.5, 3)

# --- Runs ---
DUREE_RUN = 30                 # secondes de jeu
RUN_AVANCE_MAX = 2             # un run ne peut pas finir plus de 2 s en avance
RUN_RETARD_MAX = 180           # ni plus de 3 min après (pause, réseau lent)
# Combo : (à partir de combien de cibles d'affilée, multiplicateur)
PALIERS_COMBO = ((40, 2.5), (20, 2), (8, 1.5), (0, 1))
COMBO_MAX = PALIERS_COMBO[0][1]
BONUS_DOREE = 3                # une cible dorée vaut 3 fois plus
CHANCE_DOREE = 0.06            # chance que la cible principale soit dorée
CHANCE_BOMBE = 0.18            # chance qu'une bombe apparaisse (à partir de Medium)
PENALITE_BOMBE = 3             # secondes perdues en cliquant une bombe : le run finit plus tôt
BOMBES_MAX = 5                 # au-delà, les bombes ne raccourcissent plus le run accepté
PENALITE_RATE = 0              # points retirés par clic raté, en valeur de cible (0 = aucun)
COMBO_DUREE = 2                # secondes sans toucher de cible avant que le combo retombe à zéro
# Temps minimum entre deux cibles : sert à refuser les scores impossibles.
INTERVALLE_MIN = {"easy": 0.12, "medium": 0.12, "hard": 0.12, "impossible": 0.12, "demonic": 0.5}
RUN_COMPTE_MIN = 15            # un run de moins de 15 s ne compte ni pour les caisses ni pour "Termine N runs"

# --- Modes de jeu : dans quelles difficultés chacun se joue ---
GENRES = {
    "classic": ("easy", "medium", "hard", "impossible", "demonic"),   # 30 s, un maximum de points
    "challenge": ("easy", "medium", "hard"),                          # N cibles le plus vite possible
    "survival": ("easy", "medium", "hard"),                           # 3 vies, de plus en plus rapide
}
NOMS_GENRES = {"classic": "Classique", "challenge": "Challenge", "survival": "Survie"}

# Challenge : toucher CHALLENGE_CIBLES cibles le plus vite possible (une dorée compte double).
CHALLENGE_CIBLES = 30
CHALLENGE_PENALITE_RATE = 1    # secondes ajoutées au chrono par clic raté
CHALLENGE_DUREE_MAX = 120      # au-delà, le challenge est perdu
CHALLENGE_TEMPS_MIN = 6        # aucun temps plus court n'est accepté
CHALLENGE_MARGE = 5            # le temps annoncé peut être au plus 5 s sous le temps vu par le serveur
# Points gagnés = valeur des cibles x (CHALLENGE_REFERENCE / temps), entre x0.5 et x2.
CHALLENGE_REFERENCE = 25       # en 25 s : x1 ; en 12,5 s ou moins : x2
CHALLENGE_BONUS = (0.5, 2.0)

# Survie : SURVIE_VIES vies. Une vie perdue par clic raté, bombe touchée, ou cible non touchée
# à temps. Le temps laissé par cible part de "départ" et raccourcit à chaque cible touchée.
SURVIE_VIES = 3
SURVIE_DUREE_MAX = 300
SURVIE_DELAIS = {"easy": (2200, 550), "medium": (1700, 450), "hard": (1300, 380)}   # (départ, minimum) en ms
SURVIE_ACCELERATION = 0.97     # temps multiplié par 0,97 à chaque cible touchée

# --- Boutique ---   type -> (colonne en base, prix des niveaux 1, 2, 3)
AMELIORATIONS = {
    "slow": ("slow_stage", (100, 200, 2500, 8000)),   # 4 niveaux, le premier petit et pas cher
    "aide": ("aide_level", (800, 3500, 9000)),
    "multi": ("multi_level", (2000, 7000, 15000)),
}
THEMES = {
    "farwest": 0, "cyberpunk": 3000, "oiia": 3000, "huhcat": 3000, "bananacat": 3000,
    "tralalero": 6000, "bombardiro": 6000, "tungtung": 6000, "ballerina": 6000,
}
THEME_DEFAUT = "farwest"

# --- Caisses : 4 raretés ---
RARETES = ("common", "rare", "epic", "legendary")
NOMS_RARETES = {"common": "commune", "rare": "rare", "epic": "épique", "legendary": "légendaire"}
COLONNE_CAISSE = {r: "crates_" + r for r in RARETES}
# Contenu : (chances sur 100, type, mini, maxi). Le total de chaque ligne fait 100.
BUTIN = {
    "common":    ((80, "points", 20, 60), (19, "points", 80, 150), (1, "theme", 0, 0)),
    "rare":      ((65, "points", 80, 160), (32, "points", 200, 350), (3, "theme", 0, 0)),
    "epic":      ((55, "points", 250, 450), (37, "points", 500, 800), (8, "theme", 0, 0)),
    "legendary": ((80, "points", 1000, 1800), (20, "theme", 0, 0)),
}
# Points donnés à la place du thème quand le joueur les possède déjà tous.
POINTS_SI_TOUS_LES_THEMES = {"common": 150, "rare": 350, "epic": 800, "legendary": 1800}
RUNS_PAR_CAISSE = 5            # une caisse commune offerte tous les 5 runs terminés

# --- Série de connexion ---
SERIE_POINTS = 50              # points par jour de série...
SERIE_PLAFOND = 5              # ...jusqu'au 5e jour (250 points)
SERIE_CAISSES = ((7, "legendary"), (3, "rare"))   # tous les 7 jours : légendaire ; tous les 3 : rare

# --- Missions du jour : une facile, une moyenne, une difficile, de catégories différentes ---
# (catégorie, type, mode ou None, seuil, objectif)
#   precision : finir un run dans ce mode avec au moins "seuil" % de précision
#   score     : marquer au moins "seuil" points en un run dans ce mode
#   combo     : atteindre un combo de "objectif"
#   hits, golden, runs : total à atteindre dans la journée
#   no_bomb   : finir "objectif" runs dans ce mode sans toucher de bombe
#   perfect   : finir un run dans ce mode sans aucun clic raté
#   (les six types ci-dessus avec un mode se jouent en Classique)
#   challenge_time : finir un Challenge dans ce mode en moins de "seuil" secondes
#   survival_hits  : toucher au moins "seuil" cibles en un run de Survie dans ce mode
MISSIONS = {
    "facile": (
        ("Précision", "precision", "easy", 70, 1), ("Score", "score", "easy", 40, 1),
        ("Combo", "combo", None, 0, 10), ("Endurance", "hits", None, 0, 100),
        ("Endurance", "runs", None, 0, 3), ("Dorées", "golden", None, 0, 2),
        ("Sang-froid", "no_bomb", "medium", 0, 1),
        ("Challenge", "challenge_time", "easy", 45, 1), ("Survie", "survival_hits", "easy", 25, 1),
    ),
    "moyenne": (
        ("Précision", "precision", "medium", 85, 1), ("Score", "score", "medium", 160, 1),
        ("Combo", "combo", None, 0, 20), ("Endurance", "hits", None, 0, 220),
        ("Endurance", "runs", "hard", 0, 3), ("Dorées", "golden", None, 0, 5),
        ("Sang-froid", "no_bomb", "medium", 0, 3),
        ("Challenge", "challenge_time", "medium", 35, 1), ("Survie", "survival_hits", "medium", 45, 1),
    ),
    "difficile": (
        ("Précision", "precision", "hard", 92, 1), ("Score", "score", "hard", 650, 1),
        ("Combo", "combo", None, 0, 40), ("Endurance", "hits", None, 0, 400),
        ("Endurance", "runs", None, 0, 10), ("Dorées", "golden", None, 0, 9),
        ("Sang-froid", "perfect", "medium", 0, 1), ("Sang-froid", "no_bomb", "hard", 0, 3),
        ("Challenge", "challenge_time", "hard", 28, 1), ("Survie", "survival_hits", "hard", 70, 1),
    ),
}
# Récompense à récupérer : (rareté de la caisse, points)
RECOMPENSES_MISSIONS = {"facile": ("common", 100), "moyenne": ("rare", 250), "difficile": ("epic", 500)}
CIBLES_MIN_MISSION = 10        # précision, sans-faute, sans-bombe : au moins 10 cibles touchées dans le run
                               # (un run où l'on ne touche presque rien ne valide pas ces missions)
NOMS_MODES = {"easy": "Easy", "medium": "Medium", "hard": "Hard", "impossible": "Impossible", "demonic": "Demonic"}

# ==============================
# BASE DE DONNEES
# ==============================
# Chaque entrée = une étape de migration. Pour faire évoluer la base plus tard (runs,
# caisses, missions...), on AJOUTE une étape à la fin : on ne modifie jamais les anciennes.
MIGRATIONS = [
    """
    CREATE TABLE players (
        id            INTEGER PRIMARY KEY,
        pseudo        TEXT    NOT NULL,                 -- tel que le joueur l'a écrit
        pseudo_norm   TEXT    NOT NULL UNIQUE,          -- en minuscules : "Bob" et "bob" = même compte
        password_hash TEXT    NOT NULL,                 -- empreinte bcrypt, jamais le mot de passe
        score         REAL    NOT NULL DEFAULT 0 CHECK (score >= 0),   -- toujours un multiple de 0,5
        slow_level    INTEGER NOT NULL DEFAULT 0 CHECK (slow_level  BETWEEN 0 AND 3),
        aide_level    INTEGER NOT NULL DEFAULT 0 CHECK (aide_level  BETWEEN 0 AND 3),
        multi_level   INTEGER NOT NULL DEFAULT 0 CHECK (multi_level BETWEEN 0 AND 3),
        theme         TEXT    NOT NULL DEFAULT 'farwest',              -- thème équipé
        created_at    INTEGER NOT NULL,                 -- dates en secondes (heure Unix)
        last_login_at INTEGER
    );
    CREATE INDEX idx_players_score ON players (score DESC);

    -- Thèmes possédés : une ligne par (joueur, thème)
    CREATE TABLE player_themes (
        player_id INTEGER NOT NULL REFERENCES players (id) ON DELETE CASCADE,
        theme     TEXT    NOT NULL,
        bought_at INTEGER NOT NULL,
        PRIMARY KEY (player_id, theme)
    ) WITHOUT ROWID;

    -- Connexions en cours. On ne garde que l'empreinte du jeton : même avec une copie
    -- de la base, personne ne peut se connecter à la place d'un joueur.
    CREATE TABLE sessions (
        id         INTEGER PRIMARY KEY,                 -- sert aussi à savoir laquelle est la plus récente
        token_hash TEXT    NOT NULL UNIQUE,
        player_id  INTEGER NOT NULL REFERENCES players (id) ON DELETE CASCADE,
        created_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL
    );
    CREATE INDEX idx_sessions_player ON sessions (player_id);
    """,
    # ---- étape 2 : runs, classements, caisses, missions, série de connexion ----
    """
    ALTER TABLE players ADD COLUMN total_earned REAL    NOT NULL DEFAULT 0;   -- points gagnés depuis toujours (classement général)
    ALTER TABLE players ADD COLUMN crates       INTEGER NOT NULL DEFAULT 0 CHECK (crates >= 0);   -- caisses à ouvrir
    ALTER TABLE players ADD COLUMN runs_done    INTEGER NOT NULL DEFAULT 0;   -- runs terminés
    ALTER TABLE players ADD COLUMN streak       INTEGER NOT NULL DEFAULT 0;   -- jours de connexion d'affilée
    ALTER TABLE players ADD COLUMN streak_day   TEXT;                         -- dernier jour compté (AAAA-MM-JJ)

    -- Un run = une partie chronométrée. status : open (en cours), done (validé),
    -- rejected (score impossible), abandoned (jamais terminé).
    CREATE TABLE runs (
        id         INTEGER PRIMARY KEY,
        player_id  INTEGER NOT NULL REFERENCES players (id) ON DELETE CASCADE,
        mode       TEXT    NOT NULL,
        status     TEXT    NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done', 'rejected', 'abandoned')),
        started_at INTEGER NOT NULL,
        ended_at   INTEGER,
        score      REAL    NOT NULL DEFAULT 0,
        hits       INTEGER NOT NULL DEFAULT 0,
        misses     INTEGER NOT NULL DEFAULT 0,
        golden     INTEGER NOT NULL DEFAULT 0,
        best_combo INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX idx_runs_player ON runs (player_id, status);
    CREATE INDEX idx_runs_classement ON runs (mode, status, ended_at, score);

    -- Missions du jour : 3 lignes par joueur et par jour.
    CREATE TABLE missions (
        player_id     INTEGER NOT NULL REFERENCES players (id) ON DELETE CASCADE,
        day           TEXT    NOT NULL,
        slot          INTEGER NOT NULL,
        kind          TEXT    NOT NULL,
        param         TEXT,
        target        INTEGER NOT NULL,
        progress      INTEGER NOT NULL DEFAULT 0,
        reward_kind   TEXT    NOT NULL,
        reward_amount INTEGER NOT NULL,
        done          INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (player_id, day, slot)
    ) WITHOUT ROWID;
    """,
    # ---- étape 3 : caisses de 4 raretés, missions par difficulté avec récompense à récupérer ----
    """
    ALTER TABLE players RENAME COLUMN crates TO crates_common;
    ALTER TABLE players ADD COLUMN crates_rare      INTEGER NOT NULL DEFAULT 0 CHECK (crates_rare >= 0);
    ALTER TABLE players ADD COLUMN crates_epic      INTEGER NOT NULL DEFAULT 0 CHECK (crates_epic >= 0);
    ALTER TABLE players ADD COLUMN crates_legendary INTEGER NOT NULL DEFAULT 0 CHECK (crates_legendary >= 0);

    DELETE FROM missions;      -- les missions du jour sont retirées au nouveau format
    ALTER TABLE missions ADD COLUMN category   TEXT    NOT NULL DEFAULT '';
    ALTER TABLE missions ADD COLUMN difficulty TEXT    NOT NULL DEFAULT 'facile';
    ALTER TABLE missions ADD COLUMN threshold  INTEGER NOT NULL DEFAULT 0;   -- le seuil (% ou points)
    ALTER TABLE missions ADD COLUMN claimed    INTEGER NOT NULL DEFAULT 0;   -- 1 = récompense récupérée
    """,
    # ---- étape 4 : modes de jeu Challenge et Survie ----
    """
    ALTER TABLE runs ADD COLUMN kind    TEXT NOT NULL DEFAULT 'classic';   -- classic, challenge ou survival
    ALTER TABLE runs ADD COLUMN time_ms INTEGER;                           -- chrono du Challenge
    DROP INDEX idx_runs_classement;
    CREATE INDEX idx_runs_classement ON runs (kind, mode, status, ended_at);
    """,
    # ---- étape 5 : le bonus Slow passe de 3 à 4 niveaux (un premier niveau moins cher) ----
    # Les anciens niveaux 1, 2, 3 deviennent 2, 3, 4 : personne ne perd ce qu'il a acheté.
    # L'ancienne colonne slow_level reste dans la table mais n'est plus utilisée.
    """
    ALTER TABLE players ADD COLUMN slow_stage INTEGER NOT NULL DEFAULT 0 CHECK (slow_stage BETWEEN 0 AND 4);
    UPDATE players SET slow_stage = slow_level + 1 WHERE slow_level > 0;
    """,
]


def _connexion():
    conn = sqlite3.connect(DB, timeout=5, isolation_level=None)  # transactions gérées à la main
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@contextmanager
def db():
    """Lecture simple."""
    conn = _connexion()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction():
    """Écriture : tout réussit ou rien n'est modifié. Le verrou pris dès le début empêche
    deux achats lancés en même temps de dépenser deux fois les mêmes points."""
    conn = _connexion()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()


def _ouvrir_base(mode):
    """Ouvre la base dans ce mode de journal et vérifie qu'on peut vraiment y écrire."""
    conn = _connexion()
    try:
        conn.execute(f"PRAGMA journal_mode = {mode}")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("COMMIT")
        return conn, None
    except sqlite3.Error as erreur:
        conn.close()
        return None, erreur


def init_db():
    nouvelle = not os.path.exists(DB)
    # Le mode WAL est le plus rapide, mais certains disques ne le supportent pas (dossier
    # chiffré, clé USB, dossier partagé, disque réseau...) : SQLite répond alors
    # "disk I/O error". Dans ce cas on passe au mode classique, qui marche partout.
    conn, erreur = _ouvrir_base("WAL")
    if conn is None:
        print(f"ATTENTION : mode WAL indisponible ici ({erreur}). Passage au mode classique.")
        if nouvelle:  # base toute neuve et encore vide : on repart d'un fichier propre
            for suffixe in ("", "-wal", "-shm", "-journal"):
                try:
                    os.remove(DB + suffixe)
                except OSError:
                    pass
        conn, erreur = _ouvrir_base("DELETE")
    if conn is None:
        dossier = os.path.dirname(DB)
        raise SystemExit(
            f"\nIMPOSSIBLE D'OUVRIR LA BASE {DB}\n  Erreur : {erreur}\n"
            "  A verifier, dans l'ordre :\n"
            "   1. un autre serveur tourne-t-il encore ?        pgrep -a uvicorn\n"
            f"   2. le disque est-il plein ?                     df -h {dossier}\n"
            f"   3. a qui sont les fichiers ?                    ls -la {dossier}\n"
            "      (ils doivent appartenir au compte qui lance le serveur, pas a root)\n"
            f"   4. sur quel type de disque est le dossier ?     df -T {dossier}\n"
            "  Si la base ne contient rien d'important, supprime catchme.db, catchme.db-wal et\n"
            "  catchme.db-shm puis relance : elle sera recreee.\n")
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for numero in range(version, len(MIGRATIONS)):
            conn.executescript("BEGIN;" + MIGRATIONS[numero] + f"PRAGMA user_version = {numero + 1}; COMMIT;")
    finally:
        conn.close()
    if nouvelle:
        try:
            os.chmod(DB, 0o600)  # lisible uniquement par le compte qui lance le serveur
        except OSError:
            pass


init_db()

# ==============================
# LIMITEUR D'ESSAIS (en mémoire)
# ==============================
class Limiteur:
    def __init__(self):
        self._essais = {}
        self._verrou = threading.Lock()

    def _recents(self, cle, fenetre, maintenant):
        file = self._essais.setdefault(cle, deque())
        while file and file[0] <= maintenant - fenetre:
            file.popleft()
        return file

    def bloque(self, cle, maxi, fenetre):
        """Secondes à attendre si la limite est atteinte, sinon 0."""
        maintenant = time.monotonic()
        with self._verrou:
            file = self._recents(cle, fenetre, maintenant)
            return int(file[0] + fenetre - maintenant) + 1 if len(file) >= maxi else 0

    def compter(self, cle, fenetre):
        maintenant = time.monotonic()
        with self._verrou:
            self._recents(cle, fenetre, maintenant).append(maintenant)
            if len(self._essais) > 20000:  # ménage si la table grossit trop
                for k in [k for k, f in self._essais.items() if not f or f[-1] <= maintenant - 3600]:
                    del self._essais[k]

    def oublier(self, cle):
        with self._verrou:
            self._essais.pop(cle, None)


limiteur = Limiteur()
ECHECS_MAX, ECHECS_FENETRE = 5, 300            # 5 mauvais mots de passe par compte / 5 min
LOGIN_IP_MAX, LOGIN_IP_FENETRE = 30, 300       # 30 essais de connexion par adresse / 5 min
INSCRIPTIONS_IP_MAX, INSCRIPTIONS_FENETRE = 5, 3600   # 5 comptes créés par adresse / heure
INSCRIPTIONS_TOTAL_MAX = 200                   # et 200 par heure au total


def adresse_client(request: Request) -> str:
    if PROXY_DE_CONFIANCE:
        ip = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for", "").split(",")[0]
        if ip.strip():
            return ip.strip()[:64]
    return request.client.host if request.client else "?"


def attendre(secondes):
    minutes = max(1, round(secondes / 60))
    raise HTTPException(429, f"Trop d'essais. Réessaie dans {minutes} min.")


# ==============================
# MOTS DE PASSE ET JETONS
# ==============================
PSEUDO_OK = re.compile(r"^[\w.\-]{3,25}$")  # lettres, chiffres, _ . -


def normaliser_pseudo(pseudo: str):
    pseudo = unicodedata.normalize("NFKC", pseudo).strip()
    return pseudo, pseudo.casefold()


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    return bcrypt.hashpw(mot_de_passe.encode("utf-8"), bcrypt.gensalt(BCRYPT_COUT)).decode("ascii")


def verifier_mot_de_passe(mot_de_passe: str, empreinte: str) -> bool:
    try:
        return bcrypt.checkpw(mot_de_passe.encode("utf-8"), empreinte.encode("ascii"))
    except ValueError:
        return False


# Vérifiée quand le pseudo n'existe pas : la réponse met le même temps que pour un vrai
# compte, donc on ne peut pas deviner quels pseudos existent en chronométrant.
EMPREINTE_FACTICE = hacher_mot_de_passe(secrets.token_urlsafe(16))


def empreinte_jeton(jeton: str) -> str:
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


def maintenant() -> int:
    return int(time.time())


# ==============================
# OUTILS
# ==============================
def champ(data, cle, maxi=200) -> str:
    valeur = data.get(cle) if isinstance(data, dict) else None
    if not isinstance(valeur, str) or len(valeur) > maxi:
        raise HTTPException(400, "Requête invalide")
    return valeur


def fmt(valeur) -> str:
    return str(int(valeur)) if float(valeur).is_integer() else f"{valeur:.1f}"


def aujourdhui() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def minuit() -> int:
    """Heure Unix du début de la journée (heure du serveur)."""
    t = time.localtime()
    return int(time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1)))


def debut_semaine() -> int:
    """Lundi 00:00 : les classements de la semaine repartent de là."""
    return minuit() - time.localtime().tm_wday * 86400


def crediter(conn, player_id, points):
    conn.execute("UPDATE players SET score = score + ?, total_earned = total_earned + ? WHERE id = ?",
                 (points, points, player_id))


def texte_mission(m) -> str:
    mode, seuil, n = NOMS_MODES.get(m["param"], ""), m["threshold"], m["target"]
    s = "s" if n > 1 else ""
    mini = f" ({CIBLES_MIN_MISSION} cibles touchées minimum)"   # la condition est écrite dans la mission
    return {
        "precision": f"Classique {mode} : termine un run avec au moins {seuil} % de précision" + mini,
        "score": f"Classique {mode} : marque au moins {seuil} points en un seul run",
        "challenge_time": f"Challenge {mode} : termine en moins de {seuil} secondes",
        "survival_hits": f"Survie {mode} : touche au moins {seuil} cibles en un run",
        "combo": f"Atteins un combo de {n}",
        "hits": f"Touche {n} cibles",
        "golden": f"Touche {n} cible{s} dorée{s}",
        "runs": f"Termine {n} run{s}" + (f" en {mode}" if mode else ""),
        "no_bomb": f"Classique {mode} : termine {n} run{s} sans toucher de bombe" + mini,
        "perfect": f"Classique {mode} : termine un run sans aucun clic raté" + mini,
    }.get(m["kind"], m["kind"])


def texte_recompense(rarete, points) -> str:
    return f"Caisse {NOMS_RARETES[rarete]} + {points} points"


def donner_caisse(conn, player_id, rarete, nombre=1):
    colonne = COLONNE_CAISSE[rarete]  # nom pris dans NOTRE table
    conn.execute(f"UPDATE players SET {colonne} = {colonne} + ? WHERE id = ?", (nombre, player_id))


def missions_du_jour(conn, player_id):
    """Les 3 missions du jour du joueur (facile, moyenne, difficile), créées au premier appel."""
    jour = aujourdhui()
    requete = "SELECT * FROM missions WHERE player_id = ? AND day = ? ORDER BY slot"
    lignes = conn.execute(requete, (player_id, jour)).fetchall()
    if not lignes:
        conn.execute("DELETE FROM missions WHERE player_id = ? AND day <> ?", (player_id, jour))
        hasard = random.Random(f"{jour}:{player_id}")
        prises = set()
        for slot, (difficulte, choix) in enumerate(MISSIONS.items()):
            libres = [m for m in choix if m[0] not in prises] or list(choix)  # catégories différentes
            categorie, kind, mode, seuil, objectif = hasard.choice(libres)
            prises.add(categorie)
            rarete, points = RECOMPENSES_MISSIONS[difficulte]
            conn.execute("""INSERT OR IGNORE INTO missions (player_id, day, slot, kind, param, target, threshold,
                            category, difficulty, reward_kind, reward_amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                         (player_id, jour, slot, kind, mode, objectif, seuil, categorie, difficulte, rarete, points))
        lignes = conn.execute(requete, (player_id, jour)).fetchall()
    return lignes


def liste_missions(lignes) -> list:
    return [{"slot": m["slot"], "category": m["category"], "difficulty": m["difficulty"],
             "label": texte_mission(m), "progress": m["progress"], "target": m["target"],
             "reward": texte_recompense(m["reward_kind"], m["reward_amount"]), "rarity": m["reward_kind"],
             "done": bool(m["done"]), "claimed": bool(m["claimed"])} for m in lignes]


def etat_joueur(conn, player_id) -> dict:
    """Ce que le jeu a le droit de savoir sur un joueur (jamais l'empreinte du mot de passe)."""
    p = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
    themes = [r[0] for r in conn.execute("SELECT theme FROM player_themes WHERE player_id = ? ORDER BY bought_at",
                                         (player_id,))]
    # meilleur score en Classique et en Survie, meilleur temps (le plus court) en Challenge
    records = {genre: {} for genre in GENRES}
    for r in conn.execute("""SELECT kind, mode, MAX(score) AS score, MIN(time_ms) AS temps FROM runs
                             WHERE player_id = ? AND status = 'done' GROUP BY kind, mode""", (player_id,)):
        if r["kind"] in records:
            records[r["kind"]][r["mode"]] = r["temps"] if r["kind"] == "challenge" else r["score"]
    missions = missions_du_jour(conn, player_id)
    return {"pseudo": p["pseudo"], "score": p["score"], "slow": p["slow_stage"], "aide": p["aide_level"],
            "multi": p["multi_level"], "themes": themes, "theme": p["theme"],
            "total": p["total_earned"], "streak": p["streak"], "runs": p["runs_done"], "best": records,
            "crates": {r: p[COLONNE_CAISSE[r]] for r in RARETES},
            "missions_done": sum(1 for m in missions if m["done"]), "missions_total": len(missions),
            "missions_to_claim": sum(1 for m in missions if m["done"] and not m["claimed"])}


def joueur_connecte(authorization: str = Header(default="")) -> dict:
    """Vérifie l'en-tête  Authorization: Bearer <jeton>  et renvoie le joueur."""
    jeton = authorization[7:].strip() if authorization[:7].lower() == "bearer " else ""
    if not 20 <= len(jeton) <= 200:
        raise HTTPException(401, "Connexion requise")
    h = empreinte_jeton(jeton)
    with db() as conn:
        ligne = conn.execute("SELECT player_id FROM sessions WHERE token_hash = ? AND expires_at > ?",
                             (h, maintenant())).fetchone()
    if not ligne:
        raise HTTPException(401, "Session expirée, reconnecte-toi")
    return {"id": ligne["player_id"], "token_hash": h}


# ==============================
# APPLICATION
# ==============================
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)  # pas de page de doc publique


@app.middleware("http")
async def limite_taille(request: Request, call_next):
    taille = request.headers.get("content-length")
    if taille and (not taille.isdigit() or int(taille) > 4096):
        return JSONResponse({"detail": "Requête trop grande"}, status_code=413)
    return await call_next(request)


@app.exception_handler(HTTPException)
async def erreur_http(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def erreur_validation(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"detail": "Requête invalide"})


@app.exception_handler(Exception)
async def erreur_interne(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Erreur serveur"})  # aucun détail technique


# ---------- Comptes ----------
@app.post("/register", status_code=201)
def register(request: Request, data: dict = Body(...)):
    pseudo, norme = normaliser_pseudo(champ(data, "pseudo", 64))
    mot_de_passe = champ(data, "password", 200)

    if not PSEUDO_OK.match(pseudo):
        raise HTTPException(400, "Pseudo : 3 à 25 caractères (lettres, chiffres, _ . -)")
    if not 8 <= len(mot_de_passe) or len(mot_de_passe.encode("utf-8")) > 72:
        raise HTTPException(400, "Mot de passe : 8 à 72 caractères")
    if mot_de_passe.casefold() == norme:
        raise HTTPException(400, "Le mot de passe doit être différent du pseudo")

    ip = adresse_client(request)
    attente = (limiteur.bloque("inscription:" + ip, INSCRIPTIONS_IP_MAX, INSCRIPTIONS_FENETRE)
               or limiteur.bloque("inscription:*", INSCRIPTIONS_TOTAL_MAX, INSCRIPTIONS_FENETRE))
    if attente:
        attendre(attente)

    empreinte = hacher_mot_de_passe(mot_de_passe)
    try:
        with transaction() as conn:
            cur = conn.execute(
                "INSERT INTO players (pseudo, pseudo_norm, password_hash, theme, created_at) VALUES (?, ?, ?, ?, ?)",
                (pseudo, norme, empreinte, THEME_DEFAUT, maintenant()))
            conn.execute("INSERT INTO player_themes (player_id, theme, bought_at) VALUES (?, ?, ?)",
                         (cur.lastrowid, THEME_DEFAUT, maintenant()))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Pseudo déjà utilisé")

    limiteur.compter("inscription:" + ip, INSCRIPTIONS_FENETRE)
    limiteur.compter("inscription:*", INSCRIPTIONS_FENETRE)
    return {"status": "ok"}


def bonus_du_jour(conn, player_id):
    """Première connexion de la journée : fait avancer la série et donne la récompense.
    Renvoie None si le bonus du jour a déjà été pris."""
    p = conn.execute("SELECT streak, streak_day FROM players WHERE id = ?", (player_id,)).fetchone()
    jour = aujourdhui()
    if p["streak_day"] == jour:
        return None
    hier = time.strftime("%Y-%m-%d", time.localtime(minuit() - 43200))  # midi de la veille
    serie = p["streak"] + 1 if p["streak_day"] == hier else 1
    points = SERIE_POINTS * min(serie, SERIE_PLAFOND)
    rarete = next((r for tous_les, r in SERIE_CAISSES if serie % tous_les == 0), None)
    conn.execute("UPDATE players SET streak = ?, streak_day = ? WHERE id = ?", (serie, jour, player_id))
    crediter(conn, player_id, points)
    if rarete:
        donner_caisse(conn, player_id, rarete)
    return {"streak": serie, "points": points, "crate": rarete}


@app.post("/login")
def login(request: Request, data: dict = Body(...)):
    version = data.get("client") if isinstance(data, dict) else None
    if isinstance(version, bool) or not isinstance(version, int) or version < VERSION_JEU_MIN:
        raise HTTPException(426, "Version du jeu trop ancienne : télécharge la dernière version.")
    pseudo, norme = normaliser_pseudo(champ(data, "pseudo", 64))
    mot_de_passe = champ(data, "password", 200)
    ip = adresse_client(request)

    attente = (limiteur.bloque("echec:" + norme, ECHECS_MAX, ECHECS_FENETRE)
               or limiteur.bloque("login:" + ip, LOGIN_IP_MAX, LOGIN_IP_FENETRE))
    if attente:
        attendre(attente)
    limiteur.compter("login:" + ip, LOGIN_IP_FENETRE)

    with db() as conn:
        joueur = conn.execute("SELECT id, password_hash FROM players WHERE pseudo_norm = ?", (norme,)).fetchone()
    bon = verifier_mot_de_passe(mot_de_passe, joueur["password_hash"] if joueur else EMPREINTE_FACTICE)
    if not joueur or not bon:
        limiteur.compter("echec:" + norme, ECHECS_FENETRE)
        raise HTTPException(401, "Identifiants incorrects")  # même message dans les deux cas
    limiteur.oublier("echec:" + norme)

    jeton = secrets.token_urlsafe(32)  # 256 bits d'aléatoire
    t = maintenant()
    with transaction() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (t,))
        conn.execute("INSERT INTO sessions (token_hash, player_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                     (empreinte_jeton(jeton), joueur["id"], t, t + SESSION_JOURS * 86400))
        # on ne garde que les SESSIONS_MAX connexions les plus récentes du joueur
        conn.execute("""DELETE FROM sessions WHERE player_id = ? AND id NOT IN (
                            SELECT id FROM sessions WHERE player_id = ? ORDER BY id DESC LIMIT ?)""",
                     (joueur["id"], joueur["id"], SESSIONS_MAX))
        conn.execute("UPDATE players SET last_login_at = ? WHERE id = ?", (t, joueur["id"]))
        bonus = bonus_du_jour(conn, joueur["id"])
        etat = etat_joueur(conn, joueur["id"])
    return {"status": "ok", "token": jeton, "player": etat, "daily": bonus}


@app.post("/session/resume")
def reprendre_session(data: dict = Body(...), joueur: dict = Depends(joueur_connecte)):
    """Version téléphone : le jeu garde son jeton et rouvre la session à chaque lancement,
    sans redemander le mot de passe. Même contrôle de version et même bonus du jour qu'à la
    connexion ; la session est prolongée de SESSION_JOURS jours."""
    version = data.get("client") if isinstance(data, dict) else None
    if isinstance(version, bool) or not isinstance(version, int) or version < VERSION_JEU_MIN:
        raise HTTPException(426, "Version du jeu trop ancienne : télécharge la dernière version.")
    t = maintenant()
    with transaction() as conn:
        conn.execute("UPDATE sessions SET expires_at = ? WHERE token_hash = ?",
                     (t + SESSION_JOURS * 86400, joueur["token_hash"]))
        conn.execute("UPDATE players SET last_login_at = ? WHERE id = ?", (t, joueur["id"]))
        bonus = bonus_du_jour(conn, joueur["id"])
        etat = etat_joueur(conn, joueur["id"])
    return {"status": "ok", "player": etat, "daily": bonus}


@app.post("/logout")
def logout(joueur: dict = Depends(joueur_connecte)):
    with transaction() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (joueur["token_hash"],))
    return {"status": "ok"}


@app.get("/me")
def me(joueur: dict = Depends(joueur_connecte)):
    with db() as conn:
        return {"player": etat_joueur(conn, joueur["id"])}


# ---------- Boutique ----------
@app.get("/catalog")
def catalog():
    """Les prix et règles officiels, pour que le jeu affiche les mêmes que le serveur."""
    return {"upgrades": {k: list(v[1]) for k, v in AMELIORATIONS.items()}, "themes": THEMES,
            "run_duration": DUREE_RUN, "combo_tiers": [list(p) for p in PALIERS_COMBO],
            "min_client": VERSION_JEU_MIN,
            "golden_bonus": BONUS_DOREE, "golden_chance": CHANCE_DOREE, "bomb_chance": CHANCE_BOMBE,
            "bomb_penalty": PENALITE_BOMBE, "miss_penalty": PENALITE_RATE, "combo_seconds": COMBO_DUREE, "runs_per_crate": RUNS_PAR_CAISSE,
            "crates": [{"key": r, "name": NOMS_RARETES[r], "loot": [list(lot) for lot in BUTIN[r]]} for r in RARETES],
            "kinds": {g: list(modes) for g, modes in GENRES.items()},
            "challenge": {"targets": CHALLENGE_CIBLES, "miss_seconds": CHALLENGE_PENALITE_RATE,
                          "max_seconds": CHALLENGE_DUREE_MAX, "reference": CHALLENGE_REFERENCE},
            "survival": {"lives": SURVIE_VIES, "max_seconds": SURVIE_DUREE_MAX, "speedup": SURVIE_ACCELERATION,
                         "delays": {m: list(d) for m, d in SURVIE_DELAIS.items()}}}


@app.post("/shop/upgrade")
def acheter_amelioration(data: dict = Body(...), joueur: dict = Depends(joueur_connecte)):
    type_ = champ(data, "type", 20)
    if type_ not in AMELIORATIONS:
        raise HTTPException(400, "Amélioration inconnue")
    colonne, prix = AMELIORATIONS[type_]  # nom de colonne pris dans NOTRE table, jamais dans la requête
    with transaction() as conn:
        p = conn.execute(f"SELECT score, {colonne} AS niveau FROM players WHERE id = ?", (joueur["id"],)).fetchone()
        if p["niveau"] >= len(prix):
            raise HTTPException(409, "Niveau maximum déjà atteint")
        cout = prix[p["niveau"]]
        if p["score"] < cout:
            raise HTTPException(400, f"Score insuffisant ({fmt(p['score'])} < {cout})")
        conn.execute(f"UPDATE players SET score = score - ?, {colonne} = {colonne} + 1 WHERE id = ?",
                     (cout, joueur["id"]))
        return {"status": "ok", "player": etat_joueur(conn, joueur["id"])}


def _theme_demande(data) -> str:
    cle = champ(data, "key", 40)
    if cle not in THEMES:
        raise HTTPException(400, "Thème inconnu")
    return cle


@app.post("/themes/buy")
def acheter_theme(data: dict = Body(...), joueur: dict = Depends(joueur_connecte)):
    cle = _theme_demande(data)
    with transaction() as conn:
        if conn.execute("SELECT 1 FROM player_themes WHERE player_id = ? AND theme = ?",
                        (joueur["id"], cle)).fetchone():
            raise HTTPException(409, "Thème déjà possédé")
        score = conn.execute("SELECT score FROM players WHERE id = ?", (joueur["id"],)).fetchone()["score"]
        if score < THEMES[cle]:
            raise HTTPException(400, f"Score insuffisant ({fmt(score)} < {THEMES[cle]})")
        conn.execute("INSERT INTO player_themes (player_id, theme, bought_at) VALUES (?, ?, ?)",
                     (joueur["id"], cle, maintenant()))
        conn.execute("UPDATE players SET score = score - ?, theme = ? WHERE id = ?", (THEMES[cle], cle, joueur["id"]))
        return {"status": "ok", "player": etat_joueur(conn, joueur["id"])}


@app.post("/themes/equip")
def equiper_theme(data: dict = Body(...), joueur: dict = Depends(joueur_connecte)):
    cle = _theme_demande(data)
    with transaction() as conn:
        if not conn.execute("SELECT 1 FROM player_themes WHERE player_id = ? AND theme = ?",
                            (joueur["id"], cle)).fetchone():
            raise HTTPException(403, "Thème non possédé")
        conn.execute("UPDATE players SET theme = ? WHERE id = ?", (cle, joueur["id"]))
        return {"status": "ok", "player": etat_joueur(conn, joueur["id"])}


# ---------- Runs ----------
def palier_combo(combo) -> float:
    return next(m for seuil, m in PALIERS_COMBO if combo >= seuil)


def _entier(data, cle, maxi) -> int:
    v = data.get(cle) if isinstance(data, dict) else None
    if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= maxi:
        raise HTTPException(400, "Requête invalide")
    return v


@app.post("/run/start")
def run_start(data: dict = Body(...), joueur: dict = Depends(joueur_connecte)):
    mode = champ(data, "mode", 20)
    genre = champ(data, "kind", 20) if "kind" in data else "classic"
    if genre not in GENRES:
        raise HTTPException(400, "Mode de jeu inconnu")
    if mode not in GENRES[genre]:
        raise HTTPException(400, "Difficulté indisponible dans ce mode de jeu")
    with transaction() as conn:
        # un seul run à la fois par joueur : l'ancien, jamais terminé, est abandonné
        conn.execute("UPDATE runs SET status = 'abandoned', ended_at = ? WHERE player_id = ? AND status = 'open'",
                     (maintenant(), joueur["id"]))
        cur = conn.execute("INSERT INTO runs (player_id, mode, kind, started_at) VALUES (?, ?, ?, ?)",
                           (joueur["id"], mode, genre, maintenant()))
        return {"status": "ok", "run_id": cur.lastrowid, "kind": genre, "duration": DUREE_RUN}


def points_challenge(par_cible, temps_ms) -> float:
    """Points d'un Challenge réussi : plus le temps est court, plus ça rapporte."""
    bonus = min(CHALLENGE_BONUS[1], max(CHALLENGE_BONUS[0], CHALLENGE_REFERENCE * 1000 / temps_ms))
    return round(par_cible * CHALLENGE_CIBLES * bonus * 4) / 4


@app.post("/run/end")
def run_end(data: dict = Body(...), joueur: dict = Depends(joueur_connecte)):
    run_id = _entier(data, "run_id", 2 ** 62)
    hits = _entier(data, "hits", 100000)
    misses = _entier(data, "misses", 100000)
    golden = _entier(data, "golden", 100000)
    best_combo = _entier(data, "best_combo", 100000)
    bombes = _entier(data, "bombs", 100000) if "bombs" in data else 0
    temps_ms = _entier(data, "time_ms", 10 ** 7) if "time_ms" in data else 0
    score = data.get("score", 0)
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or score < 0:
        raise HTTPException(400, "Requête invalide")

    refus = None
    with transaction() as conn:
        run = conn.execute("SELECT * FROM runs WHERE id = ? AND player_id = ? AND status = 'open'",
                           (run_id, joueur["id"])).fetchone()
        if not run:
            raise HTTPException(409, "Ce run n'est plus en cours")
        t = maintenant()
        mode, genre = run["mode"], run["kind"]
        joue = t - run["started_at"]   # durée vue par le serveur (décompte et réseau compris)
        p = conn.execute("SELECT multi_level, runs_done FROM players WHERE id = ?", (joueur["id"],)).fetchone()
        par_cible = BASE_POINTS[mode] * (MULTIPLICATEURS_EASY if mode == "easy" else MULTIPLICATEURS)[p["multi_level"]]

        # --- Le résultat est-il possible ? ---
        incoherent = golden > hits or golden > 5 + hits * 0.3 or best_combo > hits
        score_max = par_cible * COMBO_MAX * ((hits - golden) + golden * BONUS_DOREE)
        mauvais_score = score > score_max + 1e-6 or abs(score * 4 - round(score * 4)) > 1e-6
        if genre == "classic":
            if joue < DUREE_RUN - RUN_AVANCE_MAX - PENALITE_BOMBE * min(bombes, BOMBES_MAX):
                refus = "Run terminé trop tôt"
            elif joue > DUREE_RUN + RUN_RETARD_MAX:
                refus = "Run expiré"
            elif incoherent or mauvais_score or hits > int(DUREE_RUN / INTERVALLE_MIN[mode]):
                refus = "Score refusé"
            temps_ms = None
        elif genre == "challenge":
            # le chrono annoncé ne peut pas être beaucoup plus court que le temps réellement écoulé
            if joue > CHALLENGE_DUREE_MAX + RUN_RETARD_MAX:
                refus = "Run expiré"
            elif (incoherent or hits + golden < CHALLENGE_CIBLES or hits > CHALLENGE_CIBLES
                  or temps_ms < CHALLENGE_TEMPS_MIN * 1000 or temps_ms > CHALLENGE_DUREE_MAX * 1000
                  or temps_ms < (joue - CHALLENGE_MARGE) * 1000):
                refus = "Temps refusé"
            else:
                score = points_challenge(par_cible, temps_ms)   # calculé ici, jamais envoyé par le jeu
        else:  # survival
            if joue > SURVIE_DUREE_MAX + RUN_RETARD_MAX:
                refus = "Run expiré"
            elif incoherent or mauvais_score or hits > int(joue / INTERVALLE_MIN[mode]) + 5:
                refus = "Score refusé"
            temps_ms = None

        if refus:
            conn.execute("UPDATE runs SET status = 'rejected', ended_at = ? WHERE id = ?", (t, run_id))
        else:
            if genre == "challenge":
                ancien = conn.execute("""SELECT MIN(time_ms) FROM runs WHERE player_id = ? AND mode = ?
                                         AND kind = 'challenge' AND status = 'done'""",
                                      (joueur["id"], mode)).fetchone()[0]
                record = ancien is None or temps_ms < ancien
            else:
                ancien = conn.execute("""SELECT MAX(score) FROM runs WHERE player_id = ? AND mode = ?
                                         AND kind = ? AND status = 'done'""",
                                      (joueur["id"], mode, genre)).fetchone()[0]
                record = ancien is None or score > ancien
            conn.execute("""UPDATE runs SET status = 'done', ended_at = ?, score = ?, hits = ?, misses = ?,
                            golden = ?, best_combo = ?, time_ms = ? WHERE id = ?""",
                         (t, score, hits, misses, golden, best_combo, temps_ms, run_id))
            crediter(conn, joueur["id"], score)
            compte = joue >= RUN_COMPTE_MIN   # empêche d'enchaîner des runs de 2 secondes pour les caisses
            caisse_offerte = compte and (p["runs_done"] + 1) % RUNS_PAR_CAISSE == 0
            if caisse_offerte:
                donner_caisse(conn, joueur["id"], "common")

            # --- Missions du jour : on fait avancer, la récompense sera à récupérer ---
            precision = 100 * hits / (hits + misses) if hits + misses else 0
            assez = hits >= CIBLES_MIN_MISSION
            classique = genre == "classic"
            accomplies = []
            for m in missions_du_jour(conn, joueur["id"]):
                if m["done"]:
                    continue
                k, bon_mode, progres = m["kind"], m["param"] in (None, mode), m["progress"]
                if k == "hits":
                    progres += hits
                elif k == "golden":
                    progres += golden
                elif k == "combo":
                    progres = max(progres, best_combo)
                elif bon_mode and ((k == "runs" and compte)
                                   or (classique and k == "precision" and assez and precision >= m["threshold"])
                                   or (classique and k == "score" and score >= m["threshold"])
                                   or (classique and k == "no_bomb" and assez and bombes == 0)
                                   or (classique and k == "perfect" and assez and misses == 0 and bombes == 0)
                                   or (genre == "challenge" and k == "challenge_time"
                                       and temps_ms < m["threshold"] * 1000)
                                   or (genre == "survival" and k == "survival_hits" and hits >= m["threshold"])):
                    progres += 1
                fini = progres >= m["target"]
                conn.execute("UPDATE missions SET progress = ?, done = ? WHERE player_id = ? AND day = ? AND slot = ?",
                             (min(progres, m["target"]), int(fini), joueur["id"], m["day"], m["slot"]))
                if fini:
                    accomplies.append({"label": texte_mission(m),
                                       "reward": texte_recompense(m["reward_kind"], m["reward_amount"])})

            if compte:
                conn.execute("UPDATE players SET runs_done = runs_done + 1 WHERE id = ?", (joueur["id"],))
            faits = p["runs_done"] + (1 if compte else 0)
            return {"status": "ok", "kind": genre, "score": score, "time_ms": temps_ms, "record": record,
                    "previous_best": ancien or 0, "crate": "common" if caisse_offerte else None,
                    "missions": accomplies, "next_crate_in": RUNS_PAR_CAISSE - faits % RUNS_PAR_CAISSE,
                    "player": etat_joueur(conn, joueur["id"])}
    raise HTTPException(400, refus)  # hors de la transaction : le refus reste enregistré


# ---------- Caisses ----------
@app.post("/crates/open")
def ouvrir_caisse(data: dict = Body(...), joueur: dict = Depends(joueur_connecte)):
    rarete = champ(data, "rarity", 20)
    if rarete not in BUTIN:
        raise HTTPException(400, "Caisse inconnue")
    colonne = COLONNE_CAISSE[rarete]
    with transaction() as conn:
        if conn.execute(f"SELECT {colonne} FROM players WHERE id = ?", (joueur["id"],)).fetchone()[0] < 1:
            raise HTTPException(400, "Aucune caisse de ce type à ouvrir")
        conn.execute(f"UPDATE players SET {colonne} = {colonne} - 1 WHERE id = ?", (joueur["id"],))

        # tirage : un nombre de 0 à 99, comparé aux chances cumulées de BUTIN
        tirage, cumul, lot = secrets.randbelow(100), 0, BUTIN[rarete][-1]
        for lot in BUTIN[rarete]:
            cumul += lot[0]
            if tirage < cumul:
                break
        _, kind, mini, maxi = lot
        recompense = None
        if kind == "theme":
            possedes = {r[0] for r in conn.execute("SELECT theme FROM player_themes WHERE player_id = ?",
                                                   (joueur["id"],))}
            manquants = [k for k in THEMES if k not in possedes]
            if manquants:
                cle = manquants[secrets.randbelow(len(manquants))]
                conn.execute("INSERT INTO player_themes (player_id, theme, bought_at) VALUES (?, ?, ?)",
                             (joueur["id"], cle, maintenant()))
                recompense = {"kind": "theme", "key": cle}
            else:
                mini = maxi = POINTS_SI_TOUS_LES_THEMES[rarete]
        if recompense is None:
            points = mini + 10 * secrets.randbelow((maxi - mini) // 10 + 1)
            crediter(conn, joueur["id"], points)
            recompense = {"kind": "points", "amount": points}
        return {"status": "ok", "rarity": rarete, "reward": recompense, "player": etat_joueur(conn, joueur["id"])}


# ---------- Missions ----------
@app.get("/missions")
def missions(joueur: dict = Depends(joueur_connecte)):
    with transaction() as conn:
        lignes = missions_du_jour(conn, joueur["id"])
        serie = conn.execute("SELECT streak FROM players WHERE id = ?", (joueur["id"],)).fetchone()["streak"]
    return {"missions": liste_missions(lignes), "streak": serie, "reset_in": minuit() + 86400 - maintenant()}


@app.post("/missions/claim")
def recuperer_mission(data: dict = Body(...), joueur: dict = Depends(joueur_connecte)):
    """Récupère la récompense d'une mission accomplie : une caisse et des points."""
    slot = _entier(data, "slot", 10)
    with transaction() as conn:
        m = next((m for m in missions_du_jour(conn, joueur["id"]) if m["slot"] == slot), None)
        if not m or not m["done"]:
            raise HTTPException(400, "Mission pas encore accomplie")
        if m["claimed"]:
            raise HTTPException(409, "Récompense déjà récupérée")
        conn.execute("UPDATE missions SET claimed = 1 WHERE player_id = ? AND day = ? AND slot = ?",
                     (joueur["id"], m["day"], slot))
        donner_caisse(conn, joueur["id"], m["reward_kind"])
        crediter(conn, joueur["id"], m["reward_amount"])
        return {"status": "ok", "reward": {"crate": m["reward_kind"], "points": m["reward_amount"]},
                "missions": liste_missions(missions_du_jour(conn, joueur["id"])),
                "player": etat_joueur(conn, joueur["id"])}


# ---------- Classements ----------
_classements = {}


@app.get("/leaderboard")
def leaderboard(board: str = "total", period: str = "all", kind: str = "classic"):
    """board = total (points gagnés depuis toujours) ou une difficulté ; kind = mode de jeu ;
    period = week ou all. En Challenge, le meilleur est le temps le plus court."""
    if kind not in GENRES or (board != "total" and board not in GENRES[kind]):
        raise HTTPException(400, "Classement inconnu")
    if period not in ("week", "all"):
        raise HTTPException(400, "Période inconnue")
    cle = (board, period, kind)
    cache = _classements.get(cle)
    if not cache or time.monotonic() - cache[0] > 2:  # recalculé au plus toutes les 2 secondes
        depuis = debut_semaine() if period == "week" else 0
        with db() as conn:
            if board == "total":
                lignes = [{"pseudo": r["pseudo"], "score": r["score"]} for r in conn.execute(
                    "SELECT pseudo, total_earned AS score FROM players ORDER BY total_earned DESC, id LIMIT 10")]
            elif kind == "challenge":
                lignes = [{"pseudo": r["pseudo"], "time_ms": r["temps"]} for r in conn.execute(
                    """SELECT p.pseudo AS pseudo, MIN(r.time_ms) AS temps FROM runs r JOIN players p ON p.id = r.player_id
                       WHERE r.kind = 'challenge' AND r.mode = ? AND r.status = 'done' AND r.ended_at >= ?
                       GROUP BY r.player_id ORDER BY temps ASC, MIN(r.ended_at) LIMIT 10""", (board, depuis))]
            else:
                lignes = [{"pseudo": r["pseudo"], "score": r["score"]} for r in conn.execute(
                    """SELECT p.pseudo AS pseudo, MAX(r.score) AS score FROM runs r JOIN players p ON p.id = r.player_id
                       WHERE r.kind = ? AND r.mode = ? AND r.status = 'done' AND r.ended_at >= ?
                       GROUP BY r.player_id ORDER BY score DESC, MIN(r.ended_at) LIMIT 10""", (kind, board, depuis))]
            cache = (time.monotonic(), lignes)
        _classements[cle] = cache
    return cache[1]
