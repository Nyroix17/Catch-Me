import pygame
from random import randint
import tkinter as TK
import requests

BASE_URL = "https://clickme.abrdns.com"  # ou l'IP de ton serveur

pseudo_joueur = ""
root = TK.Tk()
root.withdraw()
x = root.winfo_screenwidth()
y = root.winfo_screenheight()

# BY IA
class InputBox:
    def __init__(self, x, y, w, h, password=False):
        self.rect = pygame.Rect(x, y, w, h)
        self.color_inactive = pygame.Color("lightskyblue3")
        self.color_active = pygame.Color("dodgerblue2")
        self.color = self.color_inactive
        self.text = ""
        self.password = password
        self.active = False
        self.txt_surface = font.render("", True, (255,255,255))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
            self.color = self.color_active if self.active else self.color_inactive

        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                self.text += event.unicode

            display_text = "*" * len(self.text) if self.password else self.text
            self.txt_surface = font.render(display_text, True, (255,255,255))

    def draw(self, screen):
        screen.blit(self.txt_surface, (self.rect.x + 5, self.rect.y + 5))
        pygame.draw.rect(screen, self.color, self.rect, 2)

def draw_button(text, x, y, w, h):
    rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(screen, (70,70,70), rect)
    pygame.draw.rect(screen, (200,200,200), rect, 2)
    label = font.render(text, True, (255,255,255))
    screen.blit(label, (x + 10, y + 10))
    return rect

def login():
    username_box = InputBox(x/2 - 150, y/2 - 80, 300, 40)
    password_box = InputBox(x/2 - 150, y/2 - 20, 300, 40, password=True)
    message = ""
    
    running = True
    while running:
        background()
        # Titre et labels
        screen.blit(font.render("LOGIN", True, (255,255,255)), (x/2 - 50, 100))
        screen.blit(font.render("Username :", True, (255,255,255)), (username_box.rect.x, username_box.rect.y - 30))
        screen.blit(font.render("Password :", True, (255,255,255)), (password_box.rect.x, password_box.rect.y - 30))
        
        username_box.draw(screen)
        password_box.draw(screen)
        
        login_btn = draw_button("Login", x/2 - 150, y/2 + 50, 120, 50)
        register_btn = draw_button("Register", x/2 + 30, y/2 + 50, 120, 50)
        
        if message:
            screen.blit(font.render(message, True, (255,100,100)), (x/2 - 100, y/2 + 120))
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
            username_box.handle_event(event)
            password_box.handle_event(event)
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if login_btn.collidepoint(event.pos):
                    try:
                        r = requests.post(BASE_URL + "/login", params={
                            "pseudo": username_box.text,
                            "password": password_box.text
                        }, timeout=5)
                        if r.status_code == 200:
                            # Stocke toutes les infos du joueur pour réutilisation
                            data = r.json()
                            global score, ralentisseur, but_bonus, multiplicateur, skinAcheter, CouleurSkin
                            score = data.get("score", 0)
                            ralentisseur = data.get("ralentisseur", [])
                            but_bonus = data.get("but_bonus", [])
                            multiplicateur = data.get("multiplicateur", [])
                            skinAcheter = data.get("skinAcheter", ["Green"])
                            CouleurSkin = data.get("CouleurSkin", "Green")
                            
                            message = "Connexion réussie"
                            pygame.time.wait(500)
                            menus_principale()
                            return
                        else:
                            message = "Identifiants incorrects"
                    except:
                        message = "Erreur serveur"
                        
                if register_btn.collidepoint(event.pos):
                    register()
                    return
        flip()

def register():
    username_box = InputBox(x/2 - 150, y/2 - 120, 300, 40)
    password_box = InputBox(x/2 - 150, y/2 - 60, 300, 40, password=True)
    confirm_box = InputBox(x/2 - 150, y/2, 300, 40, password=True)
    message = ""
    
    running = True
    while running:
        background()
        screen.blit(font.render("REGISTER", True, (255,255,255)), (x/2 - 60, 100))
        screen.blit(font.render("Username :", True, (255,255,255)), (username_box.rect.x, username_box.rect.y - 30))
        screen.blit(font.render("Password :", True, (255,255,255)), (password_box.rect.x, password_box.rect.y - 30))
        screen.blit(font.render("Confirm :", True, (255,255,255)), (confirm_box.rect.x, confirm_box.rect.y - 30))
        
        username_box.draw(screen)
        password_box.draw(screen)
        confirm_box.draw(screen)
        
        create_btn = draw_button("Create", x/2 - 150, y/2 + 80, 120, 50)
        back_btn = draw_button("Back", x/2 + 30, y/2 + 80, 120, 50)
        
        if message:
            screen.blit(font.render(message, True, (255,100,100)), (x/2 - 100, y/2 + 150))
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
            username_box.handle_event(event)
            password_box.handle_event(event)
            confirm_box.handle_event(event)
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if create_btn.collidepoint(event.pos):
                    if password_box.text != confirm_box.text:
                        message = "Les mots de passe ne correspondent pas"
                    else:
                        try:
                            r = requests.post(BASE_URL + "/register", params={
                                "pseudo": username_box.text,
                                "password": password_box.text
                            }, timeout=5)
                            if r.status_code == 201:
                                message = "Compte créé"
                                pygame.time.wait(500)
                                login()
                                return
                            elif r.status_code == 409:
                                message = "Pseudo déjà utilisé"
                            else:
                                message = "Erreur inscription"
                        except:
                            message = "Erreur serveur"
                if back_btn.collidepoint(event.pos):
                    login()
                    return
        flip()

# BY HUMAIN
def cree_button(posX, posY, longueur, hauteur):
    return pygame.Rect(posX, posY, longueur, hauteur)

def dessiner(button, couleur):
    return pygame.draw.rect(screen,couleur,button)

def cree_button_random():
    largeur = randint(5, 100)
    hauteur = randint(5, 100)

    posX = randint(0, x - largeur)
    posY = randint(0, y - hauteur)

    return pygame.Rect(posX, posY, largeur, hauteur)

def texte(text, button): 
    txt = font.render(text, True, (255,255,255)) 
    txt_rect = txt.get_rect(center=button.center) 
    return screen.blit(txt, txt_rect)

def menus_principale():
    exit = False
    menu = True
    while menu:
        background()
        texte(f"Score : {score}",cree_button(100,50,0,0))
        play = cree_button(x/5, y/2, 135, 100)
        shop = cree_button((x/5)*2, y/2, 135, 100)
        instruction = cree_button((x/5)*3, y/2, 135, 100)
        leave = cree_button((x/5)*4, y/2, 135, 100)
        leaderboard = cree_button((x/2), y/1.5, 135, 100)
        dessiner(play,(0,250,0))
        dessiner(shop,(0,250,0))
        dessiner(instruction,(0,250,0))
        dessiner(leave,(0,250,0))
        dessiner(leaderboard,(0,250,0))
        texte("Play", play)
        texte("Shop", shop)
        texte("Instruction", instruction)
        texte("Leave", leave)
        texte("leaderboard", leaderboard)
        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN:
                if play.collidepoint(event.pos):
                    afficher_difficult()
                if shop.collidepoint(event.pos):
                    afficher_shop()
                if instruction.collidepoint(event.pos):
                    afficher_instruction()
                if leaderboard.collidepoint(event.pos):
                    afficher_leaderboard()
                if leave.collidepoint(event.pos):
                    exit = True
                    menu = False
        flip()
    if exit:
        pygame.quit()

def afficher_difficult():
    global delai
    lvl = True
    while lvl:
        background()
        easy = cree_button(x/4, y/2.5, 125, 100)
        medium = cree_button((x/4) * 2, y/2.5, 125, 100)
        hard = cree_button((x/4) * 3, y/2.5, 125, 100)
        impossible = cree_button((x/3), y/1.5, 125, 100)
        demonic = cree_button((x/3) * 2, y/1.5, 125, 100)
        dessiner(easy,(0,250,0))
        dessiner(medium,(0,250,0))
        dessiner(hard,(0,250,0))
        dessiner(impossible,(0,250,0))
        dessiner(demonic,(0,250,0))
        texte("Easy", easy)
        texte("Medium", medium)
        texte("Hard", hard)
        texte("Impossible", impossible)
        texte("Demonic", demonic)
        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN:
                if easy.collidepoint(event.pos):
                    delai = 1000
                    if 1 in ralentisseur:
                        delai = 1050
                    elif 2 in ralentisseur:
                        delai = 1150
                    elif 3 in ralentisseur:
                        delai = 1250
                    lvl = False
                    start("easy")
                if medium.collidepoint(event.pos):
                    delai = 550
                    if 1 in ralentisseur:
                        delai = 600
                    elif 2 in ralentisseur:
                        delai = 700
                    elif 3 in ralentisseur:
                        delai = 800
                    lvl = False
                    start("medium")
                if hard.collidepoint(event.pos):
                    if 1 in ralentisseur:
                        delai = 400
                    elif 2 in ralentisseur:
                        delai = 500
                    elif 3 in ralentisseur:
                        delai = 600
                    lvl = False
                    start("hard")
                if impossible.collidepoint(event.pos):
                    delai = 0
                    if 1 in ralentisseur:
                        delai = 50
                    elif 2 in ralentisseur:
                        delai = 150
                    elif 3 in ralentisseur:
                        delai = 250
                    lvl = False
                    start("impossible")
                if demonic.collidepoint(event.pos):
                    delai = 999999
                    lvl = False
                    start("demonic")
        flip()

def afficher_shop():
    global score, CouleurSkin, skinAcheter, but_bonus, ralentisseur, multiplicateur, pseudo

    achat = True
    message = ""

    while achat:
        background()
        texte(f"Score : {score}", cree_button(100, 50, 0, 0))

        # Bouton retour
        back = cree_button((x / 8), y / 8, 70, 50)
        dessiner(back, (0, 200, 0))
        texte("Back", back)

        # Définition complète des items avec condition d’apparition
        shop_items = [
            # Ralentisseurs
            {"name": "Slow lvl.1", "btn": cree_button(x / 4, y / 5, 135, 100), "price": 10, "type": "ralentisseur", "level": 1, "pre_req": 0},
            {"name": "Slow lvl.2", "btn": cree_button((x / 4)*2, y / 5, 135, 100), "price": 150, "type": "ralentisseur", "level": 2, "pre_req": 1},
            {"name": "Slow lvl.3", "btn": cree_button((x / 4)*3, y / 5, 135, 100), "price": 500, "type": "ralentisseur", "level": 3, "pre_req": 2},
            # Boutons bonus
            {"name": "Aide lvl.1", "btn": cree_button(x / 4, (y / 5)*2, 135, 100), "price": 50, "type": "but_bonus", "level": 1, "pre_req": 0},
            {"name": "Aide lvl.2", "btn": cree_button((x / 4)*2, (y / 5)*2, 135, 100), "price": 200, "type": "but_bonus", "level": 2, "pre_req": 1},
            {"name": "Aide lvl.3", "btn": cree_button((x / 4)*3, (y / 5)*2, 135, 100), "price": 500, "type": "but_bonus", "level": 3, "pre_req": 2},
            # Multiplicateurs
            {"name": "Score lvl.1", "btn": cree_button(x / 4, (y / 5)*3, 135, 100), "price": 100, "type": "multiplicateur", "level": 1, "pre_req": 0},
            {"name": "Score lvl.2", "btn": cree_button((x / 4)*2, (y / 5)*3, 135, 100), "price": 400, "type": "multiplicateur", "level": 2, "pre_req": 1},
            {"name": "Score lvl.3", "btn": cree_button((x / 4)*3, (y / 5)*3, 135, 100), "price": 900, "type": "multiplicateur", "level": 3, "pre_req": 2},
            # Skins
            {"name": "Skin Green", "btn": cree_button(x / 4, (y / 5)*4, 135, 100), "price": 0, "type": "skin", "level": 1, "pre_req": 0},
            {"name": "Skin Red", "btn": cree_button((x / 4)*2, (y / 5)*4, 135, 100), "price": 150, "type": "skin", "level": 2, "pre_req": 1},
            {"name": "Skin Blue", "btn": cree_button((x / 4)*3, (y / 5)*4, 135, 100), "price": 150, "type": "skin", "level": 3, "pre_req": 2},
        ]

        # Dessiner uniquement les items dont le pré-requis est rempli
        for item in shop_items:
            collection = {
                "ralentisseur": ralentisseur,
                "but_bonus": but_bonus,
                "multiplicateur": multiplicateur,
                "skin": skinAcheter
            }[item["type"]]

            if item["pre_req"] == 0 or item["pre_req"] in collection:
                dessiner(item["btn"], (0, 200, 0))
                texte(f"{item['name']} - {item['price']} pts", item["btn"])

        # Gestion des clics
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if back.collidepoint(event.pos):
                    achat = False
                    return

                for item in shop_items:
                    collection = {
                        "ralentisseur": ralentisseur,
                        "but_bonus": but_bonus,
                        "multiplicateur": multiplicateur,
                        "skin": skinAcheter
                    }[item["type"]]

                    if item["pre_req"] != 0 and item["pre_req"] not in collection:
                        continue  # Pré-requis non rempli

                    if item["btn"].collidepoint(event.pos):
                        if item["level"] in collection:
                            message = f"Vous possédez déjà {item['name']}"
                        elif score >= item["price"]:
                            score -= item["price"]
                            collection.append(item["level"])
                            if item["type"] == "skin":
                                CouleurSkin = item["name"].split()[1]
                            message = f"Acheté {item['name']} !"

                            # 🔵 Mise à jour BDD
                            try:
                                requests.post(BASE_URL + "/update_shop", params={
                                    "pseudo": pseudo,
                                    "score": score,
                                    "ralentisseur": ",".join(map(str, ralentisseur)),
                                    "but_bonus": ",".join(map(str, but_bonus)),
                                    "multiplicateur": ",".join(map(str, multiplicateur)),
                                    "skinAcheter": ",".join(map(str, skinAcheter)),
                                    "CouleurSkin": CouleurSkin
                                }, timeout=5)
                            except:
                                message = "Erreur serveur, achat non sauvegardé"
                        else:
                            message = "Score insuffisant"

        if message:
            screen.blit(font.render(message, True, (255, 100, 100)), (x/2 - 150, y - 50))

        flip()

def afficher_instruction():
    instruction_open = True
    while instruction_open:
        background()
        
        # Title
        title_text = font.render("How to Play", True, (255,255,255))
        screen.blit(title_text, (x/2 - title_text.get_width()/2, 100))
        
        # Instructions lines
        lines = [
            "Objective: Click moving buttons to earn points.",
            "Controls: Use the MOUSE to click buttons as fast as possible.",
            "",
            "Difficulty Levels:",
            " - Easy: Buttons move slowly, 1 point per click.",
            " - Medium: Buttons move faster, 2 points per click.",
            " - Hard: Buttons move quickly, 5 points per click.",
            " - Impossible: Buttons move very fast, 15 points per click.",
            " - Demonic: Buttons move erratically, special button gives 50 points.",
            "",
            "Bonuses (buy in Shop using points):",
            " - Slow (reduces button speed): Level 1 = 10 pts (25% slower)",
            "   Level 2 = 150 pts (50% slower), Level 3 = 500 pts (75% slower)",
            " - Extra Buttons (more clickable buttons appear): Level 1 = 50 pts,",
            "   Level 2 = 200 pts, Level 3 = 500 pts",
            " - Score Multiplier (increases points per click): Level 1 = x1.5,",
            "   Level 2 = x2, Level 3 = x3",
            " - Skins: Change button colors (cosmetic only).",
            "",
            "Game Tips:",
            " - Use Slow + Extra Buttons together for easier clicks.",
            " - Multipliers stack with points from all buttons.",
            " - Press ESC to pause or abandon the game.",
            " - Try to maximize points before buying upgrades!"
        ]
        
        for i, line in enumerate(lines):
            txt = font.render(line, True, (255,255,255))
            screen.blit(txt, (x/4, 200 + i * 30))
        
        # Back button
        back = cree_button(x / 8 , y / 8, 70, 50)
        dessiner(back,(0,200,0))
        texte("Back", back)
        
        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN:
                if back.collidepoint(event.pos):
                    instruction_open = False
        flip()

def afficher_leaderboard():
    running = True
    while running:
        background()
        titre = font.render("Leaderboard Mondial", True, (255,255,255))
        screen.blit(titre,(x/2 - 150,100))

        try:
            r = requests.get(BASE_URL + "/leaderboard")
            data = r.json()
        except:
            data = []

        for i, joueur in enumerate(data):
            txt = font.render(f"{i+1}. {joueur['pseudo']} : {joueur['score']}", True,(255,255,255))
            screen.blit(txt,(x/3,200 + i*40))

        back = cree_button(x/8,y/8,70,50)
        dessiner(back,(0,200,0))
        texte("Back",back)

        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN:
                if back.collidepoint(event.pos):
                    running = False
        flip()

def start(mode):
    global score
    global skinAcheter
    global CouleurSkin
    global but_bonus
    global ralentisseur
    global multiplicateur
    global dernier_mouvement
    if mode == "easy":
        game = True
        while game:
            background()
            temps = pygame.time.get_ticks()
            if temps - dernier_mouvement >= delai:
                but = cree_button_random()
                i = cree_button_random()
                k = cree_button_random()
                j = cree_button_random()
                inv = cree_button_random()
                dernier_mouvement = temps

            apparition_button(but,i,j,k,inv,mode)
            
            texte("Catch-Me",cree_button(x/2, y/2, 0, 0))
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    game = gagner(mode,but,i,j,k,inv,pygame.mouse.get_pos())

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        Abondon = True
                        while Abondon:
                            background()
                            sortir = cree_button(x/2,y/2,135,100)
                            dessiner(sortir, (0,255,0))
                            texte("Abondonner",sortir)
                            for click in pygame.event.get():
                                if click.type == pygame.MOUSEBUTTONDOWN:
                                    if sortir.collidepoint(click.pos):
                                        game = False
                                        Abondon = False
                                if click.type == pygame.KEYDOWN:
                                    if click.key == pygame.K_ESCAPE:
                                        Abondon = False
                            flip()
            flip()
        replay(mode)
    if mode == "medium":
        game = True
        while game:
            background()
            temps = pygame.time.get_ticks()
            if temps - dernier_mouvement >= delai:
                but = cree_button_random()
                i = cree_button_random()
                k = cree_button_random()
                j = cree_button_random()
                inv = cree_button_random()
                dernier_mouvement = temps

            apparition_button(but,i,j,k,inv,mode)
            
            texte("Catch-Me",cree_button(x/2, y/2, 0, 0))
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    game = gagner(mode,but,i,j,k,inv,pygame.mouse.get_pos())

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        Abondon = True
                        while Abondon:
                            background()
                            sortir = cree_button(x/2,y/2,135,100)
                            dessiner(sortir, (0,255,0))
                            texte("Abondonner",sortir)
                            for click in pygame.event.get():
                                if click.type == pygame.MOUSEBUTTONDOWN:
                                    if sortir.collidepoint(click.pos):
                                        game = False
                                        Abondon = False
                                if click.type == pygame.KEYDOWN:
                                    if click.key == pygame.K_ESCAPE:
                                        Abondon = False
                            flip()
            flip()
        replay(mode)    
    if mode == "hard":
        game = True
        while game:
            background()
            temps = pygame.time.get_ticks()
            if temps - dernier_mouvement >= delai:
                but = cree_button_random()
                i = cree_button_random()
                k = cree_button_random()
                j = cree_button_random()
                inv = cree_button_random()
                dernier_mouvement = temps

            apparition_button(but,i,j,k,inv,mode)
            
            texte("Catch-Me",cree_button(x/2, y/2, 0, 0))
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    game = gagner(mode,but,i,j,k,inv,pygame.mouse.get_pos())

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        Abondon = True
                        while Abondon:
                            background()
                            sortir = cree_button(x/2,y/2,135,100)
                            dessiner(sortir, (0,255,0))
                            texte("Abondonner",sortir)
                            for click in pygame.event.get():
                                if click.type == pygame.MOUSEBUTTONDOWN:
                                    if sortir.collidepoint(click.pos):
                                        game = False
                                        Abondon = False
                                if click.type == pygame.KEYDOWN:
                                    if click.key == pygame.K_ESCAPE:
                                        Abondon = False
                            flip()
            flip()
        replay(mode)
    if mode == "impossible":
        game = True
        while game:
            background()
            temps = pygame.time.get_ticks()
            if temps - dernier_mouvement >= delai:
                but = cree_button_random()
                i = cree_button_random()
                k = cree_button_random()
                j = cree_button_random()
                inv = cree_button_random()
                dernier_mouvement = temps

            apparition_button(but,i,j,k,inv,mode)
            
            texte("Catch-Me",cree_button(x/2, y/2, 0, 0))
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    game = gagner(mode,but,i,j,k,inv,pygame.mouse.get_pos())

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        Abondon = True
                        while Abondon:
                            background()
                            sortir = cree_button(x/2,y/2,135,100)
                            dessiner(sortir, (0,255,0))
                            texte("Abondonner",sortir)
                            for click in pygame.event.get():
                                if click.type == pygame.MOUSEBUTTONDOWN:
                                    if sortir.collidepoint(click.pos):
                                        game = False
                                        Abondon = False
                                if click.type == pygame.KEYDOWN:
                                    if click.key == pygame.K_ESCAPE:
                                        Abondon = False
                            flip()
            flip()
        replay(mode)
    if mode == "demonic":
        game = True
        but = cree_button_random()
        i = cree_button_random()
        k = cree_button_random()
        j = cree_button_random()
        inv = cree_button_random()
        while game:
            background()
            apparition_button(but,i,j,k,inv,mode)

            temps = pygame.time.get_ticks()
            if temps - dernier_mouvement >= delai:
                inv = cree_button_random()
                dernier_mouvement = temps

            texte("Catch-Me",cree_button(x/2, y/2, 0, 0))
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    resultat = gagner(mode,but,i,j,k,inv,pygame.mouse.get_pos())

                    if resultat == "move":
                        but = cree_button_random()
                        i = cree_button_random()
                        k = cree_button_random()
                        j = cree_button_random()
                        inv = cree_button_random()

                    elif resultat == "win":
                        game = False

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        Abondon = True
                        while Abondon:
                            background()
                            sortir = cree_button(x/2,y/2,135,100)
                            dessiner(sortir, (0,255,0))
                            texte("Abondonner",sortir)
                            for click in pygame.event.get():
                                if click.type == pygame.MOUSEBUTTONDOWN:
                                    if sortir.collidepoint(click.pos):
                                        game = False
                                        Abondon = False
                                if click.type == pygame.KEYDOWN:
                                    if click.key == pygame.K_ESCAPE:
                                        Abondon = False
                            flip()
            flip()
        replay(mode)

def apparition_button(but,i,j,k,inv,mode): # Crée les boutons du jeux 
    global skinAcheter
    global CouleurSkin
    global but_bonus
    global ralentisseur
    global multiplicateur
    global dernier_mouvement
    if CouleurSkin == "Green":
        dessiner(but,(0,200,0))
        if (1 in but_bonus)and (2 not in but_bonus):
            dessiner(i,(0,200,0))
        if (2 in but_bonus)and (3 not in but_bonus):
            dessiner(i,(0,200,0))
            dessiner(k,(0,200,0))
        if (3 in but_bonus):
            dessiner(i,(0,200,0))
            dessiner(k,(0,200,0))
            dessiner(j,(0,200,0))
                    
    if CouleurSkin == "Red":
        dessiner(but,(200,0,0))
        if (1 in but_bonus)and (2 not in but_bonus):
            dessiner(i,(200,0,0))
        if (2 in but_bonus)and (3 not in but_bonus):
            dessiner(i,(200,0,0))
            dessiner(k,(200,0,0))
        if (3 in but_bonus):
            dessiner(i,(200,0,0))
            dessiner(k,(200,0,0))
            dessiner(j,(200,0,0))

    if CouleurSkin == "Blue":
        dessiner(but,(0,0,200))
        if (1 in but_bonus)and (2 not in but_bonus):
            dessiner(i,(0,0,200))
        if (2 in but_bonus)and (3 not in but_bonus):
            dessiner(i,(0,0,200))
            dessiner(k,(0,0,200))
        if (3 in but_bonus):
            dessiner(i,(0,0,200))
            dessiner(k,(0,0,200))
            dessiner(j,(0,0,200))
    
    if mode == "demonic":
        if (3 in but_bonus) and (3 in ralentisseur):
            dessiner(inv,(60,61,60))
        else:
            dessiner(inv,(60,60,60))

def gagner(mode,but,i,j,k,inv,position):
    global score
    if mode == "easy":
        if but.collidepoint(position) or i.collidepoint(position) or k.collidepoint(position) or j.collidepoint(position):
                        if (1 in multiplicateur) and (2 not in multiplicateur):
                            score += 1 * 2
                            requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 1 * 1.5})
                        elif (1 in multiplicateur) and (3 not in multiplicateur):
                            score += 1 * 2.5
                            requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 1 * 2})
                        elif (3 in multiplicateur):
                            score += 1 * 3
                            requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 1 * 3})
                        else:
                            score += 1
                            requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 1})
                        print(f"Bouton clicker, Vous avez gagner !\n Votre score et maintenant à {score} point")
                        return False
        return True
    if mode == "medium":
        if but.collidepoint(position) or i.collidepoint(position) or k.collidepoint(position) or j.collidepoint(position):
                        if (1 in multiplicateur) and (2 not in multiplicateur):
                            score += 2 * 1.5
                            requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 2 * 1.5})
                        elif (1 in multiplicateur) and (3 not in multiplicateur):
                            score += 2 * 2
                            requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 2 * 2})
                        elif (3 in multiplicateur):
                            score += 2 * 3
                            requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 2 * 3})
                        else:
                            score += 2
                            requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 2})
                        print(f"Bouton clicker, Vous avez gagner !\n Votre score et maintenant à {score} point")
                        return False
        return True
    if mode == "hard":
        if but.collidepoint(position) or i.collidepoint(position) or k.collidepoint(position) or j.collidepoint(position):
                        if (1 in multiplicateur) and (2 not in multiplicateur):
                            score += 5 * 1.5
                            requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 5 * 1.5})
                        elif (1 in multiplicateur) and (3 not in multiplicateur):
                            score += 5 * 2
                            requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 5 * 2})
                        elif (3 in multiplicateur):
                            score += 5 * 3
                            requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 5 * 3})
                        else:
                            score += 5
                            requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 5})
                        print(f"Bouton clicker, Vous avez gagner !\n Votre score et maintenant à {score} point")
                        return False
        return True
    if mode == "impossible":
        if but.collidepoint(position) or i.collidepoint(position) or k.collidepoint(position) or j.collidepoint(position):
                        if (1 in multiplicateur) and (2 not in multiplicateur):
                            score += 15 * 1.5
                            requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 15 * 1.5})
                        elif (1 in multiplicateur) and (3 not in multiplicateur):
                            score += 15 * 2
                            requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 15 * 2})
                        elif (3 in multiplicateur):
                            score += 15 * 3
                            requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 15 * 3})
                        else:
                            score += 15
                            requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 15})
                        print(f"Bouton clicker, Vous avez gagner !\n Votre score et maintenant à {score} point")
                        return False
        return True
    if mode == "demonic":
        tout = [but, i, j, k]
        for elt in tout:
            if (elt.left - 10 <= position[0] <= elt.right + 10) and (elt.top - 10 <= position[1] <= elt.bottom + 10):
                return "move"
            
        if inv.collidepoint(position):
            if (1 in multiplicateur) and (2 not in multiplicateur):
                score += 50 * 1.5
                requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 50 * 1.5})
            elif (1 in multiplicateur) and (3 not in multiplicateur):
                score += 50 * 2
                requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 50 * 2})
            elif (3 in multiplicateur):
                score += 50 * 3
                requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 50 * 3})
            else:
                score += 50
                requests.post(BASE_URL + "/add_score", params={"pseudo": pseudo_joueur, "points": 50})
            print(f"Bouton clicker, Vous avez gagner !\n Votre score et maintenant à {score} point")
            return "win"
    
def replay(mode):
    global score
    rejouer =  cree_button(x / 3 , y / 2, 135, 100)
    menu_principale = cree_button((x / 3) * 2, y / 2, 135, 100)
    quitter = cree_button((x / 2), y / 1.2, 135, 100)
    choix = True
    exit = False
    while choix:
        background()
        texte(f"Score : {score}",cree_button(100,50,0,0))
        dessiner(rejouer,(0,200,0))
        dessiner(menu_principale,(0,200,0))
        dessiner(quitter,(0,200,0))
        texte("Replay", rejouer)
        texte("Menus", menu_principale)
        texte("Leave", quitter)
        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN:
                if rejouer.collidepoint(event.pos):
                    choix = False
                    start(mode)
                if menu_principale.collidepoint(event.pos):
                    choix = False
                if quitter.collidepoint(event.pos):
                    choix = False
                    exit = True
        flip()
    if exit:
        pygame.quit()

dernier_mouvement = pygame.time.get_ticks()
delai = 1000  # valeur par défaut
pygame.init()
screen = pygame.display.set_mode((x, y))
# Définition des racourcies
def background():
    return screen.fill((60,60,60))
def flip():
    return pygame.display.flip()
font = pygame.font.Font(None, 36) # Config de la police de l'écriture
# --------------------------------------- #
score = 0
#Definition des buffs:
ralentisseur = [] # Ralentisseur obtenue par le joueur (0 par défauts)
but_bonus = [] # Boutton bonus obtenue par le joueur
multiplicateur = [] # Les duplicateurs debloquer par le joueur
skinAcheter = ["Green"] # les skins obtenue par le joueur (skin classic par défaut)
CouleurSkin = "Green"

login()
# menus_principale()
