"""Vista escenario (Fase 3–5): acordes en color sobre la letra, con transposición
instantánea, tamaño de fuente, navegación de lista y exportar.

Alineación por LAYOUT (no por fuente monoespaciada): cada sílaba es una caja
CENTRADA [acorde encima · sílaba debajo]; las palabras se agrupan y la línea hace
*wrap* por palabra en pantallas angostas. Así el acorde siempre queda centrado
sobre su sílaba, independientemente de la fuente, y las líneas largas no se
recortan. Cuando el acorde de una sílaba la ensancha más allá de su propia letra,
se agrega un guion de unión entre ella y la siguiente para que la palabra se siga
leyendo de corrido (ver ``_word_col``).

Reutiliza la lógica del escritorio sin cambios:
- ``transposer.display_song``: offset global + modulación por bloque (no destructivo).
"""

from __future__ import annotations
from typing import Callable
import asyncio
import time
import flet as ft

from models.song import Song, Line, Syllable
from models.transposer import display_song, semitones_between
from utils.metronome import BPM_MIN, BPM_MAX, beats_per_measure, valid_bpm
from views.metro_sound import MetroSound
from utils.song_text import SECTION_LABELS
from utils.lyrics_parser import is_chord_line
from views.widgets import (back_button, circle_button, title_block,
                           square_button, wrap_lyric_line, sheet_option,
                           _safe_update, sheet_dialog, stepper_row,
                           LYRIC_ALIGNMENTS, LYRIC_ALIGN_DEFAULT,
                           lyric_row_alignment)
import theme


_CONNECTOR = "-"    # guion de unión entre sílabas de una misma palabra (ver _word_col)


def _es_casilla(syl: Syllable) -> bool:
    """Acorde suelto SIN letra (cambio de acorde a mitad de palabra o frase, sin
    sílaba nueva). Se dibuja en blanco, con el acorde flotando encima: su propio
    hueco ya separa visualmente, sin necesidad de un guion ni de rellenar con ``-``."""
    return bool(syl.chord and syl.chord.value) and not syl.text.strip()


def _es_solo_puntuacion(syl: Syllable) -> bool:
    """Sílaba que es puro signo (":", ",", "¡", '"'…), sin ninguna letra."""
    t = syl.text.strip()
    return bool(t) and not any(ch.isalpha() for ch in t)


def _mover_sueltos_tras_puntuacion(syllables: list[Syllable]) -> list[Syllable]:
    """Un acorde suelto (``_es_casilla``) justo ANTES de un signo de puntuación se
    corre para caer DESPUÉS de él: el signo cierra la frase anterior, y el acorde
    nuevo marca el arranque de la que sigue, no el cierre de la que termina. P. ej.
    en «pujante: "Tu Dios...»: el acorde suelto es el que arranca la cita, así que
    debe quedar después de los dos puntos, no pegado a «pujante»."""
    result = list(syllables)
    i = 0
    while i < len(result) - 1:
        if (_es_casilla(result[i]) and result[i + 1].chord is None
                and _es_solo_puntuacion(result[i + 1])):
            result[i], result[i + 1] = result[i + 1], result[i]
            i += 2
        else:
            i += 1
    return result


def _ancho_estimado(texto: str, size: int) -> float:
    """Proxy (no una medida real) del ancho en píxeles de ``texto`` en una fuente
    monoespaciada al tamaño ``size``: alcanza para decidir si hace falta el guion de
    unión; el ancho real de cada caja lo resuelve Flet solo al dibujar."""
    return len(texto) * size


def _se_ensancho(syl: Syllable, size: int, chord_size: int) -> bool:
    """¿El acorde de ``syl`` es más ancho que su propia sílaba?"""
    value = syl.chord.value if syl.chord else ""
    return bool(value) and _ancho_estimado(value, chord_size) > _ancho_estimado(syl.text, size)


def _syllable_box(syl: Syllable, size: int, chord_size: int,
                  show_chord: bool, show_lyric: bool) -> ft.Control:
    """Caja de UNA sílaba: acorde CENTRADO arriba, sílaba CENTRADA abajo. El ancho de
    la caja lo decide Flet (el mayor entre los dos textos), así que un acorde ancho
    sobre una sílaba corta queda centrado sobre ella en vez de pegado a la izquierda
    (que es lo que daba la alineación por columnas de caracteres de antes)."""
    value = syl.chord.value if syl.chord else ""
    texto = " " if _es_casilla(syl) else syl.text
    rows: list[ft.Control] = []
    if show_chord:
        rows.append(ft.Text(value or " ", font_family=theme.FONT_MONO, size=chord_size,
                            weight=ft.FontWeight.BOLD, color=theme.THEME["chord"], no_wrap=True))
    if show_lyric:
        rows.append(ft.Text(texto or " ", font_family=theme.FONT_MONO, size=size,
                            color=theme.THEME["text"], no_wrap=True))
    return ft.Column(rows, spacing=0, tight=True,
                     horizontal_alignment=ft.CrossAxisAlignment.CENTER)


def _connector_box(size: int, chord_size: int,
                   show_chord: bool, show_lyric: bool) -> ft.Control:
    """Guion de unión entre dos sílabas de la misma palabra (ver ``_word_col``)."""
    rows: list[ft.Control] = []
    if show_chord:
        rows.append(ft.Text(" ", size=chord_size, no_wrap=True))
    if show_lyric:
        rows.append(ft.Text(_CONNECTOR, font_family=theme.FONT_MONO, size=size,
                            color=theme.THEME["text"], no_wrap=True))
    return ft.Column(rows, spacing=0, tight=True,
                     horizontal_alignment=ft.CrossAxisAlignment.CENTER)


def _word_col(word_syllables: list[Syllable], size: int, chord_size: int,
              show_chord: bool = True, show_lyric: bool = True) -> ft.Control:
    """Fila de una palabra: una caja centrada POR SÍLABA (acorde arriba, letra
    abajo), con un guion de unión entre dos sílabas cuando el acorde de cualquiera
    de las dos la ensanchó más allá de su propia letra (nunca al lado de una
    casilla: ver ``_es_casilla``).

    ``show_chord``/``show_lyric`` permiten omitir una fila entera cuando la línea es
    de solo acordes (sin letra) o de solo letra (sin acordes), y así no dejar filas
    en blanco que agrandan el espacio vertical."""
    celdas: list[ft.Control] = []
    n = len(word_syllables)
    for i, syl in enumerate(word_syllables):
        celdas.append(_syllable_box(syl, size, chord_size, show_chord, show_lyric))
        if i < n - 1:
            sig = word_syllables[i + 1]
            if (not _es_casilla(syl) and not _es_casilla(sig)
                    and (_se_ensancho(syl, size, chord_size)
                         or _se_ensancho(sig, size, chord_size))):
                celdas.append(_connector_box(size, chord_size, show_chord, show_lyric))
    return ft.Row(celdas, spacing=0, tight=True,
                  vertical_alignment=ft.CrossAxisAlignment.START)


def _group_words(syllables: list[Syllable]) -> list[list[Syllable]]:
    """Agrupa sílabas en palabras (se cierra al llegar a una que termina en espacio
    o es una casilla vacía), para que el *wrap* ocurra entre palabras, no dentro."""
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


def _line_block(line: Line, size: int, align: str = LYRIC_ALIGN_DEFAULT) -> ft.Control:
    """Un renglón: cada palabra es una fila de cajas [acorde / sílaba]; *wrap* por
    palabra. Antes de agrupar, los acordes sueltos que caen justo antes de un signo
    de puntuación se corren para después (ver ``_mover_sueltos_tras_puntuacion``).

    Si la línea no tiene acordes se omite la fila de acordes, y si no tiene letra se
    omite la fila de letra (evita renglones en blanco que inflan el espacio)."""
    syls = _mover_sueltos_tras_puntuacion(line.syllables)
    has_chords = any(s.chord for s in syls)
    has_lyric = any(s.text.strip() for s in syls)
    if not has_chords and not has_lyric:
        return ft.Container(height=int(size * 0.3))  # línea vacía / solo huecos: separador tenue
    chord_size = max(10, round(size * 0.8))
    cols = [_word_col(w, size, chord_size, show_chord=has_chords, show_lyric=has_lyric)
            for w in _group_words(syls)]
    return ft.Container(
        padding=ft.Padding.only(bottom=3),
        content=ft.Row(cols, wrap=True, spacing=0, run_spacing=2,
                       alignment=lyric_row_alignment(align),
                       vertical_alignment=ft.CrossAxisAlignment.START),
    )


def _intro_line_block(line: Line, size: int,
                      align: str = LYRIC_ALIGN_DEFAULT) -> ft.Control:
    """Renglón de la «Introducción»: casillas mostradas como guiones monoespaciados,
    con el acorde encima de la casilla que lo tenga (si no hay ninguno, solo guiones)."""
    has_chords = any(s.chord for s in line.syllables)
    chord_size = max(10, round(size * 0.8))
    slot_w = round(size * 2.4)
    cols: list[ft.Control] = []
    for syl in line.syllables:
        value = syl.chord.value if syl.chord else ""
        rows: list[ft.Control] = []
        if has_chords:
            rows.append(ft.Text(value or " ", font_family=theme.FONT_MONO, size=chord_size,
                                weight=ft.FontWeight.BOLD, color=theme.THEME["chord"],
                                no_wrap=True))
        rows.append(ft.Text("-", font_family=theme.FONT_MONO, size=size,
                            color=theme.THEME["text"], no_wrap=True))
        cols.append(ft.Container(width=slot_w, content=ft.Column(
            rows, spacing=0, tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER)))
    return ft.Container(
        padding=ft.Padding.only(bottom=3),
        content=ft.Row(cols, wrap=True, spacing=0, run_spacing=2,
                       alignment=lyric_row_alignment(align),
                       vertical_alignment=ft.CrossAxisAlignment.START))


# Padding lateral del cuerpo (ListView left+right) que se resta al ancho de pantalla.
_BODY_SIDE_PAD = 32


def stage_body_from(disp: Song, size: int, page_width: float | None = None,
                    align: str = LYRIC_ALIGN_DEFAULT) -> list[ft.Control]:
    """Controles del cuerpo a partir de una canción YA transpuesta (``display_song``).

    ``page_width`` (ancho de pantalla) permite partir los renglones de letra largos
    por puntuación antes de que Flet los corte a mitad de frase. ``align`` es la
    alineación de la letra elegida en el botón «Aa» (ver ``LYRIC_ALIGNMENTS``)."""
    avail = (page_width or 400) - _BODY_SIDE_PAD
    blocks: list[ft.Control] = []
    for section in disp.sections:
        label = section.label or SECTION_LABELS.get(section.type, "")
        if label:
            blocks.append(ft.Container(
                padding=ft.Padding.only(top=8, bottom=1),
                # SIEMPRE centrada, aunque la letra vaya a la izquierda: la etiqueta
                # separa bloques, no es texto que se lea de corrido.
                alignment=ft.Alignment.CENTER,
                content=ft.Text(label.upper(), size=theme.SIZE_SECTION,
                                color=theme.THEME["section_label"]),
            ))
        for line in section.lines:
            # Las casillas se dibujan como guiones con su acorde encima, estén en
            # la Introducción, en un interludio o en cualquier sección donde se
            # agreguen ([Final], [Coro]…). Lo que manda es la línea, no el tipo de
            # sección: antes se descartaban fuera de la intro y solo se veía su
            # encabezado.
            if is_chord_line(line):
                blocks.append(_intro_line_block(line, size, align))
            else:
                for part in wrap_lyric_line(line.syllables, size, avail):
                    blocks.append(_line_block(
                        Line(id=line.id, position=line.position, syllables=part),
                        size, align))
    return blocks


_circle_button = circle_button        # alias: el nombre corto ya está por todo el módulo


# Ancho del botón play (ícono 26 + padding 8×2). El «Aa» usa el mismo para alinearse.
_PLAY_WIDTH = 42
# Ancho de las casillas laterales del panel del escenario. Las dos filas usan los
# mismos anchos a izquierda y derecha, y así el centro (slider arriba, A−/nº/A+
# abajo) coincide, y el ↻ cae justo bajo el ícono de correr.
_SLOT_WIDTH = 30


def _slot(content: ft.Control, on_click=None, tooltip: str | None = None) -> ft.Control:
    """Casilla lateral de ancho fijo, opcionalmente pulsable."""
    return ft.Container(
        width=_SLOT_WIDTH, height=34, alignment=ft.Alignment.CENTER,
        ink=on_click is not None, border_radius=17,
        on_click=on_click, tooltip=tooltip, content=content)


_back_button = back_button
_title_block = title_block


def _song_meta(song: Song) -> list[str]:
    """Tono original · ritmo · capo · autor, omitiendo lo que la canción no tenga.

    El AUTOR va al final a propósito: la línea no siempre entra completa y se recorta
    por la derecha, así que adelante van los datos que hacen falta para tocar
    (original, ritmo, capo). El autor se alcanza a leer con el deslizamiento de
    ``title_block``."""
    meta: list[str] = []
    if song.original_key:
        meta.append(f"Original: {song.original_key}")
    if song.rhythm:
        meta.append(f"Ritmo: {song.rhythm}")
    if song.capo:                       # solo si usa capo (capo != 0)
        meta.append(f"Capo: T{song.capo}")
    if song.author:
        meta.append(song.author)
    return meta


class StageScreen:
    """Escenario con transposición, tamaño de fuente, navegación de lista y exportar."""

    def __init__(self, page: ft.Page, song: Song, on_back: Callable[[], None],
                 initial_offset: int = 0,
                 on_prev: Callable[[], None] | None = None,
                 on_next: Callable[[], None] | None = None,
                 position_label: str = "",
                 nav_buttons: bool = True,
                 on_edit: Callable[[int], None] | None = None,
                 on_edit_lyrics: Callable[[int], None] | None = None,
                 on_present: Callable | None = None,
                 on_persist_key: Callable | None = None,
                 on_offset_change: Callable[[int], None] | None = None,
                 size: int = theme.SIZE_STAGE,
                 on_size_change: Callable[[int], None] | None = None,
                 align: str = LYRIC_ALIGN_DEFAULT,
                 on_align_change: Callable[[str], None] | None = None) -> None:
        self.page = page
        self.song = song
        self.on_back = on_back
        self.on_prev = on_prev
        self.on_next = on_next
        self.position_label = position_label
        # ‹ Anterior / Siguiente › en píldoras. Solo dentro de una LISTA, donde el
        # orden es algo que armaste y conviene tener a mano. Recorriendo un álbum o
        # la biblioteca alcanza con arrastrar; ahí se deja únicamente el contador.
        self.nav_buttons = nav_buttons
        # Exportar vive en el menú ⋮ de la lista de canciones, no aquí.
        self.on_edit = on_edit              # abre el editor de acordes de esta canción
        self.on_edit_lyrics = on_edit_lyrics  # abre el editor de letra
        self.on_present = on_present        # abre el modo escenario (limpio + autoscroll)
        # Persistir el cambio de tono como el nuevo tono de la canción. Si se
        # provee (vista normal), transponer guarda; si no (dentro de una lista),
        # el cambio es solo visual para esa lista. Firma: (song, delta) -> Song.
        self.on_persist_key = on_persist_key
        # Dentro de una lista: guardar el desfase de tono en la COPIA de la lista
        # (no toca la canción original). Firma: (offset) -> None.
        self.on_offset_change = on_offset_change
        self.offset = initial_offset        # tono de la lista, si viene de una
        # Tamaño del texto: este es el ÚNICO lugar donde se ajusta (botón «Aa»); el
        # escenario lo hereda al abrirse. ``on_size_change`` lo persiste en las
        # preferencias (lo inyecta ``main``); sin él, el cambio dura la sesión.
        self.size = size
        self.on_size_change = on_size_change
        # Alineación de la letra: como el tamaño, se ajusta desde el «Aa» y vale para
        # TODA la app (``on_align_change`` la persiste; lo inyecta ``main``).
        self.align = align
        self.on_align_change = on_align_change
        self._swipe_dx = 0.0                # distancia acumulada del arrastre lateral
        # Los botones flotan a la derecha en columna (van en un Stack): 3 botones de
        # 60 + 2×12 de espacio + 24 de margen ≈ 228. El hueco inferior deja que la
        # última línea suba por encima de ellos y no quede tapada.
        self._body = ft.ListView(
            expand=True, spacing=2,
            padding=ft.Padding.only(left=16, right=16, top=8, bottom=228),
        )
        self._status = ft.Text("", size=12, color=theme.THEME["chord"])
        self._size_text: ft.Text | None = None    # número del cuadro «Tamaño del texto»
        # Tono: se muestra en el botón flotante y, si está abierto, en su cuadro.
        self._fab_key = ft.Text("", size=18, weight=ft.FontWeight.BOLD,
                                color=theme.THEME["chord"])
        self._tone_key: ft.Text | None = None
        self._tone_offset: ft.Text | None = None

    def build(self) -> ft.Control:
        """Barra superior + cuerpo scrollable, con «Aa» y «▶» flotando abajo.

        El cuerpo va en un ``GestureDetector`` para cambiar de canción arrastrando de
        lado (solo dentro de una lista, donde hay anterior/siguiente)."""
        self._refresh(update=False)
        cuerpo = ft.GestureDetector(
            expand=True,
            on_horizontal_drag_start=self._swipe_reset,
            on_horizontal_drag_update=self._swipe_track,
            on_horizontal_drag_end=self._on_swipe, content=self._body)
        column = ft.Column(
            [self._top_bar(), ft.Container(height=6), cuerpo],
            expand=True, spacing=0,
        )
        return ft.Stack(expand=True, controls=[column, self._fabs()])

    def _swipe_reset(self, _e=None) -> None:
        self._swipe_dx = 0.0

    def _swipe_track(self, e) -> None:
        self._swipe_dx += getattr(e, "primary_delta", None) or 0

    def _on_swipe(self, _e=None) -> None:
        """Arrastre lateral (en una lista, por distancia): izquierda → siguiente,
        derecha → anterior."""
        dx, self._swipe_dx = self._swipe_dx, 0.0
        if dx < -_SWIPE_MIN and self.on_next is not None:
            self.on_next()
        elif dx > _SWIPE_MIN and self.on_prev is not None:
            self.on_prev()

    # ------------------------------------------------------------------
    # Botones flotantes: «Aa» (tamaño del texto) y «▶» (modo escenario)
    # ------------------------------------------------------------------
    def _fab(self, content: ft.Control, tooltip: str, on_click,
             bgcolor: str | None = None, border: str | None = None) -> ft.Control:
        """Botón flotante cuadrado de esquinas redondeadas."""
        return ft.Container(
            width=60, height=60, border_radius=18, ink=True,
            bgcolor=bgcolor or theme.THEME["surface2"],
            border=ft.Border.all(1, border or theme.THEME["border"]),
            alignment=ft.Alignment.CENTER, tooltip=tooltip,
            on_click=on_click, content=content)

    def _fabs(self) -> ft.Control:
        """Columna vertical a la derecha: Tono · Fuente · Escenario (editar va arriba)."""
        botones: list[ft.Control] = [
            self._fab(
                ft.Column([self._fab_key,
                           ft.Text("Tono", size=8, color=theme.THEME["text_muted"])],
                          spacing=0, tight=True,
                          alignment=ft.MainAxisAlignment.CENTER,
                          horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                "Cambiar el tono", lambda _e: self._open_tone_sheet(),
                bgcolor=theme.THEME["chord_bg"], border=theme.THEME["chord"]),
            self._fab(
                ft.Text("Aa", size=20, weight=ft.FontWeight.BOLD,
                        color=theme.THEME["text"]),
                "Tamaño del texto", lambda _e: self._open_font_sheet()),
        ]
        if self.on_present is not None:
            botones.append(self._fab(
                ft.Icon(ft.Icons.PLAY_ARROW, size=30, color=theme.THEME["bg"]),
                "Modo escenario",
                # Se le pasa el tamaño actual: el escenario hereda la fuente de aquí.
                lambda _e: self.on_present(self.song, self.offset, self.size),
                bgcolor=theme.THEME["accent"], border=theme.THEME["accent"]))
        return ft.Container(
            right=16, bottom=24,
            content=ft.Column(botones, spacing=12, tight=True,
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER))

    def _open_edit_sheet(self) -> None:
        """Menú «Editar»: elegir entre editar la letra o los acordes."""
        def choose(fn):
            self.page.pop_dialog()
            if fn is not None:
                fn(self.song.id)

        opciones: list[ft.Control] = []
        if self.on_edit_lyrics is not None:
            opciones.append(sheet_option(
                ft.Icons.LYRICS, "Editar letra",
                "Cambiar el texto de la canción",
                lambda _e: choose(self.on_edit_lyrics)))
        if self.on_edit is not None:
            opciones.append(sheet_option(
                ft.Icons.MUSIC_NOTE, "Editar acordes",
                "Asignar acordes a las sílabas",
                lambda _e: choose(self.on_edit)))
        dialog = sheet_dialog(
            ft.Column(tight=True, spacing=2, controls=opciones),
            title="Editar",
            content_padding=ft.Padding.only(left=8, right=8, bottom=8),
        )
        self.page.show_dialog(dialog)

    def _open_font_sheet(self) -> None:
        """Cuadro del «Aa»: tamaño del texto (A− · número · A+ · Restablecer) y
        alineación de la letra. Las dos cosas son de la APP, no de la canción."""
        self._size_text = ft.Text(str(self.size), size=26, weight=ft.FontWeight.BOLD,
                                  color=theme.THEME["text"])
        dialog = sheet_dialog(
            content_padding=ft.Padding.only(left=16, right=16, top=8, bottom=8),
            content=ft.Column(tight=True, spacing=10,
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                              controls=[
                ft.Text("Tamaño del texto", size=16, color=theme.THEME["text"]),
                stepper_row("A−", lambda _e: self._resize(-2), self._size_text,
                            "A+", lambda _e: self._resize(2)),
                ft.TextButton("Restablecer", on_click=lambda _e: self._reset_size()),
                ft.Container(height=1, bgcolor=theme.THEME["border"]),
                ft.Text("Alineación de la letra", size=16, color=theme.THEME["text"]),
                ft.Row(spacing=10, controls=[self._align_pill(clave)
                                             for clave in LYRIC_ALIGNMENTS]),
                ft.Text("Se aplica a todas las canciones", size=11,
                        color=theme.THEME["text_muted"]),
            ]),
        )
        self.page.show_dialog(dialog)

    def _align_pill(self, clave: str) -> ft.Control:
        """Una opción de alineación; la activa va con el color del acorde."""
        etiqueta, icono = LYRIC_ALIGNMENTS[clave]
        activa = self.align == clave
        color = theme.THEME["chord"] if activa else theme.THEME["text_muted"]
        return ft.Container(
            expand=True, ink=True, border_radius=14, height=44,
            alignment=ft.Alignment.CENTER,
            on_click=lambda _e, c=clave: self._set_align(c),
            bgcolor=theme.THEME["chord_bg"] if activa else theme.THEME["surface"],
            border=ft.Border.all(
                1, theme.THEME["chord"] if activa else theme.THEME["border"]),
            content=ft.Row(tight=True, spacing=6,
                           alignment=ft.MainAxisAlignment.CENTER, controls=[
                ft.Icon(icono, size=18, color=color),
                ft.Text(etiqueta, size=13,
                        color=color if activa else theme.THEME["text"]),
            ]))

    def _set_align(self, clave: str) -> None:
        """Cambia la alineación, la persiste y repinta la letra."""
        self.align = clave
        if self.on_align_change is not None:
            self.on_align_change(clave)      # queda guardada para toda la app
        self.page.pop_dialog()
        self._refresh()

    def _refresh(self, update: bool = True) -> None:
        """Recalcula la canción mostrada al offset actual y repinta el cuerpo."""
        disp = display_song(self.song, self.offset)
        self._body.controls = stage_body_from(disp, self.size, self.page.width, self.align)
        clave = disp.key or "—"
        self._fab_key.value = clave
        if self._tone_key is not None:
            self._tone_key.value = clave
        if self._tone_offset is not None:
            self._tone_offset.value = f"{self.offset:+d}".replace("+0", "0")
        if update:
            _safe_update(self.page)

    def _persists_key(self) -> bool:
        """En la vista normal el cambio de tono se guarda; en una lista es visual."""
        return self.on_persist_key is not None

    def _transpose(self, delta: int) -> None:
        if self._persists_key():
            self.song = self.on_persist_key(self.song, delta)   # transpone y guarda
            self._refresh()
        else:
            self.offset += delta
            self._refresh()
            if self.on_offset_change is not None:
                self.on_offset_change(self.offset)   # guarda el tono en la copia de la lista

    def _reset_tone(self) -> None:
        # Persistiendo: «Restablecer» vuelve al tono original registrado.
        if self._persists_key():
            delta = semitones_between(self.song.key, self.song.original_key)
            if delta:
                self.song = self.on_persist_key(self.song, delta)
                self._refresh()
            return
        self.offset = 0
        self._refresh()
        if self.on_offset_change is not None:
            self.on_offset_change(0)                 # el tono de la copia vuelve a 0

    def _open_tone_sheet(self) -> None:
        """Cuadro «Tono»: − · tono actual · +. En una lista muestra el desfase."""
        persiste = self._persists_key()
        clave = display_song(self.song, self.offset).key or "—"
        self._tone_key = ft.Text(clave, size=26, weight=ft.FontWeight.BOLD,
                                 color=theme.THEME["chord"])
        centro: list[ft.Control] = [self._tone_key]
        if not persiste:
            # En una lista el cambio es visual: se muestra cuánto se subió/bajó.
            self._tone_offset = ft.Text(f"{self.offset:+d}".replace("+0", "0"),
                                        size=12, color=theme.THEME["text_muted"])
            centro.append(self._tone_offset)
        else:
            self._tone_offset = None

        controles: list[ft.Control] = [
            ft.Text("Tono", size=16, color=theme.THEME["text"]),
            stepper_row("−", lambda _e: self._transpose(-1),
                        ft.Column(centro, spacing=0, tight=True,
                                  horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        "+", lambda _e: self._transpose(1)),
        ]
        # «Restablecer» solo tiene sentido si hay a dónde volver: en una lista, al
        # tono de la lista; persistiendo, al tono original (si está registrado).
        if not persiste or self.song.original_key:
            etiqueta = "Al tono original" if persiste else "Restablecer"
            controles.append(ft.TextButton(etiqueta,
                                           on_click=lambda _e: self._reset_tone()))

        dialog = sheet_dialog(
            ft.Column(controles, tight=True, spacing=10,
                      horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            content_padding=ft.Padding.only(left=16, right=16, top=8, bottom=8),
        )
        self.page.show_dialog(dialog)

    def _resize(self, delta: int) -> None:
        self._set_size(self.size + delta)

    def _reset_size(self) -> None:
        self._set_size(theme.SIZE_STAGE)

    def _set_size(self, value: int) -> None:
        self.size = max(12, min(48, value))
        if self._size_text is not None:
            self._size_text.value = str(self.size)
            _safe_update(self._size_text)
        self._refresh()
        if self.on_size_change is not None:
            self.on_size_change(self.size)     # lo guarda en preferencias

    def _nav_pill(self, text: str, cb, enabled: bool) -> ft.Control:
        """‹ Anterior / Siguiente › encerrado en una píldora (como «+ Puente»)."""
        color = theme.THEME["chord"] if enabled else theme.THEME["text_muted"]
        return ft.Container(
            ink=enabled, border_radius=16,
            on_click=(lambda _e: cb()) if enabled else None,
            padding=ft.Padding.symmetric(horizontal=14, vertical=7),
            bgcolor=theme.THEME["surface2"],
            border=ft.Border.all(1, theme.THEME["border"]),
            content=ft.Text(text, size=13, color=color))

    def _nav_row(self) -> ft.Control:
        """Posición dentro del recorrido («2/500»), con las píldoras ‹/› solo si esta
        vista las lleva (``nav_buttons``); si no, queda el contador solo."""
        controls: list[ft.Control] = [
            ft.Text(self.position_label, size=12, color=theme.THEME["text_muted"]),
        ]
        if self.nav_buttons:
            controls = [
                self._nav_pill("‹ Anterior", self.on_prev, self.on_prev is not None),
                controls[0],
                self._nav_pill("Siguiente ›", self.on_next, self.on_next is not None),
            ]
        return ft.Row(
            alignment=ft.MainAxisAlignment.CENTER, spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=controls,
        )

    def _top_bar(self) -> ft.Control:
        meta = _song_meta(self.song)
        # ← a la izquierda y ✎ a la derecha; ambos ocupan 44 px, así el título
        # queda centrado (el ✎ hace de par simétrico del ←).
        puede_editar = self.on_edit is not None or self.on_edit_lyrics is not None
        derecha = (square_button(ft.Icons.EDIT, "Editar",
                                 lambda: self._open_edit_sheet())
                   if puede_editar else ft.Container(width=44))
        row1 = ft.Row(
            [
                _back_button(self.on_back),
                ft.Column(_title_block(self.song.title, meta, self.page),
                          spacing=0, tight=True, expand=True,
                          horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                derecha,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        # Tono, fuente, editar y escenario viven en los botones flotantes.
        rows: list[ft.Control] = [row1]
        # La fila aparece si hay algo que mostrar: las píldoras, o —cuando están
        # apagadas— el contador de posición.
        if self.on_prev is not None or self.on_next is not None or self.position_label:
            rows.append(self._nav_row())
        rows.append(self._status)
        return ft.Container(
            # Panel superior: fondo propio y esquinas inferiores redondeadas.
            bgcolor=theme.THEME["surface"],
            border_radius=ft.BorderRadius.only(bottom_left=18, bottom_right=18),
            padding=ft.Padding.only(left=8, right=8, top=8, bottom=10),
            content=ft.Column(rows, spacing=4,
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )


def _stage_bg() -> str:
    """Fondo del modo escenario: negro puro en temas oscuros (menos brillo y más
    contraste en tarima); en temas claros se usa el fondo del tema (el texto del
    tema es oscuro y sobre negro sería ilegible)."""
    return "#000000" if theme.is_dark() else theme.THEME["bg"]

# Distancia mínima (px) de un arrastre lateral para cambiar de canción. Se mide por
# distancia, no por velocidad, para que funcione también con un arrastre lento.
_SWIPE_MIN = 55

# Alto FIJO del panel del título en el modo escenario. El header flota sobre el
# cuerpo (va en un Stack) y el cuerpo reserva exactamente este alto con el padding
# superior de su ListView. Al ser el mismo número, el título cae justo sobre ese
# espacio; y como ocultarlo no cambia el tamaño del cuerpo, la letra no se mueve
# ni brinca al mostrar/ocultar el título. Da para título + autor/tono + posición
# («2 de 5») sin apretarse.
_HEADER_H = 76

# Alto FIJO del panel de control inferior, con el mismo criterio que _HEADER_H:
# flota sobre el cuerpo y este reserva su alto con el padding inferior. Tiene dos
# valores porque el panel crece una fila cuando la canción trae metrónomo.
_PANEL_H = 60          # solo la fila de velocidad (play + slider)
_PANEL_H_METRO = 100   # velocidad + metrónomo
_PANEL_MARGIN = 10     # margen inferior del panel (ver _panel)

# Autoscroll. La velocidad se mide en **píxeles por segundo**.
#
# El deslizamiento es UNA sola animación nativa hasta el final (``_launch_glide``):
# Flutter la corre entera del lado de Dart, suave y sin que Python toque el scroll por
# el camino. La versión anterior empujaba el scroll cada 100 ms con un ``scroll_to``
# animado; encadenar animaciones cortas con su easing hacía un pulso en cada costura
# (~10 por segundo) que en el teléfono se veía entrecortado —peor a alta velocidad y
# apenas perceptible a la mínima—. La curva LINEAL (sin easing) es lo que la hace
# pareja de punta a punta.
#
# Un bucle liviano (``_autoscroll``) SUPERVISA, no anima: casi siempre solo duerme;
# relanza la animación cuando cambió algo (velocidad, o el usuario arrastró y su turno
# caducó) y la detiene al llegar al final.
_TICK = 0.1                  # segundos entre chequeos del supervisor
_SPEED_MIN = 4.0             # px/s: apenas se mueve
_SPEED_MAX = 90.0            # px/s
_SPEED_DEFAULT = 18.0

# Cuánto sigue mandando el usuario tras su último movimiento. El turno CADUCA solo:
# cada movimiento suyo lo renueva, y si deja de mover, el autoscroll retoma. Así el
# mecanismo no depende de recibir un evento final (que el límite de ``scroll_interval``
# puede descartar) y es imposible que el autoscroll se quede colgado cediendo.
# Debe superar con holgura el intervalo entre eventos de scroll (50 ms).
_USER_GRACE = 0.25           # segundos


class PresentScreen:
    """Modo escenario: SOLO la canción (limpio, sin barra de herramientas), con
    **autoscroll** (play/pausa + velocidad) y el metrónomo si la canción trae BPM.

    El tamaño del texto y la alineación de la letra se heredan de la vista de canción
    (``size`` y ``align``, los dos del botón «Aa»): aquí no se editan, para tener un
    solo lugar donde se ajustan.

    En temas oscuros el fondo es **negro puro** (no el del tema); en claros, el
    fondo del tema (ver ``_stage_bg``)."""

    def __init__(self, page: ft.Page, song: Song, offset: int,
                 on_exit: Callable[[], None],
                 on_prev: Callable[[], None] | None = None,
                 on_next: Callable[[], None] | None = None,
                 position_label: str = "",
                 nav_buttons: bool = True,
                 size: int = theme.SIZE_STAGE,
                 align: str = LYRIC_ALIGN_DEFAULT) -> None:
        self.page = page
        self.song = song
        self.align = align            # alineación de la letra, heredada del «Aa»
        self.offset = offset          # tono con el que se venía viendo
        self.on_exit = on_exit
        self.on_prev = on_prev        # canción anterior de la lista (None en la 1ª)
        self.on_next = on_next        # canción siguiente de la lista (None en la última)
        self.position_label = position_label
        # Flechas ‹ › a los lados del título: solo dentro de una LISTA. En un álbum o
        # en la biblioteca se pasa de canción arrastrando, y queda solo el contador.
        self.nav_buttons = nav_buttons
        self._chrome_visible = True   # header + panel se ocultan/muestran al tocar
        self._header_box: ft.Control | None = None
        self._panel_box: ft.Control | None = None
        self._swipe_dx = 0.0          # distancia acumulada del arrastre lateral
        # Tamaño heredado de la vista de canción (su botón «Aa»): aquí no se edita.
        self.size = size
        self._speed = _SPEED_DEFAULT  # píxeles por segundo
        self._playing = False
        self._running = False         # evita lanzar dos supervisores a la vez
        self._needs_restart = False   # relanzar la animación (velocidad nueva o tras arrastrar)
        self._pixels = 0.0            # posición real del scroll (la reporta on_scroll)
        self._user_hold = 0.0         # hasta cuándo manda el usuario (ver _user_moving)
        self._max_extent: float | None = None   # None = aún no la sabemos
        # Metrónomo: solo existe si la canción trae un BPM válido. Sin BPM, ningún
        # atributo de metrónomo se crea (renderizado condicional real, no disabled).
        # Se resuelve ANTES del cuerpo porque el alto del panel (y por tanto el
        # espacio que el cuerpo le reserva abajo) depende de si lleva metrónomo.
        self._bpm = valid_bpm(song.bpm)
        self._metro_toggle: ft.Control | None = None   # casilla ▶/■ del panel
        # El título y el panel FLOTAN sobre el cuerpo; este reserva el alto de cada
        # uno con su padding. Así ocultarlos no redimensiona el cuerpo (la letra no
        # brinca) y, en pantalla completa, la última línea puede subir por encima de
        # donde vive el panel en vez de quedar pegada al borde.
        self._body = ft.ListView(
            expand=True, spacing=2, on_scroll=self._on_scroll, scroll_interval=50,
            padding=ft.Padding.only(left=16, right=16, top=_HEADER_H + 6,
                                    bottom=self._panel_space() + 6))
        self._play_box = ft.Container(
            content=self._play_icon(), on_click=self._toggle_play,
            ink=True, padding=8, border_radius=20)
        if self._bpm is not None:
            # El SONIDO lo lleva el motor de audio en bucle (no se dispara un click
            # por golpe: eso iba a destiempo). No hay indicador que late: un pulso en
            # pantalla corre con el reloj del sistema, el audio con el del hardware, y
            # sin nada que los re-sincronice el desfase crecía hasta notarse. El acento
            # va en el propio audio (golpe 1 seco y fuerte; ver utils/click_track.py).
            self._beats = beats_per_measure(song.rhythm)
            self._metro_sound = MetroSound(page)   # bucle (no-op sin flet-audio)
            self._metro_on = False
            self._metro_text = ft.Text(str(self._bpm), size=15,
                                       weight=ft.FontWeight.BOLD, color=theme.THEME["text"])

    def _panel_h(self) -> int:
        """Alto fijo del panel inferior; crece una fila si hay metrónomo."""
        return _PANEL_H_METRO if self._bpm is not None else _PANEL_H

    def _panel_space(self) -> int:
        """Espacio que el cuerpo reserva abajo: el panel más su margen."""
        return self._panel_h() + _PANEL_MARGIN

    def _play_icon(self) -> ft.Control:
        """Ícono Material (el glifo ▶ se pintaba como emoji naranja en Android)."""
        return ft.Icon(ft.Icons.PAUSE if self._playing else ft.Icons.PLAY_ARROW,
                       size=26, color=theme.THEME["text"])

    def build(self) -> ft.Control:
        self._refresh()
        self.page.bgcolor = _stage_bg()        # se restaura al salir (_exit)
        _safe_update(self.page)
        self._header_box = self._header()
        self._panel_box = self._panel()
        # Tocar la canción oculta/muestra el header y el panel (pantalla completa solo
        # letra); arrastrar de lado cambia de canción.
        cuerpo = ft.GestureDetector(
            expand=True, on_tap=self._toggle_panel,
            on_horizontal_drag_start=self._swipe_reset,
            on_horizontal_drag_update=self._swipe_track,
            on_horizontal_drag_end=self._on_swipe, content=self._body)
        # Título y panel FLOTAN sobre el cuerpo (Stack) en vez de empujarlo: el
        # cuerpo ocupa toda la pantalla y ya reserva el alto de ambos con su padding.
        # Así, mostrarlos u ocultarlos NO lo redimensiona y la letra se queda quieta.
        return ft.Stack(expand=True, controls=[
            cuerpo,
            ft.Container(top=0, left=0, right=0, content=self._header_box),
            ft.Container(bottom=0, left=0, right=0, content=self._panel_box),
        ])

    def _nav_button(self, icon: str, cb, show: bool) -> ft.Control:
        """Botón circular ‹/› para cambiar de canción; con estilo propio (verde), no se
        confunde con «volver». Si no aplica (extremo de la lista), deja un hueco para
        que el título siga centrado."""
        if not show:
            return ft.Container(width=44)
        return ft.Container(
            width=44, height=44, border_radius=22, ink=True,
            bgcolor=theme.THEME["chord_bg"],
            border=ft.Border.all(1, theme.THEME["chord"]),
            alignment=ft.Alignment.CENTER, on_click=cb,
            content=ft.Icon(icon, size=26, color=theme.THEME["chord"]))

    def _go_prev(self) -> None:
        """Detiene el metrónomo (si lo hay) antes de cambiar de canción."""
        if self._bpm is not None:
            self._detener_metro()
        if self.on_prev is not None:
            self.on_prev()

    def _go_next(self) -> None:
        """Detiene el metrónomo (si lo hay) antes de cambiar de canción."""
        if self._bpm is not None:
            self._detener_metro()
        if self.on_next is not None:
            self.on_next()

    def _header(self) -> ft.Control:
        """Título centrado con ‹ anterior / siguiente › a los lados (solo en una lista;
        ver ``nav_buttons``). Sin las flechas, el título ocupa todo el ancho y la
        posición queda bajo él."""
        if self.nav_buttons:
            prev = self._nav_button(
                ft.Icons.CHEVRON_LEFT, lambda _e: self._go_prev(),
                self.on_prev is not None)
            nxt = self._nav_button(
                ft.Icons.CHEVRON_RIGHT, lambda _e: self._go_next(),
                self.on_next is not None)
        else:
            prev = nxt = ft.Container(width=0)
        titulo = _title_block(self.song.title, _song_meta(self.song), self.page)
        if self.position_label:
            titulo = titulo + [ft.Text(self.position_label, size=11,
                                       color=theme.THEME["text_muted"])]
        col = ft.Column(titulo, spacing=0, tight=True, expand=True,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        return ft.Container(
            # Panel superior con esquinas inferiores redondeadas, como el resto.
            # Alto FIJO (_HEADER_H): es el espacio que el cuerpo reserva arriba.
            height=_HEADER_H,
            bgcolor=theme.THEME["surface"],
            border_radius=ft.BorderRadius.only(bottom_left=18, bottom_right=18),
            padding=ft.Padding.only(left=12, right=12, top=8, bottom=8),
            content=ft.Row([prev, col, nxt],
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    def _toggle_panel(self, _e=None) -> None:
        # Oculta/muestra título y panel a la vez (pantalla completa con solo letra y
        # acordes). Ambos flotan, así que esto NO redimensiona el cuerpo: su espacio
        # ya está reservado y la letra no se mueve.
        self._chrome_visible = not self._chrome_visible
        # Solo se cambia la visibilidad: NUNCA se toca el scroll. Tocar la pantalla
        # no debe mover la letra. (Hubo aquí un «reanclado» que forzaba el scroll a
        # self._pixels tras el toggle; hacía falta cuando el chrome vivía en la
        # Column y ocultarlo redimensionaba el cuerpo. Con el chrome flotando ya no
        # hay re-layout, y además corría la pantalla: _pixels llega con retraso
        # —on_scroll está limitado a 50 ms— así que al tocar durante la inercia
        # devolvía la letra a una posición vieja.)
        for box in (self._header_box, self._panel_box):
            if box is not None:
                box.visible = self._chrome_visible
                _safe_update(box)
        # El toque que llegó hasta aquí YA canceló la animación nativa del autoscroll:
        # Flutter frena cualquier animación de scroll en cuanto un dedo toca la lista.
        # Y este caso no lo cubre ``_on_scroll``, que solo marca el relanzado ante un
        # ARRASTRE (movimiento con el turno del usuario abierto, o un evento USER con
        # dirección); un toque simple no mueve la lista ni trae dirección, así que sin
        # esto el supervisor se quedaba durmiendo y la letra congelada con el ícono en
        # ⏸. Aquí sabemos con certeza que hubo un toque: se pide relanzar.
        if self._playing:
            self._needs_restart = True

    def _swipe_reset(self, _e=None) -> None:
        self._swipe_dx = 0.0

    def _swipe_track(self, e) -> None:
        self._swipe_dx += getattr(e, "primary_delta", None) or 0

    def _on_swipe(self, _e=None) -> None:
        """Arrastre lateral (por distancia, funciona con arrastre lento): izquierda →
        siguiente, derecha → anterior."""
        dx, self._swipe_dx = self._swipe_dx, 0.0
        if dx < -_SWIPE_MIN and self.on_next is not None:
            self._go_next()
        elif dx > _SWIPE_MIN and self.on_prev is not None:
            self._go_prev()

    def _panel(self) -> ft.Control:
        """Panel fijo con la velocidad del autoscroll (y el metrónomo si la canción
        trae BPM); la ✕ sale del escenario.

        El tamaño del texto NO se edita aquí: se hereda de la vista de canción (su
        botón «Aa»), que lo pasa al abrir el escenario. Así hay un solo lugar donde
        se ajusta la fuente."""
        muted = theme.THEME["text_muted"]
        texto = theme.THEME["text"]
        # Tortuga/liebre no existen en Material: caminar y correr dicen lo mismo.
        velocidad = ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6, controls=[
                self._play_box,
                _slot(ft.Icon(ft.Icons.DIRECTIONS_WALK, size=18, color=muted)),
                ft.Slider(min=_SPEED_MIN, max=_SPEED_MAX, value=self._speed,
                          expand=True, on_change=self._on_speed),
                _slot(ft.Icon(ft.Icons.DIRECTIONS_RUN, size=18, color=muted)),
            ])
        filas: list[ft.Control] = [velocidad]
        if self._bpm is not None:
            self._metro_toggle = _slot(self._metro_icon(self._metro_on),
                                       on_click=self._toggle_metro,
                                       tooltip="Metrónomo")
            metronomo = ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6, controls=[
                    # Ícono Material, no el glifo «♩»: la fuente de Android no lo
                    # trae y lo pintaba como una «J» (igual que pasó con el ▶).
                    ft.Container(width=_PLAY_WIDTH, alignment=ft.Alignment.CENTER,
                                 content=ft.Icon(ft.Icons.MUSIC_NOTE, size=20,
                                                 color=texto)),
                    _slot(ft.Container(width=1, height=20, bgcolor=theme.THEME["border"])),
                    ft.Row(expand=True, alignment=ft.MainAxisAlignment.CENTER, spacing=10,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                               _circle_button("−", lambda _e: self._adjust_metro_bpm(-5),
                                              diameter=40, bgcolor=theme.THEME["surface2"]),
                               self._metro_text,
                               _circle_button("+", lambda _e: self._adjust_metro_bpm(5),
                                              diameter=40, bgcolor=theme.THEME["surface2"]),
                           ]),
                    self._metro_toggle,
                ])
            filas.append(metronomo)
        return ft.Container(
            visible=self._chrome_visible,      # se oculta/muestra al tocar la pantalla
            # Alto FIJO (_panel_h): es el espacio que el cuerpo reserva abajo.
            height=self._panel_h(),
            margin=ft.Margin.only(left=10, right=10, bottom=_PANEL_MARGIN),
            padding=ft.Padding.only(left=8, right=4, top=4, bottom=4),
            bgcolor=theme.THEME["surface"], border_radius=24,
            border=ft.Border.all(1, theme.THEME["border"]),
            content=ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=4, controls=[
                    ft.Column(filas, spacing=0, tight=True, expand=True),
                    # El divisor acompaña al alto real del panel: una fila (solo
                    # velocidad) o dos (con metrónomo).
                    ft.Container(width=1, height=64 if len(filas) > 1 else 40,
                                 bgcolor=theme.THEME["border"]),
                    ft.IconButton(ft.Icons.CLOSE, icon_size=22, icon_color=muted,
                                  tooltip="Salir del escenario",
                                  on_click=lambda _e: self._exit()),
                ]),
        )

    def _refresh(self) -> None:
        disp = display_song(self.song, self.offset)
        self._body.controls = stage_body_from(disp, self.size, self.page.width, self.align)
        _safe_update(self._body)

    # ------------------------------------------------------------------
    # Metrónomo (solo si la canción trae BPM válido; ver ``self._bpm``)
    # ------------------------------------------------------------------
    def _metro_icon(self, running: bool) -> ft.Control:
        """Ícono de la casilla ▶/■: sonando muestra detener, detenido muestra play."""
        return ft.Icon(ft.Icons.STOP if running else ft.Icons.PLAY_ARROW, size=18,
                       color=theme.THEME["text"] if running else theme.THEME["text_muted"])

    def _detener_metro(self) -> None:
        """Detiene el metrónomo: el sonido y la bandera. Se usa al apagar el toggle
        y al salir o cambiar de canción."""
        self._metro_on = False
        self._metro_sound.stop()

    def _toggle_metro(self, _e=None) -> None:
        """Arranca o detiene el bucle del compás."""
        if self._bpm is None:
            return
        self._metro_on = not self._metro_on
        if self._metro_on:
            self._metro_sound.start(self._bpm, self._beats)
        else:
            self._detener_metro()
        if self._metro_toggle is not None:
            self._metro_toggle.content = self._metro_icon(self._metro_on)
            _safe_update(self._metro_toggle)

    def _adjust_metro_bpm(self, delta: int) -> None:
        """Ajusta el tempo ±5 BPM (tope en BPM_MIN/BPM_MAX); solo de sesión, no
        se guarda en la base de datos. Si está sonando, se rearma el compás al
        tempo nuevo."""
        if self._bpm is None:
            return
        self._bpm = max(BPM_MIN, min(BPM_MAX, self._bpm + delta))
        self._metro_text.value = str(self._bpm)
        _safe_update(self._metro_text)
        if self._metro_on:
            self._metro_sound.start(self._bpm, self._beats)

    def _on_speed(self, e) -> None:
        self._speed = float(e.control.value)
        # Con la nueva velocidad, la animación en curso ya no dura lo que debe: se marca
        # para relanzarla desde donde va la letra (el supervisor la toma en el próximo
        # chequeo). En pausa no hay animación que relanzar.
        if self._playing:
            self._needs_restart = True

    def _user_moving(self) -> bool:
        """¿Manda el usuario ahora mismo? Su turno caduca solo (ver ``_USER_GRACE``)."""
        return time.monotonic() < self._user_hold

    def _on_scroll(self, e) -> None:
        """Sigue la posición del scroll y distingue si manda el usuario.

        El deslizamiento del autoscroll es UNA animación nativa hacia el final (ver
        ``_launch_glide``): sus posiciones intermedias ya no pueden frenar el avance
        —el destino es fijo—, así que aquí se sigue SIEMPRE la posición real. Hace
        falta para pausar o retomar (tras arrastrar o cambiar la velocidad) desde donde
        va la letra AHORA, no desde donde arrancó la animación.

        ``USER`` solo lo dispara el usuario, nunca el autoscroll: por eso abre su
        turno. El turno se RENUEVA con cada movimiento y CADUCA solo al dejar de
        moverse. Así no depende de recibir el evento final —que el límite de eventos
        puede descartar— y nunca se queda colgado cediéndole el mando.
        """
        self._max_extent = e.max_scroll_extent or 0.0
        movimiento = e.event_type in (ft.ScrollType.UPDATE, ft.ScrollType.OVERSCROLL)
        gesto = (e.event_type == ft.ScrollType.USER
                 and e.direction in (ft.ScrollDirection.FORWARD,
                                     ft.ScrollDirection.REVERSE))
        if gesto or (movimiento and self._user_moving()):
            self._user_hold = time.monotonic() + _USER_GRACE      # abre/renueva su turno
            # Tocar la pantalla cancela la animación nativa, así que SIEMPRE habrá que
            # relanzarla al soltar. Se marca aquí, no en el supervisor, porque un
            # arrastre corto (o su inercia) puede caber entre dos chequeos y entonces
            # ningún tick vería el gesto: quedaría quieto hasta tocar el slider.
            self._needs_restart = True
        self._pixels = e.pixels or 0.0
        if e.event_type == ft.ScrollType.END:
            # Se detuvo del todo: ya se anotó la posición final, el turno se cierra
            # sin esperar a que caduque (el autoscroll retoma enseguida).
            self._user_hold = 0.0

    def _set_playing(self, playing: bool) -> None:
        self._playing = playing
        # Reemplazar el contenido repinta seguro; mutar propiedades no siempre.
        self._play_box.content = self._play_icon()
        _safe_update(self._play_box)

    def _toggle_play(self, _e=None) -> None:
        self._set_playing(not self._playing)
        if self._playing:
            self._needs_restart = True           # el supervisor lanzará la animación
            if not self._running:
                self.page.run_task(self._autoscroll)
        else:
            # Pausa: la animación nativa sigue viva en Flutter aunque el bucle pare, así
            # que hay que cortarla y dejar la letra donde va ahora.
            self.page.run_task(self._freeze)

    def _at_end(self) -> bool:
        """¿Llegamos al final? ``max_extent`` en 0 significa que todo cabe en pantalla."""
        return self._max_extent is not None and self._pixels >= self._max_extent - 0.5

    async def _autoscroll(self) -> None:
        """Supervisor: NO anima cuadro a cuadro (eso lo hace Flutter en ``_launch_glide``);
        solo lanza/relanza la animación cuando hace falta y la detiene al final. Casi
        todos los giros solo duermen."""
        self._running = True
        try:
            while self._playing:
                if self._user_moving():
                    # El usuario mueve la pantalla; su arrastre ya canceló la animación
                    # nativa y ``_on_scroll`` marcó el relanzado. Se cede hasta que su
                    # turno caduque; entonces ``_pixels`` trae dónde dejó la letra y se
                    # relanza desde ahí (p. ej. arrastrar al inicio para repetir, sin
                    # volver a dar ▶).
                    await asyncio.sleep(_TICK)
                    continue
                if self._at_end():
                    self._set_playing(False)     # se detiene solo y el ícono vuelve a ▶
                    break
                if self._max_extent is None:
                    # Aún no sabemos el largo total (el primer evento de scroll no llegó):
                    # un pasito corto lo revela y de paso avanza.
                    await self._scroll_step()
                elif self._needs_restart:
                    self._needs_restart = False
                    await self._launch_glide()
                await asyncio.sleep(_TICK)
        finally:
            self._running = False

    async def _launch_glide(self) -> None:
        """Lanza UNA animación nativa, lineal, desde donde va la letra hasta el final.

        La duración sale de la distancia que falta y la velocidad, así el ritmo es el
        del slider. Al ser una sola animación (y sin easing) Flutter la corre pareja,
        sin las costuras del empuje por pasos."""
        restante = (self._max_extent or 0.0) - self._pixels
        if restante <= 0.5:
            self._set_playing(False)
            return
        ms = max(1, int(restante / self._speed * 1000))
        try:
            await self._body.scroll_to(       # scroll_to es async en Flet 0.85
                offset=self._max_extent, duration=ms,
                curve=ft.AnimationCurve.LINEAR)
        except Exception:
            # Si el ListView ya no está montado, el bucle muere: el ícono no puede
            # quedarse en ⏸ diciendo que sigue tocando.
            self._set_playing(False)

    async def _scroll_step(self) -> None:
        """Bootstrap: mientras no se conoce ``max_extent`` se avanza a pasos cortos (que
        además provocan el evento de scroll que lo revela). En cuanto se sabe, el
        supervisor pasa a ``_launch_glide`` y esto no se usa más."""
        destino = self._pixels + self._speed * _TICK
        try:
            await self._body.scroll_to(offset=destino, duration=int(_TICK * 1000),
                                       curve=ft.AnimationCurve.LINEAR)
        except Exception:
            self._set_playing(False)
            return
        self._pixels = destino

    async def _freeze(self) -> None:
        """Corta la animación nativa dejando la letra donde va ahora (un ``scroll_to`` de
        duración 0 a la posición actual reemplaza a la animación en curso)."""
        try:
            await self._body.scroll_to(offset=self._pixels, duration=0)
        except Exception:
            pass

    def stop(self) -> None:
        """Detiene la reproducción (autoscroll + metrónomo) y restaura el fondo del
        tema, SIN navegar. Se llama al salir por cualquier vía —la ✕, cambiar de
        canción y también el «atrás» del sistema, que salta ``_exit``— para que el
        metrónomo no siga sonando en la pantalla anterior. Es idempotente."""
        self._playing = False                   # detiene el autoscroll
        if self._bpm is not None:
            self._detener_metro()               # detiene el sonido del metrónomo
        self.page.bgcolor = theme.THEME["bg"]   # devuelve el fondo del tema
        _safe_update(self.page)

    def _exit(self) -> None:
        self.stop()
        self.on_exit()
