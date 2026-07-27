"""Maqueta: acordes CENTRADOS sobre su sílaba (con guion único de unión).

Compara, palabra por palabra, el algoritmo de HOY (``views.stage_view._word_col``,
importado tal cual — nada duplicado) contra una propuesta de cajas por sílaba
centradas, con UN guion (no varios) uniendo sílabas cuando el acorde de cualquiera
de las dos las separó.

Nada de esto se usa desde la app todavía: es solo para decidir si conviene portar el
reemplazo a ``views/stage_view.py`` y ``views/edit_view.py`` (ver conversación).
"""

from __future__ import annotations
import flet as ft

import theme
from models.song import Syllable, Chord
from views.widgets import logo_header

NOMBRE = "Acordes centrados (spike)"
DESCRIPCION = "Hoy (alineado a la izquierda) vs. propuesta (centrado + guion único)."


# --- Copia FIEL de views/stage_view.py (``_word_chord_lyric``/``_word_col``) --------
# No se puede importar stage_view acá: arrastra metro_sound -> click_track ->
# database.config, y la trampa del laboratorio (ver ui_lab/main.py) revienta cualquier
# import que toque ``database``, aunque sea solo por una constante de ruta. Se copian
# las dos funciones tal cual están hoy para comparar contra la propuesta.
_SLOT_LEAD = " "
_SLOT_DASH = "-"


def _hoy_word_chord_lyric(word_syllables: list[Syllable]) -> tuple[str, str]:
    chord_str = ""
    lyric_str = ""
    for syl in word_syllables:
        value = syl.chord.value if syl.chord else ""
        es_casilla = bool(value) and not syl.text.strip()
        if es_casilla:
            lyric_str += _SLOT_LEAD
        text = _SLOT_DASH if es_casilla else syl.text
        if value:
            gap = 1 if (chord_str and not chord_str.endswith(" ")) else 0
            col = max(len(lyric_str), len(chord_str) + gap)
            if col > len(lyric_str):
                lyric_str += "-" * (col - len(lyric_str))
            chord_str += " " * (col - len(chord_str))
            chord_str += value
        lyric_str += text
    return chord_str.rstrip(), lyric_str


def _hoy_word_col(word_syllables: list[Syllable], size: int, chord_size: int) -> ft.Control:
    chord_str, lyric_str = _hoy_word_chord_lyric(word_syllables)
    rows = [
        ft.Text(chord_str or " ", font_family=theme.FONT_MONO, size=chord_size,
                weight=ft.FontWeight.BOLD, color=theme.THEME["chord"], no_wrap=True),
        ft.Text(lyric_str or " ", font_family=theme.FONT_MONO, size=size,
                color=theme.THEME["text"], no_wrap=True),
    ]
    return ft.Column(rows, spacing=0, tight=True,
                     horizontal_alignment=ft.CrossAxisAlignment.START)


def _w(*pares: tuple[str, str | None]) -> list[Syllable]:
    """Atajo para armar una palabra: ``_w(("par", "G#m7"), ("tir", "C#7"))``."""
    return [Syllable(id=None, position=i, text=t,
                     chord=Chord(id=None, value=c) if c else None)
            for i, (t, c) in enumerate(pares)]


# Los mismos casos que ya probamos hablando: acorde ancho, mediano, corto, acorde
# solo en la 1ª sílaba, acorde MUY ancho, tres sílabas con acorde cada una, y una
# casilla suelta (acorde sin letra).
CASOS: list[tuple[str, list[Syllable]]] = [
    ("Acorde ancho (2 síl.)",     _w(("par", "G#m7"), ("tir", "C#7"))),
    ("Acorde mediano (2 síl.)",   _w(("par", "Bm7"), ("tir", "E7"))),
    ("Acorde corto (2 síl.)",     _w(("par", "A"), ("tir", "E"))),
    ("Acorde en 1 sola sílaba",   _w(("ho", "C"), ("la", None))),
    ("Acorde MUY ancho",          _w(("cie", "Cmaj7"), ("lo", "G"))),
    ("3 sílabas, 3 acordes",      _w(("ca", "G#m7"), ("mi", "C#7"), ("no", "F#"))),
    ("Casilla suelta (sin letra)", _w(("", "A"))),
    ("Casilla A MITAD de palabra (pujante)",
        _w(("pu", None), ("jan", "Em"), ("te", "C6"), ("", "D7"))),
]


# --- Propuesta: caja por sílaba, centrada, con guion único entre sílabas cuando --
# alguna de las dos se ensanchó por su acorde. Ancho estimado por caracteres× tamaño
# (proxy del ancho real en píxeles de una fuente monoespaciada, sin medir de verdad;
# alcanza para decidir CUÁNDO va el guion, el ancho de caja real lo pone Flet solo).
def _ancho(texto: str, size: int) -> float:
    return len(texto) * size


def _se_ensancho(value: str, texto: str, size: int, chord_size: int) -> bool:
    return bool(value) and _ancho(value, chord_size) > _ancho(texto or "", size)


def _es_casilla(syl: Syllable) -> bool:
    """Acorde suelto SIN letra (p. ej. un cambio de acorde a mitad de palabra, sin
    sílaba nueva). No lleva guion propio ni conector: queda en blanco, con el acorde
    flotando encima — el hueco de su propia caja ya separa visualmente sin necesidad
    de un guion (que además, al no tener texto, «se ensancha» siempre y disparaba un
    conector de más al lado)."""
    value = syl.chord.value if syl.chord else ""
    return bool(value) and not (syl.text or "").strip()


def _caja_silaba(syl: Syllable, size: int, chord_size: int) -> ft.Control:
    value = syl.chord.value if syl.chord else ""
    texto = " " if _es_casilla(syl) else (syl.text or "")
    return ft.Column(
        [
            ft.Text(value or " ", font_family=theme.FONT_MONO, size=chord_size,
                    weight=ft.FontWeight.BOLD, color=theme.THEME["chord"], no_wrap=True),
            ft.Text(texto or " ", font_family=theme.FONT_MONO, size=size,
                    color=theme.THEME["text"], no_wrap=True),
        ],
        spacing=0, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _guion_conector(size: int, chord_size: int) -> ft.Control:
    return ft.Column(
        [
            ft.Text(" ", size=chord_size, no_wrap=True),
            ft.Text("-", font_family=theme.FONT_MONO, size=size,
                    color=theme.THEME["text"], no_wrap=True),
        ],
        spacing=0, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _es_solo_puntuacion(syl: Syllable) -> bool:
    """Sílaba que es puro signo (":", ",", "¡", '"', etc.), sin ninguna letra."""
    t = (syl.text or "").strip()
    return bool(t) and not any(ch.isalpha() for ch in t)


def _mover_sueltos_tras_puntuacion(syls: list[Syllable]) -> list[Syllable]:
    """Un acorde suelto (casilla) justo ANTES de un signo de puntuación se corre
    para caer DESPUÉS de él: el signo cierra la frase que va antes, y el acorde
    nuevo marca el arranque de la frase que sigue — no al revés. P. ej. en
    «pujante: "Tu Dios...»: el D7 suelto es el acorde de arranque de la cita, no
    el que cierra «pujante», así que debe quedar después de los dos puntos."""
    syls = list(syls)
    i = 0
    while i < len(syls) - 1:
        if (_es_casilla(syls[i]) and syls[i + 1].chord is None
                and _es_solo_puntuacion(syls[i + 1])):
            syls[i], syls[i + 1] = syls[i + 1], syls[i]
            i += 2
        else:
            i += 1
    return syls


def _word_col_nuevo(word_syllables: list[Syllable], size: int, chord_size: int) -> ft.Control:
    celdas: list[ft.Control] = []
    n = len(word_syllables)
    for i, syl in enumerate(word_syllables):
        value = syl.chord.value if syl.chord else ""
        texto = syl.text or ""
        celdas.append(_caja_silaba(syl, size, chord_size))
        if i < n - 1:
            sig = word_syllables[i + 1]
            val_sig = sig.chord.value if sig.chord else ""
            texto_sig = sig.text or ""
            # Ninguna de las dos casillas vacías lleva conector: su propio hueco
            # (acorde flotando sobre blanco) ya hace de separador.
            if (not _es_casilla(syl) and not _es_casilla(sig)
                    and (_se_ensancho(value, texto, size, chord_size)
                         or _se_ensancho(val_sig, texto_sig, size, chord_size))):
                celdas.append(_guion_conector(size, chord_size))
    return ft.Row(celdas, spacing=0, tight=True,
                  vertical_alignment=ft.CrossAxisAlignment.START)


# --- Armado de la maqueta -------------------------------------------------------
_SIZE = 20
_CHORD_SIZE = 16


def _fila_caso(titulo: str, palabra: list[Syllable]) -> ft.Control:
    hoy = _hoy_word_col(palabra, _SIZE, _CHORD_SIZE)
    nuevo = _word_col_nuevo(palabra, _SIZE, _CHORD_SIZE)
    return ft.Container(
        padding=ft.Padding.symmetric(vertical=10, horizontal=12),
        border=ft.Border.only(bottom=ft.BorderSide(1, theme.THEME["border"])),
        content=ft.Column(spacing=6, controls=[
            ft.Text(titulo, size=11, color=theme.THEME["text_muted"]),
            ft.Row(spacing=24, controls=[
                ft.Column(spacing=2, controls=[
                    ft.Text("hoy", size=10, color=theme.THEME["danger"]),
                    ft.Container(bgcolor=theme.THEME["chord_bg"], padding=6,
                                border_radius=4, content=hoy),
                ]),
                ft.Column(spacing=2, controls=[
                    ft.Text("propuesta", size=10, color=theme.THEME["accent"]),
                    ft.Container(bgcolor=theme.THEME["chord_bg"], padding=6,
                                border_radius=4, content=nuevo),
                ]),
            ]),
        ]),
    )


def _group_words(syllables: list[Syllable]) -> list[list[Syllable]]:
    """Copia de ``views.stage_view._group_words`` (misma razón que arriba: no se
    puede importar el módulo real acá sin arrastrar la base de datos)."""
    words: list[list[Syllable]] = []
    current: list[Syllable] = []
    for syl in syllables:
        current.append(syl)
        if syl.text == "" or syl.text.endswith(" "):
            words.append(current)
            current = []
    if current:
        words.append(current)
    return words


def _hoy_line_block(syls: list[Syllable], size: int) -> ft.Control:
    chord_size = max(10, round(size * 0.8))
    cols = [_hoy_word_col(w, size, chord_size) for w in _group_words(syls)]
    return ft.Container(
        padding=ft.Padding.only(bottom=3),
        content=ft.Row(cols, wrap=True, spacing=0, run_spacing=2,
                       alignment=ft.MainAxisAlignment.CENTER,
                       vertical_alignment=ft.CrossAxisAlignment.START),
    )


def _nuevo_line_block(syls: list[Syllable], size: int) -> ft.Control:
    chord_size = max(10, round(size * 0.8))
    syls = _mover_sueltos_tras_puntuacion(syls)
    cols = [_word_col_nuevo(w, size, chord_size) for w in _group_words(syls)]
    return ft.Container(
        padding=ft.Padding.only(bottom=3),
        content=ft.Row(cols, wrap=True, spacing=0, run_spacing=2,
                       alignment=ft.MainAxisAlignment.CENTER,
                       vertical_alignment=ft.CrossAxisAlignment.START),
    )


# --- Canción real: "067 - ¡Señor, yo te conozco!" (id 111 en la base del ---------
# escritorio, Himnario Adventista), copiada UNA vez con una consulta de solo
# lectura. Es la que pediste probar: tiene mucha densidad de acordes (varias
# sílabas de 1-2 letras con acordes de 2-4), justo el caso que expone el problema.
TITULO_REAL = "067 - ¡Señor, yo te conozco!"
CANCION_REAL: list[tuple[str, list[list[tuple[str, str | None]]]]] = [
    ("Introducción", [
        [('', None), ('', None), ('', None), ('', None), ('', None)],
        [('', None), ('', None), ('', None), ('', None), ('', None)],
    ]),
    ("Estrofa 1", [
        [('¡', None), ('Se', 'G'), ('ñor', None), (', ', None), ('yo ', None), ('te ', None), ('co', 'Em'), ('noz', 'C6'), ('co', 'D7'), ('! ', None), ('La ', 'G'), ('no', 'C'), ('che ', 'G'), ('a', 'C6'), ('zul', None), (', ', None), ('se', 'D7'), ('re', 'G'), ('na', None), (',', None)],
        [('me ', None), ('di', None), ('ce ', None), ('des', None), ('de ', None), ('le', 'Em'), ('jos', 'C6'), ('', 'D7'), (': ', None), ('"', None), ('Tu ', 'G'), ('Dios ', 'C'), ('se ', 'Em'), ('es', 'Dsus4'), ('con', 'D'), ('de ', None), ('a', None), ('llí', 'G'), ('".', None)],
        [('Pe', 'Am7'), ('ro ', 'G'), ('la ', 'D'), ('no', 'G'), ('che ', 'C'), ('os', None), ('cu', 'D7'), ('ra', None), (', ', None), ('la ', 'G'), ('de ', 'Am6'), ('', 'G'), ('nu', 'D'), ('bla', 'G'), ('dos ', 'C6'), ('lle', 'D7'), ('na', None), (',', None)],
        [('me ', None), ('di', 'G'), ('ce ', None), ('más ', None), ('pu', None), ('jan', 'Em'), ('te', 'C6'), ('', 'D7'), (': ', None), ('"', None), ('Tu ', 'G'), ('Dios ', 'C'), ('se ', 'Em'), ('a', 'Dsus4'), ('cer', None), ('ca ', 'D7'), ('a ', None), ('ti', 'G'), ('".', None)],
    ]),
    ("Estrofa 2", [
        [('Te ', 'G'), ('a', None), ('cer', None), ('cas', None), (', ', None), ('sí', None), ('; ', None), ('co', None), ('noz', 'Em'), ('co ', 'C6'), ('', 'D7'), ('las ', 'G'), ('or', 'C'), ('las ', 'G'), ('de ', 'C6'), ('tu ', 'D7'), ('man', 'G'), ('to', None)],
        [('en ', None), ('e', None), ('sa ', None), ('ar', None), ('dien', None), ('te ', None), ('nu', 'Em'), ('be ', 'C6'), ('', 'D7'), ('con ', 'G'), ('que ', 'C'), ('ce', 'Em'), ('ñi', 'Dsus4'), ('do ', 'D'), ('es', None), ('tás', 'G'), (';', None)],
        [('el ', 'Am7'), ('res', 'G'), ('plan', 'D'), ('dor ', 'G'), ('co', 'C'), ('noz', 'D7'), ('co ', None), ('de ', 'G'), ('', 'Am6'), ('tu ', 'G'), ('sem', 'D'), ('blan', 'G'), ('te ', 'C6'), ('san', 'D7'), ('to', None)],
        [('cuan', None), ('do ', 'G'), ('al ', None), ('cru', None), ('zar ', None), ('el ', 'Em'), ('é', None), ('ter', 'C6'), ('', 'D7'), (', ', None), ('re', 'G'), ('lam', 'C'), ('pa', 'Em'), ('gue', 'Dsus4'), ('an', None), ('do ', 'D7'), ('vas', 'G'), ('.', None)],
    ]),
    ("Estrofa 3", [
        [('Co', 'G'), ('noz', None), ('co ', None), ('de ', None), ('tus ', None), ('pa', 'Em'), ('sos ', 'C6'), ('', 'D7'), ('las ', 'G'), ('in', 'C'), ('vi', 'G'), ('si', 'C6'), ('bles ', 'D7'), ('hue', 'G'), ('llas', None)],
        [('del ', None), ('re', None), ('pen', None), ('ti', None), ('no ', None), ('true', 'Em'), ('no ', 'C6'), ('', 'D7'), ('en ', 'G'), ('el ', 'C'), ('cru', 'Em'), ('jien', 'Dsus4'), ('te ', 'D'), ('son', 'G'), (';', None)],
        [('las ', 'Am7'), ('chis', 'G'), ('pas ', 'D'), ('de ', 'G'), ('tu ', 'C'), ('ca', 'D7'), ('rro ', None), ('co', 'G'), ('noz', 'Am6'), ('co ', 'G'), ('', 'D'), ('en ', None), ('las ', 'G'), ('cen', 'C6'), ('te', 'D7'), ('llas', None), (',', None)],
        [('tu ', None), ('a', None), ('lien', 'G'), ('to ', None), ('en ', None), ('el ', None), ('ru', 'Em'), ('gi', None), ('do ', 'C6'), ('', 'D7'), ('del ', 'G'), ('rá', 'C'), ('pi', 'Em'), ('do ', 'Dsus4'), ('a', None), ('qui', 'D7'), ('lón', 'G'), ('.', None)],
    ]),
    ("Estrofa 4", [
        [('¡', None), ('Se', 'G'), ('ñor', None), ('!, ', None), ('yo ', None), ('te ', None), ('co', 'Em'), ('noz', 'C6'), ('co', 'D7'), ('; ', None), ('mi ', 'G'), ('co', 'C'), ('ra', 'G'), ('zón ', 'C6'), ('te ', 'D7'), ('a', None), ('do', 'G'), ('ra', None), (';', None)],
        [('mi ', None), ('es', None), ('pí', None), ('ri', None), ('tu ', None), ('de ', None), ('hi', None), ('no', 'Em'), ('jos ', 'C6'), ('', 'D7'), ('an', 'G'), ('te ', 'C'), ('tus ', 'Em'), ('pies ', 'Dsus4'), ('es', 'D'), ('tá', 'G'), (';', None)],
        [('pe', 'Am7'), ('ro ', 'G'), ('mi ', 'D'), ('len', 'G'), ('gua ', 'C'), ('ca', 'D7'), ('lla', None), (', ', None), ('por', 'G'), ('que ', 'Am6'), ('', 'G'), ('mi ', 'D'), ('men', 'G'), ('te ', 'C6'), ('ig', None), ('no', 'D7'), ('ra', None)],
        [('los ', None), ('cán', 'G'), ('ti', None), ('cos ', None), ('que ', None), ('lle', 'Em'), ('gan ', 'C6'), ('', 'D7'), ('al ', 'G'), ('gran', 'C'), ('de ', 'Em'), ('Je', 'Dsus4'), ('ho', 'D7'), ('vá', 'G'), ('.', None)],
    ]),
]


def _cancion_bloques(builder) -> list[ft.Control]:
    size = theme.SIZE_STAGE
    blocks: list[ft.Control] = [
        ft.Text(TITULO_REAL, size=15, weight=ft.FontWeight.BOLD,
                color=theme.THEME["text"]),
    ]
    for label, lineas in CANCION_REAL:
        blocks.append(ft.Container(
            padding=ft.Padding.only(top=8, bottom=1),
            alignment=ft.Alignment.CENTER,
            content=ft.Text(label.upper(), size=theme.SIZE_SECTION,
                            color=theme.THEME["section_label"])))
        for pares in lineas:
            syls = [Syllable(id=None, position=i, text=t,
                             chord=Chord(id=None, value=c) if c else None)
                    for i, (t, c) in enumerate(pares)]
            if not any(s.text.strip() for s in syls):
                blocks.append(ft.Container(height=int(size * 0.3)))
                continue
            blocks.append(builder(syls, size))
    return blocks


def _panel_cancion(builder) -> ft.Control:
    return ft.Column(expand=True, spacing=0, scroll=ft.ScrollMode.AUTO,
                     controls=_cancion_bloques(builder))


# Frases COMPLETAS (línea entera, no una sola palabra): demuestran el reordenamiento
# del acorde suelto alrededor de un signo de puntuación («pujante: "Tu...» real de
# la canción, y una versión más corta con coma para el mismo patrón).
FRASES: list[tuple[str, list[tuple[str, str | None]]]] = [
    ("Acorde suelto + «:» (real, Estrofa 1)", [
        ("me ", None), ("di", "G"), ("ce ", None), ("más ", None), ("pu", None),
        ("jan", "Em"), ("te", "C6"), ("", "D7"), (": ", None), ('"', None),
        ("Tu ", "G"),
    ]),
    ("Acorde suelto + «,»", [
        ("la ", "G"), ("de ", "Am6"), ("", "G"), ("nu", "D"), ("bla", "G"),
        ("dos ", "C6"),
    ]),
]


def _fila_frase(titulo: str, pares: list[tuple[str, str | None]]) -> ft.Control:
    syls = [Syllable(id=None, position=i, text=t,
                     chord=Chord(id=None, value=c) if c else None)
            for i, (t, c) in enumerate(pares)]
    hoy = _hoy_line_block(syls, _SIZE)
    nuevo = _nuevo_line_block(syls, _SIZE)
    return ft.Container(
        padding=ft.Padding.symmetric(vertical=10, horizontal=12),
        border=ft.Border.only(bottom=ft.BorderSide(1, theme.THEME["border"])),
        content=ft.Column(spacing=6, controls=[
            ft.Text(titulo, size=11, color=theme.THEME["text_muted"]),
            ft.Text("hoy", size=10, color=theme.THEME["danger"]),
            ft.Container(bgcolor=theme.THEME["chord_bg"], padding=6,
                        border_radius=4, content=hoy),
            ft.Text("propuesta (con reordenamiento)", size=10, color=theme.THEME["accent"]),
            ft.Container(bgcolor=theme.THEME["chord_bg"], padding=6,
                        border_radius=4, content=nuevo),
        ]),
    )


def construir(page: ft.Page, db) -> ft.Control:
    filas = [_fila_caso(titulo, palabra) for titulo, palabra in CASOS]
    frases = [_fila_frase(titulo, pares) for titulo, pares in FRASES]
    casos = ft.Column(expand=True, spacing=0, scroll=ft.ScrollMode.AUTO, controls=[
        ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            content=ft.Text(
                "Frases completas: el acorde suelto que cae justo antes de un signo de "
                "puntuación se corre para sonar DESPUÉS de él (marca el arranque de la "
                "frase siguiente, no el cierre de la anterior).",
                size=11, color=theme.THEME["text_muted"]),
        ),
        *frases,
        ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            content=ft.Text(
                "Cada fila: mismo caso con el algoritmo de hoy (izquierda, alineado a "
                "la izquierda) vs. la propuesta (derecha, cajas centradas por sílaba, "
                "con un guion único de unión cuando hace falta).",
                size=11, color=theme.THEME["text_muted"]),
        ),
        *filas,
    ])
    tabs = ft.Tabs(expand=True, length=3, selected_index=0, content=ft.Column(
        expand=True, controls=[
            ft.TabBar(tabs=[
                ft.Tab(label="Casos sueltos"),
                ft.Tab(label="Hoy (canción)"),
                ft.Tab(label="Propuesta (canción)"),
            ]),
            ft.TabBarView(expand=True, controls=[
                casos,
                ft.Container(padding=12, content=_panel_cancion(_hoy_line_block)),
                ft.Container(padding=12, content=_panel_cancion(_nuevo_line_block)),
            ]),
        ]))
    return ft.Column(expand=True, spacing=0, controls=[logo_header(), tabs])
