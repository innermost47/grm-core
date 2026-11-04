// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Anthony Charretier
//
// French and English texts of the universe page (the browser's language chooses; a button switches).

export const TEXTS = {
  en: {
    title: "The Relational Universe",
    lead: "Everything you will see and hear is held together by one network of relations.",
    intro: [
      "From the Big Bang to the end of time: the light of the first plasma, the first nuclei, the moment the universe becomes transparent, the first stars, the galaxies, the Sun, the Earth, and what comes after us.",
      "Nothing here is drawn by hand. The temperatures, the dates, the colour of the stars, the life of the Sun, the pitch of the music: each is a node of a GRM network, tied to the others by the laws of physics, like elastics. Pull one, and everything answers.",
      "The music too: a chord made of the sound that crossed the young universe, and a distant flute in the Lydian mode whose pitch follows the air of the Earth.",
      "Change the constants of nature, and launch another universe.",
    ],
    launch: "Launch the universe",
    launchWith: "with the current constants",
    launchThis: "Launch a Big Bang with these constants",
    resume: "Resume", pausesOn: "Pauses: on", pausesOff: "Pauses: off", chapter: "Chapter", theEnd: "The end",
    again: "Watch it again",
    settings: "Constants",
    sound: "Sound on: use headphones",
    by: "A project by Anthony Charretier, built on the GRM engine.",
    source: "Source code and the network, on GitHub",
    license: "Free software, AGPL-3.0",
    play: "Play", pause: "Pause", toToday: "Today", toEnd: "To the end", newBang: "New Big Bang", elastics: "Elastics",
    close: "Close", muteOn: "Sound off", muteOff: "Sound on",
    time: "time", temperature: "light", left: "end in", size: "observable universe", today: "This is today. Touch the constants and watch the universe answer.",
    end: "The end: no star, no black hole, only a cold dark that keeps expanding. Another Big Bang?",
    pageTitle: "The Relational Universe · from the Big Bang to the end of time",
    resetHint: "Double-click: back to our universe's value",
    endCrunch: "The end: everything was crushed back into a point. Another Big Bang?",
    presets: "Presets", yours: "Yours", save: "Save these constants", saveName: "Name of this universe",
    reset: "Our universe", invalid: "This universe cannot be built here:",
    params: {
      alpha: ["Electromagnetism α", "× ours: how strongly light and electrons hold atoms"],
      G: ["Gravity G", "× ours"],
      me: ["Electron mass", "× ours"],
      mp: ["Proton mass", "× ours"],
      H0: ["Expansion today H0", "km/s/Mpc (ours: 67.4)"],
      ombh2: ["Ordinary matter Ω_b h²", "ours: 0.0224"],
      omch2: ["Dark matter Ω_c h²", "ours: 0.120"],
      Tcmb: ["Light left today T0", "kelvin (ours: 2.7255)"],
    },
    presetNames: { ours: "Our universe (Planck 2018)", gravity: "Gravity × 10", alpha: "α × 1.1", electron: "Electron × 2",
      baryons: "Twice the ordinary matter", fast: "A faster expansion (H0 = 80)",
      crunch: "Too much matter: Big Crunch", hot: "A burning universe (T × 37)", broken: "Everything wrong at once" },
    consequences: { starLife: "A star like the Sun lives", starColour: "Its surface:", flute: "The flute:", light: "Light freed at",
      ours: "ours:", sunDead: "In this universe the Sun is already dead: no flute today.",
      noTime: "Stars live too briefly for life to have time (4.5 billion years on Earth).",
      crunch: "Too much matter: expansion stops, everything falls back. Big Crunch after", opaque: "The light is set free very late: the sky stays a furnace for a long time." },
    kinds: { law: "law of physics", hypothesis: "hypothesis (scaling, set on our universe)", music: "musical choice" },
    elasticsLead: "Every number of this universe, and the relation that holds it. Laws of physics, hypotheses (set on our universe), and the choices of the music.",
    keyValues: "What the network finds now",
    values: {
      t0: "age of the universe today", Rhor: "radius of the observable universe today", zrec: "redshift of the freed light", trec: "light set free after", tnuc: "first nuclei after",
      l1: "first acoustic peak (ℓ)", tstar: "life of a star like the Sun", Tsun: "surface of the Sun", cair: "speed of sound in air",
      flute0: "the flute's F", pad1: "the cosmic chord's F", tbh: "a black hole evaporates after",
      tblack: "white dwarfs turn black after", tevap: "galaxies evaporate after", tproton: "protons decay after (if they do)",
      tsmbh: "the largest black holes evaporate after", tmax: "the expansion stops after", dmerge: "galaxies merge, before the end:",
      dcook: "stars are cooked, before the end:", tcrunch: "Big Crunch after",
    },
    epochs: {
      plasma: ["The first plasma", "Light and particles at billions of degrees. Everything you will ever know is here, packed in this glow."],
      nuclei: ["The first nuclei", "Protons and neutrons stick together: hydrogen and helium are made, in a few minutes."],
      sound: ["An ocean of light that sings", "Sound waves cross the plasma. Their chord is the one you hear: it will be frozen in the sky."],
      light: ["The universe becomes transparent", "Electrons join the nuclei: light is set free. It still reaches us today, cooled to microwaves."],
      dark: ["The dark ages", "Cold gas, no star yet. Gravity slowly gathers matter."],
      stars: ["The first stars", "Gas collapses and ignites: the universe lights up again."],
      galaxies: ["The galaxies", "Stars gather into galaxies. Ours is at the centre of the screen (not of the universe: it has no centre)."],
      sun: ["The Sun is born", "A star among billions. The Earth forms around it; then the flute."],
      today: ["Today", "{age}. You are here."],
      giant: ["The Sun becomes a red giant", "The Earth is burnt: the flute falls silent."],
      starsEnd: ["The last stars go out", "No more gas to make stars. The galaxies fade."],
      blackDwarfs: ["The degenerate era", "The dead stars cool: white dwarfs turn red, then black, after about {tblack}. The other galaxies are gone beyond our horizon."],
      evaporate: ["The galaxies evaporate", "Passing close, stars share out their energy: after about {tevap}, nine in ten have been flung into the void, the others have sunk into the central black hole."],
      longNight: ["The long night", "Black dwarfs, neutron stars and black holes drift in the dark, for a time beyond anything that has passed."],
      protons: ["Matter decays", "If protons decay (never seen yet), the black dwarfs vanish into light after about {tproton}: nothing is left but black holes."],
      holes: ["The age of black holes", "Only black holes are left. Very slowly, they lose their mass as light (Hawking)."],
      hawking: ["The last flashes", "One by one, black holes evaporate in a last flash: the stellar ones after about {tbh}, the largest after {tsmbh}."],
      end: ["The dark era", "The last black hole is gone. Only scattered light remains, ever colder, in a universe that keeps growing."],
      recollapse: ["The great turnaround", "Gravity wins: the expansion stops after {tmax}, and everything starts to fall back. The light warms up again."],
      merge: ["The galaxies collide", "The whole universe is now as dense as a galaxy: they merge into one swarm of stars."],
      cook: ["The sky outshines the stars", "The light of the sky is hotter than the stars' surface: they can no longer cool, and are cooked from outside."],
      plasmaAgain: ["Plasma again", "Atoms are broken: the universe becomes opaque again, a furnace like its first days, {trec} before the end."],
      nucleiBroken: ["The nuclei break", "Light is now hot enough to break nuclei: helium and hydrogen made in the first minutes are undone, {tnuc} before the end."],
      crunch: ["The Big Crunch", "Everything is crushed into one point, infinitely hot. What comes next, no physics knows yet."],
    },
  },
  fr: {
    title: "L'Univers relationnel",
    lead: "Tout ce que vous allez voir et entendre est tenu par un seul réseau de relations.",
    intro: [
      "Du Big Bang à la fin des temps : la lumière du premier plasma, les premiers noyaux, l'instant où l'univers devient transparent, les premières étoiles, les galaxies, le Soleil, la Terre, et ce qui vient après nous.",
      "Rien n'est dessiné à la main. Les températures, les dates, la couleur des étoiles, la vie du Soleil, la hauteur de la musique : chacun est un nœud d'un réseau GRM, relié aux autres par les lois de la physique, comme par des élastiques. Tirez sur l'un, tout répond.",
      "La musique aussi : un accord fait du son qui a traversé le jeune univers, et une flûte lointaine en mode lydien dont la hauteur suit l'air de la Terre.",
      "Changez les constantes de la nature, et lancez un autre univers.",
    ],
    launch: "Lancer l'univers",
    launchWith: "avec les constantes actuelles",
    launchThis: "Lancer un Big Bang avec ces constantes",
    resume: "Reprendre", pausesOn: "Pauses : oui", pausesOff: "Pauses : non", chapter: "Chapitre", theEnd: "Fin",
    again: "Revoir ce film",
    settings: "Constantes",
    sound: "Avec le son : un casque, c'est mieux",
    by: "Un projet d'Anthony Charretier, construit sur le moteur GRM.",
    source: "Le code et le réseau, sur GitHub",
    license: "Logiciel libre, AGPL-3.0",
    play: "Lecture", pause: "Pause", toToday: "Aujourd'hui", toEnd: "Jusqu'à la fin", newBang: "Nouveau Big Bang", elastics: "Élastiques",
    close: "Fermer", muteOn: "Couper le son", muteOff: "Remettre le son",
    time: "temps", temperature: "lumière", left: "fin dans", size: "univers observable", today: "Nous sommes aujourd'hui. Touchez les constantes et regardez l'univers répondre.",
    end: "La fin : plus d'étoile, plus de trou noir, seulement un noir froid qui s'étend toujours. Un autre Big Bang ?",
    pageTitle: "L'Univers relationnel · du Big Bang à la fin des temps",
    resetHint: "Double-clic : retour à la valeur de notre univers",
    endCrunch: "La fin : tout a été écrasé en un point. Un autre Big Bang ?",
    presets: "Préréglages", yours: "Les vôtres", save: "Garder ces constantes", saveName: "Nom de cet univers",
    reset: "Notre univers", invalid: "Cet univers ne peut pas être construit ici :",
    params: {
      alpha: ["Électromagnétisme α", "× le nôtre : la force qui tient les atomes"],
      G: ["Gravité G", "× la nôtre"],
      me: ["Masse de l'électron", "× la nôtre"],
      mp: ["Masse du proton", "× la nôtre"],
      H0: ["Expansion aujourd'hui H0", "km/s/Mpc (la nôtre : 67,4)"],
      ombh2: ["Matière ordinaire Ω_b h²", "la nôtre : 0,0224"],
      omch2: ["Matière noire Ω_c h²", "la nôtre : 0,120"],
      Tcmb: ["Lumière restante T0", "kelvins (la nôtre : 2,7255)"],
    },
    presetNames: { ours: "Notre univers (Planck 2018)", gravity: "Gravité × 10", alpha: "α × 1,1", electron: "Électron × 2",
      baryons: "Deux fois plus de matière ordinaire", fast: "Une expansion plus rapide (H0 = 80)",
      crunch: "Trop de matière : Big Crunch", hot: "Un univers brûlant (T × 37)", broken: "Tout de travers à la fois" },
    consequences: { starLife: "Une étoile comme le Soleil vit", starColour: "Sa surface :", flute: "La flûte :", light: "Lumière libérée à",
      ours: "le nôtre :", sunDead: "Dans cet univers, le Soleil est déjà mort : pas de flûte aujourd'hui.",
      noTime: "Les étoiles vivent trop peu pour que la vie ait le temps (4,5 milliards d'années sur Terre).",
      crunch: "Trop de matière : l'expansion s'arrête, tout retombe. Big Crunch après", opaque: "La lumière se libère très tard : le ciel reste longtemps une fournaise." },
    kinds: { law: "loi de la physique", hypothesis: "hypothèse (loi d'échelle, réglée sur notre univers)", music: "choix musical" },
    elasticsLead: "Chaque nombre de cet univers, et la relation qui le tient. Lois de la physique, hypothèses (réglées sur notre univers), et choix de la musique.",
    keyValues: "Ce que le réseau trouve maintenant",
    values: {
      t0: "âge de l'univers aujourd'hui", Rhor: "rayon de l'univers observable aujourd'hui", zrec: "décalage de la lumière libérée", trec: "lumière libérée après", tnuc: "premiers noyaux après",
      l1: "premier pic acoustique (ℓ)", tstar: "vie d'une étoile comme le Soleil", Tsun: "surface du Soleil", cair: "vitesse du son dans l'air",
      flute0: "le fa de la flûte", pad1: "le fa de l'accord cosmique", tbh: "un trou noir s'évapore après",
      tblack: "les naines blanches noircissent après", tevap: "les galaxies s'évaporent après", tproton: "les protons se désintègrent après (s'ils le font)",
      tsmbh: "les plus grands trous noirs s'évaporent après", tmax: "l'expansion s'arrête après", dmerge: "les galaxies fusionnent, avant la fin :",
      dcook: "les étoiles cuisent, avant la fin :", tcrunch: "Big Crunch après",
    },
    epochs: {
      plasma: ["Le premier plasma", "Lumière et particules à des milliards de degrés. Tout ce que vous connaîtrez est là, serré dans cette lueur."],
      nuclei: ["Les premiers noyaux", "Protons et neutrons s'assemblent : l'hydrogène et l'hélium naissent, en quelques minutes."],
      sound: ["Un océan de lumière qui chante", "Des ondes sonores traversent le plasma. Leur accord est celui que vous entendez : il restera gravé dans le ciel."],
      light: ["L'univers devient transparent", "Les électrons rejoignent les noyaux : la lumière se libère. Elle nous parvient encore, refroidie en micro-ondes."],
      dark: ["Les âges sombres", "Du gaz froid, pas encore d'étoile. La gravité rassemble lentement la matière."],
      stars: ["Les premières étoiles", "Le gaz s'effondre et s'allume : l'univers se rallume."],
      galaxies: ["Les galaxies", "Les étoiles se rassemblent en galaxies. La nôtre est au centre de l'écran (pas de l'univers : il n'a pas de centre)."],
      sun: ["Le Soleil naît", "Une étoile parmi des milliards. La Terre se forme autour ; puis la flûte."],
      today: ["Aujourd'hui", "{age}. Vous êtes ici."],
      giant: ["Le Soleil devient une géante rouge", "La Terre est brûlée : la flûte se tait."],
      starsEnd: ["Les dernières étoiles s'éteignent", "Plus de gaz pour faire des étoiles. Les galaxies pâlissent."],
      blackDwarfs: ["L'ère dégénérée", "Les étoiles mortes refroidissent : les naines blanches rougissent, puis noircissent, après environ {tblack}. Les autres galaxies ont disparu derrière notre horizon."],
      evaporate: ["Les galaxies s'évaporent", "En se frôlant, les étoiles s'échangent leur énergie : après environ {tevap}, neuf sur dix ont été projetées dans le vide, les autres sont tombées dans le trou noir central."],
      longNight: ["La longue nuit", "Naines noires, étoiles à neutrons et trous noirs dérivent dans le noir, pendant un temps sans commune mesure avec tout ce qui a précédé."],
      protons: ["La matière se désintègre", "Si les protons se désintègrent (jamais observé), les naines noires s'effacent en lumière après environ {tproton} : il ne reste que des trous noirs."],
      holes: ["L'ère des trous noirs", "Il ne reste que des trous noirs. Très lentement, ils perdent leur masse en lumière (Hawking)."],
      hawking: ["Les derniers éclairs", "Un à un, les trous noirs s'évaporent dans un dernier éclair : les stellaires après environ {tbh}, les plus grands après {tsmbh}."],
      end: ["L'ère sombre", "Le dernier trou noir a disparu. Il ne reste qu'une lumière éparse, toujours plus froide, dans un univers qui grandit toujours."],
      merge: ["Les galaxies se percutent", "L'univers entier est maintenant aussi dense qu'une galaxie : elles fusionnent en un seul essaim d'étoiles."],
      cook: ["Le ciel brille plus que les étoiles", "La lumière du ciel est plus chaude que la surface des étoiles : elles ne peuvent plus se refroidir, et cuisent de l'extérieur."],
      plasmaAgain: ["Le retour du plasma", "Les atomes sont brisés : l'univers redevient opaque, une fournaise comme à ses premiers jours, {trec} avant la fin."],
      nucleiBroken: ["Les noyaux se brisent", "La lumière est assez chaude pour casser les noyaux : l'hélium et l'hydrogène des premières minutes sont défaits, {tnuc} avant la fin."],
      recollapse: ["Le grand retournement", "La gravité l'emporte : l'expansion s'arrête après {tmax} et tout commence à retomber. La lumière se réchauffe."],
      crunch: ["Le Big Crunch", "Tout est écrasé en un point, infiniment chaud. Ce qui vient après, aucune physique ne le sait encore."],
    },
  },
};

// French texts of the relations (the English ones are in universe.js)
export const RELATIONS_FR = {
  "Bohr radius": "a0 = ħ / (m_e c α) : la taille de l'atome",
  "Rydberg energy": "Ry = α² m_e c² / 2 : ce qui lie un électron à un proton",
  "gravitational coupling": "α_G = G m_p² / (ħ c) : la faiblesse de la gravité entre deux protons",
  "Hubble constant in SI": "H0 en 1/s",
  "little h": "h = H0 / 100",
  "critical density": "ρ_c = 3 H0² / (8π G) (Friedmann)",
  "baryons": "Ω_b = ω_b / h²",
  "dark matter": "Ω_c = ω_c / h²",
  "matter": "Ω_m = Ω_b + Ω_c",
  "light energy density": "ρ_γ = π²/15 (kT)⁴ / (ħc)³ (corps noir)",
  "light share": "Ω_γ = ρ_γ / (ρ_c c²)",
  "radiation share": "Ω_r = Ω_γ (1 + 0,2271 N_eff) : lumière et neutrinos",
  "flat universe": "Ω_m + Ω_r + Ω_Λ = 1 (pas de courbure : ce que mesure Planck)",
  "baryons per photon": "η = n_b / n_γ, n_γ = 2ζ(3)/π² (kT/ħc)³",
  "deuterium bottleneck": "les noyaux se forment quand la lumière cesse de casser le deutérium : 6,5 η (kT/m_p c²)^3/2 e^(B_D/kT) = 1 (Saha)",
  "hydrogen recombines": "la moitié de l'hydrogène est neutre : x²/(1-x) = (m_e kT/2πħ²)^3/2 e^(-Ry/kT) / n_b à x = 1/2 (Saha)",
  "delayed recombination": "la vraie recombinaison a du retard sur Saha (Peebles 1968, non modélisé) : facteur réglé pour que notre univers donne le z* = 1089,9 de Planck",
  "redshift of recombination": "1 + z = T / T0",
  "when nuclei form": "t = ∫ da / (a H(a)), H² = H0² (Ω_r a⁻⁴ + Ω_m a⁻³ + Ω_Λ), a = T0 / T",
  "when light is set free": "la même intégrale de Friedmann, jusqu'à la recombinaison",
  "age of the universe": "aujourd'hui : a = 1",
  "first stars": "les premières étoiles s'allument vers z = 20 (simulations de la formation des structures ; non dérivé ici)",
  "baryon loading": "R = 3ρ_b / 4ρ_γ = (3Ω_b / 4Ω_γ) a : les baryons alourdissent le son",
  "loading at recombination": "R* = R(a*)",
  "sound horizon": "r_s = ∫ c_s da / (a² H), c_s = c / √(3(1+R)) : la distance parcourue par le son avant la libération de la lumière",
  "distance to the light": "D = ∫ c da / (a² H), de la recombinaison jusqu'à nous",
  "acoustic scale": "ℓ_A = π D / r_s : la taille du son dans le ciel",
  "first peak": "ℓ_n = ℓ_A (n - φ), φ ≈ 0,27 (Doran & Lilley 2002)",
  "mass of a star": "M ~ m_p α_G^-3/2 : la gravité contre la pression de la matière chaude (préfacteur : le Soleil)",
  "life of a star": "t ~ α² α_G⁻¹ (m_p/m_e)² ħ/(m_p c²) (Carr & Rees 1979 ; préfacteur : le Soleil vit 10 milliards d'années)",
  "surface of a star": "une photosphère se place là où les atomes retiennent leurs électrons : T ∝ Ry / k (préfacteur : le Soleil, 5772 K)",
  "birth of the Sun": "le Soleil naît à la même part de l'âge de l'univers que chez nous (4,567 milliards d'années avant notre aujourd'hui)",
  "observable universe": "R = ∫ c da / (a² H) du Big Bang à aujourd'hui : d'où vient la lumière que nous voyons maintenant (rayon, aujourd'hui)",
  "white dwarfs go black": "les étoiles mortes refroidissent en naines noires : ~10¹⁵ ans pour nous (Adams & Laughlin 1997), à l'échelle de la vie des étoiles",
  "stars in a galaxy": "une galaxie comme la nôtre contient 10¹¹ soleils de matière : autant d'étoiles de la masse de cet univers qu'il en tient",
  "crossing time of a galaxy": "t_traversée = 1/√(Gρ), ρ = 18π² fois la densité moyenne de matière quand les galaxies s'effondrent (G s'élimine)",
  "stars exchange their energy": "t_relax = N / (8 ln N) t_traversée : les passages rapprochés redistribuent lentement l'énergie des étoiles (Binney & Tremaine)",
  "galaxies evaporate": "t_évap ≈ 136 t_relax : les étoiles qui gagnent de l'énergie s'échappent, les autres tombent dans le trou noir central (Binney & Tremaine)",
  "protons decay": "si les protons se désintègrent (jamais observé : > 2,4 × 10³⁴ ans, Super-Kamiokande), ~10³⁷ ans (Adams & Laughlin), τ ∝ m_p⁻⁵ (grande unification)",
  "galaxies merge": "les galaxies se touchent quand l'univers entier est aussi dense qu'elles : 18π² fois plus dense qu'à leur formation (Rees 1969)",
  "the sky outshines the stars": "quand la lumière du ciel est aussi chaude que la surface des étoiles, elles ne peuvent plus se refroidir : elles cuisent de l'extérieur (Rees 1969)",
  "time left when galaxies merge": "l'intégrale de Friedmann, à rebours : il retombe comme il a grandi",
  "time left when the stars are cooked": "l'intégrale de Friedmann, à rebours",
  "the Sun becomes a red giant": "après sa vie sur la séquence principale",
  "end of the stars": "les dernières naines rouges s'éteignent, le gaz est épuisé : ~10¹⁴ ans pour nous (Adams & Laughlin 1997), à l'échelle de la vie des étoiles",
  "a stellar black hole evaporates": "t = 5120 π G² M³ / (ħ c⁴), M = 10 étoiles (Hawking 1974)",
  "the largest black holes evaporate": "la même, M = 10¹⁰ étoiles (les plus grands trous noirs connus)",
  "the Earth warmed by the Sun": "T = T_soleil √(R_soleil / 2d) (1 - albédo)^1/4, et l'effet de serre (+33 K aujourd'hui, gardé en rapport)",
  "weight of the air": "M = 28,97 masses atomiques par molécule (N₂, O₂)",
  "speed of sound in air": "c² = γ R T / M (gaz parfait, γ = 1,4)",
};
for (let k = 1; k <= 7; k++) RELATIONS_FR[`flute note ${k}`] = `f = c / (2 (L + 1,22 r)) : un tuyau ouvert coupé pour le degré ${k} du mode lydien, dans notre air`;
for (let n = 1; n <= 6; n++) RELATIONS_FR[`cosmic chord ${n}`] = `pic ${n} du son du ciel, transposé pour que notre premier pic soit un fa`;

export function pickLanguage() {
  try {
    const saved = localStorage.getItem("grm-universe-lang");
    if (saved === "fr" || saved === "en") return saved;
  } catch { /* private mode */ }
  return (navigator.language || "en").toLowerCase().startsWith("fr") ? "fr" : "en";
}

// a length in words: "6 000 km", "4.9 light-years", "46.2 billion light-years", "10^35 light-years"
export function formatLength(meters, lang) {
  return formatLogLength(Math.log10(meters), lang);
}
// the same from log10 of the length in metres (any size, even beyond what a number can hold)
export function formatLogLength(logMeters, lang) {
  const fr = lang === "fr";
  const ly = fr ? "années-lumière" : "light-years";
  const logLy = logMeters - Math.log10(9.4607e15);
  if (logLy >= 12) {
    const e = Math.floor(logLy);
    const sup = (n) => String(n).split("").map((d) => "⁰¹²³⁴⁵⁶⁷⁸⁹"[+d]).join("");
    if (e < 100) return `${(10 ** (logLy - e)).toLocaleString(fr ? "fr-FR" : "en-US", { maximumFractionDigits: 1 })}×10${sup(e)} ${ly}`;
    if (e < 1e6) return `10${sup(e)} ${ly}`;
    const mant = e / 10 ** Math.floor(Math.log10(e));
    return `10^(${mant.toLocaleString(fr ? "fr-FR" : "en-US", { maximumFractionDigits: 1 })}×10${sup(Math.floor(Math.log10(e)))}) ${ly}`;
  }
  const meters = 10 ** logMeters;
  const num = (x, d = 1) => x.toLocaleString(fr ? "fr-FR" : "en-US", { maximumFractionDigits: d });
  const LY = 9.4607e15;
  if (meters < 1000) return `${num(meters, 0)} m`;
  if (meters < 0.05 * LY) return `${num(meters / 1000, 0)} km`;
  const y = meters / LY;
  if (y < 1e6) return `${num(y, y < 10 ? 1 : 0)} ${fr ? "années-lumière" : y < 2 ? "light-year" : ly}`;
  if (y < 1e9) return `${num(y / 1e6, 0)} ${fr ? (y < 2e6 ? "million d'années-lumière" : "millions d'années-lumière") : "million light-years"}`;
  return `${num(y / 1e9, 1)} ${fr ? "milliards d'années-lumière" : "billion light-years"}`;
}

// a duration in words: "3 minutes", "380 000 years", "13.8 billion years", "10^14 years"
export function formatTime(seconds, lang) {
  const fr = lang === "fr";
  const year = 3.15576e7;
  const num = (x, d = 1) => x.toLocaleString(fr ? "fr-FR" : "en-US", { maximumFractionDigits: d });
  if (seconds < 1) return fr ? `${num(seconds, 3)} seconde` : `${num(seconds, 3)} second`;
  if (seconds < 120) return `${num(seconds, 0)} ${fr ? "secondes" : "seconds"}`;
  if (seconds < 7200) return `${num(seconds / 60, 0)} minutes`;
  if (seconds < 2 * 86400) return `${num(seconds / 3600, 0)} ${fr ? "heures" : "hours"}`;
  const y = seconds / year;
  if (y < 1) return `${num(seconds / 86400, 0)} ${fr ? "jours" : "days"}`;
  if (y < 1e6) return `${num(Math.round(y / (y < 1e3 ? 1 : 1e3)) * (y < 1e3 ? 1 : 1e3), 0)} ${fr ? "ans" : "years"}`;
  if (y < 1e9) return `${num(y / 1e6, 0)} ${fr ? "millions d'années" : "million years"}`;
  if (y < 1e12) return `${num(y / 1e9, 1)} ${fr ? "milliards d'années" : "billion years"}`;
  const e = Math.floor(Math.log10(y));
  const sup = String(e).split("").map((d) => "⁰¹²³⁴⁵⁶⁷⁸⁹"[+d]).join("");
  return `10${sup} ${fr ? "ans" : "years"}`;
}

// a temperature given by its log10 (the far future is colder than any number a computer holds)
export function formatTemperature(logT, lang) {
  const fr = lang === "fr";
  const sup = (e) => (e < 0 ? "⁻" : "") + String(Math.abs(e)).split("").map((d) => "⁰¹²³⁴⁵⁶⁷⁸⁹"[+d]).join("");
  if (logT < -1e6) {
    // after the stars, space grows exponentially: the light's temperature is 10 to the power of a power
    const e2 = Math.floor(Math.log10(-logT));
    const m2 = -logT / 10 ** e2;
    return `10^(−${m2.toFixed(1).replace(".", fr ? "," : ".")}×10${sup(e2)}) K`;
  }
  if (logT >= 6 || logT < -2) {
    const e = Math.floor(logT);
    const m = 10 ** (logT - e);
    return logT >= 6 ? `${m.toFixed(1).replace(".", fr ? "," : ".")}×10${sup(e)} K` : `10${sup(e)} K`;
  }
  const T = 10 ** logT;
  return `${T.toLocaleString(fr ? "fr-FR" : "en-US", { maximumFractionDigits: T < 10 ? 2 : 0 })} K`;
}
