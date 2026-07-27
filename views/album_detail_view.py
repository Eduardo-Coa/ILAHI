"""Vista propia de un álbum o de un autor, y el selector para sumarles canciones.

Tocar una fila en «Álbumes» ya no filtra la lista en el sitio: abre esta pantalla,
con la misma forma que el detalle de una lista (``views.setlist_view``): ← volver,
el nombre centrado arriba y las canciones debajo. Donde la lista tiene el ▶ de
reproducir, aquí va un ＋ que abre dos caminos:

  · «Nueva canción»     → el formulario de siempre, con el álbum/autor ya puesto.
  · «Elegir existentes» → ``AddToEntryScreen``: le asigna ese álbum/autor a las
                          canciones que se toquen (no las copia: una canción tiene
                          UN álbum y UN autor, así que agregarla la mueve).

El cuerpo con las canciones NO se arma aquí: lo pasa quien crea la pantalla
(``main`` reutiliza ``SongsScreen`` embebida), para no duplicar la fila de canción
ni perder su lista con ventana deslizante, que es lo que hace que un álbum de
cientos de himnos abra rápido.
"""

from __future__ import annotations
from typing import Callable
import flet as ft

import theme
from database.db import author_display
from views.widgets import (accent_fab, back_button, centered_header, list_row_card,
                           sheet_dialog, sheet_option, show_toast, _safe_update,
                           WindowedList, SONG_ROW_HEIGHT, SONG_ROW_EXTENT)
from views.search_field import search_pill

# Nombre de la columna que agrupa, y cómo se llama en pantalla.
_CAMPO = {"album": "album", "autor": "author"}
_ETIQUETA = {"album": "álbum", "autor": "autor"}


def campo_de(tipo: str) -> str:
    """Columna de ``songs`` que agrupa a esa entrada ("album" | "author")."""
    return _CAMPO.get(tipo, "author")


def etiqueta_de(tipo: str) -> str:
    """Cómo se nombra el grupo en los textos de la interfaz."""
    return _ETIQUETA.get(tipo, "autor")


def show_add_to_entry_sheet(page, tipo: str, name: str,
                            on_new: Callable[[], None],
                            on_pick: Callable[[], None]) -> None:
    """Cuadro del ＋: crear una canción nueva en el grupo, o traer una que ya existe."""
    etiqueta = etiqueta_de(tipo)

    def nueva(_e=None) -> None:
        page.pop_dialog()
        on_new()

    def elegir(_e=None) -> None:
        page.pop_dialog()
        on_pick()

    page.show_dialog(sheet_dialog(
        title=f"Agregar a «{author_display(name)}»",
        content_padding=ft.Padding.only(left=8, right=8, bottom=8),
        content=ft.Column(tight=True, spacing=2, controls=[
            sheet_option(ft.Icons.ADD, "Nueva canción",
                         f"Escribe o pega la letra, con el {etiqueta} ya puesto", nueva),
            sheet_option(ft.Icons.LIBRARY_MUSIC, "Elegir existentes",
                         "De las canciones que ya tienes", elegir),
        ]),
    ))


class EntryDetailScreen:
    """Pantalla de un álbum o un autor: ← volver · nombre centrado · canciones · ＋."""

    def __init__(self, tipo: str, name: str, body: ft.Control,
                 on_back: Callable[[], None], on_add: Callable[[], None]) -> None:
        self.tipo = tipo
        self.name = name
        self.body = body                  # cuerpo con las canciones (SongsScreen)
        self.on_back = on_back
        self.on_add = on_add

    def build(self) -> ft.Control:
        columna = ft.Column(expand=True, spacing=0, controls=[
            centered_header(author_display(self.name),
                            left=back_button(self.on_back)),
            self.body,
        ])
        # Donde el detalle de una lista tiene el ▶, aquí va el ＋.
        fab = ft.Container(
            right=18, bottom=24,
            content=accent_fab(
                ft.Icons.ADD,
                f"Agregar canciones a este {etiqueta_de(self.tipo)}",
                lambda _e: self.on_add()))
        return ft.Stack(expand=True, controls=[columna, fab])


class AddToEntryScreen:
    """Selector de canciones para sumar a un álbum o autor.

    Mismo diseño que el selector de una lista (``SongPickerScreen``): ← volver,
    buscador y filas con un ＋ a la derecha. Solo aparecen las que TODAVÍA no
    pertenecen al grupo, y al tocarlas se les asigna en el acto (autosave).
    """

    def __init__(self, db, tipo: str, name: str, on_back: Callable[[], None],
                 page=None) -> None:
        self.db = db
        self.tipo = tipo
        self.name = name
        self.campo = campo_de(tipo)
        self.on_back = on_back
        self.page = page
        self._query = ""
        # Igual que en la biblioteca: solo se arman las filas cercanas a lo que se ve.
        # Con cientos de canciones, construirlas todas congela la pantalla al abrirla
        # y en cada tecla del buscador.
        self._list = ft.ListView(expand=True, controls=[], scroll_interval=50,
                                 build_controls_on_demand=False)
        self._filler = WindowedList(self._list, self._tile,
                                    row_height=SONG_ROW_EXTENT, page=page)
        self._list.on_scroll = self._filler.on_scroll

    def build(self) -> ft.Control:
        header = centered_header(f"Agregar al {etiqueta_de(self.tipo)}",
                                 left=back_button(self.on_back))
        search = search_pill("Buscar canción…", self._on_query, ft.Container(width=2))
        self._refill()
        return ft.Column([header, search, self._list], expand=True, spacing=0)

    def _on_query(self, e) -> None:
        self._query = e.control.value or ""
        self._refill(update=True)

    def _refill(self, update: bool = False, keep_position: bool = False) -> None:
        # Las que ya están en el grupo no vuelven a ofrecerse.
        songs = [s for s in self.db.list_songs(self._query)
                 if (s.get(self.campo) or None) != self.name]
        self._filler.reset(
            songs, keep_position=keep_position,
            empty=ft.Container(padding=20, content=ft.Text(
                "(no hay más canciones para agregar)", color=theme.THEME["text_muted"])))
        if update:
            _safe_update(self._list)

    # -- fila: ♪ · título/autor (o álbum) · ＋ --
    def _tile(self, song: dict) -> ft.Control:
        info = ft.Column([
            ft.Text(song["title"], size=16, weight=ft.FontWeight.W_500,
                    color=theme.THEME["text"], no_wrap=True),
            # Sin autor se cae al ÁLBUM antes que a «Desconocido»: los himnos del
            # cancionero incluido no llevan autor y si no se leerían todos igual.
            ft.Text(song.get("author") or song.get("album") or "Desconocido", size=12,
                    color=theme.THEME["text_muted"], no_wrap=True),
        ], spacing=1, tight=True)
        return list_row_card([
            ft.Container(width=40, alignment=ft.Alignment.CENTER,
                         content=ft.Icon(ft.Icons.MUSIC_NOTE, size=22,
                                         color=theme.THEME["text_muted"])),
            ft.Container(expand=True,
                         padding=ft.Padding.symmetric(horizontal=4, vertical=4),
                         content=info),
            self._add_badge(song),
        ], key=f"pick-{song['id']}", height=SONG_ROW_HEIGHT)

    def _add_badge(self, song: dict) -> ft.Control:
        """Botón ＋ con el diseño del badge de tono (igual que el selector de listas)."""
        return ft.Container(
            width=52, height=52, ink=True,
            border=ft.Border.all(1, theme.THEME["chord"]),
            border_radius=12, bgcolor=theme.THEME["chord_bg"],
            alignment=ft.Alignment.CENTER,
            tooltip=f"Agregar a este {etiqueta_de(self.tipo)}",
            on_click=lambda _e, s=song: self._add(s),
            content=ft.Column([
                ft.Icon(ft.Icons.ADD, size=20, color=theme.THEME["chord"]),
                ft.Text("Agregar", size=8, color=theme.THEME["text_muted"]),
            ], spacing=0, tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )

    def _add(self, song: dict) -> None:
        self.db.set_song_group(song["id"], self.campo, self.name)
        # Solo sale esa fila: rearmar el catálogo entero por cada canción agregada
        # cuesta miles de controles hacia Flutter (ver WindowedList.drop).
        self._filler.drop(lambda s: s["id"] == song["id"])
        _safe_update(self._list)
        if self.page is not None:
            show_toast(self.page, f"✓ «{song['title']}» agregada a «{self.name}»")
