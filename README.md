# audio_transcriber

Librairie Python **100 % locale et hors-ligne** de transcription vocale
(`faster-whisper`) et de distinction multi-interlocuteurs (diarisation légère
stéréo et acoustique spectrale sous NumPy).

Distribuée sous licence **GNU General Public License v3.0 (GPL-3.0-or-later)**.

---

## À quoi sert cette librairie ?

- **Transcrire** des fichiers audio ou vidéo (`WAV`, `MP3`, `OGG`, `FLAC`,
  `M4A`, `MP4`, `MOV`, `MTS`, ainsi que les projets Audacity `.aup3`) sans
  cloud externe.
- **Extraire la piste audio d'une vidéo** (`extract_audio()`) avec déduction
  automatique du format de sortie (remux natif `.m4a`, `.opus`, `.mp3`,
  `.flac`, `.ogg`, `.wma` ou repli `.wav`).
- **Distinguer automatiquement les interlocuteurs** (`Interlocuteur_1`,
  `Interlocuteur_2`, etc.) et **conserver leurs profils vocaux** d'un fichier à
  l'autre via un fichier JSON local (`profiles_path`).
- **Exporter en plusieurs formats** :
  - `to_plain_text()` : texte brut ;
  - `to_timestamped_text()` : `[MM:SS] Interlocuteur_1 : ...` ;
  - `to_lrc_text()` : `[MM:SS.cc] Interlocuteur_1 : ...` (karaoké LRC) ;
  - `to_dict()` : dictionnaire structuré sérialisable en JSON.

---

## Architecture & fichiers principaux

Le package est découpé en modules spécialisés dans `src/audio_transcriber/` :

- **`__init__.py`** : point d'entrée public exposant la version dynamique
  (`__version__`) ainsi que toutes les classes, fonctions et constantes utiles.
- **`config.py` (`TranscriberConfig`)** : centralise les paramètres du modèle
  Whisper (`model_size`, `device`, `compute_type`, `language`), les seuils de
  diarisation (`max_speakers`, `similarity_threshold`) et les chemins locaux
  (`cache_dir`, `profiles_path`).
- **`engine.py` (`AudioTranscriber`)** : orchestre le chargement paresseux de
  `faster-whisper` (cache local prioritaire), la transcription progressive
  interruptible (`stop_event`, `on_segment`) et l'appel à la diarisation.
- **`audio_loader.py` (`AudioSignalLoader`)** : décode uniformément les flux
  audio en matrices NumPy `float32` 2D (`WAV` 8/16/24/32 bits, bases SQLite
  Audacity `.aup3`, et conteneurs audio/vidéo via `PyAV`).
- **`audio_extractor.py` (`extract_audio`, `infer_audio_extension`)** : sonde
  le codec interne d'une vidéo et extrait la piste audio sur disque par remux
  natif sans perte ou conversion PCM `.wav`.
- **`diarizer.py` (`SpeakerDiarizer`)** : attribue les locuteurs par énergie
  stéréo (dialogue bi-canal) ou empreinte spectrale multi-trames (mono), et
  gère la persistance atomique des profils vocaux en JSON.
- **`models.py` (`TranscriptSegment`, `TranscriptionResult`)** : structures de
  données immuables/typées portant les horodatages, les locuteurs et les
  méthodes d'export (`to_plain_text`, `to_timestamped_text`, `to_lrc_text`,
  `to_dict`).
---

## Projets consommateurs & choix techniques

`audio_transcriber` est conçue comme une brique autonome réutilisable dans
deux applications principales aux contraintes complémentaires :

- **AnonVault / Anonymizer** (dépôt GitHub `xylo2/Anonymizer`) : outil
  d'anonymisation en masse de pièces confidentielles (Windows & Linux). La
  librairie y convertit des enregistrements vocaux et projets Audacity en texte
  structuré (`to_timestamped_text()`, `to_dict()`) avant la passe de détection
  et de remplacement des données personnelles.
- **MediaReader** (dépôt GitHub `xylo2/MediaReader`) : lecteur multimédia
  multiplateforme développé en **Python Flet 1.0** pour **Android et Windows**.
  La librairie y génère des sous-titres synchronisés (`to_lrc_text()`) et des
  transcriptions consultables directement sur l'appareil.

### Justifications de l'architecture

- **100 % hors-ligne & confidentialité (`faster-whisper` local)** : indispensable
  pour AnonVault afin qu'aucune pièce sensible ne transite vers un serveur
  tiers, et pour MediaReader afin d'assurer une lecture mobile autonome sans
  connexion réseau.
- **Diarisation légère sous NumPy pur & profils JSON** : remplace les lourds
  modèles neuronaux de diarisation (PyTorch / pyannote) pour conserver un
  paquet `.whl` compact compatible mobile Android (Flet 1.0), tout en
  permettant de réutiliser les mêmes noms d'interlocuteurs sur un lot de
  fichiers via `profiles_path`.
- **Exécution non bloquante (`stop_event`, `on_segment`)** : permet l'annulation
  immédiate et l'affichage progressif des segments dans les interfaces
  graphiques (Tkinter pour AnonVault, Flet 1.0 pour MediaReader).

---

## Installation & génération du paquet (`.whl`)

Pour installer l'environnement de développement local (`venv`) :

    python -m venv .venv
    source .venv/bin/activate  # Sous Windows : .venv\Scripts\activate
    pip install -r requirements.txt

Pour générer un paquet autonome (`.whl` et `.tar.gz`) dans `dist/` et le
déployer directement dans les projets consommateurs :

    python tools/build_package.py
    python tools/build_package.py --deploy ../AnonVault ../MediaReader
---

## Exemples d'utilisation commentés

### 1. Transcription interactive, diarisation persistante et arrêt propre
**À quoi ça sert :** transcrire un enregistrement tout en affichant les phrases
au fur et à mesure dans une interface graphique (`on_segment`), pouvoir
interrompre le traitement à tout moment (`stop_event`), puis associer un nom
réel (`Alice`) à une empreinte vocale conservée dans `voices.json` pour les
fichiers suivants.

    import threading
    from audio_transcriber import AudioTranscriber, TranscriberConfig

    cfg = TranscriberConfig(model_size="base", profiles_path="voices.json")
    engine = AudioTranscriber(config=cfg)
    stop_evt = threading.Event()

    res = engine.transcribe("appel.wav", on_segment=print, stop_event=stop_evt)
    engine.diarizer.rename_speaker("Interlocuteur_1", "Alice")
    print(res.to_timestamped_text())

### 2. Extraction rapide de la piste audio d'une vidéo
**À quoi ça sert :** isoler la bande-son d'une vidéo sans ré-encodage coûteux
lorsque le codec est compatible (ex. AAC -> `.m4a` automatique), ou forcer une
conversion universelle en `.wav` pour archivage ou traitement externe.

    from audio_transcriber import extract_audio

    audio_file = extract_audio("interview.mp4")
    wav_file = extract_audio("interview.mp4", "sortie/piste.wav")

### 3. Exports multi-formats (Anonymisation, Sous-titres LRC, JSON)
**À quoi ça sert :** adapter la sortie aux besoins du logiciel consommateur :
texte brut ou horodaté `[MM:SS]` pour l'anonymisation dans **AnonVault**,
paroles synchronisées `[MM:SS.cc]` pour le lecteur **MediaReader**, ou
dictionnaire structuré pour une sauvegarde JSON.

    print(res.to_plain_text())
    print(res.to_lrc_text())
    payload = res.to_dict()

---

## Exécuter les tests unitaires

    python tools/run_tests_clip.py
    python tools/run_tests_clip.py --no-clipboard
