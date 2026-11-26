# audio_transcriber

Librairie Python **100 % locale et hors-ligne** de transcription vocale
(`faster-whisper`) et de distinction multi-interlocuteurs (diarisation légère
stéréo et acoustique spectrale sous NumPy).

Distribuée sous licence **GNU General Public License v3.0 (GPL-3.0-or-later)**.

---

## À quoi sert cette librairie ?

- **Transcrire** des fichiers audio ou vidéo (`WAV`, `MP3`, `OGG`, `FLAC`,
  `M4A`, `MP4`, ainsi que les projets Audacity `.aup3`) sans cloud externe.
- **Distinguer automatiquement les interlocuteurs** (`Interlocuteur_1`,
  `Interlocuteur_2`, etc.) par séparation des canaux stéréo ou par empreinte
  vocale acoustique sur piste mono.
- **Exporter en plusieurs formats** :
  - `to_plain_text()` : texte brut ;
  - `to_timestamped_text()` : `[MM:SS] Interlocuteur_1 : ...` ;
  - `to_lrc_text()` : `[MM:SS.cc] Interlocuteur_1 : ...` (karaoké LRC) ;
  - `to_dict()` : dictionnaire structuré sérialisable en JSON.

---

## Installation du environnement de développement (`venv`)

    python -m venv .venv
    source .venv/bin/activate  # Sous Windows : .venv\Scripts\activate
    pip install -r requirements.txt
## Exporter et installer la librairie dans un autre projet

Pour générer un paquet autonome (`.whl` et `.tar.gz`) dans le dossier `dist/` :

    python tools/build_package.py

Ensuite, depuis le `venv` de **n'importe quel autre projet** (par exemple
AnonVault ou Explorateur Audio NAS), installez le fichier `.whl` généré :

    pip install C:\git\AudioTranscriber\dist\audio_transcriber-0.1.0-py3-none-any.whl

---

## Points d'entrée principaux

- `AudioTranscriber(config=None, model_override=None)` : point d'entrée
  principal (`transcribe(file_path, stop_event=None, on_segment=None)`).
- `TranscriberConfig(...)` : paramètres du modèle (`model_size`, `device`,
  `compute_type`, `language`, `vad_filter`), de la diarisation
  (`enable_diarization`, `max_speakers`, `speaker_prefix`,
  `similarity_threshold`) et du cache local (`cache_dir`).
- `SpeakerDiarizer` : module autonome d'attribution des voix.
- `TranscriptionResult` & `TranscriptSegment` : structures de résultats et
  méthodes d'export (`to_plain_text`, `to_timestamped_text`, `to_lrc_text`,
  `to_dict`).

---

## Exécuter les tests unitaires

    # Lanceur unifié avec couverture et copie dans le presse-papiers
    python tools/run_tests_clip.py

    # Sans toucher au presse-papiers
    python tools/run_tests_clip.py --no-clipboard
