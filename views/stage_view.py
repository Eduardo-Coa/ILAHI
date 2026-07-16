"""Vista escenario (Fase 3–5): acordes en color sobre la letra, con transposición
instantánea, tamaño de fuente, navegación de lista y exportar.

Alineación por LAYOUT (no por fuente monoespaciada): cada sílaba es una columna
[acorde encima · sílaba debajo]; las palabras se agrupan y la línea hace *wrap*
por palabra en pantallas angostas. Así el acorde siempre queda sobre su sílaba,
independientemente de la fuente, y las líneas largas no se recortan.

Reutiliza la lógica del escritorio sin cambios:
- ``transposer.display_song``: offset global + modulación por bloque (no destructivo).
"""

from __future__ import annotations
from typing import Callable
import asyncio
import flet as ft

from models.song import Song, Line, Syllable
from models.transposer import display_song, semitones_between
from utils.metronome import BPM_MIN, BPM_MAX, Metronome, beats_per_measure, valid_bpm
from views.metro_sound import MetroSound
from utils.song_text import SECTION_LABELS
from utils.lyrics_parser import is_chord_line
from views.widgets import (back_button, circle_button, title_block,
                           square_button, wrap_lyric_line, sheet_option)
import theme


def _safe_update(control: ft.Control) -> None:
    """Actualiza el control solo si está montado (headless-safe)."""
    try:
        control.update()
    except Exception:
        pass


def _word_chord_lyric(word_syllables: list[Syllable]) -> tuple[str, str]:
    """(fila_de_acordes, texto) de UNA palabra, con los acordes alineados por carácter
    dentro de la palabra (así el *wrap* es por palabra y la palabra no se parte).

    Cuando dos sílabas seguidas tienen acorde y el primero es más ancho que su sílaba
    (p. ej. «G#m7» sobre «par»), el segundo acorde se saldría de su sílaba; para que
    encaje se empuja la sílaba siguiente a la derecha rellenando la letra con guiones
    (queda «par--tir»). Los guiones se ponen solos, solo cuando hacen falta: con
    acordes cortos (A, E) no se agrega ninguno."""
    chord_str = ""
    lyric_str = ""
    for syl in word_syllables:
        value = syl.chord.value if syl.chord else ""
        # casilla de acorde sin letra (slot con acorde) → guión de apoyo
        text = "-" if (value and not syl.text.strip()) else syl.text
        if value:
            # El acorde y su sílaba deben empezar en la misma columna, dejando ≥1
            # hueco tras el acorde anterior. Si esa columna queda más allá de la letra
            # actual, se rellena con guiones para que el acorde caiga sobre su sílaba.
            gap = 1 if (chord_str and not chord_str.endswith(" ")) else 0
            col = max(len(lyric_str), len(chord_str) + gap)
            if col > len(lyric_str):
                lyric_str += "-" * (col - len(lyric_str))
            chord_str += " " * (col - len(chord_str))
            chord_str += value
        lyric_str += text
    return chord_str.rstrip(), lyric_str


def _word_col(word_syllables: list[Syllable], size: int, chord_size: int,
              show_chord: bool = True, show_lyric: bool = True) -> ft.Control:
    """Columna de una palabra: acordes (monoespaciados) encima, palabra ENTERA debajo.

    ``show_chord``/``show_lyric`` permiten omitir una fila entera cuando la línea es
    de solo acordes (sin letra) o de solo letra (sin acordes), y así no dejar filas
    en blanco que agrandan el espacio vertical."""
    chord_str, lyric_str = _word_chord_lyric(word_syllables)
    rows: list[ft.Control] = []
    if show_chord:
        rows.append(ft.Text(chord_str or " ", font_family=theme.FONT_MONO, size=chord_size,
                            weight=ft.FontWeight.BOLD, color=theme.THEME["chord"], no_wrap=True))
    if show_lyric:
        rows.append(ft.Text(lyric_str or " ", font_family=theme.FONT_MONO, size=size,
                            color=theme.THEME["text"], no_wrap=True))
    return ft.Column(rows, spacing=0, tight=True,
                     horizontal_alignment=ft.CrossAxisAlignment.START)


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


def _line_block(line: Line, size: int) -> ft.Control:
    """Un renglón: cada palabra es una columna [acordes / palabra]; *wrap* por palabra.

    Si la línea no tiene acordes se omite la fila de acordes, y si no tiene letra se
    omite la fila de letra (evita renglones en blanco que inflan el espacio)."""
    syls = line.syllables
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
                       alignment=ft.MainAxisAlignment.CENTER,
                       vertical_alignment=ft.CrossAxisAlignment.START),
    )


def _intro_line_block(line: Line, size: int) -> ft.Control:
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
                       alignment=ft.MainAxisAlignment.CENTER,
                       vertical_alignment=ft.CrossAxisAlignment.START))


# Padding lateral del cuerpo (ListView left+right) que se resta al ancho de pantalla.
_BODY_SIDE_PAD = 32


def stage_body_from(disp: Song, size: int, page_width: float | None = None) -> list[ft.Control]:
    """Controles del cuerpo a partir de una canción YA transpuesta (``display_song``).

    ``page_width`` (ancho de pantalla) permite partir los renglones de letra largos
    por puntuación antes de que Flet los corte a mitad de frase."""
    avail = (page_width or 400) - _BODY_SIDE_PAD
    blocks: list[ft.Control] = []
    for section in disp.sections:
        label = section.label or SECTION_LABELS.get(section.type, "")
        if label:
            blocks.append(ft.Container(
                padding=ft.Padding.only(top=8, bottom=1),
                alignment=ft.Alignment.CENTER,        # etiqueta centrada como la letra
                content=ft.Text(label.upper(), size=theme.SIZE_SECTION,
                                color=theme.THEME["section_label"]),
            ))
        for line in section.lines:
            if section.type == "intro":
                blocks.append(_intro_line_block(line, size))
            elif is_chord_line(line):
                continue          # las casillas de solo acordes viven en la intro
            else:
                for part in wrap_lyric_line(line.syllables, size, avail):
                    blocks.append(_line_block(
                        Line(id=line.id, position=line.position, syllables=part), size))
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
    """Autor · tono original · ritmo · capo, omitiendo lo que la canción no tenga."""
    meta: list[str] = []
    if song.author:
        meta.append(song.author)
    if song.original_key:
        meta.append(f"Original: {song.original_key}")
    if song.rhythm:
        meta.append(f"Ritmo: {song.rhythm}")
    if song.capo:                       # solo si usa capo (capo != 0)
        meta.append(f"Capo: T{song.capo}")
    return meta


class StageScreen:
    """Escenario con transposición, tamaño de fuente, navegación de lista y exportar."""

    def __init__(self, page: ft.Page, song: Song, on_back: Callable[[], None],
                 initial_offset: int = 0,
                 on_prev: Callable[[], None] | None = None,
                 on_next: Callable[[], None] | None = None,
                 position_label: str = "",
                 on_edit: Callable[[int], None] | None = None,
                 on_edit_lyrics: Callable[[int], None] | None = None,
                 on_present: Callable | None = None,
                 on_persist_key: Callable | None = None,
                 on_offset_change: Callable[[int], None] | None = None) -> None:
        self.page = page
        self.song = song
        self.on_back = on_back
        self.on_prev = on_prev
        self.on_next = on_next
        self.position_label = position_label
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
        self.size = theme.SIZE_STAGE
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
                lambda _e: self.on_present(self.song, self.offset),
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
        dialog = ft.AlertDialog(
            modal=False,
            shape=ft.RoundedRectangleBorder(radius=20),
            bgcolor=theme.THEME["surface2"],
            title=ft.Text("Editar", size=18, weight=ft.FontWeight.BOLD,
                          color=theme.THEME["text"]),
            content_padding=ft.Padding.only(left=8, right=8, bottom=8),
            content=ft.Column(tight=True, spacing=2, controls=opciones),
        )
        self.page.show_dialog(dialog)

    def _open_font_sheet(self) -> None:
        """Cuadro «Tamaño del texto»: A− · número · A+ · Restablecer."""
        self._size_text = ft.Text(str(self.size), size=26, weight=ft.FontWeight.BOLD,
                                  color=theme.THEME["text"])
        dialog = ft.AlertDialog(
            modal=False,
            shape=ft.RoundedRectangleBorder(radius=20),
            bgcolor=theme.THEME["surface2"],
            content_padding=ft.Padding.only(left=16, right=16, top=8, bottom=8),
            content=ft.Column(tight=True, spacing=10,
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                              controls=[
                ft.Text("Tamaño del texto", size=16, color=theme.THEME["text"]),
                ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=24, controls=[
                    _circle_button("A−", lambda _e: self._resize(-2)),
                    self._size_text,
                    _circle_button("A+", lambda _e: self._resize(2)),
                ]),
                ft.TextButton("Restablecer", on_click=lambda _e: self._reset_size()),
            ]),
        )
        self.page.show_dialog(dialog)

    def _refresh(self, update: bool = True) -> None:
        """Recalcula la canción mostrada al offset actual y repinta el cuerpo."""
        disp = display_song(self.song, self.offset)
        self._body.controls = stage_body_from(disp, self.size, self.page.width)
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
            ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=24, controls=[
                _circle_button("−", lambda _e: self._transpose(-1)),
                ft.Column(centro, spacing=0, tight=True,
                          horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                _circle_button("+", lambda _e: self._transpose(1)),
            ]),
        ]
        # «Restablecer» solo tiene sentido si hay a dónde volver: en una lista, al
        # tono de la lista; persistiendo, al tono original (si está registrado).
        if not persiste or self.song.original_key:
            etiqueta = "Al tono original" if persiste else "Restablecer"
            controles.append(ft.TextButton(etiqueta,
                                           on_click=lambda _e: self._reset_tone()))

        dialog = ft.AlertDialog(
            modal=False,
            shape=ft.RoundedRectangleBorder(radius=20),
            bgcolor=theme.THEME["surface2"],
            content_padding=ft.Padding.only(left=16, right=16, top=8, bottom=8),
            content=ft.Column(controles, tight=True, spacing=10,
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER),
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
        """Fila anterior/siguiente (en píldoras) para moverse dentro de una lista."""
        return ft.Row(
            alignment=ft.MainAxisAlignment.CENTER, spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                self._nav_pill("‹ Anterior", self.on_prev, self.on_prev is not None),
                ft.Text(self.position_label, size=12, color=theme.THEME["text_muted"]),
                self._nav_pill("Siguiente ›", self.on_next, self.on_next is not None),
            ],
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
                ft.Column(_title_block(self.song.title, meta), spacing=0, tight=True,
                          expand=True,
                          horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                derecha,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        # Tono, fuente, editar y escenario viven en los botones flotantes.
        rows: list[ft.Control] = [row1]
        if self.on_prev is not None or self.on_next is not None:
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

# Autoscroll. La velocidad se mide en **píxeles por segundo**, no en píxeles por
# tick: así el slider significa lo mismo aunque cambie la cadencia del bucle.
_TICK = 0.1                  # segundos entre pasos
_SPEED_MIN = 4.0             # px/s: apenas se mueve
_SPEED_MAX = 90.0            # px/s
_SPEED_DEFAULT = 18.0


class PresentScreen:
    """Modo escenario: SOLO la canción (limpio, sin barra de herramientas), con
    control de tamaño de fuente y **autoscroll** (play/pausa + velocidad).

    En temas oscuros el fondo es **negro puro** (no el del tema); en claros, el
    fondo del tema (ver ``_stage_bg``)."""

    def __init__(self, page: ft.Page, song: Song, offset: int,
                 on_exit: Callable[[], None],
                 on_prev: Callable[[], None] | None = None,
                 on_next: Callable[[], None] | None = None,
                 position_label: str = "") -> None:
        self.page = page
        self.song = song
        self.offset = offset          # tono con el que se venía viendo
        self.on_exit = on_exit
        self.on_prev = on_prev        # canción anterior de la lista (None en la 1ª)
        self.on_next = on_next        # canción siguiente de la lista (None en la última)
        self.position_label = position_label
        self._chrome_visible = True   # header + panel se ocultan/muestran al tocar
        self._header_box: ft.Control | None = None
        self._panel_box: ft.Control | None = None
        self._swipe_dx = 0.0          # distancia acumulada del arrastre lateral
        self.size = 14                # tamaño inicial (rango permitido 12–64)
        self._speed = _SPEED_DEFAULT  # píxeles por segundo
        self._playing = False
        self._running = False         # evita lanzar dos bucles a la vez
        self._pixels = 0.0            # posición real del scroll (la reporta on_scroll)
        self._pending_anchor = 0.0    # posición a restaurar tras ocultar/mostrar el chrome
        self._max_extent: float | None = None   # None = aún no la sabemos
        # El panel es fijo y no se puede ocultar: el hueco de abajo deja que la
        # última línea de la canción suba por encima de él al hacer scroll.
        # El espacio superior reserva el alto del panel del título (que flota encima):
        # así el título no empuja la letra y ocultarlo no la mueve.
        self._body = ft.ListView(
            expand=True, spacing=2, on_scroll=self._on_scroll, scroll_interval=50,
            padding=ft.Padding.only(left=16, right=16, top=_HEADER_H + 6, bottom=28))
        self._play_box = ft.Container(
            content=self._play_icon(), on_click=self._toggle_play,
            ink=True, padding=8, border_radius=20)
        self._size_text: ft.Text | None = None
        # Metrónomo: solo existe si la canción trae un BPM válido. Sin BPM, ningún
        # atributo de metrónomo se crea (renderizado condicional real, no disabled).
        self._bpm = valid_bpm(song.bpm)
        self._metro_toggle: ft.Control | None = None   # casilla ▶/■ del panel
        if self._bpm is not None:
            self._metro = Metronome(self._bpm, self._on_metro_beat,
                                    beats=beats_per_measure(song.rhythm))
            self._metro_sound = MetroSound(page)   # clicks (no-op sin flet-audio)
            self._metro_dot = ft.Container(
                width=14, height=14, border_radius=7,
                bgcolor=theme.THEME["chord_bg"],
                border=ft.Border.all(1, theme.THEME["border"]))
            self._metro_text = ft.Text(str(self._bpm), size=15,
                                       weight=ft.FontWeight.BOLD, color=theme.THEME["text"])

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
        # El título FLOTA sobre el cuerpo (Stack) en vez de empujarlo: el cuerpo ya
        # reserva su alto con el padding superior del ListView. Así, mostrarlo u
        # ocultarlo NO redimensiona el cuerpo y la letra se queda quieta.
        return ft.Stack(expand=True, controls=[
            ft.Column([cuerpo, self._panel_box], expand=True, spacing=0),
            ft.Container(top=0, left=0, right=0, content=self._header_box),
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
            self._metro.stop()
        if self.on_prev is not None:
            self.on_prev()

    def _go_next(self) -> None:
        """Detiene el metrónomo (si lo hay) antes de cambiar de canción."""
        if self._bpm is not None:
            self._metro.stop()
        if self.on_next is not None:
            self.on_next()

    def _header(self) -> ft.Control:
        """Título centrado con ‹ anterior / siguiente › a los lados (para la lista)."""
        prev = self._nav_button(
            ft.Icons.CHEVRON_LEFT, lambda _e: self._go_prev(),
            self.on_prev is not None)
        nxt = self._nav_button(
            ft.Icons.CHEVRON_RIGHT, lambda _e: self._go_next(),
            self.on_next is not None)
        titulo = _title_block(self.song.title, _song_meta(self.song))
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
        # Oculta/muestra header y panel a la vez: al ocultarlos, su espacio lo gana
        # el cuerpo (pantalla completa con solo letra y acordes).
        self._chrome_visible = not self._chrome_visible
        # Guardar la posición ANTES del re-layout: al cambiar el tamaño del cuerpo,
        # el ListView pierde su scroll y brinca a 0. Se captura aquí (y no en
        # _reanchor) porque el reset dispara un on_scroll(0) que podría pisar
        # _pixels antes de que la corrutina llegue a leerlo.
        self._pending_anchor = self._pixels
        for box in (self._header_box, self._panel_box):
            if box is not None:
                box.visible = self._chrome_visible
                _safe_update(box)
        # Reanclar de inmediato (scroll instantáneo) para que el brinco a 0 no
        # llegue a verse, en vez de esperar al siguiente tick del autoscroll.
        self.page.run_task(self._reanchor)

    async def _reanchor(self) -> None:
        """Devuelve el scroll a donde iba, sin animación, tras ocultar/mostrar el
        chrome. El cliente aplica primero el re-layout y luego este salto, así que
        la posición correcta se restaura en el mismo frame."""
        try:
            await self._body.scroll_to(
                offset=self._pending_anchor, duration=ft.Duration(milliseconds=0))
        except Exception:
            pass
        self._pixels = self._pending_anchor

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
        """Panel fijo con velocidad de scroll y tamaño de texto; la ✕ sale del escenario."""
        muted = theme.THEME["text_muted"]
        texto = theme.THEME["text"]
        self._size_text = ft.Text(str(self.size), size=17, weight=ft.FontWeight.BOLD,
                                  color=texto)
        # Tortuga/liebre no existen en Material: caminar y correr dicen lo mismo.
        velocidad = ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6, controls=[
                self._play_box,
                _slot(ft.Icon(ft.Icons.DIRECTIONS_WALK, size=18, color=muted)),
                ft.Slider(min=_SPEED_MIN, max=_SPEED_MAX, value=self._speed,
                          expand=True, on_change=self._on_speed),
                _slot(ft.Icon(ft.Icons.DIRECTIONS_RUN, size=18, color=muted)),
            ])
        fuente = ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6, controls=[
                # «Aa» alineado bajo el play: mismo ancho, mismo color, en negrita.
                ft.Container(width=_PLAY_WIDTH, alignment=ft.Alignment.CENTER,
                             content=ft.Text("Aa", size=15, weight=ft.FontWeight.BOLD,
                                             color=texto)),
                _slot(ft.Container(width=1, height=20, bgcolor=theme.THEME["border"])),
                ft.Row(expand=True, alignment=ft.MainAxisAlignment.CENTER, spacing=10,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                           _circle_button("A−", lambda _e: self._resize(-2), diameter=40,
                                          bgcolor=theme.THEME["surface2"]),
                           self._size_text,
                           _circle_button("A+", lambda _e: self._resize(2), diameter=40,
                                          bgcolor=theme.THEME["surface2"]),
                       ]),
                # ROTATE_LEFT es la misma flecha circular que REFRESH pero invertida:
                # apunta hacia atrás, que es lo que significa «volver al tamaño base».
                _slot(ft.Icon(ft.Icons.ROTATE_LEFT, size=20, color=muted),
                      on_click=lambda _e: self._reset_size(),
                      tooltip="Restablecer el tamaño"),
            ])
        filas: list[ft.Control] = [velocidad, fuente]
        if self._bpm is not None:
            self._metro_toggle = _slot(self._metro_icon(), on_click=self._toggle_metro,
                                       tooltip="Metrónomo")
            metronomo = ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6, controls=[
                    ft.Container(width=_PLAY_WIDTH, alignment=ft.Alignment.CENTER,
                                 content=ft.Text("♩", size=18, weight=ft.FontWeight.BOLD,
                                                 color=texto)),
                    _slot(ft.Container(width=1, height=20, bgcolor=theme.THEME["border"])),
                    ft.Row(expand=True, alignment=ft.MainAxisAlignment.CENTER, spacing=10,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                               _circle_button("−", lambda _e: self._adjust_metro_bpm(-5),
                                              diameter=40, bgcolor=theme.THEME["surface2"]),
                               ft.Row([self._metro_dot, self._metro_text], spacing=6,
                                      tight=True,
                                      vertical_alignment=ft.CrossAxisAlignment.CENTER),
                               _circle_button("+", lambda _e: self._adjust_metro_bpm(5),
                                              diameter=40, bgcolor=theme.THEME["surface2"]),
                           ]),
                    self._metro_toggle,
                ])
            filas.append(metronomo)
        return ft.Container(
            visible=self._chrome_visible,      # se oculta/muestra al tocar la pantalla
            margin=ft.Margin.only(left=10, right=10, bottom=10),
            padding=ft.Padding.only(left=8, right=4, top=4, bottom=4),
            bgcolor=theme.THEME["surface"], border_radius=24,
            border=ft.Border.all(1, theme.THEME["border"]),
            content=ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=4, controls=[
                    ft.Column(filas, spacing=0, tight=True, expand=True),
                    ft.Container(width=1, height=64, bgcolor=theme.THEME["border"]),
                    ft.IconButton(ft.Icons.CLOSE, icon_size=22, icon_color=muted,
                                  tooltip="Salir del escenario",
                                  on_click=lambda _e: self._exit()),
                ]),
        )

    def _refresh(self) -> None:
        disp = display_song(self.song, self.offset)
        self._body.controls = stage_body_from(disp, self.size, self.page.width)
        _safe_update(self._body)

    def _resize(self, delta: int) -> None:
        self._set_size(self.size + delta)

    def _reset_size(self) -> None:
        self._set_size(theme.SIZE_STAGE)

    def _set_size(self, value: int) -> None:
        self.size = max(12, min(64, value))
        if self._size_text is not None:
            self._size_text.value = str(self.size)
            _safe_update(self._size_text)
        self._refresh()

    # ------------------------------------------------------------------
    # Metrónomo (solo si la canción trae BPM válido; ver ``self._bpm``)
    # ------------------------------------------------------------------
    def _on_metro_beat(self, index: int) -> None:
        """Enciende el punto de pulso (dorado en el acento, golpe 0) y lo apaga
        tras un instante; solo actualiza el punto, nunca el resto de la UI, para
        no interferir con el autoscroll."""
        if self._bpm is None:
            return
        self._metro_sound.click(index)             # click audible (si hay audio)
        self._metro_dot.bgcolor = (theme.THEME["accent"] if index == 0
                                   else theme.THEME["chord"])
        _safe_update(self._metro_dot)
        self.page.run_task(self._metro_dot_off)

    async def _metro_dot_off(self) -> None:
        await asyncio.sleep(0.12)
        if self._bpm is None:
            return
        self._metro_dot.bgcolor = theme.THEME["chord_bg"]
        _safe_update(self._metro_dot)

    def _metro_icon(self, running: bool | None = None) -> ft.Control:
        """Ícono de la casilla ▶/■: corriendo muestra detener, detenido muestra play."""
        if running is None:
            running = self._bpm is not None and self._metro.playing
        return ft.Icon(ft.Icons.STOP if running else ft.Icons.PLAY_ARROW, size=18,
                       color=theme.THEME["text"] if running else theme.THEME["text_muted"])

    def _toggle_metro(self, _e=None) -> None:
        if self._bpm is None:
            return
        arranca = not self._metro.playing
        if arranca:
            self.page.run_task(self._metro.run)
        else:
            self._metro.stop()
            self._metro_dot.bgcolor = theme.THEME["chord_bg"]
            _safe_update(self._metro_dot)
        # El ícono refleja el estado al que se VA: ``run_task`` apenas agenda la
        # corrutina, así que leer ``playing`` aquí daría todavía el estado viejo.
        if self._metro_toggle is not None:
            self._metro_toggle.content = self._metro_icon(arranca)
            _safe_update(self._metro_toggle)

    def _adjust_metro_bpm(self, delta: int) -> None:
        """Ajusta el tempo ±5 BPM (tope en BPM_MIN/BPM_MAX); solo de sesión, no
        se guarda en la base de datos."""
        if self._bpm is None:
            return
        self._bpm = max(BPM_MIN, min(BPM_MAX, self._bpm + delta))
        self._metro_text.value = str(self._bpm)
        _safe_update(self._metro_text)
        self._metro.set_bpm(self._bpm)

    def _on_speed(self, e) -> None:
        self._speed = float(e.control.value)

    def _on_scroll(self, e) -> None:
        """Posición y final reales del scroll, los reporte quien los reporte.

        Mientras el autoscroll corre, ``pixels`` llega a mitad de la animación y
        frenaría el avance; por eso solo se sincroniza la posición cuando está en
        pausa (que es cuando el usuario desliza con el dedo). El final del
        contenido, en cambio, siempre interesa.
        """
        self._max_extent = e.max_scroll_extent or 0.0
        if not self._playing:
            self._pixels = e.pixels or 0.0

    def _set_playing(self, playing: bool) -> None:
        self._playing = playing
        # Reemplazar el contenido repinta seguro; mutar propiedades no siempre.
        self._play_box.content = self._play_icon()
        _safe_update(self._play_box)

    def _toggle_play(self, _e=None) -> None:
        self._set_playing(not self._playing)
        if self._playing and not self._running:
            self.page.run_task(self._autoscroll)

    def _at_end(self) -> bool:
        """¿Llegamos al final? ``max_extent`` en 0 significa que todo cabe en pantalla."""
        return self._max_extent is not None and self._pixels >= self._max_extent - 0.5

    async def _autoscroll(self) -> None:
        self._running = True
        try:
            while self._playing:
                if self._at_end():
                    self._set_playing(False)     # se detiene solo y el ícono vuelve a ▶
                    break
                destino = self._pixels + self._speed * _TICK
                if self._max_extent is not None:
                    destino = min(destino, self._max_extent)
                try:
                    await self._body.scroll_to(   # scroll_to es async en Flet 0.85
                        offset=destino,
                        duration=ft.Duration(milliseconds=int(_TICK * 1000)))
                except Exception:
                    # Si el ListView ya no está montado, el bucle muere: el ícono
                    # no puede quedarse en ⏸ diciendo que sigue tocando.
                    self._set_playing(False)
                    break
                self._pixels = destino
                await asyncio.sleep(_TICK)
        finally:
            self._running = False

    def _exit(self) -> None:
        self._playing = False                   # detiene el autoscroll al salir
        if self._bpm is not None:
            self._metro.stop()                  # detiene el metrónomo al salir
        self.page.bgcolor = theme.THEME["bg"]   # devuelve el fondo del tema
        _safe_update(self.page)
        self.on_exit()
