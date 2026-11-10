import pygame
from random import randint
import tkinter as TK

root = TK.Tk()
root.withdraw()
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

pygame.init()
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Mon jeu")
def button():
    return pygame.Rect(randint(5,800),randint(randint(10,400),randint(401,800)),randint(5,randint(6,100)),randint(5,randint(6, 100)))

score = 600
#Definition des buffs:
ralentisseur = [0] # Ralentisseur obtenue par le joueur (0 par défauts)
but_bonus = [0] # Boutton bonus obtenue par le joueur
multiplicateur = [0] # Les duplicateurs debloquer par le joueur
skinAcheter = [1] # les skins obtenue par le joueur (skin classic par défaut)
CouleurSkin = "Green"

font = pygame.font.Font(None, 36) # Config de la police de l'écriture

menus = True
running = True
enter = True

ez = False
med = True
h = False
imp = False

dernier_mouvement = pygame.time.get_ticks()
delai = 1000  # valeur par défaut

but = button() # test
while running:
    x = screen.get_width()
    y = screen.get_height()
    while menus:
        screen.fill((60,60,60))
        play = pygame.Rect(screen.get_width() / 4,screen.get_height() / 2,100,100 )
        shop = pygame.Rect((screen.get_width() / 4) * 2,screen.get_height() / 2,100,100)
        leave = pygame.Rect((screen.get_width() / 4) * 3,screen.get_height() / 2,100,100)
        pygame.draw.rect(screen,(0,200,0),play)
        pygame.draw.rect(screen,(0,200,0),shop)
        pygame.draw.rect(screen,(0,200,0),leave)
        screen.blit(font.render("Jouer",True,(255,255,255)),(play.left  , (y / 2) + (play.height / 2.5)))
        screen.blit(font.render("Boutique",True,(255,255,255)),(shop.left  , (y / 2) + (shop.height / 2.5)))
        screen.blit(font.render("Quitter",True,(255,255,255)),(leave.left  , (y / 2) + (leave.height / 2.5)))
        screen.blit(font.render(f"Score : {score}",True,(255,255,255)),(25 , 25))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                menus = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if play.collidepoint(event.pos):
                    choix_dif = True
                    # Création des choix pour la difficulte
                    while choix_dif:
                        screen.fill((0,200,0))
                        screen.blit(font.render(f"Score : {score}",True,(255,255,255)),(25 , 25))
                        easy = pygame.Rect(x / 5, y / 2, 100, 50)
                        pygame.draw.rect(screen,(0,255,0),easy)
                        screen.blit(font.render("Easy",True,(255,255,255)),(easy.left  , (y / 2) + (easy.height / 2.5)))
                        medium = pygame.Rect((x / 5) * 2 , y / 2, 100, 50)
                        pygame.draw.rect(screen,(0,255,0),medium)
                        screen.blit(font.render("Medium",True,(255,255,255)),(medium.left  , (y / 2) + (medium.height / 2.5)))
                        hard = pygame.Rect((x / 5) * 3 , y / 2, 100, 50)
                        pygame.draw.rect(screen,(0,255,0),hard)
                        screen.blit(font.render("Hard",True,(255,255,255)),(hard.left  , (y / 2) + (hard.height / 2.5)))
                        impossible = pygame.Rect((x / 5) * 4 , y / 2, 100, 50)
                        pygame.draw.rect(screen,(0,255,0),impossible)
                        screen.blit(font.render("Impossible",True,(255,255,255)),(impossible.left  , (y / 2) + (impossible.height / 2.5)))
                        # go = pygame.Rect((x / 2) , y / 1.5, 100, 50) Bouton continer apres le choix de la difficulter
                        # pygame.draw.rect(screen,(0,255,0),go)
                        # screen.blit(font.render("Continue",True,(255,255,255)),(go.left  , (y / 1.5) + (go.height / 2.5))) (BOUTON CONTINUE POUR LE CHOIX DE LA DIFFICULTER)
                        for event in pygame.event.get():
                            if event.type == pygame.MOUSEBUTTONDOWN:
                                if easy.collidepoint(event.pos):
                                    ez = True
                                    med = False
                                    h = False
                                    imp = False
                                    delai = 1000
                                    if 1 in ralentisseur:
                                        delai = 1050
                                    elif 2 in ralentisseur:
                                        delai = 1150
                                    elif 3 in ralentisseur:
                                        delai = 1250
                                    choix_dif = False
                                if medium.collidepoint(event.pos):
                                    ez = False
                                    med = True
                                    h = False
                                    imp = False
                                    delai = 550
                                    if 1 in ralentisseur:
                                        delai = 600
                                    elif 2 in ralentisseur:
                                        delai = 700
                                    elif 3 in ralentisseur:
                                        delai = 800
                                    choix_dif = False
                                if hard.collidepoint(event.pos):
                                    ez = False
                                    med = False
                                    h = True
                                    imp = False
                                    delai = 350
                                    if 1 in ralentisseur:
                                        delai = 400
                                    elif 2 in ralentisseur:
                                        delai = 500
                                    elif 3 in ralentisseur:
                                        delai = 600
                                    choix_dif = False
                                if impossible.collidepoint(event.pos):
                                    ez = False
                                    med = False
                                    h = False
                                    imp = True
                                    delai = 0
                                    if 1 in ralentisseur:
                                        delai = 50
                                    elif 2 in ralentisseur:
                                        delai = 150
                                    elif 3 in ralentisseur:
                                        delai = 250
                                    choix_dif = False
                                # if go.collidepoint(event.pos): (bouton 'continuer' apres le choix de la difficulter)
                                #     choix_dif = False 
                        pygame.display.flip()
                    menus = False
                if shop.collidepoint(event.pos):
                    achat = True
                    while achat:
                        screen.fill((80,80,80))
                        screen.blit(font.render(f"Score : {score}",True,(255,255,255)),(25 , 25))
                        retour = pygame.Rect((x / 8) , y / 8, 70, 50)
                        up1 = pygame.Rect((x / 4) , y / 5, 110, 100)
                        up2 = pygame.Rect((x / 4) * 2, y / 5, 110, 100)
                        up3 = pygame.Rect((x / 4) * 3, y / 5, 110, 100)
                        aide1 = pygame.Rect((x / 4),(y / 5) * 2, 110, 100)
                        aide2 = pygame.Rect((x / 4) * 2 ,(y / 5) * 2, 110, 100)
                        aide3 = pygame.Rect((x / 4) * 3 ,(y / 5) * 2, 110, 100)
                        dupli1 = pygame.Rect((x / 4),(y / 5) *3, 110, 100)
                        dupli2 = pygame.Rect((x / 4) * 2,(y / 5) *3, 110, 100)
                        dupli3 = pygame.Rect((x / 4) * 3,(y / 5) *3, 110, 100)
                        skin1 = pygame.Rect((x / 4) ,(y / 5) * 4, 110, 100)
                        skin2 = pygame.Rect((x / 4) * 2,(y / 5) * 4, 110, 100)
                        skin3 = pygame.Rect((x / 4) * 3,(y / 5) * 4, 110, 100)

                        pygame.draw.rect(screen,(0,200,0),retour)
                        screen.blit(font.render("Back",True,(255,255,255)),(retour.left  , (y / 8) + (retour.height / 2.5)))

                        # Ralentisseur
                        pygame.draw.rect(screen,(0,200,0),up1)
                        screen.blit(font.render("Slow lvl.1",True,(255,255,255)),(up1.left  , (y / 5) + (up1.height / 2.5)))
                        if 1 in ralentisseur:
                            pygame.draw.rect(screen,(0,200,0),up2)
                            screen.blit(font.render("Slow lvl.2",True,(255,255,255)),(up2.left  , (y / 5) + (up2.height / 2.5)))
                        if 2 in ralentisseur:
                            pygame.draw.rect(screen,(0,200,0),up3)
                            screen.blit(font.render("Slow lvl.3",True,(255,255,255)),(up3.left  , (y / 5) + (up3.height / 2.5)))

                        # plus de boutton
                        pygame.draw.rect(screen,(0,200,0),aide1)
                        screen.blit(font.render("Aide lvl.1",True,(255,255,255)),(aide1.left  , ((y / 5) *2) + (aide1.height / 2.5)))
                        if 1 in but_bonus:
                            pygame.draw.rect(screen,(0,200,0),aide2)
                            screen.blit(font.render("Aide lvl.2",True,(255,255,255)),(aide2.left  , ((y / 5) *2) + (aide2.height / 2.5)))
                        if 2 in but_bonus:
                            pygame.draw.rect(screen,(0,200,0),aide3)
                            screen.blit(font.render("Aide lvl.3",True,(255,255,255)),(aide3.left  , ((y / 5) *2) + (aide3.height / 2.5)))
                        
                        # Duplicateur de score
                        pygame.draw.rect(screen,(0,200,0),dupli1)
                        screen.blit(font.render("Score lvl.1",True,(255,255,255)),(dupli1.left  , (y / 5) * 3 + (dupli1.height / 2.5)))
                        if 1 in multiplicateur:
                            pygame.draw.rect(screen,(0,200,0),dupli2)
                            screen.blit(font.render("Score lvl.2",True,(255,255,255)),(dupli2.left  , (y / 5) * 3 + (dupli2.height / 2.5)))
                        if 2 in multiplicateur:
                            pygame.draw.rect(screen,(0,200,0),dupli3)
                            screen.blit(font.render("Score lvl.3",True,(255,255,255)),(dupli3.left  , (y / 5) * 3 + (dupli3.height / 2.5)))

                        # Skin des bouttons
                        pygame.draw.rect(screen,(0,200,0),skin1)
                        screen.blit(font.render("Skin Green",True,(255,255,255)),(skin1.left  , (y / 5) * 4 + (skin1.height / 2.5)))
                        pygame.draw.rect(screen,(0,200,0),skin2)
                        screen.blit(font.render("Skin Red",True,(255,255,255)),(skin2.left  , (y / 5) * 4 + (skin2.height / 2.5)))
                        pygame.draw.rect(screen,(0,200,0),skin3)
                        screen.blit(font.render("Skin Blue",True,(255,255,255)),(skin3.left  , (y / 5) * 4 + (skin3.height / 2.5)))

                        for event in pygame.event.get():
                            if event.type == pygame.MOUSEBUTTONDOWN:
                                # Les boutons des ralentisseurs
                                if up1.collidepoint(event.pos):
                                    if 1 in ralentisseur:
                                        print("Vous posseder deja ce buff")
                                    elif (score >= 20) and (1 not in ralentisseur):
                                        ralentisseur.append(1)
                                        score -= 10
                                        print(f"Bien jouer, vous venez d'obtenir le 1er buff ! (Votre score apres l'achat : {score})")
                                    else:
                                        print(f"Vous n'avez pas asser de score ({score} < 20)")
                                if (1 in ralentisseur) and (up2.collidepoint(event.pos)):
                                    if 2 in ralentisseur:
                                        print("Vous posseder deja ce buff")
                                    elif (score >= 150) and (2 not in ralentisseur):
                                        ralentisseur.append(2)
                                        score -= 150
                                        print(f"Bien jouer, vous venez d'obtenir le 2eme buff ! (Votre score apres l'achat : {score})")
                                    else:
                                        print(f"Vous n'avez pas asser de score ({score} < 150)")
                                if (2 in ralentisseur) and (up3.collidepoint(event.pos)):
                                    if 3 in ralentisseur:
                                        print("Vous posseder deja ce buff")
                                    elif (score >= 500) and (up3.collidepoint(event.pos)):
                                        ralentisseur.append(3)
                                        score -= 500
                                        print(f"Bien jouer, vous venez d'obtenir le 3eme et dernier buff ! (Votre score apres l'achat : {score})")
                                    else:
                                        print(f"Vous n'avez pas asser de score ({score} < 500)")
                                # Les boutons des boutons bonus (Aide et crée + de bouton sur la map)
                                if aide1.collidepoint(event.pos):
                                    if 1 in but_bonus:
                                        print("Vous posseder deja cette aide")
                                    elif (score >= 50) and (1 not in but_bonus):
                                        but_bonus.append(1)
                                        score -= 50
                                        print(f"Bien jouer, vous venez d'obtenir la 1ere aide ! (Votre score apres l'achat : {score})")
                                    else:
                                        print(f"Vous n'avez pas asser de score ({score} < 50)")
                                if (1 in but_bonus) and aide2.collidepoint(event.pos):
                                    if 2 in but_bonus:
                                        print("Vous posseder deja cette aide")
                                    elif (score >= 200) and (2 not in but_bonus):
                                        but_bonus.append(2)
                                        score -= 200
                                        print(f"Bien jouer, vous venez d'obtenir la 2eme aide ! (Votre score apres l'achat : {score})")
                                    else:
                                        print(f"Vous n'avez pas asser de score ({score} < 200)")
                                if (2 in but_bonus) and (aide3.collidepoint(event.pos)):
                                    if 3 in but_bonus:
                                        print("Vous posseder deja cette aide")
                                    elif (score >= 500) and (3 not in but_bonus):
                                        but_bonus.append(3)
                                        score -= 500
                                        print(f"Bien jouer, vous venez d'obtenir la 3eme et dernière aide ! (Votre score apres l'achat : {score})")
                                    else:
                                        print(f"Vous n'avez pas asser de score ({score} < 500)")
                                if dupli1.collidepoint(event.pos):
                                    if 1 in multiplicateur:
                                        print("Vous posseder deja ce duplicateur")
                                    elif (score >= 50) and (1 not in multiplicateur):
                                        multiplicateur.append(1)
                                        score -= 100
                                        print(f"Bien jouer, vous venez d'obtenir le 1er multiplicateur ! (Votre score apres l'achat : {score})")
                                    else:
                                        print(f"Vous n'avez pas asser de score ({score} < 50)")
                                if dupli2.collidepoint(event.pos):
                                    if 2 in multiplicateur:
                                        print("Vous posseder deja ce duplicateur")
                                    elif (score >= 400) and (2 not in multiplicateur):
                                        multiplicateur.append(2)
                                        score -= 400
                                        print(f"Bien jouer, vous venez d'obtenir le 2eme multiplicateur ! (Votre score apres l'achat : {score})")
                                    else:
                                        print(f"Vous n'avez pas asser de score ({score} < 400)")
                                if dupli3.collidepoint(event.pos):
                                    if 3 in multiplicateur:
                                        print("Vous posseder deja ce duplicateur")
                                    elif (score >= 900) and (3 not in multiplicateur):
                                        multiplicateur.append(3)
                                        score -= 900
                                        print(f"Bien jouer, vous venez d'obtenir le 3eme et dernier multiplicateur ! (Votre score apres l'achat : {score})")
                                    else:
                                        print(f"Vous n'avez pas asser de score ({score} < 400)")
                                if skin1.collidepoint(event.pos):
                                    CouleurSkin = "Green"
                                    print(f"Vous avez équiper le skin {CouleurSkin}")
                                if skin2.collidepoint(event.pos):
                                    if (2 in skinAcheter):
                                        CouleurSkin = "Red"
                                        print(f"Vous avez équiper le skin {CouleurSkin}")
                                    elif (score >= 150) and (2 not in skinAcheter):
                                        score -= 150
                                        CouleurSkin = "Red"
                                        skinAcheter.append(2)
                                        print(f"Bien jouer, vous venez d'obtenir et d'équiper le skin {CouleurSkin} ! (Votre score apres l'achat : {score})")
                                    else:
                                        print(f"Vous n'avez pas asser de score ({score} < 150)")
                                if skin3.collidepoint(event.pos):
                                    if (3 in skinAcheter):
                                        CouleurSkin = "Blue"
                                        print(f"Vous avez équiper le skin {CouleurSkin}")
                                    if (score >= 150) and (3 not in skinAcheter):
                                        score -= 150
                                        skinAcheter.append(3)
                                        CouleurSkin = "Blue"
                                        print(f"Bien jouer, vous venez d'obtenir et d'équiper le skin {CouleurSkin} ! (Votre score apres l'achat : {score})")
                                    else:
                                        print(f"Vous n'avez pas asser de score ({score} < 150)")

                                if retour.collidepoint(event.pos):
                                    achat = False
                        pygame.display.flip()
                if leave.collidepoint(event.pos):
                    running = False
                    menus = False
        pygame.display.flip()
    screen.fill((30,30,30))

    temps = pygame.time.get_ticks()
    if temps - dernier_mouvement >= delai:
        but = button()
        i = button()
        k = button()
        j = button()
        dernier_mouvement = temps

    if CouleurSkin == "Green":
        pygame.draw.rect(screen,(0,200,0),but)
        if (1 in but_bonus)and (2 not in but_bonus):
            pygame.draw.rect(screen,(0,200,0),i)
        if (2 in but_bonus)and (3 not in but_bonus):
            pygame.draw.rect(screen,(0,200,0),i)
            pygame.draw.rect(screen,(0,200,0),k)
        if (3 in but_bonus):
            pygame.draw.rect(screen,(0,200,0),i)
            pygame.draw.rect(screen,(0,200,0),k)
            pygame.draw.rect(screen,(0,200,0),j)
            
    if CouleurSkin == "Red":
        pygame.draw.rect(screen,(200,0,0),but)
        if (1 in but_bonus)and (2 not in but_bonus):
            pygame.draw.rect(screen,(200,0,0),i)
        if (2 in but_bonus)and (3 not in but_bonus):
            pygame.draw.rect(screen,(200,0,0),i)
            pygame.draw.rect(screen,(200,0,0),k)
        if (3 in but_bonus):
            pygame.draw.rect(screen,(200,0,0),i)
            pygame.draw.rect(screen,(200,0,0),k)
            pygame.draw.rect(screen,(200,0,0),j)

    if CouleurSkin == "Blue":
        pygame.draw.rect(screen,(0,0,200),but)
        if (1 in but_bonus)and (2 not in but_bonus):
            pygame.draw.rect(screen,(0,0,200),i)
        if (2 in but_bonus)and (3 not in but_bonus):
            pygame.draw.rect(screen,(0,0,200),i)
            pygame.draw.rect(screen,(0,0,200),k)
        if (3 in but_bonus):
            pygame.draw.rect(screen,(0,0,200),i)
            pygame.draw.rect(screen,(0,0,200),k)
            pygame.draw.rect(screen,(0,0,200),j)
    
    x = screen.get_width()
    y = screen.get_height()
    screen.blit(font.render("Attrape moi", True,(255,255,255)),(x / 2, y / 2))
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.MOUSEBUTTONDOWN:
            if but.collidepoint(event.pos) or i.collidepoint(event.pos) or k.collidepoint(event.pos) or j.collidepoint(event.pos):
                if ez:
                    if (1 in multiplicateur) and (2 not in multiplicateur):
                        score += 1 * 2
                    elif (1 in multiplicateur) and (3 not in multiplicateur):
                        score += 1 * 2.5
                    elif (3 in multiplicateur):
                        score += 1 * 3
                    else:
                        score += 1
                elif med:
                    if (1 in multiplicateur) and (2 not in multiplicateur):
                        score += 2 * 1.5
                    elif (1 in multiplicateur) and (3 not in multiplicateur):
                        score += 2 * 2
                    elif (3 in multiplicateur):
                        score += 2 * 3
                    else:
                        score += 2
                elif h:
                    if (1 in multiplicateur) and (2 not in multiplicateur):
                        score += 5 * 1.5
                    elif (1 in multiplicateur) and (3 not in multiplicateur):
                        score += 5 * 2
                    elif (3 in multiplicateur):
                        score += 5 * 3
                    else:
                        score += 5
                elif imp:
                    if (1 in multiplicateur) and (2 not in multiplicateur):
                        score += 15 * 1.5
                    elif (1 in multiplicateur) and (3 not in multiplicateur):
                        score += 15 * 2
                    elif (3 in multiplicateur):
                        score += 15 * 3
                    else:
                        score += 15
                print(f"Bouton clicker, Vous avez gagner !\n Votre score et maintenant à {score} point")
                but2 =  pygame.Rect(x / 4 , y / 2, 100, 100)
                but3 = pygame.Rect((x / 4) * 2, y / 2, 100, 100)
                but4 = pygame.Rect((x / 4) * 3, y / 2, 100, 100)
                choix = True
                while choix:
                    screen.fill((30,30,30))
                    screen.blit(font.render(f"Score : {score}",True,(255,255,255)),(x/2 , y/3 ))
                    pygame.draw.rect(screen,(0,200,0),but2)
                    pygame.draw.rect(screen,(0,200,0),but3)
                    pygame.draw.rect(screen,(0,200,0),but4)
                    screen.blit(font.render("Rejouer",True,(255,255,255)),(but2.left  , (y / 2) + (but2.height / 2.5)))
                    screen.blit(font.render("Menus",True,(255,255,255)),(but3.left  , (y / 2) + (but2.height / 2.5)))
                    screen.blit(font.render("Quitter",True,(255,255,255)),(but4.left ,( y / 2) + (but3.height / 2.5)))
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            running = False
                        if event.type == pygame.MOUSEBUTTONDOWN:
                            if but2.collidepoint(event.pos):
                                choix = False
                            if but3.collidepoint(event.pos):
                                menus = True
                                choix = False
                            if but4.collidepoint(event.pos):
                                running = False
                                choix = False
                    pygame.display.flip()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                Abondon = True
                while Abondon:
                    screen.fill((0,0,0,100))
                    sortir = pygame.Rect(x/2,y/2,100,100)
                    pygame.draw.rect(screen,(0,255,0),sortir)
                    screen.blit(font.render("Abondonner",True, (255,0,0)),(x/2 ,(y/2) + sortir.height/2))
                    att = True
                    for click in pygame.event.get():
                        if click.type == pygame.MOUSEBUTTONDOWN:
                            if sortir.collidepoint(click.pos):
                                menus = True
                                Abondon = False
                        if click.type == pygame.KEYDOWN:
                            if click.key == pygame.K_ESCAPE:
                                Abondon = False
                    pygame.display.flip()
    if med:
        enter = True
    if hard:
        enter = True

    pygame.display.flip()
pygame.quit()

# A  AJOUTER : 
# Des bonus tels que un agrandisseur de forme, des skins a chaque pallier, une sorte de 'passe de jeux', un bouton changer de niveau quand on win.
# et le fait que le bouton quitter ne sois pas clicable sans faire expres apres un win (sois retirer, sois faire un timer apres la win pour qu'il ne soit pas clicker instant).
# Ajouter un mode de jeux ou le joueur joue jusqu'a ce qu'il atteigne le nombre max de click ou le nb max de spawn de cube et ou la difficulter augmente a chaque réussite