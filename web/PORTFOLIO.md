# L'Univers relationnel

*Du Big Bang à la fin des temps, chaque nombre tenu par un seul réseau de relations.*

**L'Univers relationnel** est une simulation 3D interactive de l'univers, qui tourne dans le navigateur, sur ordinateur
comme sur téléphone. On lance le Big Bang et on traverse toute l'histoire : le premier plasma, les premiers noyaux,
la lumière qui se libère, les âges sombres, les premières étoiles, les galaxies, la naissance du Soleil, aujourd'hui,
puis la fin des étoiles et l'évaporation des trous noirs.

Il ne s'agit pas d'une animation scénarisée. L'âge de l'univers, la température de la lumière fossile, la durée de vie
des étoiles, la couleur du Soleil, la vitesse du son dans l'air et même la musique sont les **nœuds d'un seul réseau
GRM** : un solveur de relations qui cherche l'état où toutes les lois tiennent ensemble à la fois. Chaque nombre est
retenu par des « élastiques » (une loi de la physique, une hypothèse ou un choix musical), et tous sont listés et
sourcés dans la page.

## Toucher les constantes

On peut modifier les constantes de la nature : la force de la gravité, la constante de structure fine, la masse de
l'électron et du proton, l'expansion, la quantité de matière, la température de la lumière. Le réseau se résout de
nouveau et l'univers entier répond : les étoiles changent de couleur et de durée de vie, la lumière se libère plus tôt
ou plus tard, la flûte joue plus haut ou plus bas, toujours juste.

Si on pousse trop loin, avec trop de matière ou un ciel brûlant, l'univers se referme. Certains univers ne tiennent
pas du tout : le réseau le dit et nomme la relation qui casse.

## Deux fins, jouées jusqu'au bout

Chaque univers est un film qui va jusqu'à sa fin, et chaque étape de cette fin est un nœud du réseau.

- **La fin froide** : les dernières étoiles s'éteignent, les naines blanches noircissent, les galaxies s'évaporent
  (neuf étoiles sur dix projetées dans le vide, les autres avalées par le trou noir central), les protons se
  désintègrent peut-être, puis les trous noirs s'évaporent un à un dans un dernier éclair, jusqu'au noir, vers
  10¹⁰⁰ ans.
- **Le Big Crunch** : l'expansion s'arrête et le film se retourne, la chute durant à l'écran aussi longtemps que la
  montée. Les galaxies se percutent, le ciel devient plus brillant que les étoiles qui cuisent de l'extérieur, les
  atomes puis les noyaux sont brisés, et tout s'écrase en un point dans un dernier flash. Pendant la chute, l'accord
  cosmique monte avec la lumière.

## La musique

La musique est elle aussi calculée par le réseau. Une nappe cosmique est jouée à partir des pics acoustiques du jeune
univers, transposés de 50 octaves. Une flûte lointaine joue en mode lydien sur fa, avec des tuyaux taillés pour l'air
de la Terre : si l'air change, la flûte change avec lui. L'atténuation du son par l'air suit la norme ISO 9613-1.

## Technique

- **JavaScript pur**, sans étape de build : Three.js (WebGL) pour la 3D, l'API Web Audio pour le son.
- **grm.js** : un portage JavaScript du solveur GRM en Python (moindres carrés pondérés en espace log, Gauss-Newton
  et Levenberg-Marquardt, continuation). Il est vérifié nombre par nombre contre la version Python (131 contrôles).
- **La physique** : équations de Friedmann (valeurs Planck 2018, avec courbure), équilibre de Saha pour les noyaux et
  la recombinaison, horizon sonore et premier pic acoustique, lois d'échelle de Carr et Rees pour les étoiles,
  évaporation de Hawking pour les trous noirs.
- **Validation** : notre univers retrouve 13,8 milliards d'années, une recombinaison à z ≈ 1090 et un premier pic
  acoustique proche de ℓ = 220, comme les mesures de Planck. Les limites du modèle sont écrites noir sur blanc.
- **Bilingue** français / anglais, adapté au mobile, et des préréglages pour essayer d'autres univers ou garder les
  siens.

Le code est libre (AGPL-3.0) et fait partie du projet GRM :
**[github.com/innermost47/grm-core](https://github.com/innermost47/grm-core)**
