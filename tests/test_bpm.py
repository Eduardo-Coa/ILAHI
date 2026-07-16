"""Pruebas del campo BPM (tempo del metrónomo) en canciones."""

from __future__ import annotations

from models.song import Song, Section, Line, Syllable, Chord
from utils.song_io import song_to_dict, dict_to_song


def _sample_song_with_bpm(bpm: int | None) -> Song:
    """Crea una canción de prueba con BPM específico."""
    song = Song(id=None, title="Canción BPM", author="Autor", key="C", bpm=bpm)
    section = Section(id=None, position=0, type="verse", label="Estrofa 1")
    line = Line(id=None, position=0)
    line.syllables = [
        Syllable(id=None, position=0, text="Glo", chord=Chord(id=None, value="C")),
        Syllable(id=None, position=1, text="ria"),
    ]
    section.lines.append(line)
    song.sections.append(section)
    return song


# ============================================================================
# Tests de base de datos (round-trip BD)
# ============================================================================

def test_save_and_load_preserves_bpm(db):
    """Guardar canción con BPM y cargar preserva el valor."""
    song = _sample_song_with_bpm(95)
    sid = db.save_song(song)
    loaded = db.load_song(sid)

    assert loaded.bpm == 95


def test_save_and_load_bpm_none(db):
    """Guardar canción sin BPM (None) y cargar lo mantiene como None."""
    song = _sample_song_with_bpm(None)
    sid = db.save_song(song)
    loaded = db.load_song(sid)

    assert loaded.bpm is None


def test_bpm_in_list_songs(db):
    """El campo BPM se preserva en actualizaciones (UPDATE)."""
    song = _sample_song_with_bpm(120)
    sid = db.save_song(song)

    # Cambiar BPM y guardar de nuevo (UPDATE)
    loaded = db.load_song(sid)
    loaded.bpm = 140
    db.save_song(loaded)

    reloaded = db.load_song(sid)
    assert reloaded.bpm == 140


# ============================================================================
# Tests de serialización (round-trip song_io)
# ============================================================================

def test_song_to_dict_includes_bpm():
    """song_to_dict incluye el campo BPM."""
    song = _sample_song_with_bpm(95)
    data = song_to_dict(song)

    assert "bpm" in data
    assert data["bpm"] == 95


def test_dict_to_song_conserva_bpm():
    """dict_to_song lee y conserva el BPM."""
    original = _sample_song_with_bpm(95)
    data = song_to_dict(original)
    restored = dict_to_song(data)

    assert restored.bpm == 95


def test_dict_to_song_bpm_none():
    """dict_to_song con BPM None lo mantiene como None."""
    original = _sample_song_with_bpm(None)
    data = song_to_dict(original)
    restored = dict_to_song(data)

    assert restored.bpm is None


def test_dict_to_song_sin_clave_bpm():
    """Archivos .hymnchords antiguos sin clave 'bpm' importan sin error; BPM = None."""
    # Simular un archivo viejo que no tiene la clave "bpm"
    data = {
        "format": "hymnchords-song",
        "version": 1,
        "title": "Canción antigua",
        "author": "Autor",
        "key": "C",
        "rhythm": "4/4",
        "capo": 0,
        "notes": None,
        # Nota: falta la clave "bpm"
        "sections": [],
    }
    song = dict_to_song(data)

    assert song.bpm is None


def test_dict_to_song_bpm_invalido():
    """Un BPM no numérico se convierte a None."""
    data = {
        "format": "hymnchords-song",
        "version": 1,
        "title": "Canción",
        "author": "Autor",
        "key": "C",
        "rhythm": "4/4",
        "bpm": "no es un número",
        "capo": 0,
        "notes": None,
        "sections": [],
    }
    song = dict_to_song(data)

    assert song.bpm is None
