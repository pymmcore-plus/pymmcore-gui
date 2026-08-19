# MDA Position Map - Note de conception

## Objectif

Ajouter a `pymmcore-gui` un widget de type carte 2D qui :

- affiche les positions XY definies dans le MDA ;
- represente pour chaque position le champ observe sous forme de rectangle ;
- aide l'utilisateur a se reperer spatialement entre les positions ;
- permette a terme de cliquer sur une position pour y deplacer la platine ;
- reste synchronise avec la table de positions du MDA.

Le besoin n'est pas de remplacer `Stage Explorer`, mais de completer le workflow MDA avec une vue synoptique des positions.

## Positionnement par rapport a `Stage Explorer`

`Stage Explorer` sait deja :

- afficher la FOV courante ;
- deplacer la platine ;
- dessiner des ROIs ;
- generer un `grid_plan` et lancer un MDA a partir d'une ROI.

Mais il ne consomme pas nativement la liste des positions du MDA.

Le nouveau widget doit donc etre pense comme :

- soit un nouveau widget dedie, par exemple `MDA Position Map`
- soit une extension reutilisant des briques de `Stage Explorer`

La solution la plus propre semble etre un nouveau widget specialise MDA, qui pourra ensuite partager certaines briques avec `Stage Explorer`.

## MVP recommande

Version minimale utile :

- lire les positions XY de la sequence MDA courante ;
- calculer la largeur et la hauteur de FOV ;
- dessiner un rectangle par position ;
- afficher un index ou un nom de position ;
- surligner la position selectionnee dans la table ;
- mettre a jour la carte quand la table change.

Pas besoin au debut de :

- dessiner les images acquises ;
- gerer les ROIs libres ;
- gerer la 3D ;
- introduire des modeles complexes de calibration.

## Source de verite

La source de verite des positions doit rester la sequence MDA et son editeur de positions.

En pratique :

- la table des positions MDA reste la representation autoritaire ;
- la carte n'est pas la source principale des donnees ;
- la carte est d'abord une vue synchronisee, puis un moyen d'interaction secondaire.

Cela evite :

- d'avoir deux listes de positions concurrentes ;
- de creer des divergences entre la table et la carte ;
- de compliquer la serialisation du MDA.

## Implementation prevue pour l'enregistrement des positions

Le point important est de definir tres clairement comment les positions sont creees et mises a jour.

### Principe general

L'enregistrement des positions doit rester rattache au workflow MDA existant.

Le widget de carte ne doit pas stocker sa propre liste persistante independante. Il doit :

- lire les positions depuis le modele MDA ;
- proposer des actions utilisateur ;
- deleguer ensuite l'ecriture au widget ou au modele de positions du MDA.

### Actions a prevoir

#### 1. Ajouter la position courante

Action utilisateur :

- bouton `Ajouter position courante`

Effet attendu :

- lire `x` et `y` depuis la platine XY courante ;
- lire `z` si le MDA inclut Z ou si la table de positions inclut un Z explicite ;
- creer une nouvelle entree de position dans la table MDA ;
- rafraichir la carte.

Usage :

- l'utilisateur se deplace a la platine ;
- clique sur `Ajouter position courante` ;
- voit apparaitre un nouveau rectangle sur la carte.

#### 2. Mettre a jour la position selectionnee

Action utilisateur :

- bouton `Remplacer par position courante`

Effet attendu :

- lire la ligne selectionnee dans la table MDA ;
- remplacer ses coordonnees XY par la position courante de la platine ;
- optionnellement remplacer Z selon le mode choisi ;
- rafraichir la carte.

Usage :

- corriger une position deja definie sans devoir la supprimer puis la recreer.

#### 3. Supprimer la position selectionnee

Action utilisateur :

- suppression depuis la table MDA, ou depuis la carte si une position est selectionnee

Effet attendu :

- suppression dans le modele MDA ;
- la carte suit automatiquement.

#### 4. Selection bidirectionnelle

Effet attendu :

- clic dans la table -> surbrillance sur la carte
- clic sur un rectangle de la carte -> selection de la ligne correspondante

Cela est essentiel pour rendre la carte utile au quotidien.

### Ce qu'il ne faut pas faire au debut

Pour le MVP, il vaut mieux eviter :

- edition libre des rectangles par drag-and-drop
- stockage d'une liste parallele locale au widget
- formats de sauvegarde specifiques a la carte

Ces fonctions sont possibles plus tard, mais elles compliquent beaucoup la coherence avec le MDA.

## Calcul de la taille des rectangles

Le rectangle ne doit pas etre derive uniquement d'un grossissement saisi a la main.

La priorite doit etre :

1. calibration effective du core
2. taille d'image effective
3. ROI camera
4. binning courant

Calcul vise :

- `fov_width_um = image_width_px * pixel_size_um`
- `fov_height_um = image_height_px * pixel_size_um`

Le widget doit si possible utiliser :

- `getPixelSizeUm()`
- `getImageWidth()`
- `getImageHeight()`

et ensuite tenir compte des changements de ROI et de binning si ceux-ci modifient la taille image ou la calibration effective.

## Synchronisation envisagee avec le MDA

Le plus probable est que le widget doive s'accrocher a l'objet ou au modele utilise par `MDAWidget`.

Synchronisations souhaitees :

- changement de sequence MDA
- ajout/suppression/modification de positions
- changement de selection dans la table
- eventuellement progression de l'acquisition multi-position

L'ideal est d'eviter toute logique de polling si une connexion par signaux est possible.

## Architecture proposee

### Option A : nouveau widget dedie

Exemple de nom :

- `MDAPositionMapWidget`

Responsabilites :

- afficher la carte ;
- connaitre la FOV courante ;
- synchroniser la selection ;
- deleguer les operations d'ajout/modification/suppression au modele MDA.

Avantage :

- claire separation des responsabilites ;
- plus simple a proposer upstream.

### Option B : extension de `Stage Explorer`

Cette option consisterait a reutiliser directement `Stage Explorer` comme support principal.

Avantage :

- reutilisation de la scene 2D existante ;
- reutilisation du rendu de FOV et de certaines interactions.

Inconvenient :

- risque de melanger deux usages differents :
  - exploration libre / scan ROI
  - edition et visualisation des positions MDA

Pour l'instant, l'option A semble preferable.

## Etapes de mise en oeuvre recommandees

### Etape 1

Prototype en lecture seule :

- afficher les positions MDA existantes
- afficher le rectangle de FOV
- synchroniser la selection

### Etape 2

Ajout de l'enregistrement de positions :

- `Ajouter position courante`
- `Remplacer par position courante`
- `Aller a la position selectionnee`

### Etape 3

Ameliorations de confort :

- labels plus lisibles
- position active pendant acquisition
- options de style
- prise en compte explicite du ROI et du binning

## Questions a garder ouvertes

- quel est l'objet exact a ecouter dans `MDAWidget` pour suivre les positions ?
- faut-il prendre en charge le Z dans la carte, ou rester strictement en XY ?
- comment gerer les inversions d'axes ou rotations si la calibration n'est pas triviale ?
- faut-il afficher seulement le centre, ou toujours le rectangle complet ?

## Position retenue

Pour la suite du developpement :

- le widget de carte doit etre un composant MDA, pas un simple outil ROI ;
- l'enregistrement des positions doit rester pilote par le modele MDA ;
- la carte doit etre une vue synchronisee et un support d'interaction, pas une base de donnees parallele ;
- l'implementation du workflow d'enregistrement doit commencer par `Ajouter position courante` et `Remplacer par position courante`.

