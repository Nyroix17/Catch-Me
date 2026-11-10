"""
CATCH-ME - version 1.1

Il faut Python, pygame et requests :   pip install pygame requests
Le dossier "themes" doit rester à côté de ce fichier.
"""
import pygame
from random import randint
import random as _random
import math
import os
import re
import sys
import time
import threading
import requests
from array import array
from random import random

VERSION = "1.1"
VERSION_JEU = 2   # numéro envoyé au serveur : il refuse les versions trop anciennes
BASE_URL = "https://clickme.abrdns.com"

pseudo_joueur = ""
token_joueur = ""

# Windows : sans ça, quand l'affichage est réglé à 125 % ou 150 %, le système "ment" sur
# la taille de l'écran. Le plein écran changeait alors de résolution (long écran noir) et
# l'image restait entourée de noir. À faire AVANT de créer la moindre fenêtre.
if sys.platform == "win32":
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

pygame.mixer.pre_init(22050, -16, 1, 512)  # son : petit délai, 16 bits, mono
pygame.init()

_mixer = pygame.mixer.get_init()
if not _mixer or _mixer[1] != -16:  # sinon les sons du jeu ne peuvent pas être fabriqués
    try:
        pygame.mixer.quit()
        pygame.mixer.init(22050, -16, 1, 512, allowedchanges=0)
    except Exception:
        pass

# Taille de l'écran : sert seulement à choisir la taille de la fenêtre au lancement.
try:
    x, y = pygame.display.get_desktop_sizes()[0]
except Exception:
    _ecran = pygame.display.Info()
    x, y = _ecran.current_w, _ecran.current_h

# =========================
# FENETRE REDIMENSIONNABLE : TOUT EN POURCENTAGE
# =========================
# Le jeu se dessine directement dans la fenêtre : x et y sont SA taille en pixels.
# Aucune taille n'est fixe. Chaque mesure est écrite pour une fenêtre de référence de
# 1920 x 1080, puis convertie à la taille réelle :
#     L(v) : une largeur   -> même pourcentage de la LARGEUR de la fenêtre
#     H(v) : une hauteur   -> même pourcentage de la HAUTEUR de la fenêtre
#     U(v) : texte, cibles rondes, bordures -> suit la plus petite des deux échelles,
#            pour que rien ne soit déformé et que les textes tiennent dans leurs boutons
# Exemple : un bouton L(210) x H(96) fait toujours 10,9 % de la largeur et 8,9 % de la
# hauteur de la fenêtre, quelle que soit sa taille.
X_REF, Y_REF = 1920, 1080
taille_fenetre = (max(640, int(x * 0.8)), max(360, int(y * 0.8)))  # taille au lancement
plein_ecran = False
screen = pygame.display.set_mode(taille_fenetre, pygame.RESIZABLE)
x, y = screen.get_size()
SX, SY, S = x / X_REF, y / Y_REF, min(x / X_REF, y / Y_REF)


def L(v):
    return int(round(v * SX))


def H(v):
    return int(round(v * SY))


def U(v):
    return int(round(v * S))


def _adapter_toile():
    """Appelé au début de chaque image : si la fenêtre a changé de taille, on recalcule
    les échelles et on vide les images déjà préparées (elles seront refaites à la bonne
    taille). Tout le reste se recalcule tout seul puisque tout passe par L, H et U."""
    global x, y, screen, SX, SY, S
    screen = pygame.display.get_surface()
    fw, fh = screen.get_size()
    fw, fh = max(1, fw), max(1, fh)
    if (fw, fh) != (x, y):
        x, y = fw, fh
        SX, SY = x / X_REF, y / Y_REF
        S = min(SX, SY)
        _fonds.clear()
        _btn_cache.clear()
        _cibles.clear()


def souris():
    return pygame.mouse.get_pos()


def taille_bureau():
    try:
        return pygame.display.get_desktop_sizes()[0]
    except Exception:
        return (x, y)


def basculer_plein_ecran():
    """F11 : plein écran à la taille exacte de l'écran, et retour à la fenêtre d'avant."""
    global plein_ecran, taille_fenetre
    if plein_ecran:
        # En deux temps. D'abord on quitte le plein écran SANS changer de taille : demander
        # une autre taille pendant qu'on est encore en plein écran fait changer la
        # résolution de l'écran (le long écran noir). Ensuite seulement on redonne à la
        # fenêtre sa taille d'avant.
        pygame.display.set_mode(taille_bureau(), pygame.RESIZABLE)
        pygame.display.set_mode(taille_fenetre, pygame.RESIZABLE)
    else:
        taille_fenetre = pygame.display.get_surface().get_size()  # pour y revenir ensuite
        pygame.display.set_mode(taille_bureau(), pygame.FULLSCREEN)
    plein_ecran = not plein_ecran


def evenements():
    """Remplace pygame.event.get() : F11 est géré ici, le reste est transmis au jeu."""
    sortie = []
    recevoir_actualisation()
    for e in pygame.event.get():
        if e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
            basculer_plein_ecran()
            continue
        if e.type == pygame.KEYDOWN and e.key == pygame.K_F10:
            basculer_son()
            continue
        sortie.append(e)
    return sortie

pygame.display.set_caption("Catch-Me " + VERSION)
clock = pygame.time.Clock()

# =========================
# ETAT JOUEUR
# =========================
score = 0.0
delai = 1000

ralentisseur = []
but_bonus = []
multiplicateur = []
skinAcheter = [1]        # liste des id de thèmes possédés (1 = Far West, gratuit)
CouleurSkin = "farwest"  # clé du thème équipé
caisses = {}             # caisses à ouvrir, par rareté : {"common": 2, "rare": 0, ...}
serie = 0                # jours de connexion d'affilée
records = {}             # records par mode de jeu puis difficulté : {"classic": {"easy": 120}, ...}
missions_faites = (0, 3)  # (accomplies, total) aujourd'hui
missions_a_recuperer = 0  # récompenses de mission en attente

BASE_POINTS = {"easy": 1, "medium": 2, "hard": 5, "impossible": 15, "demonic": 50}

# Règles des runs. Remplacées à la connexion par celles du serveur, qui fait foi.
DUREE_RUN = 30
PALIERS_COMBO = [(40, 2.5), (20, 2), (8, 1.5), (0, 1)]  # (cibles d'affilée, multiplicateur)
BONUS_DOREE = 3
RUNS_PAR_CAISSE = 5
CHANCE_DOREE = 0.06      # chance que la cible principale soit dorée
CHANCE_BOMBE = 0.18      # chance qu'une bombe apparaisse (à partir de Medium)
PENALITE_BOMBE = 3.0     # secondes perdues en cliquant une bombe
PENALITE_RATE = 0.0      # points retirés par clic raté, en valeur de cible (0 = aucun)
COMBO_DUREE = 2.0        # secondes sans toucher de cible avant que le combo retombe à zéro
MODES_SANS_PENALITE = ("impossible", "demonic")  # modes où l'on clique à l'aveugle

# Modes de jeu : (clé serveur, nom, résumé) et les difficultés jouables dans chacun.
GENRES = [("classic", "Classique", "un maximum de points"), ("challenge", "Challenge", "le plus vite possible"),
          ("survival", "Survie", "tenir le plus longtemps")]
MODES_PAR_GENRE = {"classic": ["easy", "medium", "hard", "impossible", "demonic"],
                   "challenge": ["easy", "medium", "hard"], "survival": ["easy", "medium", "hard"]}
NOMS_MODES = {"easy": "Easy", "medium": "Medium", "hard": "Hard", "impossible": "Impossible", "demonic": "Demonic"}
# Challenge : nombre de cibles à toucher, secondes ajoutées par clic raté, durée maximum.
CHALLENGE = {"cibles": 30, "rate_s": 1.0, "max_s": 120.0}
# Survie : vies, durée maximum, accélération par cible touchée, (départ, minimum) du temps par cible en ms.
SURVIE = {"vies": 3, "max_s": 300.0, "acceleration": 0.97,
          "delais": {"easy": (2200, 550), "medium": (1700, 450), "hard": (1300, 380)}}

# Caisses : (clé serveur, nom, couleur). Le contenu (BUTIN) vient du serveur à la connexion.
RARETES = [("common", "Commune", (175, 175, 180)), ("rare", "Rare", (80, 150, 255)),
           ("epic", "Épique", (185, 100, 255)), ("legendary", "Légendaire", (255, 200, 60))]
BUTIN = {  # (chances sur 100, type, mini, maxi)
    "common": [(80, "points", 20, 60), (19, "points", 80, 150), (1, "theme", 0, 0)],
    "rare": [(65, "points", 80, 160), (32, "points", 200, 350), (3, "theme", 0, 0)],
    "epic": [(55, "points", 250, 450), (37, "points", 500, 800), (8, "theme", 0, 0)],
    "legendary": [(80, "points", 1000, 1800), (20, "theme", 0, 0)],
}

# =========================
# THEMES
# =========================
# Chaque thème change le fond, les boutons et les cibles à attraper.
#
# Pour utiliser de VRAIES IMAGES, dépose-les dans  themes/<key>/  (à côté de ce fichier) :
#     background.png            -> le fond (redimensionné à l'écran)
#     button.png                -> l'image des boutons
#     target.png                -> la cible à attraper (PNG transparent conseillé)
#     target_1.png, target_2... -> plusieurs images = animation image par image
#     hit.wav, miss.wav, golden.wav, bomb.wav (ou .ogg) -> les sons du thème
#     target_sheet_60ms.png     -> feuille de sprites : les images de l'animation côte à
#                                  côte dans des cases carrées (côté = hauteur du fichier),
#                                  "_60ms" = durée de chaque image (80 ms si absent).
#                                  preparer_images.py fabrique ce fichier à partir d'un GIF.
# Formats acceptés : png, jpg, jpeg, webp, gif, bmp.
# Si une image manque, le jeu dessine lui-même un remplacement aux couleurs du thème.
#
# Pour AJOUTER un thème : copie une ligne _pop(...) avec un nouvel id (ne jamais
# réutiliser ni changer un id existant : c'est lui qui est sauvegardé sur le serveur).

# Dossier du jeu. Dans une version .exe, c'est le dossier où se trouve l'exécutable,
# pour que le dossier "themes" posé à côté soit trouvé.
BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
THEMES_DIR = os.path.join(BASE_DIR, "themes")


def _pop(id_, key, name, price, c1, c2, accent, spin=False, icone="etoile"):
    """Thème "mème" : couleurs de secours + images à déposer dans themes/<key>/."""
    return dict(
        id=id_, key=key, name=name, price=price, decor="pop", cible="badge",
        fonts="comicsansms,arialrounded,verdana,dejavusans",
        ciel=(c1, c2), btn=accent, btn_hover=tuple(min(255, c + 30) for c in accent),
        bord=(255, 255, 255), texte=(255, 255, 255), accent=accent,
        panneau=tuple(int(c * 0.35) for c in c1), rayon=22, coupe=False, spin=spin, icone=icone,
    )


THEMES = [
    dict(
        id=1, key="farwest", name="Far West", price=0, decor="western", cible="crate",
        fonts="rockwell,georgia,dejavuserif,timesnewroman",
        ciel=((44, 30, 58), (236, 132, 62)),
        btn=(122, 72, 40), btn_hover=(152, 94, 54), bord=(226, 174, 88),
        texte=(252, 238, 210), accent=(226, 174, 88), panneau=(40, 24, 18),
        rayon=14, coupe=False, spin=False,
    ),
    dict(
        id=2, key="cyberpunk", name="Cyberpunk", price=3000, decor="cyber", cible="neon",
        fonts="consolas,couriernew,dejavusansmono,liberationmono",
        ciel=((8, 6, 24), (58, 12, 76)),
        btn=(18, 16, 44), btn_hover=(44, 20, 78), bord=(0, 240, 255),
        texte=(214, 250, 255), accent=(255, 0, 170), panneau=(10, 8, 28),
        rayon=0, coupe=True, spin=False,
    ),
    # ---- Chats (mèmes) ----  spin=True : l'image tourne sur elle-même
    _pop(3, "oiia", "OIIA Cat", 3000, (40, 190, 120), (20, 90, 160), (255, 196, 0), spin=True, icone="chat"),
    _pop(8, "huhcat", "Huh Cat", 3000, (250, 170, 90), (150, 70, 40), (90, 60, 160), icone="chat"),
    _pop(9, "bananacat", "Banana Cat", 3000, (255, 224, 90), (240, 150, 40), (120, 80, 30), icone="chat"),
    # ---- Brainrot : 1 thème par personnage ----
    _pop(4, "tralalero", "Tralalero Tralala", 6000, (40, 140, 220), (14, 40, 110), (30, 200, 230)),
    _pop(5, "bombardiro", "Bombardiro Crocodilo", 6000, (110, 140, 70), (40, 60, 36), (220, 120, 40)),
    _pop(6, "tungtung", "Tung Tung Tung Sahur", 6000, (190, 130, 80), (90, 50, 30), (240, 200, 120)),
    _pop(7, "ballerina", "Ballerina Cappuccina", 6000, (250, 170, 200), (150, 90, 70), (230, 90, 150)),
]

THEME_BY_ID = {t["id"]: t for t in THEMES}
THEME_BY_KEY = {t["key"]: t for t in THEMES}
THEME_DEFAUT = THEMES[0]



def theme_actuel():
    return THEME_BY_KEY.get(str(CouleurSkin).strip().lower(), THEME_DEFAUT)


def _preparer_dossiers():
    """Crée themes/<key>/ pour chaque thème afin de n'avoir qu'à y glisser les images."""
    try:
        for t in THEMES:
            os.makedirs(os.path.join(THEMES_DIR, t["key"]), exist_ok=True)
        lisez = os.path.join(THEMES_DIR, "LISEZ-MOI.txt")
        if not os.path.isfile(lisez):
            with open(lisez, "w", encoding="utf-8") as f:
                f.write(
                    "Un dossier par theme. Depose dedans (tout est optionnel) :\n"
                    "  background.png  -> fond du jeu\n"
                    "  button.png      -> image des boutons\n"
                    "  target.png      -> la cible a attraper (PNG transparent conseille)\n"
                    "  target_1.png, target_2.png, ... -> animation image par image\n"
                    "  target_sheet_60ms.png -> feuille de sprites (cases carrees, 60 ms par image)\n"
                    "preparer_images.py remplit ces dossiers tout seul (fond retire).\n"
                    "Formats : png, jpg, jpeg, webp, gif, bmp.\n"
                    "Relance le jeu apres avoir ajoute des images.\n"
                )
    except OSError:
        pass


_preparer_dossiers()

# =========================
# CHARGEMENT DES IMAGES
# =========================
_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
_assets = {}


def _charger(chemin):
    try:
        return pygame.image.load(chemin).convert_alpha()
    except Exception as e:
        print("Image illisible :", chemin, e)
        return None


def get_assets(t):
    if t["key"] in _assets:
        return _assets[t["key"]]
    dossier = os.path.join(THEMES_DIR, t["key"])
    a = {"fond": None, "btn": None, "cibles": [], "delai": 80, "sons": {}}
    try:
        fichiers = sorted(os.listdir(dossier))
    except OSError:
        fichiers = []
    for nom in fichiers:
        base, ext = os.path.splitext(nom.lower())
        if ext in (".wav", ".ogg") and base in ("hit", "miss", "golden", "bomb"):
            try:
                a["sons"][base] = pygame.mixer.Sound(os.path.join(dossier, nom))
            except Exception as e:
                print("Son illisible :", nom, e)
            continue
        if ext not in _EXT:
            continue
        chemin = os.path.join(dossier, nom)
        if base == "background" and a["fond"] is None:
            a["fond"] = _charger(chemin)
        elif base == "button" and a["btn"] is None:
            a["btn"] = _charger(chemin)
        elif base.startswith("target_sheet"):
            img = _charger(chemin)
            if img:
                cote = img.get_height()
                for n in range(max(1, img.get_width() // cote)):
                    a["cibles"].append(img.subsurface((n * cote, 0, cote, cote)).copy())
                duree = re.search(r"_(\d+)ms$", base)
                if duree:
                    a["delai"] = max(20, int(duree.group(1)))
        elif base.startswith("target"):
            img = _charger(chemin)
            if img:
                a["cibles"].append(img)
    _assets[t["key"]] = a
    return a


# =========================
# OUTILS DE DESSIN
# =========================
def _mix(c1, c2, k):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * k) for i in range(3))


def _degrade(w, h, haut, bas):
    s = pygame.Surface((w, max(1, h)))
    for yy in range(max(1, h)):
        pygame.draw.line(s, _mix(haut, bas, yy / max(1, h - 1)), (0, yy), (w, yy))
    return s


def _halo(surface, centre, rayon, couleur, alpha):
    g = pygame.Surface((rayon * 2, rayon * 2), pygame.SRCALPHA)
    pygame.draw.circle(g, (*couleur, alpha), (rayon, rayon), rayon)
    surface.blit(g, (centre[0] - rayon, centre[1] - rayon))


def _mesas(s, w, hz, graine, couleur, hauteur):
    rng = _random.Random(graine)
    px = -60
    while px < w:
        larg = rng.randint(max(40, w // 10), max(60, w // 5))
        ht = rng.uniform(0.45, 1.0) * hauteur
        pygame.draw.polygon(s, couleur, [
            (px, hz), (px + larg * 0.14, hz - ht), (px + larg * 0.86, hz - ht), (px + larg, hz)])
        px += larg + rng.randint(max(10, w // 30), max(20, w // 9))


def _cactus(s, cx, base, ht, couleur):
    l = max(4, int(ht * 0.17))
    pygame.draw.rect(s, couleur, (cx - l // 2, base - ht, l, ht), border_radius=l // 2)
    for sens, niveau, bras in ((-1, 0.45, 0.30), (1, 0.62, 0.24)):
        by = base - int(ht * niveau)
        bx = cx + sens * int(ht * 0.26)
        pygame.draw.rect(s, couleur, (min(cx, bx), by, abs(bx - cx) + l // 2, int(l * 0.8)),
                         border_radius=l // 3)
        hb = int(ht * bras)
        pygame.draw.rect(s, couleur, (bx - int(l * 0.4), by - hb, int(l * 0.8), hb + int(l * 0.8)),
                         border_radius=l // 3)


def _fond_western(w, h, t):
    hz = int(h * 0.68)
    u = min(h, w * 0.6)  # unité de taille des éléments du décor
    s = pygame.Surface((w, h))
    s.blit(_degrade(w, hz, t["ciel"][0], t["ciel"][1]), (0, 0))
    soleil = (int(w * 0.72), hz - int(u * 0.05))
    for r, a in ((0.30, 16), (0.22, 26), (0.16, 40)):
        _halo(s, soleil, int(u * r), (255, 190, 110), a)
    pygame.draw.circle(s, (255, 216, 146), soleil, int(u * 0.11))
    _mesas(s, w, hz, 3, (132, 66, 66), u * 0.17)
    _mesas(s, w, hz, 8, (88, 42, 48), u * 0.10)
    s.blit(_degrade(w, h - hz, (104, 52, 38), (44, 24, 22)), (0, hz))
    for fx, fy, k in ((0.10, 0.10, 0.20), (0.90, 0.06, 0.13), (0.56, 0.03, 0.08), (0.30, 0.04, 0.06)):
        _cactus(s, int(w * fx), hz + int(u * fy), int(u * k), (30, 22, 26))
    return s


def _fond_cyber(w, h, t):
    hz = int(h * 0.62)
    u = min(h, w * 0.6)
    s = pygame.Surface((w, h))
    s.blit(_degrade(w, hz, t["ciel"][0], t["ciel"][1]), (0, 0))
    centre = (w // 2, hz - int(u * 0.04))
    r = int(u * 0.20)
    _halo(s, centre, int(r * 1.5), (255, 0, 170), 26)
    disque = _degrade(r * 2, r * 2, (255, 214, 80), (255, 30, 150)).convert_alpha()
    masque = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    pygame.draw.circle(masque, (255, 255, 255, 255), (r, r), r)
    for n in range(6):  # bandes horizontales
        by = int(r * (1.05 + n * 0.16))
        pygame.draw.rect(masque, (0, 0, 0, 0), (0, by, r * 2, 3 + n * 2))
    disque.blit(masque, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    s.blit(disque, (centre[0] - r, centre[1] - r))
    rng = _random.Random(7)
    px = 0
    while px < w:  # immeubles
        larg = rng.randint(max(30, w // 28), max(50, w // 14))
        ht = rng.randint(int(u * 0.08), int(u * 0.34))
        pygame.draw.rect(s, (12, 10, 30), (px, hz - ht, larg, ht))
        for wy in range(hz - ht + 8, hz - 8, 14):
            for wx in range(px + 6, px + larg - 8, 12):
                if rng.random() < 0.28:
                    pygame.draw.rect(s, rng.choice(((0, 240, 255), (255, 0, 170), (255, 220, 90))),
                                     (wx, wy, 5, 7))
        px += larg + rng.randint(0, 6)
    pygame.draw.rect(s, (8, 4, 20), (0, hz, w, h - hz))
    for n in range(1, 15):  # grille en perspective
        gy = hz + int((h - hz) * (n / 14) ** 2)
        pygame.draw.line(s, _mix((8, 4, 20), (255, 0, 170), 0.25 + 0.6 * n / 14), (0, gy), (w, gy), 2)
    for n in range(-14, 15):
        pygame.draw.line(s, (150, 0, 120), (w // 2 + n * w // 60, hz), (w // 2 + n * w // 6, h), 2)
    pygame.draw.line(s, (0, 240, 255), (0, hz), (w, hz), 2)
    return s


def _fond_pop(w, h, t):
    s = _degrade(w, h, t["ciel"][0], t["ciel"][1])
    rng = _random.Random(t["id"])
    u = int(min(h, w * 0.6))
    for _ in range(26):
        _halo(s, (rng.randint(0, w), rng.randint(0, h)), rng.randint(u // 30, u // 7), (255, 255, 255), 16)
    return s


_fonds = {}


def get_fond(t):
    if t["key"] in _fonds:
        return _fonds[t["key"]]
    img = get_assets(t)["fond"]
    if img:
        iw, ih = img.get_size()
        k = max(x / iw, y / ih)
        img = pygame.transform.smoothscale(img, (max(1, int(iw * k) + 1), max(1, int(ih * k) + 1)))
        s = pygame.Surface((x, y))
        s.blit(img, ((x - img.get_width()) // 2, (y - img.get_height()) // 2))
    else:
        s = {"western": _fond_western, "cyber": _fond_cyber}.get(t["decor"], _fond_pop)(x, y, t)
    voile = pygame.Surface((x, y), pygame.SRCALPHA)
    voile.fill((0, 0, 0, 45))  # léger voile sombre pour la lisibilité
    s.blit(voile, (0, 0))
    _fonds[t["key"]] = s.convert()
    return _fonds[t["key"]]


def background():
    _adapter_toile()  # premier appel de chaque image : le jeu suit la fenêtre
    screen.blit(get_fond(theme_actuel()), (0, 0))


def flip():
    dessiner_annonce()
    pygame.display.flip()


# ---------- Polices / texte ----------
_fonts = {}


def get_font(taille, gras=False):
    t = theme_actuel()
    cle = (t["fonts"], int(taille), gras)
    if cle not in _fonts:
        try:
            _fonts[cle] = pygame.font.SysFont(t["fonts"], int(taille), bold=gras)
        except Exception:
            _fonts[cle] = pygame.font.Font(None, int(taille * 1.3))
    return _fonts[cle]


def police(taille, gras=False):
    """Police à la taille de référence `taille`, convertie à l'échelle de la fenêtre."""
    return get_font(max(6, U(taille)), gras)


def ecrire(txt, pos, taille=24, couleur=None, centre=False, gras=False, max_w=None, ombre=True):
    """`taille` est une taille de référence (fenêtre 1920 x 1080), mise à l'échelle ici."""
    txt = str(txt)
    couleur = couleur or theme_actuel()["texte"]
    taille = max(6, U(taille))
    f = get_font(taille, gras)
    while max_w and taille > 5 and f.size(txt)[0] > max_w:
        taille -= 1
        f = get_font(taille, gras)
    img = f.render(txt, True, couleur)
    r = img.get_rect()
    if centre:
        r.center = (int(pos[0]), int(pos[1]))
    else:
        r.topleft = (int(pos[0]), int(pos[1]))
    if ombre:
        o = f.render(txt, True, (0, 0, 0))
        o.set_alpha(150)
        d = max(1, U(2))
        screen.blit(o, r.move(d, d))
    screen.blit(img, r)
    return r


def titre(txt, cy=None):
    t = theme_actuel()
    cy = cy if cy is not None else int(y * 0.10)
    r = ecrire(txt, (x / 2, cy), 76, t["accent"], centre=True, gras=True, max_w=x - L(80))
    ly = r.bottom + U(6)
    pygame.draw.line(screen, t["accent"], (r.left, ly), (r.right, ly), max(1, U(3)))
    a, b = U(14), max(2, U(7))
    for px in (r.left - a, r.right + a):  # petits losanges décoratifs
        pygame.draw.polygon(screen, t["accent"], [(px, ly - b), (px + b, ly), (px, ly + b), (px - b, ly)])
    return r


def panneau(rect, alpha=185, t=None, bord=2):
    t = t or theme_actuel()
    s = pygame.Surface((max(1, rect.width), max(1, rect.height)), pygame.SRCALPHA)
    pygame.draw.rect(s, (*t["panneau"], alpha), s.get_rect(), border_radius=U(t["rayon"]))
    if bord:
        pygame.draw.rect(s, (*t["accent"], 230), s.get_rect(), max(1, U(bord)), border_radius=U(t["rayon"]))
    screen.blit(s, rect.topleft)


def hud(avec_pseudo=False):
    lignes = [f"Score : {fmt_score(score)}"]
    if avec_pseudo:
        lignes = [f"Pseudo : {pseudo_joueur}"] + lignes + [f"Série : {serie} jour" + ("s" if serie > 1 else "")]
    f = police(24, True)
    larg = max(f.size(l)[0] for l in lignes) + U(36)
    r = pygame.Rect(L(20), H(16), larg, U(16) + U(32) * len(lignes))
    panneau(r)
    for n, l in enumerate(lignes):
        ecrire(l, (r.x + U(18), r.y + U(10) + U(32) * n), 24, gras=True)


# ---------- Boutons ----------
_btn_cache = {}


def _surface_bouton(t, w, h, survol, etat):
    cle = (t["key"], w, h, survol, etat)
    if cle in _btn_cache:
        return _btn_cache[cle]
    o = max(2, U(5))          # décalage de l'ombre
    e3, e2 = max(1, U(3)), max(1, U(2))  # épaisseurs de traits
    s = pygame.Surface((w + o + 1, h + o + 1), pygame.SRCALPHA)
    r = min(U(t["rayon"]), h // 2)
    corps = pygame.Rect(0, 0, w, h)
    c = min(U(14), h // 3)
    poly = [(c, 0), (w - 1, 0), (w - 1, h - c), (w - c, h - 1), (0, h - 1), (0, c)]
    img = get_assets(t)["btn"]
    if img:
        im = pygame.transform.smoothscale(img, (w, h))
        if survol:
            im.fill((35, 35, 35), special_flags=pygame.BLEND_RGB_ADD)
        if etat == "acquis":
            im.fill((120, 120, 120), special_flags=pygame.BLEND_RGB_MULT)
        s.blit(im, (0, 0))
    else:
        col = t["btn_hover"] if survol else t["btn"]
        bord = t["bord"]
        if etat == "acquis":
            col = _mix(col, t["panneau"], 0.65)
            bord = _mix(bord, t["panneau"], 0.5)
        if t["coupe"]:
            pygame.draw.polygon(s, (0, 0, 0, 90), [(px + o, py + o) for px, py in poly])
            pygame.draw.polygon(s, col, poly)
            pygame.draw.polygon(s, t["accent"] if survol else bord, poly, e2)
            pygame.draw.line(s, t["accent"], (c + U(6), h - U(6)), (w // 3, h - U(6)), e2)
        else:
            pygame.draw.rect(s, (0, 0, 0, 90), corps.move(o, o), border_radius=r)
            pygame.draw.rect(s, col, corps, border_radius=r)
            if t["decor"] == "western":  # veines de planches + clous
                m = U(11)
                for ly in (h // 3, 2 * h // 3):
                    pygame.draw.line(s, _mix(col, (0, 0, 0), 0.22), (m, ly), (w - m, ly), e2)
                for px, py in ((m, m), (w - m, m), (m, h - m), (w - m, h - m)):
                    pygame.draw.circle(s, bord, (px, py), e3)
            else:
                pygame.draw.rect(s, _mix(col, (255, 255, 255), 0.18),
                                 (U(6), U(5), w - 2 * U(6), h // 2 - U(5)), border_radius=r)
            pygame.draw.rect(s, bord, corps, e3, border_radius=r)
    _btn_cache[cle] = s
    return s


def bouton(rect, label, sous=None, etat="normal"):
    """Dessine un bouton au style du thème et renvoie son rect (pour les clics)."""
    t = theme_actuel()
    survol = rect.collidepoint(souris())
    screen.blit(_surface_bouton(t, max(1, rect.width), max(1, rect.height), survol, etat), rect.topleft)
    coul = _mix(t["texte"], t["panneau"], 0.35) if etat == "acquis" else t["texte"]
    place = rect.width - U(20)
    if sous:
        ecrire(label, (rect.centerx, rect.centery - U(13)), 24, coul, True, True, place)
        ecrire(sous, (rect.centerx, rect.centery + U(16)), 18, coul, True, False, place)
    else:
        ecrire(label, rect.center, 26, coul, True, True, place)
    return rect


def rangee(n, cy, bw=200, bh=84, gap=24):
    """n rects de boutons centrés horizontalement autour de la hauteur cy (en pixels).
    bw, bh et gap sont des mesures de référence : largeur et espace en % de la largeur
    de la fenêtre, hauteur en % de sa hauteur."""
    bw, bh, gap = L(bw), H(bh), L(gap)
    bw = max(1, int(min(bw, (x - L(60) - (n - 1) * gap) / n)))
    x0 = (x - (n * bw + (n - 1) * gap)) // 2
    return [pygame.Rect(x0 + k * (bw + gap), int(cy - bh / 2), bw, max(1, bh)) for k in range(n)]


def bouton_retour():
    return bouton(pygame.Rect(L(24), int(y * 0.14), L(120), H(54)), "Back")


# ---------- Cibles ----------
_cibles = {}


def _disque(d, dessin):
    """Dessine en x3 puis réduit (anti-crénelage), avec une ombre portée."""
    D = d * 3
    brut = pygame.Surface((D, D), pygame.SRCALPHA)
    dessin(brut, D)
    net = pygame.transform.smoothscale(brut, (d, d))
    s = pygame.Surface((d + 12, d + 12), pygame.SRCALPHA)
    pygame.draw.circle(s, (0, 0, 0, 85), (d // 2 + 9, d // 2 + 10), d // 2)
    s.blit(net, (6, 6))
    return s


def _dessin_crate(s, D):
    """Caisse ronde : planches, croisillon, cerclage en fer et clous."""
    r = D / 2
    hp = D / 5
    tons = [(194, 136, 78), (176, 120, 66), (200, 144, 86), (170, 114, 60), (186, 128, 72)]
    for yy in range(D):
        dy = yy + 0.5 - r
        demi = math.sqrt(max(0.0, r * r - dy * dy))
        col = (118, 76, 40) if (yy % hp) < 3 else tons[int(yy // hp) % 5]
        pygame.draw.line(s, col, (int(r - demi), yy), (int(r + demi), yy))
    ep = max(3, int(D * 0.13))
    a = r * 0.68
    for sx in (1, -1):
        p1, p2 = (int(r - a * sx), int(r - a)), (int(r + a * sx), int(r + a))
        pygame.draw.line(s, (112, 68, 34), p1, p2, ep + 6)
        pygame.draw.line(s, (146, 94, 50), p1, p2, ep)
    c = (int(r), int(r))
    cercle = max(3, int(D * 0.09))
    pygame.draw.circle(s, (58, 44, 38), c, int(r), cercle)
    pygame.draw.circle(s, (226, 174, 88), c, int(r) - cercle, max(1, int(D * 0.018)))
    for ang in range(0, 360, 45):
        px = r + math.cos(math.radians(ang)) * (r - cercle / 2)
        py = r + math.sin(math.radians(ang)) * (r - cercle / 2)
        pygame.draw.circle(s, (226, 174, 88), (int(px), int(py)), max(1, int(D * 0.022)))


def _dessin_neon(s, D):
    r = int(D / 2)
    c = (r, r)
    pygame.draw.circle(s, (14, 12, 36), c, r)
    pygame.draw.circle(s, (0, 240, 255), c, r, max(3, int(D * 0.07)))
    pygame.draw.circle(s, (255, 0, 170), c, int(r * 0.62), max(2, int(D * 0.04)))
    e = max(2, int(D * 0.03))
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        pygame.draw.line(s, (0, 240, 255), (r + dx * int(r * 0.30), r + dy * int(r * 0.30)),
                         (r + dx * int(r * 0.86), r + dy * int(r * 0.86)), e)
    pygame.draw.circle(s, (255, 0, 170), c, max(2, int(r * 0.16)))


def _dessin_jeton(s, D, t):
    """Jeton de remplacement (dessin générique) tant que le thème n'a pas d'image target."""
    r = int(D / 2)
    acc = t["accent"]
    pygame.draw.circle(s, acc, (r, r), r)
    pygame.draw.circle(s, (255, 255, 255), (r, r), r, max(3, int(D * 0.08)))
    clair = 0.3 * acc[0] + 0.59 * acc[1] + 0.11 * acc[2] > 165
    encre = _mix(acc, (0, 0, 0), 0.6) if clair else (255, 255, 255)
    if t.get("icone") == "chat":  # tête de chat générique
        tr = int(r * 0.50)
        cy = int(r * 1.10)
        for sx in (-1, 1):
            pygame.draw.polygon(s, encre, [
                (r + sx * int(tr * 0.97), cy - int(tr * 0.15)),
                (r + sx * int(tr * 0.88), cy - int(tr * 1.50)),
                (r + sx * int(tr * 0.05), cy - int(tr * 0.80))])
        pygame.draw.circle(s, encre, (r, cy), tr)
        for sx in (-1, 1):
            pygame.draw.circle(s, acc, (r + sx * int(tr * 0.42), cy - int(tr * 0.12)), max(2, int(tr * 0.15)))
        pygame.draw.polygon(s, acc, [(r - int(tr * 0.16), cy + int(tr * 0.24)),
                                     (r + int(tr * 0.16), cy + int(tr * 0.24)), (r, cy + int(tr * 0.44))])
    else:  # étoile
        pts = []
        for n in range(10):
            rayon = r * (0.62 if n % 2 == 0 else 0.27)
            a = math.radians(-90 + n * 36)
            pts.append((r + rayon * math.cos(a), r + rayon * math.sin(a)))
        pygame.draw.polygon(s, encre, pts)


def get_cible(t, d):
    a = get_assets(t)
    if a["cibles"]:
        ticks = pygame.time.get_ticks()
        idx = (ticks // a["delai"]) % len(a["cibles"])
        # spin : rotation automatique, seulement pour une image fixe (pas une animation)
        ang = (int(ticks * 0.45) % 360) // 12 * 12 if t.get("spin") and len(a["cibles"]) == 1 else 0
        cle = (t["key"], d, idx, ang)
        if cle not in _cibles:
            img = a["cibles"][idx]
            iw, ih = img.get_size()
            k = d / max(iw, ih)
            img = pygame.transform.smoothscale(img, (max(1, int(iw * k)), max(1, int(ih * k))))
            if ang:
                img = pygame.transform.rotate(img, ang)
            _cibles[cle] = img
        return _cibles[cle]

    cle = (t["key"], d, 0, 0)
    if cle not in _cibles:
        if t["cible"] == "crate":
            _cibles[cle] = _disque(d, _dessin_crate)
        elif t["cible"] == "neon":
            _cibles[cle] = _disque(d, _dessin_neon)
        else:  # jeton de remplacement tant qu'aucune image n'est fournie
            _cibles[cle] = _disque(d, lambda s, D, t=t: _dessin_jeton(s, D, t))
    return _cibles[cle]


def dessiner_cible(rect, t=None):
    sp = get_cible(t or theme_actuel(), rect.width)
    screen.blit(sp, sp.get_rect(center=rect.center))


def touche(rect, pos, marge=0):
    """Vrai si pos est dans la cible ronde (rayon + marge)."""
    return math.hypot(pos[0] - rect.centerx, pos[1] - rect.centery) <= rect.width / 2 + marge


# =========================
# WEBSOCKET
# =========================
# =========================
# SONS
# =========================
# Les sons sont fabriqués par le jeu lui-même (aucun fichier nécessaire). Un thème peut
# les remplacer en déposant hit.wav, miss.wav, golden.wav ou bomb.wav dans son dossier.
# F10 change le volume : moyen -> faible -> coupé -> fort.
VOLUMES = [("fort", 1.0), ("moyen", 0.55), ("faible", 0.25), ("coupé", 0.0)]
volume_son = 1  # numéro dans VOLUMES
_sons = {}
_SON_THEME = {"hit": "hit", "rate": "miss", "or": "golden", "bombe": "bomb"}  # nom du jeu -> fichier

# Timbres : (numéro de l'harmonique, force). Peu d'harmoniques aiguës = son doux.
DOUX = ((1, 1.0), (2, 0.22), (3, 0.06))
CLOCHE = ((1, 1.0), (2.0, 0.4), (3.0, 0.15), (4.2, 0.1), (5.4, 0.05))
GRAVE = ((1, 1.0), (2, 0.3))
# do, ré, mi, sol, la : cinq notes qui sonnent toujours bien ensemble (le combo monte dessus)
GAMME = (523.25, 587.33, 659.25, 783.99, 880.0)


def _son(couches, volume=1.0):
    """Fabrique un son en superposant des couches :
    (début s, durée s, fréquence de départ, fréquence d'arrivée, force, timbre, chute).
    timbre None = souffle grave. Plus "chute" est grand, plus le son s'éteint vite."""
    reglages = pygame.mixer.get_init()
    if not reglages or reglages[1] != -16:
        return None
    frequence, _, canaux = reglages
    tampon = [0.0] * (int(frequence * max(c[0] + c[1] for c in couches)) + 2)
    hasard = _random.Random(7)
    for debut, duree, f0, f1, force, timbre, chute in couches:
        n, depart = int(frequence * duree), int(frequence * debut)
        phase = filtre = 0.0
        for i in range(n):
            pos = i / n
            # attaque douce (pas de "clac"), extinction progressive, fin en fondu
            enveloppe = min(1.0, i / (frequence * 0.006)) * math.exp(-chute * pos) * min(1.0, (1 - pos) * 8)
            if timbre is None:
                filtre += (hasard.uniform(-1, 1) - filtre) * 0.06  # on ne garde que le grave du bruit
                onde = filtre * 3
            else:
                phase += 2 * math.pi * (f0 + (f1 - f0) * pos) / frequence
                onde = sum(a * math.sin(h * phase) for h, a in timbre)
            tampon[depart + i] += onde * enveloppe * force
    data = array("h")
    for valeur in tampon:
        echantillon = int(32767 * math.tanh(valeur * volume))  # tanh : jamais de saturation dure
        for _ in range(canaux):
            data.append(echantillon)
    try:
        return pygame.mixer.Sound(buffer=data.tobytes())
    except Exception:
        return None


def _arpege(notes, ecart, duree, force, timbre=DOUX, chute=4, debut=0.0):
    return [(debut + k * ecart, duree, f, f, force, timbre, chute) for k, f in enumerate(notes)]


def _preparer_sons():
    do, mi, sol, do2, mi2 = 523.25, 659.25, 783.99, 1046.5, 1318.5
    for palier, note in enumerate(GAMME):  # petit "pop" dont la note monte avec le combo
        _sons[f"hit{palier}"] = _son([(0, 0.035, note * 1.8, note, 0.20, DOUX, 2), (0, 0.16, note, note, 0.34, DOUX, 5)])
    _sons["or"] = _son(_arpege((do2, 1568.0), 0.08, 0.55, 0.24, CLOCHE, 5))
    _sons["rate"] = _son([(0, 0.14, 140, 80, 0.4, GRAVE, 3.5)])
    _sons["bombe"] = _son([(0, 0.5, 90, 38, 0.42, GRAVE, 3.5), (0, 0.4, 0, 0, 0.3, None, 5)])
    _sons["palier"] = _son(_arpege((mi, sol, do2), 0.07, 0.26, 0.24))
    _sons["caisse"] = _son(_arpege((do, mi, sol, do2), 0.09, 0.3, 0.22)
                           + [(0.38, 0.8, f, f, 0.13, CLOCHE, 4) for f in (do, mi, sol, do2)])
    _sons["mission"] = _son(_arpege((sol, 987.77, 1174.66, 1568.0), 0.07, 0.32, 0.2, CLOCHE))
    _sons["fin"] = _son([(0, 0.3, mi, mi, 0.26, DOUX, 4), (0.16, 0.45, do, do, 0.26, DOUX, 4)])
    _sons["record"] = _son(_arpege((do, mi, sol, do2, mi2), 0.09, 0.28, 0.2)
                           + [(0.5, 0.9, f, f, 0.13, CLOCHE, 4) for f in (sol, do2, mi2)])
    _sons["decompte"] = _son([(0, 0.1, 440, 440, 0.26, DOUX, 4)])
    _sons["go"] = _son([(0, 0.3, mi, mi, 0.22, DOUX, 3.5), (0, 0.3, 987.77, 987.77, 0.15, DOUX, 3.5)])


def jouer(nom, palier=0):
    """Joue un son du jeu (ou celui du thème équipé s'il en fournit un)."""
    niveau = VOLUMES[volume_son][1]
    if niveau <= 0 or not pygame.mixer.get_init():
        return
    if not _sons:
        _preparer_sons()
    son = get_assets(theme_actuel())["sons"].get(_SON_THEME.get(nom, ""))
    if son is None:
        son = _sons.get(f"hit{min(palier, 4)}" if nom == "hit" else nom)
    if son is not None:
        try:
            son.set_volume(niveau)
            son.play()
        except Exception:
            pass


def basculer_son():
    """F10 : passe au volume suivant et l'annonce en haut de l'écran."""
    global volume_son
    volume_son = (volume_son + 1) % len(VOLUMES)
    annoncer("Son : " + VOLUMES[volume_son][0])
    jouer("hit")


_annonce = {"texte": "", "fin": 0}


def annoncer(message, duree=1400):
    """Petit message affiché quelques instants en haut de l'écran, sur n'importe quel écran."""
    _annonce["texte"], _annonce["fin"] = message, pygame.time.get_ticks() + duree


def dessiner_annonce():
    if _annonce["fin"] > pygame.time.get_ticks():
        f = police(24, True)
        cadre = pygame.Rect(0, H(22), f.size(_annonce["texte"])[0] + U(48), f.get_height() + U(22))
        cadre.centerx = x // 2
        panneau(cadre, alpha=235)
        ecrire(_annonce["texte"], cadre.center, 24, centre=True, gras=True)


# =========================
# EFFETS (particules, textes qui s'envolent, tremblement)
# =========================
particules = []
textes_volants = []
secousse = 0.0
OR = (255, 215, 80)


def vider_effets():
    global secousse
    particules.clear()
    textes_volants.clear()
    secousse = 0.0


def eclat(pos, couleurs, nombre=14, force=1.0):
    """Gerbe de particules qui partent dans tous les sens depuis pos."""
    for _ in range(nombre):
        angle = _random.uniform(0, 2 * math.pi)
        vitesse = _random.uniform(140, 460) * S * force
        vie = _random.uniform(0.25, 0.6)
        particules.append({"x": pos[0], "y": pos[1], "vx": math.cos(angle) * vitesse,
                           "vy": math.sin(angle) * vitesse, "vie": vie, "vie_max": vie,
                           "couleur": _random.choice(couleurs), "taille": _random.uniform(3, 8)})


def texte_volant(pos, txt, couleur, taille=26, vie=0.8):
    textes_volants.append({"x": pos[0], "y": pos[1], "txt": txt, "couleur": couleur,
                           "taille": taille, "vie": vie, "vie_max": vie})


def secouer(amplitude):
    global secousse
    secousse = max(secousse, amplitude)


def maj_effets(dt):
    global secousse
    for p in particules:
        p["vy"] += 1100 * S * dt  # gravité
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        p["vie"] -= dt
    for t in textes_volants:
        t["y"] -= 70 * S * dt
        t["vie"] -= dt
    particules[:] = [p for p in particules if p["vie"] > 0]
    textes_volants[:] = [t for t in textes_volants if t["vie"] > 0]
    secousse = max(0.0, secousse - 60 * S * dt)


def dessiner_effets():
    for p in particules:
        rayon = max(1, int(U(p["taille"]) * p["vie"] / p["vie_max"]))
        pygame.draw.circle(screen, p["couleur"], (int(p["x"]), int(p["y"])), rayon)
    for t in textes_volants:
        grossit = 1 + 0.25 * max(0.0, t["vie"] / t["vie_max"] - 0.75) * 4  # petit "pop" au début
        ecrire(t["txt"], (t["x"], t["y"]), t["taille"] * grossit, t["couleur"], centre=True, gras=True)


def appliquer_secousse():
    """À appeler juste avant flip() : décale toute l'image quand l'écran tremble."""
    if secousse >= 1:
        copie = screen.copy()
        a = int(secousse)
        screen.fill((0, 0, 0))
        screen.blit(copie, (randint(-a, a), randint(-a, a)))


# ---------- Cibles spéciales ----------
def _dessin_bombe(s, D):
    r = int(D / 2)
    pygame.draw.circle(s, (26, 24, 30), (r, r), r)
    pygame.draw.circle(s, (235, 60, 50), (r, r), r, max(3, int(D * 0.08)))
    a = int(r * 0.42)
    for sens in (1, -1):
        pygame.draw.line(s, (235, 60, 50), (r - a, r - a * sens), (r + a, r + a * sens), max(3, int(D * 0.11)))


def _halo_cible(d):
    """Lueur claire + double contour, pour que la cible ressorte sur n'importe quel décor."""
    cle = ("halo", d, 0, 0)
    if cle not in _cibles:
        marge = max(6, U(16))
        cote = d + 2 * marge
        s = pygame.Surface((cote, cote), pygame.SRCALPHA)
        c = (cote // 2, cote // 2)
        for n in range(marge, 0, -1):  # lueur : de plus en plus claire vers la cible
            pygame.draw.circle(s, (255, 255, 255, int(70 * (1 - n / marge) ** 1.5) + 6), c, d // 2 + n)
        pygame.draw.circle(s, (20, 16, 24, 235), c, d // 2 + max(3, U(6)))   # contour sombre
        pygame.draw.circle(s, (255, 255, 255, 245), c, d // 2 + max(2, U(4)))  # contour clair
        _cibles[cle] = s
    return _cibles[cle]


def dessiner_cible_speciale(rect, genre, echelle=1.0):
    """Dessine une cible de run : normale, dorée (vaut plus de points) ou bombe."""
    d = max(8, int(rect.width * echelle))
    zone = pygame.Rect(0, 0, d, d)
    zone.center = rect.center
    if genre == "bombe":
        cle = ("bombe", d, 0, 0)
        if cle not in _cibles:
            _cibles[cle] = _disque(d, _dessin_bombe)
        screen.blit(_cibles[cle], _cibles[cle].get_rect(center=zone.center))
        return
    halo = _halo_cible(d)
    screen.blit(halo, halo.get_rect(center=zone.center))
    dessiner_cible(zone)
    if genre == "or":  # anneau doré qui bat
        battement = math.sin(pygame.time.get_ticks() / 90)
        rayon = d // 2 + U(9) + int(U(3) * battement)
        pygame.draw.circle(screen, OR, zone.center, rayon, max(2, U(6)))
        pygame.draw.circle(screen, (255, 248, 190), zone.center, rayon + max(2, U(4)), max(1, U(2)))


# =========================
# OUTILS
# =========================
def fmt_temps(ms):
    """Un chrono en millisecondes, écrit en secondes : 23417 -> "23.42 s"."""
    return f"{ms / 1000:.2f} s"


def fmt_score(value):
    try:
        v = float(value)
    except Exception:
        return str(value)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".")


def cree_button_random():
    """Cible ronde : un carré dont le côté est le diamètre."""
    d = max(8, U(randint(48, 112)))  # diamètre : 48 à 112 en mesure de référence
    return pygame.Rect(randint(0, max(0, x - d)), randint(0, max(0, y - d)), d, d)


def replacer_cible(rect, ancien):
    """Après un redimensionnement : la cible garde sa place et sa taille en pourcentage.
    `ancien` = (x, y, S) d'avant."""
    ax, ay, a_s = ancien
    centre = (rect.centerx * x / ax, rect.centery * y / ay)
    d = max(8, int(round(rect.width * S / a_s)))
    rect.size = (d, d)
    rect.center = centre
    rect.clamp_ip(pygame.Rect(0, 0, x, y))


def _entetes():
    # Le jeton voyage dans un en-tête, jamais dans l'adresse (les adresses sont journalisées).
    return {"Authorization": "Bearer " + token_joueur} if token_joueur else {}


def _journal(erreur):
    """Note les erreurs réseau dans catchme_erreurs.log, à côté du jeu, pour pouvoir les envoyer."""
    try:
        with open(os.path.join(BASE_DIR, "catchme_erreurs.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "  " + repr(erreur)[:500] + "\n")
    except OSError:
        pass


_fil = threading.local()  # une connexion par fil d'exécution (le jeu, et les requêtes en fond)


def _connexion(neuve=False):
    """La connexion au serveur, gardée ouverte entre deux requêtes : sans cela, chaque
    action attendait une nouvelle poignée de main HTTPS (un petit gel à chaque clic)."""
    session = getattr(_fil, "session", None)
    if neuve and session is not None:
        session.close()
        session = None
    if session is None:
        session = _fil.session = requests.Session()
    return session


def _requete(methode, path, timeout, **options):
    """Envoie une requête au serveur sur la connexion gardée ouverte. Si le tunnel a coupé
    cette connexion entre-temps, on en ouvre une neuve et on réessaie aussitôt, une fois."""
    for essai in (1, 2):
        try:
            return _connexion(neuve=essai == 2).request(
                methode, BASE_URL + path, headers=_entetes(),
                timeout=(min(5, timeout), timeout), **options)
        except requests.ConnectionError as e:
            _journal(e)
        except requests.RequestException as e:
            _journal(e)
            return None
    return None


def api_post_json(path, payload=None, timeout=8):
    return _requete("POST", path, timeout, json=payload or {})


def api_get(path, params=None):
    return _requete("GET", path, 8, params=params)


class EnFond:
    """Une lecture du serveur faite en arrière-plan : l'écran s'ouvre tout de suite et
    continue de s'animer, la réponse est affichée dès qu'elle arrive."""

    def __init__(self, path, params=None):
        self.prete, self.reponse = False, None
        threading.Thread(target=self._lire, args=(path, params), daemon=True).start()

    def _lire(self, path, params):
        try:
            self.reponse = api_get(path, params)
        finally:
            self.prete = True

    def json(self, defaut):
        """Le contenu de la réponse, ou `defaut` si le serveur n'a pas répondu correctement."""
        try:
            return self.reponse.json() if self.reponse.status_code == 200 else defaut
        except Exception:
            return defaut


_actualisation = None


def actualiser_en_fond():
    """Redemande l'état du joueur au serveur sans bloquer l'écran."""
    global _actualisation
    if token_joueur:
        _actualisation = EnFond("/me")


def recevoir_actualisation():
    """Appelée à chaque image : applique l'état du joueur quand le serveur a répondu."""
    global _actualisation
    demande = _actualisation
    if demande is not None and demande.prete:
        _actualisation = None
        if token_joueur:
            appliquer_etat(demande.json({}).get("player", {}))


def detail_erreur(r, defaut):
    """Le message d'erreur renvoyé par le serveur, ou `defaut`."""
    if r is None:
        return "Serveur indisponible"
    try:
        return str(r.json().get("detail") or defaut)
    except Exception:
        return defaut


def can_show_next(level, inventory):
    return level == 1 or (level - 1 in inventory)


# Multiplicateur de score selon le plus haut niveau acheté (0 = aucun).
MULTIPLICATEURS = (1, 1.5, 2, 3)
MULTIPLICATEURS_EASY = (1, 2, 2.5, 3)


def compute_gain(mode):
    niveau = min(3, max([n for n in multiplicateur if n in (1, 2, 3)], default=0))
    table = MULTIPLICATEURS_EASY if mode == "easy" else MULTIPLICATEURS
    return BASE_POINTS[mode] * table[niveau]


# Délai (ms) entre deux déplacements selon le plus haut niveau de Slow (0 = aucun).
DELAIS = {  # sans Slow, puis Slow niveau 1, 2, 3, 4
    "easy": (1000, 1025, 1050, 1150, 1250),
    "medium": (550, 575, 600, 700, 800),
    "hard": (350, 375, 400, 500, 600),
    "impossible": (0, 25, 50, 150, 250),
}


def delai_pour(mode):
    if mode == "demonic":
        return 999999
    return DELAIS[mode][min(len(DELAIS[mode]) - 1, len(ralentisseur))]


def quitter_jeu():
    """Unique point de sortie : déconnecte la session et arrête le programme."""
    global token_joueur
    if token_joueur:
        api_post_json("/logout", timeout=2)  # le jeton ne pourra plus servir
        token_joueur = ""
    pygame.quit()
    sys.exit(0)


# =========================
# ETAT DU JOUEUR (le serveur fait foi)
# =========================
def appliquer_etat(joueur):
    """Recopie dans le jeu l'état officiel renvoyé par le serveur."""
    global pseudo_joueur, score, ralentisseur, but_bonus, multiplicateur, skinAcheter, CouleurSkin
    global caisses, serie, records, missions_faites, missions_a_recuperer, _actualisation
    if not joueur:
        return
    _actualisation = None  # cet état est plus récent qu'une actualisation encore en route
    pseudo_joueur = str(joueur.get("pseudo", pseudo_joueur))
    score = float(joueur.get("score", 0))
    ralentisseur = list(range(1, int(joueur.get("slow", 0)) + 1))    # niveau 2 -> [1, 2]
    but_bonus = list(range(1, int(joueur.get("aide", 0)) + 1))
    multiplicateur = list(range(1, int(joueur.get("multi", 0)) + 1))
    skinAcheter = sorted(THEME_BY_KEY[k]["id"] for k in joueur.get("themes", []) if k in THEME_BY_KEY) or [1]
    cle = str(joueur.get("theme", ""))
    CouleurSkin = cle if cle in THEME_BY_KEY and THEME_BY_KEY[cle]["id"] in skinAcheter else THEME_DEFAUT["key"]
    recu = joueur.get("crates", {})
    caisses = {cle: int(recu.get(cle, 0)) for cle, _, _ in RARETES} if isinstance(recu, dict) else {}
    missions_a_recuperer = int(joueur.get("missions_to_claim", 0))
    serie = int(joueur.get("streak", 0))
    recus = joueur.get("best", {})
    records = {cle: dict(recus.get(cle) or {}) for cle, _, _ in GENRES} if isinstance(recus, dict) else {}
    missions_faites = (int(joueur.get("missions_done", 0)), int(joueur.get("missions_total", 3)))


def load_player_state():
    """Redemande au serveur l'état du joueur (score, bonus, thèmes)."""
    if not token_joueur:
        return False
    r = api_get("/me")
    if not r or r.status_code != 200:
        return False
    appliquer_etat(r.json().get("player", {}))
    return True


def charger_catalogue():
    """Récupère les prix et les règles officiels pour afficher les mêmes que le serveur."""
    global DUREE_RUN, PALIERS_COMBO, BONUS_DOREE, RUNS_PAR_CAISSE, PENALITE_BOMBE
    global CHANCE_DOREE, CHANCE_BOMBE, PENALITE_RATE, COMBO_DUREE
    r = api_get("/catalog")
    if not r or r.status_code != 200:
        return
    try:
        data = r.json()
        for cle, prix in data.get("upgrades", {}).items():
            if cle in PRIX_AMELIORATIONS and prix:
                PRIX_AMELIORATIONS[cle] = [int(p) for p in prix]
        for cle, prix in data.get("themes", {}).items():
            if cle in THEME_BY_KEY:
                THEME_BY_KEY[cle]["price"] = int(prix)
        DUREE_RUN = float(data.get("run_duration", DUREE_RUN))
        paliers = sorted(((int(a), float(b)) for a, b in data.get("combo_tiers", PALIERS_COMBO)), reverse=True)
        if paliers and paliers[-1][0] == 0:
            PALIERS_COMBO = paliers
        BONUS_DOREE = float(data.get("golden_bonus", BONUS_DOREE))
        PENALITE_BOMBE = float(data.get("bomb_penalty", PENALITE_BOMBE))
        CHANCE_DOREE = float(data.get("golden_chance", CHANCE_DOREE))
        CHANCE_BOMBE = float(data.get("bomb_chance", CHANCE_BOMBE))
        PENALITE_RATE = float(data.get("miss_penalty", PENALITE_RATE))
        COMBO_DUREE = max(0.5, float(data.get("combo_seconds", COMBO_DUREE)))
        for cle, modes in data.get("kinds", {}).items():
            if cle in MODES_PAR_GENRE and modes:
                MODES_PAR_GENRE[cle] = [m for m in modes if m in NOMS_MODES]
        c = data.get("challenge", {})
        CHALLENGE.update(cibles=int(c.get("targets", CHALLENGE["cibles"])),
                         rate_s=float(c.get("miss_seconds", CHALLENGE["rate_s"])),
                         max_s=float(c.get("max_seconds", CHALLENGE["max_s"])))
        s = data.get("survival", {})
        SURVIE.update(vies=int(s.get("lives", SURVIE["vies"])), max_s=float(s.get("max_seconds", SURVIE["max_s"])),
                      acceleration=float(s.get("speedup", SURVIE["acceleration"])))
        for mode, (depart, mini) in s.get("delays", {}).items():
            SURVIE["delais"][mode] = (float(depart), float(mini))
        for caisse in data.get("crates", []):
            if caisse.get("key") in BUTIN and caisse.get("loot"):
                BUTIN[caisse["key"]] = [tuple(lot) for lot in caisse["loot"]]
        RUNS_PAR_CAISSE = int(data.get("runs_per_crate", RUNS_PAR_CAISSE))
    except Exception:
        pass


def demander(path, payload, refus):
    """Envoie une action au serveur. Renvoie (réussi, message d'erreur)."""
    r = api_post_json(path, payload)
    if r is not None and r.status_code == 200:
        appliquer_etat(r.json().get("player", {}))
        return True, ""
    return False, detail_erreur(r, refus)


# =========================
# INPUT BOX
# =========================
class InputBox:
    def __init__(self, x, y, w, h, password=False):
        self.rect = pygame.Rect(int(x), int(y), int(w), int(h))
        self.text = ""
        self.password = password
        self.active = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)

        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.unicode and event.unicode.isprintable():
                self.text += event.unicode

    def draw(self, screen_):
        t = theme_actuel()
        s = pygame.Surface((max(1, self.rect.width), max(1, self.rect.height)), pygame.SRCALPHA)
        pygame.draw.rect(s, (*t["panneau"], 230), s.get_rect(), border_radius=U(8))
        bord = t["accent"] if self.active else _mix(t["accent"], t["panneau"], 0.55)
        pygame.draw.rect(s, bord, s.get_rect(), max(1, U(3 if self.active else 2)), border_radius=U(8))
        screen_.blit(s, self.rect.topleft)
        aff = "*" * len(self.text) if self.password else self.text
        if self.active and (pygame.time.get_ticks() // 500) % 2 == 0:
            aff += "|"
        haut_texte = police(22).get_height()
        ecrire(aff, (self.rect.x + L(12), self.rect.centery - haut_texte // 2), 22,
               max_w=self.rect.width - L(24), ombre=False)


# =========================
# LOGIN / REGISTER
# =========================
def afficher_login():
    global token_joueur

    username = InputBox(0, 0, 340, 44)
    password = InputBox(0, 0, 340, 44, password=True)

    message = ""
    if pygame.mixer.get_init() and not _sons:
        _preparer_sons()  # fabriqués une fois au lancement (moins d'une seconde)

    while True:
        background()
        cadre = pygame.Rect(0, 0, L(420), H(330))
        cadre.center = (x // 2, int(y * 0.55))
        username.rect = pygame.Rect(cadre.x + L(40), cadre.y + H(60), L(340), H(44))
        password.rect = pygame.Rect(cadre.x + L(40), cadre.y + H(150), L(340), H(44))
        login_btn = pygame.Rect(cadre.x + L(40), cadre.y + H(225), L(160), H(64))
        register_btn = pygame.Rect(cadre.x + L(220), cadre.y + H(225), L(160), H(64))
        titre("CATCH-ME", int(y * 0.16))
        ecrire("LOGIN", (x / 2, int(y * 0.16) + int(y * 0.09)), 26, centre=True, gras=True)
        ecrire("version " + VERSION, (L(20), y - H(40)), 18)
        panneau(cadre)

        ecrire("Username :", (username.rect.x, username.rect.y - H(32)), 22, gras=True)
        ecrire("Password :", (password.rect.x, password.rect.y - H(32)), 22, gras=True)
        username.draw(screen)
        password.draw(screen)

        bouton(login_btn, "Login")
        bouton(register_btn, "Register")

        if message:
            ecrire(message, (x / 2, cadre.bottom + H(30)), 24, (255, 130, 110), centre=True, gras=True)

        for event in evenements():
            if event.type == pygame.QUIT:
                quitter_jeu()

            username.handle_event(event)
            password.handle_event(event)

            if event.type == pygame.MOUSEBUTTONDOWN:
                if login_btn.collidepoint(event.pos):
                    if username.text == "" or password.text == "":
                        message = "Champs vides"
                        continue
                    if len(username.text) > 25:
                        message = "Pseudo trop long"
                        continue

                    r = api_post_json("/login", {"pseudo": username.text, "password": password.text,
                                                 "client": VERSION_JEU})
                    if r is not None and r.status_code == 200:
                        data = r.json()
                        token_joueur = data.get("token", "")
                        appliquer_etat(data.get("player", {}))
                        charger_catalogue()
                        if data.get("daily"):
                            afficher_bonus_du_jour(data["daily"])
                        menus_principale()
                        return
                    message = detail_erreur(r, "Identifiants incorrects")

                if register_btn.collidepoint(event.pos):
                    afficher_register()
                    continue

        flip()
        clock.tick(60)


def afficher_register():
    username = InputBox(0, 0, 340, 44)
    password = InputBox(0, 0, 340, 44, password=True)
    confirm = InputBox(0, 0, 340, 44, password=True)

    message = ""

    while True:
        background()
        cadre = pygame.Rect(0, 0, L(420), H(420))
        cadre.center = (x // 2, int(y * 0.58))
        username.rect = pygame.Rect(cadre.x + L(40), cadre.y + H(60), L(340), H(44))
        password.rect = pygame.Rect(cadre.x + L(40), cadre.y + H(150), L(340), H(44))
        confirm.rect = pygame.Rect(cadre.x + L(40), cadre.y + H(240), L(340), H(44))
        create_btn = pygame.Rect(cadre.x + L(40), cadre.y + H(315), L(160), H(64))
        back_btn = pygame.Rect(cadre.x + L(220), cadre.y + H(315), L(160), H(64))
        titre("REGISTER", int(y * 0.14))
        panneau(cadre)

        ecrire("Username :", (username.rect.x, username.rect.y - H(32)), 22, gras=True)
        ecrire("Password :", (password.rect.x, password.rect.y - H(32)), 22, gras=True)
        ecrire("Confirm :", (confirm.rect.x, confirm.rect.y - H(32)), 22, gras=True)
        username.draw(screen)
        password.draw(screen)
        confirm.draw(screen)

        bouton(create_btn, "Create")
        bouton(back_btn, "Back")

        if message:
            ecrire(message, (x / 2, cadre.bottom + H(30)), 24, (255, 130, 110), centre=True, gras=True)

        for event in evenements():
            if event.type == pygame.QUIT:
                quitter_jeu()

            username.handle_event(event)
            password.handle_event(event)
            confirm.handle_event(event)

            if event.type == pygame.MOUSEBUTTONDOWN:
                if create_btn.collidepoint(event.pos):
                    if username.text == "" or password.text == "" or confirm.text == "":
                        message = "Champs vides"
                        continue
                    if len(username.text) > 25:
                        message = "Pseudo trop long"
                        continue
                    if password.text != confirm.text:
                        message = "Mot de passe différent"
                        continue

                    r = api_post_json("/register", {"pseudo": username.text, "password": password.text})
                    if r is None:
                        message = "Serveur indisponible"
                        continue

                    if r.status_code in (200, 201):
                        message = "Compte créé"
                        pygame.time.wait(300)
                        return
                    message = detail_erreur(r, "Erreur inscription")

                if back_btn.collidepoint(event.pos):
                    return

        flip()
        clock.tick(60)


# =========================
# LEADERBOARD
# =========================
def afficher_leaderboard():
    """Classement général (points gagnés depuis toujours), ou meilleur run par mode de jeu
    et par difficulté. En Challenge, le meilleur est le temps le plus court."""
    genre, difficulte, periode = "total", "easy", "week"
    charge, dernier = None, -10000
    lignes, lecture, recu = [], None, False

    while True:
        if genre != "total" and difficulte not in MODES_PAR_GENRE[genre]:
            difficulte = MODES_PAR_GENRE[genre][0]
        demande = (genre, difficulte, periode)
        now = pygame.time.get_ticks()
        if demande != charge:  # autre onglet : on vide et on redemande tout de suite
            lignes, recu, lecture, dernier = [], False, None, -10000
            charge = demande
        if lecture is None and now - dernier >= 5000:
            params = {"board": "total"} if genre == "total" else \
                {"board": difficulte, "kind": genre, "period": periode}
            lecture, dernier = (demande, EnFond("/leaderboard", params)), now
        if lecture is not None and lecture[1].prete:
            if lecture[0] == demande:
                data = lecture[1].json([])
                lignes, recu = data if isinstance(data, list) else [], True
            lecture = None

        background()
        titre("LEADERBOARD")
        back = bouton_retour()

        onglets = [("total", "Général")] + [(cle, nom) for cle, nom, _ in GENRES]
        rects_genre = rangee(len(onglets), y * 0.225, 230, 56, 14)
        for rect, (cle, nom) in zip(rects_genre, onglets):
            bouton(rect, nom, etat="normal" if cle == genre else "acquis")
        choix_difficulte, choix_periode = [], []
        if genre == "total":
            ecrire("Points gagnés depuis toujours", (x / 2, y * 0.30), 22, centre=True)
        else:
            modes = MODES_PAR_GENRE[genre]
            for rect, mode in zip(rangee(len(modes), y * 0.295, 170, 46, 10), modes):
                bouton(rect, NOMS_MODES[mode], etat="normal" if mode == difficulte else "acquis")
                choix_difficulte.append((rect, mode))
            for rect, (cle, nom) in zip(rangee(2, y * 0.355, 230, 42, 12),
                                        (("week", "Cette semaine"), ("all", "Tous temps"))):
                bouton(rect, nom, etat="normal" if cle == periode else "acquis")
                choix_periode.append((rect, cle))

        t = theme_actuel()
        haut = int(y * 0.40)
        pas = max(1, min(H(50), (y - haut - H(40)) // 10))
        cadre = pygame.Rect(0, haut, min(L(700), x - L(80)), pas * 10 + H(30))
        cadre.centerx = x // 2
        panneau(cadre)

        for rang, joueur in enumerate(lignes[:10]):
            p = joueur.get("pseudo", "???")
            valeur = fmt_temps(joueur["time_ms"]) if "time_ms" in joueur else fmt_score(joueur.get("score", 0))
            ly = cadre.y + H(15) + rang * pas
            ty = ly + (pas - police(24).get_height()) // 2 - U(2)
            coul = t["accent"] if rang < 3 else t["texte"]
            if p == pseudo_joueur:
                pygame.draw.rect(screen, _mix(t["panneau"], t["accent"], 0.25),
                                 (cadre.x + L(8), ly - U(2), cadre.width - L(16), pas - U(4)), border_radius=U(6))
            ecrire(f"{rang + 1}.", (cadre.x + L(30), ty), 24, coul, gras=True)
            ecrire(p, (cadre.x + L(90), ty), 24, coul, gras=rang < 3, max_w=cadre.width - L(260))
            ecrire(valeur, (cadre.right - L(30) - police(24, True).size(valeur)[0], ty), 24, coul, gras=True)
        if not lignes:
            ecrire("Aucun score pour le moment" if recu else "Chargement...", cadre.center, 24, centre=True)

        for event in evenements():
            if event.type == pygame.QUIT:
                quitter_jeu()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                if back.collidepoint(event.pos):
                    return
                for rect, (cle, _) in zip(rects_genre, onglets):
                    if rect.collidepoint(event.pos):
                        genre = cle
                for rect, mode in choix_difficulte:
                    if rect.collidepoint(event.pos):
                        difficulte = mode
                for rect, cle in choix_periode:
                    if rect.collidepoint(event.pos):
                        periode = cle

        flip()
        clock.tick(60)


# =========================
# MENUS
# =========================
def menus_principale():
    while True:
        background()
        hud(avec_pseudo=True)
        titre("CATCH-ME", int(y * 0.27))

        play, shop, caisses_btn, missions_btn = rangee(4, y * 0.53, 240, 108, 28)
        leaderboard, instruction, leave = rangee(3, y * 0.71, 240, 84, 28)
        bouton(play, "Play")
        bouton(shop, "Shop")
        nb_caisses = sum(caisses.values())
        bouton(caisses_btn, "Caisses", f"{nb_caisses} à ouvrir" if nb_caisses else "Aucune pour l'instant")
        bouton(missions_btn, "Missions", f"{missions_a_recuperer} récompense" + ("s" if missions_a_recuperer > 1 else "")
               + " à récupérer" if missions_a_recuperer else f"{missions_faites[0]}/{missions_faites[1]} aujourd'hui")
        bouton(leaderboard, "Leaderboard")
        bouton(instruction, "Instruction")
        bouton(leave, "Leave")
        for rect, actif in ((caisses_btn, nb_caisses), (missions_btn, missions_a_recuperer)):
            if actif:  # pastille qui attire l'œil
                pygame.draw.circle(screen, OR, (rect.right - U(4), rect.y + U(4)),
                                   U(11) + int(U(2) * math.sin(pygame.time.get_ticks() / 150)))

        for event in evenements():
            if event.type == pygame.QUIT:
                quitter_jeu()

            if event.type == pygame.MOUSEBUTTONDOWN:
                if play.collidepoint(event.pos):
                    afficher_modes()
                elif shop.collidepoint(event.pos):
                    afficher_shop()
                elif caisses_btn.collidepoint(event.pos):
                    afficher_caisses()
                elif missions_btn.collidepoint(event.pos):
                    afficher_missions()
                elif instruction.collidepoint(event.pos):
                    afficher_instruction()
                elif leaderboard.collidepoint(event.pos):
                    afficher_leaderboard()
                elif leave.collidepoint(event.pos):
                    quitter_jeu()

        flip()
        clock.tick(60)


def afficher_bonus_du_jour(bonus):
    """Petit écran affiché à la première connexion de la journée."""
    jouer("palier")
    jours = int(bonus.get("streak", 1))
    lignes = [f"+{fmt_score(bonus.get('points', 0))} points"]
    noms = {cle: nom.lower() for cle, nom, _ in RARETES}
    if bonus.get("crate") in noms:
        lignes.append(f"+1 caisse {noms[bonus['crate']]}")
    while True:
        background()
        titre("BONUS DU JOUR", int(y * 0.24))
        cadre = pygame.Rect(0, 0, L(620), H(300))
        cadre.center = (x // 2, int(y * 0.53))
        panneau(cadre)
        ecrire(f"Série de connexion : {jours} jour" + ("s" if jours > 1 else ""),
               (x / 2, cadre.y + H(60)), 30, centre=True, gras=True)
        for n, ligne in enumerate(lignes):
            ecrire(ligne, (x / 2, cadre.y + H(135) + n * H(52)), 36, theme_actuel()["accent"], centre=True, gras=True)
        ecrire("Reviens demain pour continuer ta série", (x / 2, cadre.bottom - H(40)), 20, centre=True)
        ok = bouton(rangee(1, cadre.bottom + H(70), 220, 80)[0], "OK")

        for event in evenements():
            if event.type == pygame.QUIT:
                quitter_jeu()
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                return
            if event.type == pygame.MOUSEBUTTONDOWN and ok.collidepoint(event.pos):
                return

        flip()
        clock.tick(60)


def afficher_modes():
    """Choix du mode de jeu : Classique, Challenge ou Survie."""
    descriptions = {
        "classic": [f"{fmt_score(DUREE_RUN)} secondes pour marquer", "un maximum de points.",
                    "Combo, cibles dorées, bombes."],
        "challenge": [f"Touche {CHALLENGE['cibles']} cibles le plus vite possible.",
                      f"Un clic raté : +{fmt_score(CHALLENGE['rate_s'])} seconde.",
                      f"Limite : {fmt_score(CHALLENGE['max_s'])} secondes, sinon c'est perdu."],
        "survival": [f"{SURVIE['vies']} vies. Les cibles disparaissent", "de plus en plus vite.",
                     "Tiens le plus longtemps possible."],
    }
    while True:
        background()
        titre("MODE DE JEU")
        back = bouton_retour()
        t = theme_actuel()

        cartes = rangee(len(GENRES), y * 0.52, 470, 420, 34)
        jouables = []
        for carte, (cle, nom, _) in zip(cartes, GENRES):
            panneau(carte, bord=4 if carte.collidepoint(souris()) else 2)
            ecrire(nom, (carte.centerx, carte.y + H(58)), 44, t["accent"], centre=True, gras=True,
                   max_w=carte.width - L(30))
            for n, ligne in enumerate(descriptions[cle]):
                ecrire(ligne, (carte.centerx, carte.y + H(140) + n * H(40)), 22, centre=True,
                       max_w=carte.width - L(30))
            rect = pygame.Rect(0, 0, carte.width - L(70), H(80))
            rect.midbottom = (carte.centerx, carte.bottom - H(28))
            bouton(rect, "Jouer")
            jouables.append((carte, cle))

        for event in evenements():
            if event.type == pygame.QUIT:
                quitter_jeu()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                if back.collidepoint(event.pos):
                    return
                for carte, cle in jouables:
                    if carte.collidepoint(event.pos) and afficher_difficult(cle) == "menu":
                        return

        flip()
        clock.tick(60)


def afficher_difficult(genre="classic"):
    """Choix de la difficulté pour un mode de jeu. Renvoie "menu" pour revenir au menu
    principal, ou None pour revenir au choix du mode."""
    global delai
    message = ""
    modes = MODES_PAR_GENRE[genre]
    nom_genre = next(nom for cle, nom, _ in GENRES if cle == genre)
    conseil = {"classic": f"Un run dure {fmt_score(DUREE_RUN)} secondes. Enchaîne les cibles sans traîner pour faire monter le combo.",
               "challenge": f"Touche {CHALLENGE['cibles']} cibles le plus vite possible (limite : {fmt_score(CHALLENGE['max_s'])} s). "
                            f"Clic raté : +{fmt_score(CHALLENGE['rate_s'])} s. Une cible dorée compte double.",
               "survival": f"{SURVIE['vies']} vies. Un clic raté, une bombe ou une cible manquée en coûte une."}[genre]

    while True:
        background()
        titre(nom_genre.upper())
        back = bouton_retour()
        ecrire(conseil, (x / 2, y * 0.25), 22, centre=True, max_w=x - L(80))

        if len(modes) > 3:
            rects = rangee(3, y * 0.44, 250, 112, 40) + rangee(len(modes) - 3, y * 0.66, 250, 112, 40)
        else:
            rects = rangee(len(modes), y * 0.52, 270, 124, 44)
        for rect, mode in zip(rects, modes):
            record = records.get(genre, {}).get(mode)
            if record is None:
                sous = f"{BASE_POINTS[mode]} pt" + ("s" if BASE_POINTS[mode] > 1 else "") + " par cible"
            else:
                sous = "Record : " + (fmt_temps(record) if genre == "challenge" else fmt_score(record))
            bouton(rect, NOMS_MODES[mode], sous)
        if message:
            ecrire(message, (x / 2, y - H(60)), 24, (255, 130, 110), centre=True, gras=True)

        choix = None
        for event in evenements():
            if event.type == pygame.QUIT:
                quitter_jeu()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return None
            if event.type == pygame.MOUSEBUTTONDOWN:
                if back.collidepoint(event.pos):
                    return None
                for rect, mode in zip(rects, modes):
                    if rect.collidepoint(event.pos):
                        choix = mode

        if choix:
            delai = delai_pour(choix)
            action, message = start(choix, genre)
            if action == "menu":
                return "menu"
            continue  # on reste sur cet écran pour choisir une autre difficulté

        flip()
        clock.tick(60)


# (titre, nom de la liste dans le jeu, nom côté serveur, message achat, message déjà possédé)
AMELIORATIONS = [
    ("Slow", "ralentisseur", "slow", "Buff Slow lvl.{n} acheté", "Vous possédez déjà ce buff"),
    ("Aide", "but_bonus", "aide", "Aide lvl.{n} achetée", "Vous possédez déjà cette aide"),
    ("Score", "multiplicateur", "multi", "Multiplicateur lvl.{n} acheté",
     "Vous possédez déjà ce multiplicateur"),
]
# Prix affichés, un par niveau (Slow en a 4, les autres 3). Remplacés à la connexion par ceux du serveur, qui décide.
PRIX_AMELIORATIONS = {"slow": [100, 200, 2500, 8000], "aide": [800, 3500, 9000], "multi": [2000, 7000, 15000]}


def afficher_shop():

    message = ""
    actualiser_en_fond()  # on repart de l'état officiel du serveur, sans bloquer l'écran

    while True:
        background()
        haut = int(y * 0.24)
        bh = H(92)
        pas = bh + H(22)
        hud()
        titre("SHOP")
        back = bouton_retour()

        zones = []  # (rect, index amélioration, niveau)
        for ligne, (nom, liste, cle_serveur, _, _) in enumerate(AMELIORATIONS):
            inventaire = globals()[liste]
            prix = PRIX_AMELIORATIONS[cle_serveur]
            rects = rangee(len(prix), haut + ligne * pas + bh / 2, 230, 92, 40)
            for n in range(1, len(prix) + 1):
                if can_show_next(n, inventaire):
                    acquis = n in inventaire
                    bouton(rects[n - 1], f"{nom} lvl.{n}", "Acquis" if acquis else f"{prix[n - 1]} pts",
                           "acquis" if acquis else "normal")
                    zones.append((rects[n - 1], ligne, n))

        themes_btn = rangee(1, haut + 3 * pas + bh / 2 + H(6), 420, 92)[0]
        bouton(themes_btn, "Thèmes", f"Équipé : {theme_actuel()['name']}")

        if message:
            ecrire(message, (x / 2, y - H(50)), 24, (255, 130, 110), centre=True, gras=True)

        for event in evenements():
            if event.type == pygame.QUIT:
                quitter_jeu()

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return

            if event.type == pygame.MOUSEBUTTONDOWN:
                if back.collidepoint(event.pos):
                    return

                if themes_btn.collidepoint(event.pos):
                    afficher_themes()
                    message = ""
                    continue

                for rect, ligne, n in zones:
                    if not rect.collidepoint(event.pos):
                        continue
                    _, liste, cle_serveur, msg_achat, msg_deja = AMELIORATIONS[ligne]
                    if n in globals()[liste]:
                        message = msg_deja
                    else:  # le serveur vérifie le prix et le solde, puis renvoie le nouvel état
                        reussi, erreur = demander("/shop/upgrade", {"type": cle_serveur}, "Achat refusé")
                        message = msg_achat.format(n=n) if reussi else erreur
                    break

        flip()
        clock.tick(60)


def _carte_theme(rect, t):
    """Carte de la boutique : aperçu de la cible + nom + prix, aux couleurs du thème t."""
    equipe = theme_actuel() is t
    possede = t["id"] in skinAcheter
    survol = rect.collidepoint(souris())

    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    r = U(16)
    s.blit(pygame.transform.smoothscale(_degrade(8, 8, t["ciel"][0], t["ciel"][1]), rect.size), (0, 0))
    masque = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(masque, (255, 255, 255, 235), masque.get_rect(), border_radius=r)
    s.blit(masque, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    sombre = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(sombre, (0, 0, 0, 70 if survol else 105), sombre.get_rect(), border_radius=r)
    s.blit(sombre, (0, 0))
    bord = (255, 255, 255) if equipe else t["bord"]
    pygame.draw.rect(s, bord, s.get_rect(), max(1, U(5 if equipe else (3 if survol else 2))), border_radius=r)
    screen.blit(s, rect.topleft)

    d = max(8, min(rect.height - H(34), U(84), rect.width // 3))
    zone = pygame.Rect(rect.x + L(18), rect.centery - d // 2, d, d)
    dessiner_cible(zone, t)

    tx = zone.right + L(22)
    larg = rect.right - tx - L(12)
    ecrire(t["name"], (tx, rect.centery - U(30)), 22, (255, 255, 255), gras=True, max_w=larg)
    if equipe:
        etat, coul = "Équipé", (140, 255, 150)
    elif possede:
        etat, coul = "Possédé - cliquer pour équiper", (235, 235, 235)
    else:
        etat, coul = f"{t['price']} pts", (255, 220, 120)
    ecrire(etat, (tx, rect.centery + U(2)), 18, coul, max_w=larg)
    a = get_assets(t)
    if t["decor"] == "pop" and not a["cibles"]:
        ecrire(f"images à ajouter : themes/{t['key']}/", (tx, rect.centery + U(26)), 14, (220, 220, 220), max_w=larg)


def afficher_themes():

    message = ""
    actualiser_en_fond()
    n = len(THEMES)
    cols = 3 if n <= 9 else 4
    rows = math.ceil(n / cols)

    while True:
        background()
        haut = int(y * 0.24)
        gap, gap_v = L(18), H(18)
        cw = max(1, int(min(L(400), (x - L(80) - (cols - 1) * gap) / cols)))
        ch = max(1, int(min(H(150), (y - haut - H(80) - (rows - 1) * gap_v) / rows)))
        x0 = (x - (cols * cw + (cols - 1) * gap)) // 2
        cartes = [(pygame.Rect(x0 + (k % cols) * (cw + gap), haut + (k // cols) * (ch + gap_v), cw, ch), t)
                  for k, t in enumerate(THEMES)]
        hud()
        titre("THEMES")
        back = bouton_retour()

        for rect, t in cartes:
            _carte_theme(rect, t)

        if message:
            ecrire(message, (x / 2, y - H(40)), 24, (255, 130, 110), centre=True, gras=True)

        for event in evenements():
            if event.type == pygame.QUIT:
                quitter_jeu()

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return

            if event.type == pygame.MOUSEBUTTONDOWN:
                if back.collidepoint(event.pos):
                    return

                for rect, t in cartes:
                    if not rect.collidepoint(event.pos):
                        continue
                    if t["id"] in skinAcheter:
                        reussi, erreur = demander("/themes/equip", {"key": t["key"]}, "Action refusée")
                        message = f"Thème {t['name']} équipé" if reussi else erreur
                    else:
                        reussi, erreur = demander("/themes/buy", {"key": t["key"]}, "Achat refusé")
                        message = f"Thème {t['name']} acheté et équipé" if reussi else erreur
                    break

        flip()
        clock.tick(60)


def afficher_instruction():
    lines = [
        "Trois modes de jeu :",
        " - Classique : 30 secondes pour marquer un maximum de points.",
        " - Challenge : toucher 30 cibles le plus vite possible, en 120 secondes maximum.",
        "   Un clic raté ajoute 1 seconde. Une cible dorée compte double.",
        " - Survie : 3 vies. Clic raté, bombe ou cible manquée = une vie. Les cibles vont de plus en plus vite.",
        "",
        "Les points (Classique et Survie) :",
        " - Chaque cible touchée d'affilée fait monter le combo : 8 = x1.5, 20 = x2, 40 = x2.5.",
        " - Le combo retombe à zéro si tu rates un clic, ou si tu ne touches rien pendant 2 secondes",
        "   (la jauge sous le combo montre le temps qu'il reste).",
        " - Cible dorée (anneau doré) : vaut 3 fois plus.",
        " - Bombe (à partir de Medium) : n'y touche pas, elle coûte 3 secondes ou une vie.",
        " - Par cible : Easy 1, Medium 2, Hard 5, Impossible 15, Demonic 50 (cible invisible).",
        " - En Challenge, plus ton temps est court, plus tu gagnes de points.",
        "",
        "Boutique :  Slow = les cibles restent plus longtemps.  Aide = plus de cibles.  Score = multiplie tes points.",
        "            Thèmes = changent le fond, les boutons, les cibles et les sons.",
        "",
        "Missions et caisses :",
        " - 3 missions par jour (facile, moyenne, difficile) : une caisse à récupérer par mission accomplie.",
        " - 4 sortes de caisses ; leurs chances sont affichées dans l'écran Caisses.",
        " - Une caisse commune tous les 5 runs. Série de connexion : rare tous les 3 jours, légendaire tous les 7.",
        "",
        "Pause : bouton Pause en haut de l'écran, ou touche ESC.   F11 = plein écran.   F10 = volume du son.",
    ]

    while True:
        background()
        haut = int(y * 0.21)
        pas = max(1, min(H(30), (y - haut - H(60)) // len(lines)))
        taille = min(22, pas * 0.72 / S)  # taille de référence qui tient dans une ligne
        cadre = pygame.Rect(0, haut, min(L(980), x - L(60)), pas * len(lines) + H(36))
        cadre.centerx = x // 2
        titre("COMMENT JOUER")
        back = bouton_retour()
        panneau(cadre)

        t = theme_actuel()
        for i, line in enumerate(lines):
            entete = line and not line.startswith(" ")
            ecrire(line, (cadre.x + L(28), cadre.y + H(18) + i * pas), taille,
                   t["accent"] if entete else t["texte"], gras=bool(entete), max_w=cadre.width - L(56), ombre=False)

        for event in evenements():
            if event.type == pygame.QUIT:
                quitter_jeu()

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return

            if event.type == pygame.MOUSEBUTTONDOWN and back.collidepoint(event.pos):
                return

        flip()
        clock.tick(60)


# =========================
# CAISSES
# =========================
def texte_butin(lot):
    chances, genre, mini, maxi = lot
    return f"{fmt_score(chances)} % : " + ("un thème" if genre == "theme" else
                                          f"{fmt_score(mini)} à {fmt_score(maxi)} points")


def dessiner_caisse(cx, cy, cote, decalage=0, couleur=None):
    """Une caisse en bois carrée, façon far west. `couleur` = la couleur de sa rareté."""
    r = pygame.Rect(0, 0, cote, cote)
    r.center = (int(cx + decalage), int(cy))
    bois, fonce, clou = (182, 126, 70), (118, 76, 40), (226, 174, 88)
    fer = _mix((58, 44, 38), couleur, 0.75) if couleur else (58, 44, 38)
    ombre = pygame.Surface((cote, max(1, cote // 5)), pygame.SRCALPHA)
    pygame.draw.ellipse(ombre, (0, 0, 0, 90), ombre.get_rect())
    screen.blit(ombre, (r.x, r.bottom - cote // 12))
    pygame.draw.rect(screen, bois, r, border_radius=max(2, cote // 20))
    for n in range(1, 5):  # planches
        ly = r.y + n * cote // 5
        pygame.draw.line(screen, fonce, (r.x, ly), (r.right, ly), max(1, cote // 60))
    e = max(3, cote // 8)
    m = cote // 7
    for a, b in (((r.x + m, r.y + m), (r.right - m, r.bottom - m)), ((r.right - m, r.y + m), (r.x + m, r.bottom - m))):
        pygame.draw.line(screen, fonce, a, b, e + max(2, cote // 40))
        pygame.draw.line(screen, (150, 98, 54), a, b, e)
    pygame.draw.rect(screen, fer, r, max(3, cote // 11), border_radius=max(2, cote // 20))
    c = max(2, cote // 40)
    for px, py in ((r.x, r.y), (r.right, r.y), (r.x, r.bottom), (r.right, r.bottom)):
        pygame.draw.circle(screen, clou, (px + (c * 2 if px == r.x else -c * 2), py + (c * 2 if py == r.y else -c * 2)), c)
    if couleur:  # pierre de la couleur de la rareté, au centre
        g = max(4, cote // 7)
        losange = [(r.centerx, r.centery - g), (r.centerx + g, r.centery), (r.centerx, r.centery + g), (r.centerx - g, r.centery)]
        pygame.draw.polygon(screen, couleur, losange)
        pygame.draw.polygon(screen, _mix(couleur, (255, 255, 255), 0.6), losange, max(1, cote // 50))


def afficher_caisses():
    """Les 4 sortes de caisses, leurs chances affichées, et l'ouverture.
    C'est le serveur qui tire le contenu, avec exactement les chances affichées ici."""
    actualiser_en_fond()
    vider_effets()
    etat, debut, butin, message = "choix", 0, None, ""
    ouverte = RARETES[0]   # la caisse en cours d'ouverture
    montree = next((r for r in RARETES if caisses.get(r[0])), RARETES[0])  # celle dont on affiche les chances

    while True:
        dt = min(clock.tick(60), 100) / 1000
        background()
        hud()
        titre("CAISSES")
        back = bouton_retour()
        t = theme_actuel()
        now = pygame.time.get_ticks()
        cx, cy, cote = x // 2, int(y * 0.47), U(230)
        boutons = []      # (rect du bouton Ouvrir, rareté)
        continuer = None

        if etat == "choix":
            cartes = rangee(len(RARETES), y * 0.46, 330, 400, 26)
            for carte, rarete in zip(cartes, RARETES):
                cle, nom, couleur = rarete
                nombre = caisses.get(cle, 0)
                if carte.collidepoint(souris()):
                    montree = rarete
                panneau(carte, bord=4 if rarete is montree else 2)
                taille = max(8, min(U(150), carte.width - L(60), carte.height // 3))
                dessiner_caisse(carte.centerx, carte.y + H(40) + taille // 2, taille,
                                math.sin(now / 260 + carte.x) * U(3) if nombre else 0, couleur)
                ecrire(nom, (carte.centerx, carte.y + H(70) + taille), 28, couleur, centre=True, gras=True,
                       max_w=carte.width - L(20))
                ecrire(f"x {nombre}", (carte.centerx, carte.y + H(112) + taille), 30, centre=True, gras=True)
                rect = pygame.Rect(0, 0, carte.width - L(50), H(70))
                rect.midbottom = (carte.centerx, carte.bottom - H(22))
                if nombre:
                    boutons.append((bouton(rect, "Ouvrir"), rarete))
                else:
                    bouton(rect, "Aucune", etat="acquis")
            # les chances de la caisse survolée
            cadre = pygame.Rect(0, 0, min(L(1150), x - L(60)), H(120))
            cadre.midtop = (x // 2, cartes[0].bottom + H(26))
            panneau(cadre)
            ecrire(f"Dans une caisse {montree[1].lower()} :", (cadre.centerx, cadre.y + H(32)), 22, montree[2],
                   centre=True, gras=True)
            ecrire("     ".join(texte_butin(lot) for lot in BUTIN.get(montree[0], [])),
                   (cadre.centerx, cadre.y + H(78)), 24, centre=True, max_w=cadre.width - L(40))
        elif etat == "ouverture":  # la caisse tremble de plus en plus fort, puis s'ouvre
            avance = (now - debut) / 1000
            dessiner_caisse(cx, cy, cote, math.sin(now / 22) * U(4 + 22 * avance), ouverte[2])
            if avance >= 1.0:
                etat = "resultat"
                jouer("caisse")
                secouer(U(12))
                eclat((cx, cy), [ouverte[2], (255, 248, 190), t["accent"], (255, 255, 255)], 60, 1.6)
        else:  # résultat
            ecrire(f"Caisse {ouverte[1].lower()}", (cx, y * 0.25), 26, ouverte[2], centre=True, gras=True)
            if butin.get("kind") == "theme" and butin.get("key") in THEME_BY_KEY:
                gagne = THEME_BY_KEY[butin["key"]]
                ecrire("NOUVEAU THÈME !", (cx, cy - U(130)), 40, OR, centre=True, gras=True)
                zone = pygame.Rect(0, 0, U(150), U(150))
                zone.center = (cx, cy)
                dessiner_cible(zone, gagne)
                ecrire(gagne["name"], (cx, cy + U(118)), 34, centre=True, gras=True)
                ecrire("À équiper dans Shop > Thèmes", (cx, cy + U(160)), 20, centre=True)
            else:
                ecrire(f"+{fmt_score(butin.get('amount', 0))}", (cx, cy - U(20)), 110, OR, centre=True, gras=True)
                ecrire("points", (cx, cy + U(70)), 36, centre=True, gras=True)
            continuer = bouton(rangee(1, y * 0.80, 300, 84)[0], "Continuer")
        if message:
            ecrire(message, (cx, y - H(34)), 24, (255, 130, 110), centre=True, gras=True)

        maj_effets(dt)
        dessiner_effets()

        for event in evenements():
            if event.type == pygame.QUIT:
                quitter_jeu()
            if etat == "ouverture":
                continue
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if etat == "choix":
                    return
                etat = "choix"
            if event.type == pygame.MOUSEBUTTONDOWN:
                if back.collidepoint(event.pos):
                    return
                if continuer and continuer.collidepoint(event.pos):
                    etat = "choix"
                for rect, rarete in boutons:
                    if rect.collidepoint(event.pos):
                        r = api_post_json("/crates/open", {"rarity": rarete[0]})
                        if r is not None and r.status_code == 200:
                            butin = r.json().get("reward", {})
                            appliquer_etat(r.json().get("player", {}))
                            etat, debut, message, ouverte = "ouverture", pygame.time.get_ticks(), "", rarete
                            jouer("decompte")
                        else:
                            message = detail_erreur(r, "Ouverture refusée")

        appliquer_secousse()
        flip()


# =========================
# MISSIONS DU JOUR
# =========================
COULEURS_DIFFICULTE = {"facile": (120, 220, 130), "moyenne": (255, 180, 70), "difficile": (255, 105, 95)}


def afficher_missions():
    """3 missions par jour : une facile, une moyenne, une difficile. Une mission accomplie
    donne une caisse (plus rare si la mission est dure) et des points, à récupérer ici."""
    lecture, missions, fin = EnFond("/missions"), [], 0
    couleur_rarete = {cle: couleur for cle, _, couleur in RARETES}
    message = ""
    vider_effets()

    while True:
        dt = min(clock.tick(60), 100) / 1000
        if lecture is not None and lecture.prete:
            data = lecture.json({})
            missions = data.get("missions", [])
            fin = pygame.time.get_ticks() + int(data.get("reset_in", 0)) * 1000
            lecture = None
        background()
        hud()
        titre("MISSIONS DU JOUR")
        back = bouton_retour()
        t = theme_actuel()

        larg, haut_carte, ecart = min(L(1100), x - L(80)), H(150), H(20)
        y0 = int(y * 0.25)
        boutons = []
        for n, m in enumerate(missions):
            carte = pygame.Rect((x - larg) // 2, y0 + n * (haut_carte + ecart), larg, haut_carte)
            fini, pris = m.get("done"), m.get("claimed")
            panneau(carte, bord=4 if fini and not pris else 2)
            coul_diff = COULEURS_DIFFICULTE.get(m.get("difficulty"), t["texte"])
            ecrire(str(m.get("difficulty", "")).upper(), (carte.x + L(28), carte.y + H(16)), 18, coul_diff, gras=True)
            ecrire(m.get("category", ""), (carte.x + L(160), carte.y + H(16)), 18, _mix(t["texte"], t["panneau"], 0.3))
            ecrire(m.get("label", ""), (carte.x + L(28), carte.y + H(46)), 26, gras=True, max_w=larg - L(330))
            cible, fait = max(1, int(m.get("target", 1))), int(m.get("progress", 0))
            barre = pygame.Rect(carte.x + L(28), carte.bottom - H(42), larg - L(430), H(20))
            pygame.draw.rect(screen, _mix(t["panneau"], (0, 0, 0), 0.4), barre, border_radius=U(8))
            if fait:
                plein = barre.copy()
                plein.width = max(U(8), int(barre.width * min(1, fait / cible)))
                pygame.draw.rect(screen, coul_diff, plein, border_radius=U(8))
            ecrire(f"{fait}/{cible}", (barre.right + L(16), barre.y - U(4)), 22, gras=True)
            # à droite : la récompense, puis le bouton pour la récupérer
            zone = pygame.Rect(carte.right - L(290), carte.y, L(270), haut_carte)
            ecrire(m.get("reward", ""), (zone.centerx, zone.y + H(34)), 20, couleur_rarete.get(m.get("rarity"), OR),
                   centre=True, gras=True, max_w=zone.width)
            rect = pygame.Rect(0, 0, zone.width - L(30), H(62))
            rect.midbottom = (zone.centerx, carte.bottom - H(18))
            if fini and not pris:
                boutons.append((bouton(rect, "Récupérer"), m))
            elif pris:
                ecrire("Récupérée", rect.center, 24, (140, 255, 150), centre=True, gras=True)
            else:
                ecrire("En cours", rect.center, 20, _mix(t["texte"], t["panneau"], 0.4), centre=True)
        if not missions:
            ecrire("Chargement..." if lecture else "Missions indisponibles (serveur injoignable)",
                   (x / 2, y / 2), 24, centre=True)
        else:
            reste = max(0, (fin - pygame.time.get_ticks()) // 1000)
            ecrire(f"Nouvelles missions dans {reste // 3600} h {reste % 3600 // 60:02d} min   |   "
                   f"Série de connexion : {serie} jour" + ("s" if serie > 1 else ""),
                   (x / 2, y0 + 3 * (haut_carte + ecart) + H(16)), 20, centre=True, max_w=x - L(80))
        if message:
            ecrire(message, (x / 2, y - H(40)), 24, (140, 255, 150), centre=True, gras=True)

        maj_effets(dt)
        dessiner_effets()

        for event in evenements():
            if event.type == pygame.QUIT:
                quitter_jeu()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                if back.collidepoint(event.pos):
                    return
                for rect, m in boutons:
                    if rect.collidepoint(event.pos):
                        r = api_post_json("/missions/claim", {"slot": m.get("slot")})
                        if r is not None and r.status_code == 200:
                            missions = r.json().get("missions", missions)
                            appliquer_etat(r.json().get("player", {}))
                            message = m.get("reward", "") + " : dans ta réserve !"
                            jouer("mission")
                            eclat(rect.center, [couleur_rarete.get(m.get("rarity"), OR), (255, 255, 255), OR], 40, 1.4)
                        else:
                            message = detail_erreur(r, "Récompense refusée")

        flip()


# =========================
# JEU : LE RUN
# =========================
def palier_combo(combo):
    """Multiplicateur du combo : x1, puis x1.5 à 5 cibles d'affilée, x2 à 10, etc."""
    return next(m for seuil, m in PALIERS_COMBO if combo >= seuil)


def numero_palier(combo):
    return sum(1 for seuil, _ in PALIERS_COMBO if combo >= seuil) - 1


def placer_cible(d, occupes):
    """Un emplacement libre sous la barre du haut, sans chevaucher les autres cibles."""
    haut = min(H(96), max(0, y - d))
    for _ in range(25):
        r = pygame.Rect(randint(0, max(0, x - d)), randint(haut, max(haut, y - d)), d, d)
        if not any(r.inflate(U(12), U(12)).colliderect(o) for o in occupes):
            break
    return r


def nouvelles_cibles(mode, genre="classic"):
    """Tire un nouveau jeu de cibles. Genres de cible : normale, or, bombe, leurre, invisible."""
    cibles = []

    def ajouter(sorte):
        d = max(8, U(randint(48, 112)))  # diamètre : 48 à 112 en mesure de référence
        cibles.append({"rect": placer_cible(d, [c["rect"] for c in cibles]), "genre": sorte,
                       "ne": pygame.time.get_ticks()})

    if mode == "demonic":  # la vraie cible est invisible, les visibles sont des pièges
        for _ in range(1 + len(but_bonus)):
            ajouter("leurre")
        ajouter("invisible")
    else:
        ajouter("or" if random() < CHANCE_DOREE else "normale")
        for _ in but_bonus:  # bonus Aide : une cible de plus par niveau
            ajouter("normale")
        if mode != "easy" and random() < CHANCE_BOMBE:
            ajouter("bombe")
    return cibles


def clic_rate(mode, genre, st, pos, texte_affiche=None):
    """Clic dans le vide. Classique : le combo retombe à zéro. Challenge : du temps en plus.
    Survie : une vie en moins (retirée par jouer_run)."""
    if genre == "challenge":
        texte_affiche = f"Raté  +{fmt_score(CHALLENGE['rate_s'])} s"
        st["alerte"] = 0.6  # le chrono clignote en rouge
    elif genre == "survival":
        texte_affiche = "Raté  -1 vie"
    else:
        aveugle = mode in MODES_SANS_PENALITE  # modes où l'on clique à l'aveugle : pas de message à chaque clic
        perte = 0 if aveugle else min(st["score"], compute_gain(mode) * PENALITE_RATE)
        st["score"] -= perte
        if not texte_affiche and not aveugle:
            texte_affiche = "Raté"
        if st["combo"] >= PALIERS_COMBO[-2][0]:
            texte_affiche = (texte_affiche + " : " if texte_affiche else "") + "combo perdu"
        if perte:
            texte_affiche += f"  -{fmt_score(perte)} pt"
    if texte_affiche:
        texte_volant(pos, texte_affiche, (255, 120, 100), 28)
    st["misses"] += 1
    st["combo"] = 0
    jouer("rate")


def clic_run(mode, genre, cibles, pos, st):
    """Traite un clic pendant un run. Renvoie "touche", "bombe", "leurre" ou "rate"."""
    if mode == "demonic":
        if any(c["genre"] == "leurre" and touche(c["rect"], pos, U(10)) for c in cibles):
            clic_rate(mode, genre, st, pos, "Piège !")
            return "leurre"
        cible = next((c for c in cibles if c["genre"] == "invisible" and touche(c["rect"], pos)), None)
    else:
        cible = next((c for c in reversed(cibles) if touche(c["rect"], pos)), None)
    if cible is None:
        clic_rate(mode, genre, st, pos)
        return "rate"

    centre = cible["rect"].center
    if cible["genre"] == "bombe":
        st["bombs"] += 1
        st["combo"] = 0
        jouer("bombe")
        secouer(U(18))
        eclat(centre, [(255, 80, 60), (50, 46, 52), (255, 180, 60)], 28, 1.5)
        texte_volant(centre, {"challenge": f"+{fmt_score(PENALITE_BOMBE)} s", "survival": "-1 vie"}.get(
            genre, f"-{fmt_score(PENALITE_BOMBE)} s"), (255, 90, 70), 36)
        return "bombe"

    t = theme_actuel()
    doree = cible["genre"] == "or"
    st["hits"] += 1
    st["golden"] += doree
    if doree:
        jouer("or")
        secouer(U(7))
        eclat(centre, [OR, (255, 248, 190), (255, 255, 255)], 30, 1.4)
    else:
        eclat(centre, [t["accent"], t["bord"], t["texte"]], 14)

    if genre == "challenge":  # pas de points ici : seul le nombre de cibles compte
        st["restantes"] = max(0, st["restantes"] - (2 if doree else 1))
        fait = CHALLENGE["cibles"] - st["restantes"]
        if doree:
            texte_volant(centre, "Compte double !", OR, 30)
        else:
            jouer("hit", fait * 5 // max(1, CHALLENGE["cibles"]))  # la note monte avec l'avancement
        return "touche"

    avant = numero_palier(st["combo"])
    st["combo"] += 1
    st["best_combo"] = max(st["best_combo"], st["combo"])
    gain = compute_gain(mode) * palier_combo(st["combo"]) * (BONUS_DOREE if doree else 1)
    st["score"] += gain
    apres = numero_palier(st["combo"])
    if not doree:
        jouer("hit", apres)
    texte_volant(centre, "+" + fmt_score(gain), OR if doree else (255, 255, 255), 46 if doree else 34, 0.9)
    if apres > avant:  # nouveau palier de combo
        jouer("palier")
        secouer(U(9))
        texte_volant((x / 2, y * 0.34), f"COMBO x{fmt_score(palier_combo(st['combo']))} !", t["accent"], 60, 1.1)
    return "touche"


def delai_cibles(mode, genre, st):
    """Temps (ms) pendant lequel les cibles restent en place."""
    if genre != "survival":
        return delai
    depart, mini = SURVIE["delais"].get(mode, (1700, 450))
    bonus_slow = delai_pour(mode) - DELAIS[mode][0]  # ce que le bonus Slow ajoute
    return max(mini, depart * SURVIE["acceleration"] ** st["hits"]) + bonus_slow


def rect_pause():
    """Le bouton Pause, dans le bandeau du haut (les cibles n'apparaissent jamais dessous)."""
    c = max(U(58), 34)
    r = pygame.Rect(0, 0, c, c)
    r.midtop = (int(x * 0.27), H(20))
    return r


def bouton_pause():
    """Le bouton Pause : les deux barres || habituelles."""
    r = bouton(rect_pause(), "")
    coul = theme_actuel()["texte"]
    larg, haut = max(3, r.width // 7), int(r.height * 0.46)
    for dx in (-1, 1):
        barre = pygame.Rect(0, 0, larg, haut)
        barre.center = (r.centerx + dx * int(larg * 1.1), r.centery)
        pygame.draw.rect(screen, coul, barre, border_radius=max(1, larg // 3))
    return r


def dessiner_run(mode, genre, cibles, st, ecoule, duree, temps_cibles, age_cibles):
    t = theme_actuel()
    now = pygame.time.get_ticks()
    anime = temps_cibles >= 250  # pas d'effet d'apparition quand les cibles bougent très vite
    reste_vague = max(0.0, 1 - age_cibles / max(1, temps_cibles))
    for c in cibles:
        if c["genre"] == "invisible":
            if 3 in but_bonus and len(ralentisseur) >= len(PRIX_AMELIORATIONS["slow"]):  # trace à peine perceptible
                r = c["rect"]
                trace = pygame.Surface(r.size, pygame.SRCALPHA)
                pygame.draw.circle(trace, (255, 255, 255, 7), (r.width // 2, r.height // 2), r.width // 2)
                screen.blit(trace, r.topleft)
            continue
        age = now - c["ne"]
        echelle = 1.0 if not anime or age >= 90 else (0.7 if age < 45 else 0.85)
        if genre == "survival" and c["genre"] != "bombe":  # anneau qui se referme : le temps qu'il reste
            rayon = c["rect"].width // 2 + U(12) + int(U(30) * reste_vague)
            pygame.draw.circle(screen, _mix((255, 80, 60), t["accent"], reste_vague), c["rect"].center, rayon,
                               max(2, U(4)))
        dessiner_cible_speciale(c["rect"], "normale" if c["genre"] == "leurre" else c["genre"], echelle)
    dessiner_effets()

    fond_barre = _mix(t["panneau"], (0, 0, 0), 0.3)
    pygame.draw.rect(screen, fond_barre, (0, 0, x, H(12)))
    bouton_pause()
    rouge = (255, 90, 70)
    if genre == "challenge":  # barre d'avancement, chrono qui monte, compteur de cibles
        total, limite = CHALLENGE["cibles"], CHALLENGE["max_s"]
        fait = total - st["restantes"]
        pygame.draw.rect(screen, t["accent"], (0, 0, int(x * fait / total), H(12)))
        presse = st["alerte"] > 0 or limite - ecoule < 15  # pénalité récente, ou limite toute proche
        ecrire(f"{ecoule:.1f} s", (L(26), H(24)), 44, rouge if presse else None, gras=True)
        ecrire(f"limite : {fmt_score(limite)} s", (L(26), H(78)), 18, rouge if limite - ecoule < 15 else None)
        ecrire(f"{fait}/{total}", (x / 2, H(52)), 54, t["accent"], centre=True, gras=True)
        return

    if genre == "survival":
        pygame.draw.rect(screen, _mix(rouge, t["accent"], reste_vague), (0, 0, int(x * reste_vague), H(12)))
        r = max(4, U(15))
        for n in range(SURVIE["vies"]):  # les vies, à droite
            centre = (x - L(40) - n * (2 * r + U(12)), H(48))
            if n < st["vies"]:
                pygame.draw.circle(screen, (255, 80, 80), centre, r)
            pygame.draw.circle(screen, t["texte"], centre, r, max(1, U(3)))
    else:
        reste = duree - ecoule
        coul = rouge if reste < 5 else t["accent"]
        pygame.draw.rect(screen, coul, (0, 0, int(x * max(0.0, reste) / duree), H(12)))
        secondes = f"{max(0.0, reste):.1f}"
        ecrire(secondes, (x - L(26) - police(44, True).size(secondes)[0], H(24)), 44, coul, gras=True)
    ecrire(fmt_score(st["score"]), (L(26), H(24)), 44, gras=True)
    if st["combo"] >= 2:
        mult = palier_combo(st["combo"])
        ecrire(f"Combo {st['combo']}" + (f"   x{fmt_score(mult)}" if mult > 1 else ""), (x / 2, H(40)), 32,
               t["accent"] if mult > 1 else None, centre=True, gras=True)
        # jauge du combo : elle se vide tant qu'on ne touche rien ; vide = combo perdu
        jauge = pygame.Rect(0, 0, L(220), max(3, H(9)))
        jauge.midtop = (x // 2, H(66))
        part = max(0.0, min(1.0, st["combo_t"] / COMBO_DUREE))
        pygame.draw.rect(screen, fond_barre, jauge, border_radius=U(4))
        pygame.draw.rect(screen, _mix(rouge, t["accent"], part), (jauge.x, jauge.y, int(jauge.width * part), jauge.height),
                         border_radius=U(4))


def decompte():
    """3, 2, 1, GO. Renvoie False si le joueur annule avec ESC."""
    for etape in ("3", "2", "1", "GO"):
        jouer("go" if etape == "GO" else "decompte")
        fin = pygame.time.get_ticks() + (350 if etape == "GO" else 600)
        while pygame.time.get_ticks() < fin:
            background()
            ecrire(etape, (x / 2, y / 2), 170, theme_actuel()["accent"], centre=True, gras=True)
            for event in evenements():
                if event.type == pygame.QUIT:
                    quitter_jeu()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return False
            flip()
            clock.tick(60)
    return True


def menu_abandon(genre="classic"):
    """Pause (ESC). Renvoie True si le joueur abandonne le run."""
    while True:
        background()
        titre("PAUSE", int(y * 0.30))
        if genre == "challenge":
            ecrire("En Challenge, le chrono continue pendant la pause.", (x / 2, y * 0.42), 24, (255, 130, 110),
                   centre=True, gras=True)
        sortir, reprendre = rangee(2, y * 0.55, 240, 96, 40)
        bouton(sortir, "Abandonner", "le run est perdu")
        bouton(reprendre, "Reprendre", "ESC")

        for click in evenements():
            if click.type == pygame.QUIT:
                quitter_jeu()
            if click.type == pygame.MOUSEBUTTONDOWN:
                if sortir.collidepoint(click.pos):
                    return True
                if reprendre.collidepoint(click.pos):
                    return False
            if click.type == pygame.KEYDOWN and click.key == pygame.K_ESCAPE:
                return False

        flip()
        clock.tick(60)


def jouer_run(mode, genre="classic"):
    """Un run dans le mode de jeu choisi.
    Renvoie (stats, réponse du serveur), ou None si abandonné, ou un texte d'erreur."""
    r = api_post_json("/run/start", {"mode": mode, "kind": genre})
    if r is None or r.status_code != 200:
        return detail_erreur(r, "Impossible de lancer le run")
    run_id = r.json().get("run_id")
    duree = float(r.json().get("duration", DUREE_RUN))

    vider_effets()
    if not decompte():
        return None

    st = {"score": 0.0, "hits": 0, "misses": 0, "golden": 0, "bombs": 0, "combo": 0, "best_combo": 0,
          "combo_t": 0.0, "alerte": 0.0, "vies": SURVIE["vies"], "restantes": CHALLENGE["cibles"], "temps_ms": 0}
    cibles = nouvelles_cibles(mode, genre)
    depart_cibles = pygame.time.get_ticks()
    ecoule = 0.0
    vue = (x, y, S)
    clock.tick(60)

    def termine():
        if genre == "challenge":
            return st["restantes"] <= 0 or ecoule >= CHALLENGE["max_s"]
        if genre == "survival":
            return st["vies"] <= 0 or ecoule >= SURVIE["max_s"]
        return ecoule >= duree

    while not termine():
        dt = min(clock.tick(60), 100) / 1000
        ecoule += dt
        st["alerte"] = max(0.0, st["alerte"] - dt)
        background()
        if (x, y, S) != vue:  # fenêtre redimensionnée en plein run
            for c in cibles:
                replacer_cible(c["rect"], vue)
            vue = (x, y, S)

        # Le combo ne tient que si on continue à toucher : la jauge se vide, puis il est perdu.
        if st["combo"] > 0:
            st["combo_t"] -= dt
            if st["combo_t"] <= 0:
                if st["combo"] >= PALIERS_COMBO[-2][0]:
                    texte_volant((x / 2, H(120)), "Trop lent : combo perdu", (255, 120, 100), 28)
                st["combo"] = 0

        temps_cibles = delai_cibles(mode, genre, st)
        if pygame.time.get_ticks() - depart_cibles >= temps_cibles:  # les cibles changent de place
            if genre == "survival":  # personne n'a touché la cible à temps
                manquee = next((c for c in cibles if c["genre"] != "bombe"), cibles[0])
                texte_volant(manquee["rect"].center, "Cible manquée  -1 vie", (255, 120, 100), 28)
                st["vies"] -= 1
                st["combo"] = 0
                jouer("rate")
                secouer(U(10))
            cibles = nouvelles_cibles(mode, genre)
            depart_cibles = pygame.time.get_ticks()

        for event in evenements():
            if event.type == pygame.QUIT:
                quitter_jeu()
            clic = event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1
            if (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE) or \
                    (clic and rect_pause().collidepoint(event.pos)):
                debut_pause = pygame.time.get_ticks()
                if menu_abandon(genre):
                    return None
                if genre == "challenge":  # en Challenge le chrono continue pendant la pause
                    ecoule += (pygame.time.get_ticks() - debut_pause) / 1000
                clock.tick(60)  # ailleurs, la pause ne compte pas
                cibles = nouvelles_cibles(mode, genre)  # nouvelles cibles : pas de visée pendant la pause
                depart_cibles = pygame.time.get_ticks()
            elif clic:
                resultat = clic_run(mode, genre, cibles, event.pos, st)
                if resultat == "touche":
                    st["combo_t"] = COMBO_DUREE
                if genre == "survival":
                    if resultat != "touche":
                        st["vies"] -= 1
                        secouer(U(10))
                elif resultat == "bombe":
                    ecoule += PENALITE_BOMBE
                    st["alerte"] = 0.6
                elif resultat == "rate" and genre == "challenge":
                    ecoule += CHALLENGE["rate_s"]
                if resultat != "rate":
                    cibles = nouvelles_cibles(mode, genre)
                    depart_cibles = pygame.time.get_ticks()

        maj_effets(dt)
        dessiner_run(mode, genre, cibles, st, ecoule, duree, temps_cibles, pygame.time.get_ticks() - depart_cibles)
        appliquer_secousse()
        flip()

    st["temps_ms"] = int(round(ecoule * 1000))
    if genre == "challenge" and st["restantes"] > 0:
        return st, {"erreur": "limite de temps dépassée", "perdu": True}

    # Le jeu envoie le détail du run ; le serveur vérifie qu'il est possible avant de créditer.
    r = api_post_json("/run/end", {"run_id": run_id, "hits": st["hits"], "misses": st["misses"],
                                   "golden": st["golden"], "best_combo": st["best_combo"],
                                   "bombs": st["bombs"], "score": st["score"],
                                   "time_ms": st["temps_ms"]}, timeout=8)
    if r is not None and r.status_code == 200:
        reponse = r.json()
        appliquer_etat(reponse.get("player", {}))
    else:
        reponse = {"erreur": detail_erreur(r, "Run non enregistré")}
    return st, reponse


def ecran_fin(mode, genre, st, reponse):
    """Résultat du run. Renvoie "replay", "difficulte", "menu" ou "quit"."""
    vider_effets()
    challenge = genre == "challenge"
    perdu = bool(reponse.get("perdu"))
    points = float(reponse.get("score", 0 if challenge else st["score"]))
    record = bool(reponse.get("record")) and (challenge or st["score"] > 0)
    jouer("record" if record else "fin")
    tirs = st["hits"] + st["misses"]
    precision = round(100 * st["hits"] / tirs) if tirs else 0
    nom_mode = NOMS_MODES[mode]
    en_clair = (lambda v: fmt_temps(v)) if challenge else fmt_score

    infos = []  # (texte, couleur ou None)
    if perdu:
        infos.append((f"La limite de {fmt_score(CHALLENGE['max_s'])} secondes est dépassée : il restait "
                      f"{st['restantes']} cible" + ("s" if st["restantes"] > 1 else "") + " à toucher.", None))
        infos.append(("Chaque clic raté ajoute du temps : vise bien plutôt que de cliquer vite.", None))
    elif "erreur" in reponse:
        infos.append(("Run non enregistré : " + reponse["erreur"], (255, 130, 110)))
    else:
        ancien = reponse.get("previous_best", 0)
        if record:
            infos.append((f"Ancien record {nom_mode} : {en_clair(ancien)}" if ancien else
                          f"Premier record en {nom_mode} !", None))
        else:
            ecart = (st["temps_ms"] - ancien) if challenge else (ancien - st["score"])
            infos.append((f"Record {nom_mode} : {en_clair(ancien)}  (il te manquait {en_clair(ecart)})", None))
        for m in reponse.get("missions", []):
            infos.append((f"Mission accomplie : {m.get('label', '')}", (140, 255, 150)))
            infos.append((f"{m.get('reward', '')} à récupérer dans Missions", (140, 255, 150)))
        if reponse.get("crate"):
            infos.append(("+1 caisse commune à ouvrir !", OR))
        elif reponse.get("next_crate_in"):
            n = int(reponse["next_crate_in"])
            infos.append((f"Prochaine caisse dans {n} run" + ("s" if n > 1 else ""), None))

    if perdu:
        nom_ecran = "TEMPS DÉPASSÉ"
    elif record:
        nom_ecran = "NOUVEAU RECORD !"
    else:
        nom_ecran = {"challenge": "CHALLENGE RÉUSSI", "survival": "PLUS DE VIES"}.get(genre, "TEMPS ÉCOULÉ")
    if challenge:
        colonnes = [("Cibles", st["hits"]), ("Précision", f"{precision} %"),
                    ("Clics ratés", st["misses"]), ("Bombes", st["bombs"])]
    else:
        colonnes = [("Cibles", st["hits"]), ("Précision", f"{precision} %"),
                    ("Meilleur combo", st["best_combo"]), ("Dorées", st["golden"])]

    prochain_feu = 0
    while True:
        dt = min(clock.tick(60), 100) / 1000
        background()
        hud()
        t = theme_actuel()
        titre(nom_ecran, int(y * 0.11))
        if record and pygame.time.get_ticks() > prochain_feu:  # petit feu d'artifice
            eclat((randint(int(x * 0.2), int(x * 0.8)), randint(int(y * 0.1), int(y * 0.4))),
                  [OR, t["accent"], (255, 255, 255)], 26, 1.3)
            prochain_feu = pygame.time.get_ticks() + 450

        cadre = pygame.Rect(0, 0, min(L(900), x - L(60)), H(160) + H(42) * max(1, len(infos)) + H(150))
        cadre.midtop = (x // 2, int(y * 0.21))
        panneau(cadre)
        couleur = OR if record else t["accent"]
        if perdu:
            ecrire("Challenge perdu", (x / 2, cadre.y + H(80)), 64, (255, 120, 100), centre=True, gras=True)
        elif challenge:  # le chrono en grand, les points gagnés en dessous
            ecrire(fmt_temps(st["temps_ms"]), (x / 2, cadre.y + H(62)), 84, couleur, centre=True, gras=True)
            ecrire(f"+{fmt_score(points)} points" if "erreur" not in reponse else "", (x / 2, cadre.y + H(124)), 26,
                   centre=True, gras=True)
        else:
            ecrire("+" + fmt_score(points), (x / 2, cadre.y + H(62)), 84, couleur, centre=True, gras=True)
            ecrire("points", (x / 2, cadre.y + H(124)), 24, centre=True)
        for n, (nom, valeur) in enumerate(colonnes):
            cx = cadre.x + cadre.width * (2 * n + 1) // 8
            ecrire(valeur, (cx, cadre.y + H(190)), 36, centre=True, gras=True)
            ecrire(nom, (cx, cadre.y + H(232)), 18, centre=True, max_w=cadre.width // 4 - L(10))
        for n, (ligne, coul) in enumerate(infos):
            ecrire(ligne, (x / 2, cadre.y + H(290) + n * H(42)), 22, coul, centre=True, gras=coul is not None,
                   max_w=cadre.width - L(40))

        rejouer, difficulte, menu_btn, quitter = rangee(4, min(y - H(70), cadre.bottom + H(70)), 230, 88, 26)
        bouton(rejouer, "Replay", nom_mode)
        bouton(difficulte, "Difficulté")
        bouton(menu_btn, "Menus")
        bouton(quitter, "Leave")

        maj_effets(dt)
        dessiner_effets()

        for event in evenements():
            if event.type == pygame.QUIT:
                quitter_jeu()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if rejouer.collidepoint(event.pos):
                    return "replay"
                if difficulte.collidepoint(event.pos):
                    return "difficulte"
                if menu_btn.collidepoint(event.pos):
                    return "menu"
                if quitter.collidepoint(event.pos):
                    return "quit"

        flip()


def start(mode, genre="classic"):
    """Enchaîne les runs. Renvoie (action, message) : action = "menu" ou "difficulte"."""
    while True:
        resultat = jouer_run(mode, genre)
        if resultat is None:           # abandonné
            return "difficulte", ""
        if isinstance(resultat, str):  # le run n'a pas pu démarrer
            return "difficulte", resultat
        action = ecran_fin(mode, genre, *resultat)
        if action == "replay":
            continue
        if action == "quit":
            quitter_jeu()
        return action, ""


# =========================
# DEMARRAGE
# =========================
if __name__ == "__main__":
    afficher_login()