# Instructions de génération de code (`ChromeAI` & `watch_clipboard`)

Respecte **impérativement** ces règles pour un assemblage fiable sans troncature ni blocage.

## 0. Communication & collaboration
* **Explications légères** : va directement au code ou au diagnostic court, sans théorie superflue.
* **Demande explicite** : indique clairement quand j'ai besoin de te fournir une trace, un `git diff` ou d'exécuter une commande / recharger l'extension.
* **Relecture des `git diff`** : relis systématiquement tout `git diff` fourni pour détecter toute régression ou altération avant de valider.

## 1. Format & limites des blocs
* **Balise en 1re ligne à l'intérieur du bloc** :
  * Fichier complet (≤ 65 lignes) : `=== FILE: chemin/relatif/fichier.ext ===`
  * Fichier long (> 65 lignes, `N` fixe calculé avant `1/N`) : `=== FILE_PART: chemin/relatif/fichier.ext | 1/N ===`
* **Chemins & clôture** : chemins relatifs à la racine sans préfixe ni `..` ; termine chaque livraison par `=== END_FILE ===` hors bloc.
* **Anti-virtualisation** : **≤ 65 lignes/bloc** (viser 45–62), **≤ 88 car./ligne**, **max 2 à 3 blocs/réponse** (annonce la suite et attends « Suite » si besoin).
* **Zéro ellipse** : toujours livrer le code intégral de chaque bloc (`...` ou diffs interdits). Fournis `1/N` à `N/N` à la création, puis uniquement les parties modifiées si `N` ne change pas.

## 2. Pièges d'affichage web & confidentialité
* **Triples backticks** : construis-les dynamiquement (`chr(96) * 3` en Python, `String.fromCharCode(96).repeat(3)` en JS), jamais en littéral dans le code.
* **URLs & `tools/fix_urls.py`** : concatène les URLs avec sous-domaine dans le code (`"sub." + "domain.tld"`). Le script `tools/fix_urls.py` répare les URLs tronquées par le web et purge `iaexport` / `verification_liens.txt`.
* **Crochets & LaTeX** : évite les index numériques entre crochets (préfère le déballage, `next(iter(...))` ou `.at(0)`) ainsi que `$` ou `\` non échappés.
* **Données abstraites** : aucun nom, téléphone, e-mail ou chemin réel (`Utilisateur_A`, `06 00 00 00 01`, `test1@exemple.invalid`).

## 3. Architecture, licence & qualité
* **Licence GNU GPL v3** : en-tête **GNU GPL v3** obligatoire sur chaque fichier source ; bibliothèques compatibles uniquement (MIT, BSD, Apache 2.0, stdlib) en import paresseux.
* **Modularité & typage** : modules légers (< ~250 lignes), extraction systématique des classes pertinentes dans des fichiers dédiés, typage `typing` et validation `os.path.realpath`.
* **Tests & couverture (`tools/run_tests_clip.py`)** : tout projet inclut `tools/run_tests_clip.py` (`unittest` + `tempfile.mkdtemp` / `node:test`) qui échoue sur tout warning Python, mesure la couverture (`--report-file`, `--coverage-file`) et copie les erreurs compactées au presse-papiers (`--no-clipboard` pour désactiver).
* **Langues & docstrings** : identifiants et fichiers en **anglais** ; commentaires, docstrings et commits en **français**. **Chaque méthode et fonction doit obligatoirement avoir une docstring ou un commentaire en français.**
