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
- **Distinguer automatiquement les interlocuteurs** (`Interlocuteur_1`,
  `Interlocuteur_2`, etc.) et **conserver leurs profils vocaux** d'un fichier à
  l'autre via un fichier JSON local (`profiles_path`).
- **Exporter en plusieurs formats** :
  - `to_plain_text()` : texte brut ;
  - `to_timestamped_text()` : `[MM:SS] Interlocuteur_1 : ...` ;
  - `to_lrc_text()` : `[MM:SS.cc] Interlocuteur_1 : ...` (karaoké LRC) ;
  - `to_dict()` : dictionnaire structuré sérialisable en JSON.

---

## Projets consommateurs & choix techniques

`audio_transcriber` est conçue comme une brique autonome réutilisable dans
deux applications principales aux contraintes complémentaires :

- **[AnonVault / Anonymizer](https://github.com)** : outil
  d'anonymisation en masse de pièces confidentielles (Windows & Linux). La
  librairie y convertit des enregistrements vocaux et projets Audacity en texte
  structuré (`to_timestamped_text()`, `to_dict()`) avant la passe de détection
  et de remplacement des données personnelles.
- **[MediaReader](https://github.com)** : lecteur multimédia
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

## Installation de l'environnement de développement (`venv`)

    python -m venv .venv
    source .venv/bin/activate  # Sous Windows : .venv\Scripts\activate
    pip install -r requirements.txt

## Exporter et installer la librairie dans un autre projet

Pour générer un paquet autonome (`.whl` et `.tar.gz`) dans le dossier `dist/` :

    python tools/build_package.py

Ensuite, depuis le `venv` de **n'importe quel autre projet** (par exemple
AnonVault ou MediaReader), installez le fichier `.whl` généré :

    pip install C:\git\AudioTranscriber\dist\audio_transcriber-0.1.0-py3-none-any.whl

---

## Points d'entrée principaux

- `AudioTranscriber(config=None, model_override=None)` : point d'entrée
  principal (`transcribe(file_path, stop_event=None, on_segment=None)`).
- `TranscriberConfig(...)` : paramètres du modèle (`model_size`, `device`,
  `compute_type`, `language`, `vad_filter`), de la diarisation
  (`enable_diarization`, `max_speakers`, `speaker_prefix`,
  `similarity_threshold`, `profiles_path`) et du cache local (`cache_dir`).
- `SpeakerDiarizer` : module autonome d'attribution et de persistance des voix
  (`save_profiles()`, `load_profiles()`, `rename_speaker()`, `clear_profiles()`).
- `TranscriptionResult` & `TranscriptSegment` : structures de résultats et
  méthodes d'export (`to_plain_text`, `to_timestamped_text`, `to_lrc_text`,
  `to_dict`).

---

## Exécuter les tests unitaires

    # Lanceur unifié avec couverture et copie dans le presse-papiers
    python tools/run_tests_clip.py

    # Sans toucher au presse-papiers
    python tools/run_tests_clip.py --no-clipboard
