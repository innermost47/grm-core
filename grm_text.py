# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
Sentence categories with the GRM, without any training.

A table has two sides: on the left the words of example sentences, on the right their category. Every line of
the table writes relations between its words and its category; nothing is fitted, nothing is trained. For a new
sentence, its words are switched on and the GRM core solves a small network:

    shares      one positive node s_c per category
    balance     sum of the shares = 1                 what one category gains, the others lose
    evidence    log s_c = log p(c | w)  for every known word w of the sentence and every category c,
                with sigma = SIGMA_WORD / sqrt(n_w)   (a word seen often speaks with more confidence)

p(c | w) is read directly from the table: how often word w came with category c (smoothed). The network finds the
shares that balance all the words at once, with their uncertainty. The answer is the leading category when it
leads the runner-up by more than GAP_SIGMA sigma, otherwise "unsure: A or B". If no word of the sentence is in the table,
only the balance remains: the shares are undetermined and the answer is "unknown" instead of a guess.

Usage:
    python grm_text.py "le gardien a arrêté le penalty"
    python grm_text.py --eval          # held-out test sentences and off-topic sentences
"""
import argparse
import math
import re
import unicodedata

from pygrm import GlobalRelationalNetwork

SIGMA_WORD = 0.5      # dex, uncertainty of one word seen once
SMOOTHING = 0.5       # added to every word / category count
GAP_SIGMA = 1.0       # the winner must lead the runner-up by this many sigma

# ------------------------------------------------------------------ the table (left: sentences, right: category)
TABLE = {
    "sport": [
        "le gardien a arrêté le penalty à la dernière minute",
        "l'équipe a gagné le match grâce à un but magnifique",
        "le cycliste a remporté l'étape de montagne du tour",
        "elle court un marathon chaque printemps",
        "l'entraîneur prépare ses joueurs pour la finale",
        "le tennisman a servi un ace sur la balle de match",
        "le stade était plein pour le derby du dimanche",
        "il s'entraîne à la salle de musculation trois fois par semaine",
        "le nageur a battu le record du monde du cent mètres",
        "l'arbitre a sifflé un carton rouge contre le défenseur",
        "les supporters chantent dans les tribunes du stade",
        "le boxeur a mis son adversaire au tapis au troisième round",
        "la championne de ski a dévalé la piste en tête",
        "le club recrute un attaquant pour la saison prochaine",
        "le basketteur a marqué un panier à trois points",
        "ils jouent au rugby le samedi après midi",
        "la course de relais a été remportée par l'équipe de france",
        "le coureur a franchi la ligne d'arrivée épuisé",
        "le champion olympique a reçu sa médaille d'or",
        "le match de football a été reporté à cause du terrain",
        "elle pratique le judo depuis l'enfance",
        "le joueur s'est blessé au genou pendant l'entraînement",
        "le tournoi de handball commence la semaine prochaine",
        "le pilote a gagné le grand prix de formule un",
        "le score final était de deux buts à un",
    ],
    "cuisine": [
        "faire revenir les oignons dans une poêle avec du beurre",
        "la recette demande trois œufs et de la farine",
        "laisser mijoter la sauce tomate pendant une heure",
        "le chef prépare un gratin de pommes de terre",
        "préchauffer le four à deux cents degrés",
        "ajouter une pincée de sel et du poivre",
        "la pâte à crêpes doit reposer une heure",
        "elle a cuisiné un poulet rôti aux herbes",
        "couper les carottes en rondelles fines",
        "le gâteau au chocolat sort du four",
        "mélanger le sucre et le beurre dans un saladier",
        "servir la soupe chaude avec du pain grillé",
        "le restaurant propose un menu de saison",
        "faire bouillir l'eau des pâtes avec du sel",
        "la tarte aux pommes refroidit sur la table",
        "il prépare une vinaigrette à l'huile d'olive",
        "le poisson se cuit à la vapeur avec du citron",
        "émincer l'ail et le persil pour la farce",
        "le dessert est une mousse au chocolat",
        "faire dorer la viande dans une cocotte",
        "la cuisson du riz prend vingt minutes",
        "elle a acheté des légumes au marché pour le dîner",
        "le boulanger sort les baguettes du four",
        "battre les blancs en neige avec un fouet",
        "assaisonner la salade avant de la servir",
    ],
    "musique": [
        "le guitariste a joué un solo pendant le concert",
        "elle chante dans une chorale depuis dix ans",
        "le groupe sort un nouvel album au printemps",
        "le pianiste répète une sonate de beethoven",
        "l'orchestre symphonique joue ce soir à la philharmonie",
        "il apprend la batterie au conservatoire",
        "la chanson passe en boucle à la radio",
        "le festival de musique accueille des milliers de spectateurs",
        "le violoniste accorde son instrument avant de jouer",
        "la mélodie de ce refrain est très entraînante",
        "le chanteur a annulé sa tournée d'été",
        "elle compose des morceaux sur son synthétiseur",
        "le rappeur a enregistré son disque en studio",
        "les musiciens montent sur scène sous les applaudissements",
        "la partition est écrite en sol majeur",
        "il joue de la basse dans un groupe de rock",
        "le chef d'orchestre lève sa baguette",
        "ce morceau de jazz commence par un solo de saxophone",
        "la chanteuse a une voix magnifique",
        "le concert de piano a été retransmis à la radio",
        "ils répètent le spectacle de musique dans la salle",
        "le dj mixe des sons électroniques toute la nuit",
        "la guitare est désaccordée depuis le dernier concert",
        "le compositeur a écrit un opéra en trois actes",
        "le public a repris le refrain en chœur",
    ],
    "météo": [
        "il va pleuvoir toute la journée sur la bretagne",
        "les températures vont baisser cette nuit",
        "un orage violent est annoncé pour ce soir",
        "le soleil brillera sur le sud du pays",
        "la neige tombe depuis ce matin en montagne",
        "le vent souffle fort sur la côte atlantique",
        "les prévisions annoncent une vague de chaleur",
        "un épais brouillard couvre la vallée",
        "il gèle la nuit et le matin les routes sont glissantes",
        "le ciel restera nuageux avec quelques averses",
        "la canicule devrait durer jusqu'à la fin de la semaine",
        "une alerte orange aux inondations a été déclenchée",
        "le thermomètre affiche moins cinq degrés",
        "des rafales de vent à cent kilomètres heure sont attendues",
        "il fait beau et chaud pour la saison",
        "la grêle a abîmé les vignes cette nuit",
        "le temps sera humide et frais demain",
        "les nuages se dissipent dans l'après midi",
        "une tempête approche des côtes",
        "la pluie et le vent vont redoubler ce week end",
        "le printemps arrive avec des températures douces",
        "le bulletin météo annonce du verglas",
        "un anticyclone apporte du soleil sur toute la france",
        "il a neigé sur les sommets cette nuit",
        "la sécheresse inquiète les agriculteurs",
    ],
    "informatique": [
        "le programme plante quand on ouvre le fichier",
        "il faut mettre à jour le système d'exploitation",
        "le développeur corrige un bug dans le code",
        "mon ordinateur portable est très lent",
        "la base de données contient des millions de lignes",
        "installer le logiciel sur le serveur",
        "le site web ne répond plus depuis ce matin",
        "elle écrit un script en python pour trier les données",
        "le réseau wifi est coupé dans le bureau",
        "sauvegarder les fichiers sur un disque dur externe",
        "le mot de passe doit contenir des chiffres",
        "un virus a infecté les ordinateurs de l'entreprise",
        "la mise à jour de l'application corrige des failles",
        "le processeur chauffe quand le jeu tourne",
        "compiler le code avant de lancer les tests",
        "le serveur a besoin de plus de mémoire",
        "il code une application mobile pour android",
        "le clavier et la souris ne répondent plus",
        "les données sont chiffrées sur le cloud",
        "le navigateur affiche une erreur de connexion",
        "le développeur pousse son code sur le dépôt",
        "l'imprimante n'est pas reconnue par l'ordinateur",
        "le logiciel libre est distribué sous licence",
        "il faut redémarrer la machine après l'installation",
        "l'écran de l'ordinateur reste noir au démarrage",
    ],
}

# held-out sentences, written separately, never used to build the relations
TEST = {
    "sport": ["le défenseur a marqué un but contre son camp", "la coureuse a gagné la médaille d'argent au relais",
              "le match de tennis a duré cinq heures", "les joueurs de rugby s'entraînent sous la pluie",
              "le gardien de but a été élu meilleur joueur du tournoi", "elle nage tous les matins à la piscine",
              "le cycliste a chuté dans la descente", "l'équipe de basket a perdu la finale"],
    "cuisine": ["faire cuire les pâtes dans l'eau bouillante", "le chef ajoute du beurre dans la sauce",
                "la recette du gâteau demande du sucre et des œufs", "couper les oignons et l'ail finement",
                "le poulet cuit au four pendant une heure", "elle prépare une soupe de légumes",
                "servir la tarte avec de la crème", "le pain sort du four bien doré"],
    "musique": ["le pianiste joue une mélodie douce", "le groupe de rock donne un concert ce soir",
                "elle chante une chanson à la radio", "le batteur a cassé sa baguette pendant le solo",
                "l'orchestre répète pour le festival", "il apprend la guitare avec un professeur",
                "le nouvel album du chanteur sort demain", "les spectateurs applaudissent les musiciens"],
    "météo": ["il pleut depuis trois jours sur la ville", "la neige bloque les routes de montagne",
              "les températures vont remonter demain", "un orage a éclaté dans la nuit",
              "le vent froid souffle sur le nord", "les prévisions annoncent du soleil pour le week end",
              "le brouillard ralentit la circulation ce matin", "la chaleur est écrasante cet été"],
    "informatique": ["le logiciel ne démarre plus après la mise à jour", "il faut changer le disque dur du serveur",
                     "le code contient un bug difficile à trouver", "mon ordinateur a attrapé un virus",
                     "le site affiche une erreur au démarrage", "elle installe python sur sa machine",
                     "les fichiers de la base de données sont corrompus", "le réseau de l'entreprise est en panne"],
}

OFF_TOPIC = ["mon chat dort sur le canapé", "la réunion de parents d'élèves est jeudi",
             "il a repeint la porte du garage", "nous partons en vacances en italie",
             "le notaire a signé l'acte de vente", "la plante verte a besoin d'arrosage"]

STOP = set("""le la les l un une des de du d et a à au aux en dans sur pour par avec sans sous ce cet cette ces
son sa ses mon ma mes ton ta tes notre nos votre vos leur leurs il elle ils elles on nous vous je tu me te se s
qui que qu quoi dont où ne pas plus très est sont été être a ont avoir fait faire va vont depuis pendant après
avant chaque toute tout tous toutes comme mais ou donc car y lui eux""".split())


def strip_accents(text):
    return "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")


def words(sentence):
    """Lower case, accents removed, small words dropped, plurals folded (gardiens -> gardien)."""
    out = []
    for w in re.findall(r"[a-zœæ]+", strip_accents(sentence.lower().replace("'", " "))):
        if w in STOP or len(w) < 3:
            continue
        for suffix in ("s", "x"):
            if w.endswith(suffix) and len(w) - len(suffix) >= 4:
                w = w[: -len(suffix)]
                break
        out.append(w)
    return out


# ------------------------------------------------------------------ relations read from the table
class RelationTable:
    def __init__(self, table):
        self.categories = list(table)
        self.count = {}                 # word -> {category: count}
        for c, sentences in table.items():
            for s in sentences:
                for w in set(words(s)):
                    self.count.setdefault(w, {k: 0 for k in self.categories})[c] += 1

    def share(self, w):
        """p(c | w) for every category, smoothed, and how often w was seen."""
        counts = self.count[w]
        total = sum(counts.values()) + SMOOTHING * len(self.categories)
        return {c: (counts[c] + SMOOTHING) / total for c in self.categories}, sum(counts.values())

    def classify(self, sentence):
        """Solve the network of the sentence. Returns (answer, shares, uncertainty, known words)."""
        known = [w for w in words(sentence) if w in self.count]
        nodes = {f"s_{c}": {"guess": 1.0 / len(self.categories)} for c in self.categories}
        rels = [{"name": "balance", "type": "sum", "terms": {f"s_{c}": 1.0 for c in self.categories},
                 "K": 1.0, "sigma": 1e-6}]
        for w in known:
            p, n = self.share(w)
            sigma = SIGMA_WORD / math.sqrt(n)
            for c in self.categories:
                rels.append({"name": f"{w}->{c}", "terms": {f"s_{c}": 1.0}, "rhs": math.log10(p[c]), "sigma": sigma})
        out = GlobalRelationalNetwork(nodes, rels, undetermined_sigma=0.5).solve(max_iterations=50)
        shares = {c: out["values"][f"s_{c}"] for c in self.categories}
        unc = {c: out["uncertainty"][f"s_{c}"] for c in self.categories}     # relative, 1 sigma
        ranked = sorted(self.categories, key=shares.get, reverse=True)
        top, second = ranked[0], ranked[1]
        if not known:
            answer = "unknown"
        else:
            # gap between the winner and the runner-up, in sigma, with their covariance (the balance ties them)
            a, b = f"s_{top}", f"s_{second}"
            cov = out["covariance"]
            var = cov[(a, a)] + cov[(b, b)] - 2 * cov.get((a, b), cov.get((b, a), 0.0))
            gap = math.log10(shares[top] / shares[second]) / math.sqrt(max(var, 1e-30))
            answer = top if gap > GAP_SIGMA else f"unsure: {top} or {second}"
        return answer, shares, unc, known

    def explain(self, sentence, category):
        """Words that pulled the sentence towards a category, strongest first."""
        known = [w for w in words(sentence) if w in self.count]
        pull = {w: self.share(w)[0][category] for w in known}
        return sorted(pull.items(), key=lambda kv: -kv[1])


# ------------------------------------------------------------------ main
def show(rt, sentence):
    answer, shares, unc, known = rt.classify(sentence)
    print(f"\n« {sentence} »")
    print(f"  answer: {answer}")
    for c in sorted(shares, key=shares.get, reverse=True):
        print(f"    {c:<13} {shares[c]:6.1%}  ± {unc[c]:.0%} (relative)")
    if known and not answer.startswith("unknown"):
        top = max(shares, key=shares.get)
        print("  pulled by: " + ", ".join(f"{w} ({p:.0%})" for w, p in rt.explain(sentence, top)[:5]))
    elif not known:
        print("  no word of this sentence is in the table")


def evaluate(rt):
    """Held-out sentences: right, unsure with the right one among two, unsure without it, wrong (a confident error)."""
    tally = {"right": 0, "unsure, right one among the two": 0, "unsure, right one missing": 0, "wrong": 0,
             "unknown": 0}
    for c, sentences in TEST.items():
        for s in sentences:
            answer = rt.classify(s)[0]
            if answer == c:
                key = "right"
            elif answer == "unknown":
                key = "unknown"
            elif answer.startswith("unsure"):
                key = "unsure, right one among the two" if c in answer.split(": ")[1].split(" or ") \
                    else "unsure, right one missing"
            else:
                key = "wrong"
            tally[key] += 1
            if key not in ("right", "unsure, right one among the two"):
                print(f"  {key}: « {s} » ({c}) -> {answer}")
    total = sum(tally.values())
    print(f"held-out sentences ({total}): " + ", ".join(f"{v} {k}" for k, v in tally.items()))
    off = [rt.classify(s)[0] for s in OFF_TOPIC]
    print(f"off-topic sentences: {sum(a == 'unknown' for a in off)} unknown, "
          f"{sum(a.startswith('unsure') for a in off)} unsure, "
          f"{sum(not a.startswith(('unknown', 'unsure')) for a in off)} given a category")
    for s, a in zip(OFF_TOPIC, off):
        print(f"    « {s} » -> {a}")


def main():
    ap = argparse.ArgumentParser(description="Sentence categories with the GRM, without any training.")
    ap.add_argument("sentence", nargs="*", help="sentence(s) to classify")
    ap.add_argument("--eval", action="store_true", help="held-out and off-topic sentences")
    args = ap.parse_args()
    rt = RelationTable(TABLE)
    print(f"table: {sum(len(v) for v in TABLE.values())} sentences, {len(rt.categories)} categories, "
          f"{len(rt.count)} words related to them")
    if args.eval:
        evaluate(rt)
    for s in args.sentence:
        show(rt, s)
    if not args.eval and not args.sentence:
        for s in ("le gardien a arrêté le penalty", "il neige sur la montagne", "mon chat dort sur le canapé"):
            show(rt, s)


if __name__ == "__main__":
    main()
