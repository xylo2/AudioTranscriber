# Changelog

Toutes les modifications notables de `audio_transcriber` sont documentées ici.

## Version 0.2.0 (2026-11-26)

### Ajouté
- Fonction `extract_audio(video_path, output_path=None)` et méthode statique
  `AudioTranscriber.extract_audio(...)` pour dissocier et enregistrer la
  piste audio d'une vidéo sur disque.
- Fonction `infer_audio_extension(video_path, codec_name=None)` avec tables
  `CODEC_TO_EXTENSION` et `VIDEO_EXT_TO_AUDIO_EXT` (remux natif sans perte
  vers `.m4a`, `.opus`, `.mp3`, `.flac`, `.ogg`, `.wma` ou repli `.wav`).
- Exposition dynamique de `__version__` dans `audio_transcriber`.

## Version 0.1.0

### Ajouté
- Transcription vocale hors-ligne via `faster-whisper` (`AudioTranscriber`).
- Diarisation légère sous NumPy pur (stéréo + empreinte spectrale) et
  persistance JSON des profils vocaux (`SpeakerDiarizer`).
- Support audio/vidéo et projets Audacity `.aup3` (`AudioSignalLoader`).
- Exports texte brut, horodaté `[MM:SS]`, karaoké `[MM:SS.cc]` LRC et JSON.
