"""Edición de canciones en el teléfono (Fase 6).

- ``NewSongScreen``: metadatos + pegar letra → ``parse_lyrics`` → guardar → editor.
- ``EditSongScreen``: rejilla de sílabas TOCABLES; al tocar una, un editor inferior
  permite escribir el acorde o elegirlo de las **sugerencias diatónicas** del tono
  (``chords_for_key``). Autosave en cada cambio; el acorde se actualiza en el sitio
  (sin repintar toda la rejilla) para que sea ágil.
"""

from __future__ import annotations
from typing import Callable
import flet as ft

from models.song import Song, Section, Line, Syllable, Chord
from models.key_chords import chords_for_key
from models.transposer import transpose_chord
from utils.lyrics_parser import (parse_lyrics, merge_lyrics, is_chord_line,
                                 INTRO_LABEL, prepend_intro, chord_line_text,
                                 normalize_intro)
from utils.metronome import valid_bpm
from utils.song_text import SECTION_LABELS
from views.widgets import (back_button, centered_header, floating_panel,
                           square_button, wrap_lyric_line)
import theme

_PUNCT = set(",.;:!¡?¿…\"'()-—«»")

# Panel de edición: 10 sugerencias en 2 filas de 5, todas del mismo ancho.
# `chords_for_key` devuelve 11; se descarta el último (el disminuido, el menos
# usado). Siempre se puede escribir a mano en la caja del acorde.
_SUGGESTIONS = 10
_PER_ROW = 5
_CHIP_W = 62          # cabe «D#m», «G#m7» y demás sufijos largos
_CHIP_H = 38
_ACTION_W = 140       # «Aplicar» y «Quitar», del mismo ancho
# Las píldoras necesitan ancho explícito: sin él, dentro de un Row se estiran a
# todo el ancho disponible. Tres caben en la fila (112×3 + espacios).
_SLOT_W = 112


def _safe_update(control: ft.Control) -> None:
    try:
        control.update()
    except Exception:
        pass


def _themed_field(label: str, value: str = "", width: float | None = None) -> ft.TextField:
    """Campo de texto con el estilo de la app: relleno y esquinas redondeadas."""
    return ft.TextField(
        label=label, value=value or "", dense=True, width=width,
        border_radius=12, filled=True, bgcolor=theme.THEME["surface"],
        border_color=theme.THEME["border"],
        focused_border_color=theme.THEME["accent"],
        color=theme.THEME["text"], cursor_color=theme.THEME["accent"])


# Secciones que se pueden insertar con un botón. «Introducción» no está: se
# antepone sola. «Interludio» crea una sección de casillas de acordes.
_SECTION_INSERTS = ["Estrofa", "Coro", "Puente", "Interludio", "Final"]


def _section_insert_row(field: ft.TextField) -> ft.Control:
    """Botones que insertan un encabezado [Sección] donde esté el cursor de la caja.

    Se rastrea la posición del cursor con ``on_selection_change``; si aún no se ha
    tocado la caja, se inserta al final (comportamiento de reserva).
    """
    state = {"sel": None}   # (inicio, fin) de la selección/cursor

    def on_sel(e) -> None:
        sel = getattr(e, "selection", None)
        if sel is not None and sel.base_offset is not None:
            state["sel"] = (sel.base_offset, sel.extent_offset)
    field.on_selection_change = on_sel

    def insert(label: str) -> None:
        text = field.value or ""
        if state["sel"] is None:
            start = end = len(text)
        else:
            a, b = state["sel"]
            start, end = sorted((a, b))
            start = max(0, min(start, len(text)))
            end = max(0, min(end, len(text)))
        before, after = text[:start], text[end:]
        # El encabezado va en su propia línea: salto antes si hace falta.
        prefix = "\n" if before and not before.endswith("\n") else ""
        # ...y la letra que sigue queda en su propia línea, sin dejar una en blanco
        # de más (si el cursor estaba al final de una línea ya existe ese salto).
        suffix = "" if after.startswith("\n") else "\n"
        header = f"[{label}]{suffix}"
        field.value = before + prefix + header + after
        # dejar el cursor justo después del encabezado insertado
        pos = len(before) + len(prefix) + len(header)
        state["sel"] = (pos, pos)
        try:
            field.selection = ft.TextSelection(base_offset=pos, extent_offset=pos)
        except Exception:
            pass
        _safe_update(field)

    chips = [
        ft.Container(
            ink=True, border_radius=16, on_click=lambda _e, l=label: insert(l),
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            bgcolor=theme.THEME["surface"],
            border=ft.Border.all(1, theme.THEME["border"]),
            content=ft.Row(tight=True, spacing=4, controls=[
                ft.Icon(ft.Icons.ADD, size=14, color=theme.THEME["chord"]),
                ft.Text(label, size=12, color=theme.THEME["chord"]),
            ]))
        for label in _SECTION_INSERTS
    ]
    return ft.Column(spacing=6, controls=[
        ft.Text("Insertar sección:", size=11, color=theme.THEME["text_muted"]),
        ft.Row(chips, wrap=True, spacing=6, run_spacing=6),
    ])


def _pill_button(icon: str, label: str, on_click) -> ft.Control:
    """Botón de acción en píldora (verde del tema), como «Guardar»."""
    return ft.Container(
        height=46, ink=True, border_radius=23, on_click=on_click,
        alignment=ft.Alignment.CENTER,
        bgcolor=theme.THEME["chord_bg"],
        border=ft.Border.all(1, theme.THEME["chord"]),
        content=ft.Row(tight=True, spacing=8,
                       alignment=ft.MainAxisAlignment.CENTER, controls=[
            ft.Icon(icon, size=18, color=theme.THEME["chord"]),
            ft.Text(label, size=14, color=theme.THEME["chord"]),
        ]))


def _assignable(text: str) -> bool:
    """True si a la sílaba se le puede poner acorde (tiene letra real o es casilla vacía)."""
    stripped = text.strip()
    if stripped == "":
        return True                          # casilla vacía para acorde de paso
    return any(c not in _PUNCT for c in stripped)


def _group_words(syllables: list[Syllable]) -> list[list[Syllable]]:
    """Agrupa sílabas en palabras (cierra al terminar en espacio o casilla vacía)."""
    words, current = [], []
    for syl in syllables:
        current.append(syl)
        if syl.text == "" or syl.text.endswith(" "):
            words.append(current)
            current = []
    if current:
        words.append(current)
    return words


# ---------------------------------------------------------------------------
# Crear canción
# ---------------------------------------------------------------------------

class NewSongScreen:
    """Formulario: metadatos + pegar letra → procesar (silabificar) → editor."""

    def __init__(self, db, on_created: Callable[[int], None],
                 on_back: Callable[[], None]) -> None:
        self.db = db
        self.on_created = on_created
        self.on_back = on_back

        self._title = _themed_field("Título")
        self._author = _themed_field("Autor")
        self._key = _themed_field("Tono (círculo)", width=150)
        self._original_key = _themed_field("Tono original", width=150)
        self._rhythm = _themed_field("Ritmo", width=150)
        self._bpm = _themed_field("BPM", width=90)
        self._capo = _themed_field("Capo", width=110, value="0")
        self._lyrics = ft.TextField(
            hint_text="Pega aquí la letra (y acordes, si tienes)…", multiline=True,
            min_lines=8, max_lines=16, border=ft.InputBorder.NONE,
            # monoespaciada: alinea los acordes pegados sobre la letra (Cifra Club)
            text_style=ft.TextStyle(font_family=theme.FONT_MONO, size=14),
            color=theme.THEME["text"], cursor_color=theme.THEME["accent"],
            hint_style=ft.TextStyle(color=theme.THEME["text_muted"]),
            content_padding=ft.Padding.all(14))
        self._status = ft.Text("", size=13, color=theme.THEME["danger"])

    def build(self) -> ft.Control:
        # El botón ← hace de «cancelar»: vuelve sin crear nada.
        header = centered_header("Nueva canción", left=back_button(self.on_back))
        caja = ft.Container(
            bgcolor=theme.THEME["surface"], border_radius=16,
            border=ft.Border.all(1, theme.THEME["border"]),
            content=self._lyrics)
        form = ft.Column([
            self._title,
            ft.Row([self._key, self._original_key], spacing=10, wrap=True),
            ft.Row([self._rhythm, self._bpm, self._capo], spacing=10),
            self._author,
            caja,
            _section_insert_row(self._lyrics),
            self._status,
            _pill_button(ft.Icons.CHECK, "Guardar", self._process),
        ], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
        return ft.Column([header, ft.Container(content=form, padding=12, expand=True)],
                         expand=True, spacing=0)

    def _process(self, _e=None) -> None:
        title = (self._title.value or "").strip()
        if not title:
            self._show("Falta el título.")
            return
        text = self._lyrics.value or ""
        if not text.strip():
            self._show("Pega la letra primero.")
            return
        song = parse_lyrics(text, title)
        normalize_intro(song)        # toda canción nueva empieza con «Introducción» completa
        song.author = (self._author.value or "").strip() or None
        song.key = (self._key.value or "").strip() or None
        song.original_key = (self._original_key.value or "").strip() or None
        song.rhythm = (self._rhythm.value or "").strip() or None
        song.bpm = valid_bpm(self._bpm.value)
        try:
            song.capo = int((self._capo.value or "0").strip() or 0)
        except ValueError:
            song.capo = 0
        song_id = self.db.save_song(song)
        self.on_created(song_id)

    def _show(self, msg: str) -> None:
        self._status.value = msg
        _safe_update(self._status)


# ---------------------------------------------------------------------------
# Editar canción (asignar acordes tocando sílabas)
# ---------------------------------------------------------------------------

class EditSongScreen:
    """Rejilla de sílabas tocables + editor de acorde inferior con sugerencias."""

    def __init__(self, db, song: Song, on_back: Callable[[], None],
                 on_edit_lyrics: Callable[[int], None] | None = None,
                 page: ft.Page | None = None) -> None:
        self.db = db
        self.song = song
        self.on_back = on_back
        self.on_edit_lyrics = on_edit_lyrics
        self.page = page
        self._selected: Syllable | None = None
        self._size = 20
        self._chord_size = 15
        self._chord_texts: dict[int, ft.Text] = {}
        self._grid = ft.ListView(expand=True, spacing=2,
                                 padding=ft.Padding.symmetric(horizontal=12, vertical=8))
        # Panel flotante: mismo patrón que los de tono y tamaño de texto.
        self._editor = floating_panel(ft.Text(""))

    def build(self) -> ft.Control:
        # Sin autor, ritmo ni capo: aquí solo estorban. Los botones son los mismos
        # que en la vista de canción, y ocupan lo mismo a cada lado del título.
        editar = None
        if self.on_edit_lyrics is not None:
            editar = square_button(ft.Icons.EDIT, "Editar la letra",
                                   lambda: self.on_edit_lyrics(self.song.id))
        header = centered_header(self.song.title or "Canción",
                                 left=back_button(self.on_back), right=editar)
        self._fill_grid()
        self._render_editor()
        # Tocar la grilla FUERA del panel lo oculta (así se gana espacio para ver la
        # canción); tocar una casilla de acorde lo vuelve a abrir (ver _select). El
        # tap sobre una casilla lo consume la casilla, así que al detector solo llega
        # el toque «al vacío».
        cuerpo = ft.GestureDetector(expand=True, on_tap=self._hide_panel,
                                    content=self._grid)
        return ft.Column([header, cuerpo, self._editor], expand=True, spacing=0)

    # -- tono y modulación por sección --
    def _effective_key(self, section: Section) -> str | None:
        """Tono en el que SUENA la sección (tono de la canción + su modulación)."""
        if not self.song.key:
            return None
        if not section.transpose:
            return self.song.key
        return transpose_chord(self.song.key, section.transpose, self.song.key)

    def _sounding(self, syl: Syllable, section: Section) -> str:
        """Acorde tal como SUENA: el guardado, más la modulación del bloque."""
        if syl.chord is None:
            return ""
        if not section.transpose:
            return syl.chord.value
        return transpose_chord(syl.chord.value, section.transpose, self.song.key)

    def _section_transpose(self, section: Section, delta: int) -> None:
        """Modula la sección (no destructivo): ajusta ``section.transpose`` y guarda.

        Los acordes guardados no cambian; se muestran —aquí y en el escenario—
        sumándoles la modulación del bloque (``display_song``).
        """
        section.transpose += delta
        self.db.save_song(self.song)      # persiste en la columna sections.transpose
        self._fill_grid()                 # la sección se repinta con sus acordes sonando
        self._render_editor()             # y las sugerencias siguen su tono

    # -- rejilla --
    def _fill_grid(self) -> None:
        self._chord_texts.clear()
        blocks: list[ft.Control] = []
        # Ancho útil de la rejilla (pantalla menos el padding lateral 12+12) para
        # partir los renglones de letra largos por coma, igual que en el escenario.
        page_w = self.page.width if self.page is not None else None
        avail = (page_w or 400) - 24
        for index, section in enumerate(self.song.sections):
            blocks.append(self._section_header(section, index))
            for line in section.lines:
                # Casillas de acorde SIEMPRE visibles y tocables (guiones), aunque
                # estén vacías: en la Introducción, en interludios y en cualquier
                # sección donde se agreguen ([Final], [Coro]…). Lo que manda es la
                # línea, no el tipo de sección.
                if is_chord_line(line):
                    blocks.append(ft.Row(
                        [self._intro_cell(s, section) for s in line.syllables],
                        wrap=True, spacing=0, run_spacing=2,
                        vertical_alignment=ft.CrossAxisAlignment.START))
                    continue
                if not any(s.text.strip() or s.chord for s in line.syllables):
                    blocks.append(ft.Container(height=int(self._size * 0.3)))
                    continue
                # Partir el renglón por coma: cada frase es su propio Row (así la
                # frase después de la coma baja aunque la de arriba se vea corta).
                for part in wrap_lyric_line(line.syllables, self._size, avail):
                    word_rows = [
                        ft.Row([self._cell(s, section) for s in word], spacing=0, tight=True,
                               vertical_alignment=ft.CrossAxisAlignment.START)
                        for word in _group_words(part)
                    ]
                    blocks.append(ft.Row(word_rows, wrap=True, spacing=0, run_spacing=2,
                                         vertical_alignment=ft.CrossAxisAlignment.START))
        self._grid.controls = blocks
        _safe_update(self._grid)

    def _intro_cell(self, syl: Syllable, section: Section) -> ft.Control:
        """Casilla de la intro: acorde (o «·») sobre un guión, de ancho fijo y tocable."""
        chord_value = self._sounding(syl, section)
        top = ft.Text(chord_value or "·", size=self._chord_size, weight=ft.FontWeight.BOLD,
                      color=theme.THEME["chord"] if chord_value else theme.THEME["text_muted"],
                      no_wrap=True)
        self._chord_texts[id(syl)] = top
        return ft.Container(
            width=round(self._size * 2.4), ink=True, border_radius=4,
            on_click=lambda _e, s=syl: self._select(s),
            content=ft.Column(
                [top, ft.Text("-", font_family=theme.FONT_MONO, size=self._size,
                              color=theme.THEME["text"], no_wrap=True)],
                spacing=0, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )

    def _section_header(self, section: Section, index: int) -> ft.Control:
        """Etiqueta de la sección + su tono + control de modulación (desde la 2ª)."""
        label = section.label or SECTION_LABELS.get(section.type, section.type)
        controls: list[ft.Control] = [
            ft.Text(label.upper(), size=theme.SIZE_SECTION,
                    color=theme.THEME["section_label"]),
        ]
        key = self._effective_key(section)
        if key:
            controls.append(ft.Text(f"· Tono {key}", size=theme.SIZE_SECTION,
                                    color=theme.THEME["chord"]))
        if index > 0:            # la 1ª sección define el tono base de la canción
            t = f"{section.transpose:+d}".replace("+0", "0")
            controls.extend([
                ft.Container(width=8),
                ft.Text("Modulación:", size=11, color=theme.THEME["text_muted"]),
                ft.TextButton("−", on_click=lambda _e, s=section: self._section_transpose(s, -1)),
                ft.Text(t, size=12, color=theme.THEME["accent"]),
                ft.TextButton("+", on_click=lambda _e, s=section: self._section_transpose(s, 1)),
            ])
        return ft.Container(
            padding=ft.Padding.only(top=8, bottom=1),
            content=ft.Row(controls, wrap=True, spacing=4,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    def _cell(self, syl: Syllable, section: Section) -> ft.Control:
        assignable = _assignable(syl.text)
        chord_value = self._sounding(syl, section)      # se muestra como suena
        top = ft.Text(
            chord_value or ("·" if assignable else " "),
            size=self._chord_size, weight=ft.FontWeight.BOLD,
            color=theme.THEME["chord"] if chord_value else theme.THEME["text_muted"],
            no_wrap=True)
        if assignable:
            self._chord_texts[id(syl)] = top
        return ft.Container(
            content=ft.Column(
                [top, ft.Text(syl.text or " ", size=self._size,
                              color=theme.THEME["text"], no_wrap=True)],
                spacing=0, tight=True, horizontal_alignment=ft.CrossAxisAlignment.START),
            on_click=(lambda _e, s=syl: self._select(s)) if assignable else None,
            padding=ft.Padding.symmetric(horizontal=2),
            border_radius=4,
        )

    # -- selección y edición del acorde --
    def _select(self, syl: Syllable) -> None:
        self._selected = syl
        self._editor.visible = True          # tocar una casilla reabre el panel
        self._render_editor()

    def _hide_panel(self, _e=None) -> None:
        """Oculta el panel de acorde cuando se toca la grilla fuera de él; el espacio
        que deja lo aprovecha la canción. Vuelve a aparecer al tocar una casilla."""
        if self._editor.visible:
            self._editor.visible = False
            _safe_update(self._editor)

    def _set_chord(self, value: str) -> None:
        """``value`` es el acorde TAL COMO SUENA en la sección.

        Se guarda **destransponido** al tono base, para que ``display_song`` (que le
        vuelve a sumar la modulación del bloque) lo muestre exactamente igual.
        """
        if self._selected is None:
            return
        value = (value or "").strip()
        loc = self._locate(self._selected)
        section = loc[0] if loc else None
        if value and section is not None and section.transpose:
            stored = transpose_chord(value, -section.transpose, self._effective_key(section))
        else:
            stored = value
        self._selected.chord = Chord(id=None, value=stored) if stored else None
        self.db.save_song(self.song)                 # autosave
        # actualizar el texto del acorde de esa sílaba (ágil), mostrando el que suena
        text = self._chord_texts.get(id(self._selected))
        if text is not None:
            text.value = value or "·"
            text.color = theme.THEME["chord"] if value else theme.THEME["text_muted"]
            _safe_update(text)
        self._render_editor()

    def _locate(self, syl: Syllable):
        """Ubica (section, line, índice) de una sílaba dentro de la canción."""
        for section in self.song.sections:
            for line in section.lines:
                for i, s in enumerate(line.syllables):
                    if s is syl:
                        return section, line, i
        return None

    def _add_slot(self, before: bool) -> None:
        """Inserta una casilla de acorde vacía a la izquierda/derecha de la sílaba."""
        if self._selected is None:
            return
        loc = self._locate(self._selected)
        if loc is None:
            return
        _section, line, idx = loc
        slot = Syllable(id=None, position=0, text="")
        line.syllables.insert(idx if before else idx + 1, slot)
        for p, s in enumerate(line.syllables):
            s.position = p
        self.db.save_song(self.song)
        self._selected = slot           # queda seleccionada para ponerle acorde
        self._fill_grid()
        self._render_editor()

    def _remove_slot(self) -> None:
        """Quita la casilla seleccionada (solo si es un slot vacío)."""
        if self._selected is None or self._selected.text.strip():
            return
        loc = self._locate(self._selected)
        if loc is None:
            return
        _section, line, idx = loc
        del line.syllables[idx]
        for p, s in enumerate(line.syllables):
            s.position = p
        self.db.save_song(self.song)
        self._selected = None
        self._fill_grid()
        self._render_editor()

    # ------------------------------------------------------------------
    # Panel de edición del acorde
    # ------------------------------------------------------------------
    def _pill(self, icon: str, label: str, on_click, accent: bool = False,
              width: float | None = None) -> ft.Control:
        """Botón alargado del panel: «Aplicar», «Quitar», «＋ izquierda»…"""
        color = theme.THEME["chord"] if accent else theme.THEME["text_muted"]
        return ft.Container(
            width=width, height=40, ink=True, border_radius=20, on_click=on_click,
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.symmetric(horizontal=14),
            bgcolor=theme.THEME["chord_bg"] if accent else theme.THEME["surface"],
            border=ft.Border.all(1, color if accent else theme.THEME["border"]),
            content=ft.Row(tight=True, spacing=8,
                           alignment=ft.MainAxisAlignment.CENTER, controls=[
                ft.Icon(icon, size=16, color=color),
                ft.Text(label, size=13, color=color),
            ]),
        )

    def _rule(self, label: str) -> ft.Control:
        """Etiqueta de sección con una línea que la separa de lo de arriba."""
        return ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
            ft.Text(label, size=11, color=theme.THEME["text_muted"]),
            ft.Container(expand=True, height=1, bgcolor=theme.THEME["border"],
                         margin=ft.Margin.only(left=10, right=2)),
        ])

    def _chip(self, chord: str, current: str) -> ft.Control:
        """Sugerencia de acorde; todas del mismo tamaño, resaltada la que está puesta."""
        activo = chord == current
        return ft.Container(
            width=_CHIP_W, height=_CHIP_H, ink=True, border_radius=10,
            alignment=ft.Alignment.CENTER,
            on_click=lambda _e: self._set_chord(chord),
            bgcolor=theme.THEME["chord_bg"] if activo else theme.THEME["surface"],
            border=ft.Border.all(1, theme.THEME["chord"] if activo
                                 else theme.THEME["border"]),
            content=ft.Text(chord, size=13, no_wrap=True,
                            weight=ft.FontWeight.BOLD if activo else ft.FontWeight.NORMAL,
                            color=theme.THEME["chord"]),
        )

    def _chip_rows(self, suggestions: list[str], current: str) -> list[ft.Control]:
        """Dos filas de 5, repartidas por igual: los botones quedan en cuadrícula."""
        chips = [self._chip(c, current) for c in suggestions]
        return [ft.Row(chips[i:i + _PER_ROW], spacing=6,
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                for i in range(0, len(chips), _PER_ROW)]

    def _render_editor(self) -> None:
        if self._selected is None:
            self._editor.content = ft.Container(
                alignment=ft.Alignment.CENTER,
                content=ft.Text("Toca una sílaba para asignarle un acorde",
                                size=13, color=theme.THEME["text_muted"]))
            _safe_update(self._editor)
            return
        syl = self._selected
        loc = self._locate(syl)
        section = loc[0] if loc else None
        # tono y acorde EN EL CONTEXTO DE LA SECCIÓN (no del tono global de la canción)
        sec_key = self._effective_key(section) if section else self.song.key
        current = self._sounding(syl, section) if section else (
            syl.chord.value if syl.chord else "")

        self._chord_field = ft.TextField(
            value=current, hint_text="—", dense=True, text_align=ft.TextAlign.CENTER,
            border=ft.InputBorder.NONE, text_size=24,
            color=theme.THEME["chord"], cursor_color=theme.THEME["accent"],
            content_padding=ft.Padding.symmetric(vertical=6),
            on_submit=lambda e: self._set_chord(e.control.value))
        caja = ft.Container(
            width=_ACTION_W, height=64, border_radius=16,
            bgcolor=theme.THEME["chord_bg"],
            border=ft.Border.all(1, theme.THEME["chord"]),
            alignment=ft.Alignment.CENTER, content=self._chord_field)

        silaba = syl.text.strip() or "␣"
        acorde = ft.Column(tight=True, spacing=6, controls=[
            ft.Text(f"Acorde para «{silaba}»", size=11, color=theme.THEME["text_muted"]),
            caja,
        ])
        acciones = ft.Column(tight=True, spacing=8, controls=[
            self._pill(ft.Icons.CHECK, "Aplicar",
                       lambda _e: self._set_chord(self._chord_field.value),
                       accent=True, width=_ACTION_W),
            self._pill(ft.Icons.DELETE_OUTLINE, "Quitar",
                       lambda _e: self._set_chord(""), width=_ACTION_W),
        ])

        casillas: list[ft.Control] = [
            self._pill(ft.Icons.ADD, "izquierda", lambda _e: self._add_slot(before=True),
                       width=_SLOT_W),
            self._pill(ft.Icons.ADD, "derecha", lambda _e: self._add_slot(before=False),
                       width=_SLOT_W),
        ]
        if not syl.text.strip():          # es una casilla (slot vacío) → se puede quitar
            casillas.append(self._pill(ft.Icons.CLOSE, "casilla",
                                       lambda _e: self._remove_slot(), width=_SLOT_W))

        # `chords_for_key` ya devuelve 10; el corte es una red por si crece.
        suggestions = chords_for_key(sec_key)[:_SUGGESTIONS]

        contenido: list[ft.Control] = [
            ft.Row([acorde, acciones], spacing=14,
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                   vertical_alignment=ft.CrossAxisAlignment.END),
            self._rule("Casilla de paso"),
            ft.Row(casillas, spacing=8, alignment=ft.MainAxisAlignment.END),
        ]
        if suggestions:
            contenido.append(self._rule(f"Sugerencias en {sec_key}"))
            contenido.extend(self._chip_rows(suggestions, current))
        else:
            contenido.append(self._rule("Sin tono: escribe el acorde a mano"))
        self._editor.content = ft.Column(contenido, spacing=10, tight=True)
        _safe_update(self._editor)


# ---------------------------------------------------------------------------
# Editar la letra (re-procesar conservando acordes)
# ---------------------------------------------------------------------------

def _chord_row_for_edit(line) -> tuple[str, str]:
    """(fila_de_acordes, fila_de_letra) para la caja editable: acordes alineados por
    columna encima de la letra, SIN guiones en la letra. Así la letra editable queda
    limpia y, al reparsear, cada acorde vuelve a caer sobre su sílaba."""
    chord_str = ""
    lyric_str = ""
    for syl in line.syllables:
        value = syl.chord.value if syl.chord else ""
        if value:
            if len(chord_str) < len(lyric_str):
                chord_str += " " * (len(lyric_str) - len(chord_str))
            elif chord_str:
                chord_str += " "  # separación mínima entre dos acordes
            chord_str += value
        lyric_str += syl.text
    return chord_str.rstrip(), lyric_str.rstrip()


def reconstruct_lyrics(song: Song) -> str:
    """Texto plano editable de la canción: encabezados [Sección] + líneas de letra.

    La «Introducción» y los **interludios** aparecen como una sección más: sus
    casillas se ven como guiones (``- - - - -``) o como la secuencia de acordes que
    tengan (``G - Bm - A``). Así se pueden ver y editar a mano, y sobre todo NO se
    pierden al reprocesar el texto (antes la Introducción se omitía y editarla no
    tenía efecto). Las líneas de letra con acordes traen una fila de acordes
    alineada encima (estilo Cifra Club): así los acordes viajan en el texto y no se
    pierden al editar una línea, y además se pueden editar a mano.
    """
    out: list[str] = []
    for section in song.sections:
        label = section.label or SECTION_LABELS.get(section.type, "")
        if label:
            out.append(f"[{label}]")
        for line in section.lines:
            if is_chord_line(line):
                # casillas (Introducción / interludio): acordes, o guiones si están vacías
                out.append(chord_line_text(line))
            else:
                # línea de letra: si tiene acordes, su fila de acordes va encima
                chord_row, lyric_row = _chord_row_for_edit(line)
                if chord_row:
                    out.append(chord_row)
                out.append(lyric_row)
        out.append("")
    return "\n".join(out).strip()


class EditLyricsScreen:
    """Editar la letra ya procesada; ``merge_lyrics`` conserva los acordes de las
    líneas que no cambien."""

    def __init__(self, db, song: Song, on_saved: Callable[[int], None],
                 on_back: Callable[[], None]) -> None:
        self.db = db
        self.song = song
        self.on_saved = on_saved
        self.on_back = on_back

        self._author = _themed_field("Autor", song.author or "")
        self._key = _themed_field("Tono (círculo)", song.key or "", width=150)
        self._original_key = _themed_field("Tono original", song.original_key or "", width=150)
        self._rhythm = _themed_field("Ritmo", song.rhythm or "", width=140)
        self._bpm = _themed_field("BPM", str(song.bpm or ""), width=90)
        self._capo = _themed_field("Capo", str(song.capo or 0), width=100)
        self._text = ft.TextField(
            value=reconstruct_lyrics(song), multiline=True, min_lines=8, max_lines=18,
            border=ft.InputBorder.NONE,
            # monoespaciada: para que las filas de acordes queden alineadas sobre la letra
            text_style=ft.TextStyle(font_family=theme.FONT_MONO, size=14),
            color=theme.THEME["text"], cursor_color=theme.THEME["accent"],
            content_padding=ft.Padding.all(14))

    def build(self) -> ft.Control:
        # El botón ← hace de «cancelar»: vuelve sin guardar nada.
        header = centered_header("Editar letra", left=back_button(self.on_back))
        caja = ft.Container(
            bgcolor=theme.THEME["surface"], border_radius=16,
            border=ft.Border.all(1, theme.THEME["border"]),
            content=self._text)
        guardar = _pill_button(ft.Icons.CHECK, "Guardar cambios", self._save)
        body = ft.Column([
            self._author,
            ft.Row([self._key, self._original_key], spacing=10, wrap=True),
            ft.Row([self._rhythm, self._bpm, self._capo], spacing=10),
            ft.Text("Los acordes de las líneas que no cambies se conservan.",
                    size=12, color=theme.THEME["text_muted"]),
            caja,
            _section_insert_row(self._text),
            guardar,
        ], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
        return ft.Column([header, ft.Container(content=body, padding=12, expand=True)],
                         expand=True, spacing=0)

    def _save(self, _e=None) -> None:
        merged = merge_lyrics(self.song, self._text.value or "")
        # Al guardar, la canción siempre queda con la «Introducción» completa (2
        # líneas de 5 casillas), aunque el texto la traiga a medias o no la traiga.
        normalize_intro(merged)
        merged.author = (self._author.value or "").strip() or None
        merged.key = (self._key.value or "").strip() or None
        merged.original_key = (self._original_key.value or "").strip() or None
        merged.rhythm = (self._rhythm.value or "").strip() or None
        merged.bpm = valid_bpm(self._bpm.value)
        merged.capo = self._parse_capo(self._capo.value)
        self.db.save_song(merged)
        self.on_saved(merged.id)

    @staticmethod
    def _parse_capo(value: str | None) -> int:
        """Capo tolerante: vacío o no numérico → 0."""
        try:
            return max(0, int((value or "0").strip()))
        except ValueError:
            return 0
