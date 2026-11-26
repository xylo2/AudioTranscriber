# Instructions de génération de code (`audio_transcriber` & `watch_clipboard`)

Respecte **impérativement** ces règles afin que `watch_clipboard` assemble les fichiers sans troncature ni blocage.

---

## 1. Balises d'en-tête & stabilité du découpage

* **Placement obligatoire** : la balise `=== FILE: ... ===` ou `=== FILE_PART: ... ===` doit toujours être placée **à l'intérieur** du bloc de code (en première ligne juste après les trois accents graves), jamais à l'extérieur.
* **Fichier complet (≤ 65 lignes)** :
  `=== FILE: chemin/relatif/du/fichier.py ===`
* **Fichier long (> 65 lignes), découpé en `N` parties** :
  `=== FILE_PART: chemin/relatif/du/fichier.py | 1/N ===`
* Utilise uniquement des **chemins relatifs à la racine du dépôt** avec `/` (sans préfixer par le nom du dossier racine).
* **Stabilité de `N`** : calcule le nombre total `N` avant la partie `1/N` et ne le modifie jamais en cours de livraison.
* **Zéro note après un bloc** : n'écris aucun commentaire juste sous la fermeture d'un bloc de code.

---

## 2. Limites anti-virtualisation & anti-blocage

* **≤ 65 lignes par bloc** (viser 45–62 lignes) et **≤ 88 caractères par ligne**.
* **Maximum 2 à 3 blocs `FILE_PART` par réponse** pour éviter tout coupe-circuit.
* Coupe toujours proprement entre deux fonctions, méthodes ou paragraphes.
* **Zéro ellipse** : `# ... reste du code ...` ou `...` strictement interdits.

---

## 3. Vigilance d'affichage & confidentialité

* **Triples backticks** : construis-les via `chr(96) * 3` en Python plutôt qu'en littéral.
* **URLs et sous-domaines** : reconstruis dynamiquement les URLs en Python (`_u("sub", "domain.tld")`).
* **Crochets d'indexation** : préfère le déballage (`a, b = pair`) ou `next(iter(seq))` aux index `[0]`, `[1]`.
* **Confidentialité & Licence** : utilise uniquement des données abstraites (`Interlocuteur_1`, `test.wav`) et applique l'en-tête **GNU GPL v3** sur chaque fichier source.

---

## 4. Architecture, typage & tests

* Modules Python sous ~250 lignes, annotés avec `typing`.
* Dépendances légères (MIT / BSD / Apache 2.0 compatibles GNU GPL v3) avec imports paresseux.
* Couvre chaque module par des tests unitaires dans `tests/` (`unittest` + `tempfile.mkdtemp`), validés sans warning.
