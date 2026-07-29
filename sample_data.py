"""Datos de ejemplo DESECHABLES para desarrollo (nunca la base real del usuario).

Construye un par de canciones y una lista (setlist) de ejemplo; se siembran en la
BD la primera vez que se abre la app, si está vacía. Sirven para ver la app leyendo
de SQLite y para tener material con acordes en la vista escenario.

Convención de espacios (igual que ``utils.lyrics_parser``): dentro de una palabra
las sílabas NO llevan espacio; la ÚLTIMA sílaba de cada palabra (salvo la última de
la línea) lleva un espacio al final. Así ``line_to_chord_lyric`` reproduce la letra
con sus espacios y alinea cada acorde sobre su sílaba.

La base de datos de desarrollo vive en una carpeta propia ('IlahiMobile'),
separada de la app de escritorio, así que sembrar aquí nunca toca datos reales.
"""

from __future__ import annotations
from models.song import Song, Section, Line, Syllable, Chord
from models.setlist import Setlist, SetlistItem

# Una "celda" es (texto_de_sílaba, acorde); acorde="" significa sin acorde.
# El espacio entre palabras va como sufijo del texto (p. ej. ("to ", "")).
Cell = tuple[str, str]


def _line(position: int, cells: list[Cell]) -> Line:
    """Construye una línea a partir de celdas (texto, acorde)."""
    syllables = [
        Syllable(
            id=None,
            position=i,
            text=text,
            chord=Chord(id=None, value=chord) if chord else None,
        )
        for i, (text, chord) in enumerate(cells)
    ]
    return Line(id=None, position=position, syllables=syllables)


def _section(position: int, type_: str, label: str | None,
             lines: list[list[Cell]]) -> Section:
    """Construye una sección con sus líneas."""
    return Section(
        id=None,
        position=position,
        type=type_,
        label=label,
        lines=[_line(i, cells) for i, cells in enumerate(lines)],
    )


def sample_songs() -> list[Song]:
    """Devuelve las canciones de ejemplo (objetos nuevos en cada llamada)."""
    cristo = Song(
        id=None,
        title="Cristo me ama",
        author="Anna B. Warner",
        key="C",
        rhythm="4/4",
        bpm=72,
        sections=[
            _section(0, "verse", "Estrofa", [
                [("Cris", "C"), ("to ", ""), ("me ", ""), ("a", "F"), ("ma ", ""),
                 ("bien ", ""), ("lo ", "G"), ("sé", "C")],
                [("La ", ""), ("Bi", "F"), ("blia ", ""), ("di", "C"), ("ce ", ""),
                 ("a", "G"), ("sí", "C")],
            ]),
            _section(1, "chorus", "Coro", [
                [("Cris", "C"), ("to ", ""), ("me ", ""), ("a", "F"), ("ma", "C")],
                [("Cris", "C"), ("to ", ""), ("me ", ""), ("a", "G"), ("ma", "C")],
            ]),
        ],
    )

    sublime = Song(
        id=None,
        title="Sublime gracia",
        author="John Newton",
        key="G",
        rhythm="3/4",
        sections=[
            _section(0, "verse", "Estrofa", [
                [("Su", ""), ("bli", "G"), ("me ", ""), ("gra", "G7"), ("cia ", ""),
                 ("del ", "C"), ("Se", "G"), ("ñor", "")],
                [("que ", ""), ("a ", ""), ("un ", "G"), ("in", ""), ("fe", "D7"),
                 ("liz ", ""), ("sal", "G"), ("vó", "")],
            ]),
        ],
    )

    return [cristo, sublime]


def sample_setlist(song_ids: list[int]) -> Setlist:
    """Lista de ejemplo con las canciones dadas y una transposición propia por lista.

    ``song_ids`` son los ids ya asignados por ``save_song``. La primera canción va en
    su tono (0) y la segunda subida +2, para demostrar la transposición por lista.
    """
    transposes = [0, 2]
    items = [
        SetlistItem(id=None, song_id=sid, position=i,
                    transpose=transposes[i % len(transposes)])
        for i, sid in enumerate(song_ids)
    ]
    return Setlist(id=None, name="Servicio domingo", items=items)
