# -*- coding: utf-8 -*-
"""
Extraction et sauvegarde de la piste audio d'une vidéo (remux ou WAV).

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

import os
from typing import Dict, Optional
import wave
import numpy as np
from audio_transcriber.audio_loader import AudioSignalLoader

CODEC_TO_EXTENSION: Dict[str, str] = {
    "aac": ".m4a",
    "alac": ".m4a",
    "mp3": ".mp3",
    "flac": ".flac",
    "opus": ".opus",
    "vorbis": ".ogg",
    "wmav1": ".wma",
    "wmav2": ".wma",
}

VIDEO_EXT_TO_AUDIO_EXT: Dict[str, str] = {
    ".mp4": ".m4a",
    ".mov": ".m4a",
    ".3gp": ".m4a",
    ".webm": ".opus",
    ".wmv": ".wma",
}


def infer_audio_extension(
    video_path: str,
    codec_name: Optional[str] = None,
) -> str:
    """Déduit l'extension audio cible selon le codec interne ou le conteneur."""
    if codec_name:
        mapped = CODEC_TO_EXTENSION.get(codec_name.strip().lower())
        if mapped:
            return mapped
        return ".wav"
    ext: str = os.path.splitext(video_path)[-1].lower()
    return VIDEO_EXT_TO_AUDIO_EXT.get(ext, ".wav")
def _probe_audio_codec(video_path: str) -> Optional[str]:
    try:
        import av  # type: ignore[import-not-found]
    except ImportError:
        return None
    container = None
    try:
        container = av.open(video_path)
        if not container.streams.audio:
            return None
        stream = next(iter(container.streams.audio))
        codec_ctx = getattr(stream, "codec_context", None)
        return str(getattr(codec_ctx, "name", "") or "").lower() or None
    except Exception:
        return None
    finally:
        if container is not None:
            try:
                container.close()
            except Exception:
                pass


def _remux_audio_stream(video_path: str, target_path: str) -> bool:
    try:
        import av  # type: ignore[import-not-found]
    except ImportError:
        return False
    in_ctr = out_ctr = None
    try:
        in_ctr = av.open(video_path)
        if not in_ctr.streams.audio:
            return False
        in_stream = next(iter(in_ctr.streams.audio))
        out_ctr = av.open(target_path, mode="w")
        out_stream = out_ctr.add_stream_from_template(in_stream)
        for packet in in_ctr.demux(in_stream):
            if packet.dts is None:
                continue
            packet.stream = out_stream
            out_ctr.mux(packet)
        return os.path.isfile(target_path) and os.path.getsize(target_path) > 0
    except Exception:
        if os.path.isfile(target_path):
            try:
                os.remove(target_path)
            except OSError:
                pass
        return False
    finally:
        for ctr in (out_ctr, in_ctr):
            if ctr is not None:
                try:
                    ctr.close()
                except Exception:
                    pass
def _write_pcm_wav(samples: np.ndarray, sample_rate: int, target_path: str) -> str:
    if samples.size == 0 or sample_rate <= 0:
        raise ValueError("Aucune piste audio exploitable trouvée dans le média.")
    if samples.ndim == 1:
        channels: int = 1
    else:
        _, channels = samples.shape
    pcm: np.ndarray = np.clip(samples * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(target_path, "wb") as wf:
        wf.setnchannels(int(channels))
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm.tobytes())
    return os.path.abspath(target_path)


def extract_audio(
    video_path: str,
    output_path: Optional[str] = None,
) -> str:
    """Extrait la piste audio d'une vidéo vers un fichier autonome et retourne son chemin."""
    if not video_path or not os.path.isfile(video_path):
        raise FileNotFoundError(f"Fichier média introuvable : '{video_path}'")

    codec_name: Optional[str] = _probe_audio_codec(video_path)
    default_ext: str = infer_audio_extension(video_path, codec_name=codec_name)
    base_stem, _ = os.path.splitext(os.path.basename(video_path))

    if output_path and os.path.isdir(output_path):
        target: str = os.path.join(output_path, f"{base_stem}{default_ext}")
    elif output_path:
        target = output_path
    else:
        parent_dir: str = os.path.dirname(os.path.abspath(video_path))
        target = os.path.join(parent_dir, f"{base_stem}{default_ext}")

    os.makedirs(os.path.dirname(os.path.abspath(target)) or ".", exist_ok=True)
    _, ext_raw = os.path.splitext(target)
    target_ext: str = ext_raw.lower()

    if target_ext != ".wav":
        if _remux_audio_stream(video_path, target):
            return os.path.abspath(target)
        if output_path and not os.path.isdir(output_path):
            raise RuntimeError(f"Impossible d'extraire la piste vers '{target}'.")
        target_root, _ = os.path.splitext(target)
        target = f"{target_root}.wav"

    samples, sample_rate = AudioSignalLoader.load_audio(video_path)
    return _write_pcm_wav(samples, sample_rate, target)
