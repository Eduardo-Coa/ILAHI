"""Pantalla de canciones: tarjetas con favorito (★), autor, ritmo, badge de tono y
menú ⋮ (Editar / Exportar / Favorito / Eliminar). Buscador, nueva e importar/exportar.

Abajo, una barra de navegación con 4 pestañas: Biblioteca · Favoritos · Listas ·
Ajustes. «Ajustes» todavía no tiene vista (marcador de posición).

Usa **íconos Material de Flet** (no glifos Unicode) porque renderizan garantizado
en Android.
"""

from __future__ import annotations
from typing import Callable
import flet as ft

import theme
from views.bottom_bar import TABS as _TABS, build_bottom_bar, fill_bar
from views.search_field import search_pill, filter_chip
from views.widgets import sheet_option as _sheet_option, show_toast, segmented_toggle
from database.db import author_display


class SongsScreen:
    """Lista de canciones con buscador, favoritos y acciones por canción."""

    def __init__(self, page: ft.Page, db, on_open_song: Callable[[int], None],
                 on_open_setlists: Callable[[], None],
                 on_import: Callable, on_export_all: Callable,
                 on_new_song: Callable[[], None],
                 on_edit_song: Callable[[int], None],
                 on_export_song: Callable,
                 on_open_authors: Callable[[], None],
                 on_open_settings: Callable[[], None] | None = None,
                 status: str = "", tab: str = "library",
                 author: str | None = None) -> None:
        self.page = page
        self.db = db
        self.on_open_song = on_open_song
        self.on_open_setlists = on_open_setlists
        self.on_import = on_import              # async: elige archivo e importa
        self.on_export_all = on_export_all      # async: exporta todo como cancionero
        self.on_new_song = on_new_song          # formulario de nueva canción
        self.on_edit_song = on_edit_song        # abre el editor de acordes
        self.on_export_song = on_export_song    # async: exporta esa canción sola
        self.on_open_authors = on_open_authors  # lista de autores (filtro)
        self.on_open_settings = on_open_settings  # pantalla de ajustes
        self.status = status
        self._tab = tab                         # "library" | "favorites"
        self._author = author                   # filtro activo por autor
        self._query = ""
        self._confirm_delete_id: int | None = None
        self._list = ft.ListView(expand=True, controls=[])
        self._bar = ft.Row(spacing=0)

    # ------------------------------------------------------------------
    def build(self) -> ft.Control:
        self._refill(update=False)
        header = ft.Container(
            padding=ft.Padding.only(top=16, bottom=6),
            alignment=ft.Alignment.CENTER,          # logo centrado
            content=ft.Image(src="ilahi-logo.png", height=52,
                             fit=ft.BoxFit.CONTAIN),
        )
        children: list[ft.Control] = [header, self._author_chip()]
        children.append(self._search_field())
        children.append(self._toggle())          # Autores | Canciones, bajo la búsqueda
        children.append(self._list)
        children.append(self._bottom_bar())
        column = ft.Column(children, expand=True, spacing=0)
        # El ＋ flota sobre la lista, justo encima de la barra inferior.
        return ft.Stack(expand=True, controls=[column, self._fab()])

    # ------------------------------------------------------------------
    # Filtro por autor
    # ------------------------------------------------------------------
    def _author_chip(self) -> ft.Control:
        """Muestra el filtro activo por autor y permite quitarlo."""
        self._chip_box = filter_chip(
            author_display(self._author) if self._author else "",
            self._clear_author, visible=bool(self._author))
        self._chip_label = self._chip_box.content.controls[1]
        # Alineado a la izquierda: sin esto el chip ocuparía todo el ancho.
        return ft.Row([self._chip_box], tight=True)

    def _clear_author(self) -> None:
        self._author = None
        self._chip_box.visible = False
        self._safe_update(self._chip_box)
        self._refill(update=True)

    def _search_field(self) -> ft.Control:
        """Buscador tipo píldora (el filtro por autor ahora vive en el toggle)."""
        return search_pill("Buscar himno o autor…", self._on_query)

    def _toggle(self) -> ft.Control:
        """Barra Autores | Canciones (Canciones activa aquí); a Autores → su pantalla."""
        return segmented_toggle(
            "Autores", "Canciones", active="right",
            on_left=lambda: self.on_open_authors(), on_right=lambda: None)

    # ------------------------------------------------------------------
    # Botón ＋ (nueva / importar / exportar)
    # ------------------------------------------------------------------
    def _fab(self) -> ft.Control:
        """FAB flotante abajo a la derecha, por encima de la barra inferior."""
        return ft.Container(
            right=18, bottom=90,
            content=ft.FloatingActionButton(
                icon=ft.Icons.ADD, tooltip="Añadir",
                bgcolor=theme.THEME["accent"], foreground_color=theme.THEME["bg"],
                shape=ft.RoundedRectangleBorder(radius=18),
                on_click=lambda _e: self._open_add_sheet()),
        )

    def _open_add_sheet(self) -> None:
        """Cuadro con esquinas redondeadas: nueva canción, importar, exportar."""
        async def do_import(_e=None) -> None:
            self.page.pop_dialog()
            await self.on_import()

        async def do_export_all(_e=None) -> None:
            self.page.pop_dialog()
            await self.on_export_all()

        def do_new(_e=None) -> None:
            self.page.pop_dialog()
            self.on_new_song()

        dialog = ft.AlertDialog(
            modal=False,
            shape=ft.RoundedRectangleBorder(radius=20),
            bgcolor=theme.THEME["surface2"],
            title=ft.Text("Añadir", size=18, weight=ft.FontWeight.BOLD,
                          color=theme.THEME["text"]),
            content_padding=ft.Padding.only(left=8, right=8, bottom=8),
            content=ft.Column(tight=True, spacing=2, controls=[
                _sheet_option(ft.Icons.ADD, "Nueva canción",
                              "Escribe o pega la letra", do_new),
                _sheet_option(ft.Icons.DOWNLOAD, "Importar…",
                              "Una canción o un cancionero .hymnchords", do_import),
                _sheet_option(ft.Icons.UPLOAD, "Exportar biblioteca",
                              "Todas tus canciones en un archivo", do_export_all),
            ]),
        )
        self.page.show_dialog(dialog)

    # ------------------------------------------------------------------
    # Barra inferior de navegación
    # ------------------------------------------------------------------
    def _bottom_bar(self) -> ft.Control:
        """Biblioteca · Favoritos · Listas · Ajustes, anclada abajo."""
        return build_bottom_bar(self._tab, self._select_tab, row=self._bar)

    def _select_tab(self, key: str) -> None:
        """Listas navega fuera; Ajustes aún no tiene vista."""
        if key == "setlists":
            self.on_open_setlists()
            return
        if key == "settings":
            if self.on_open_settings is not None:
                self.on_open_settings()
            else:
                self._set_status("Ajustes: próximamente")
            return
        if key == self._tab:
            return
        self._tab = key
        self._confirm_delete_id = None
        self._set_status("")
        self._refill(update=True)
        fill_bar(self._bar, self._tab, self._select_tab)
        self._safe_update(self._bar)

    def _set_status(self, status: str) -> None:
        self.status = status
        show_toast(self.page, status)     # confirmación flotante (toast)

    def _safe_update(self, control: ft.Control) -> None:
        """Repinta un control; ignora el caso «aún no está en la página»."""
        try:
            control.update()
        except Exception:
            pass

    def _on_query(self, e) -> None:
        self._query = e.control.value or ""
        self._confirm_delete_id = None
        self._refill(update=True)

    def _empty_message(self) -> str:
        if self._tab == "favorites" and not self._query:
            return "Aún no tienes favoritos. Toca la ♪ de una canción."
        if self._author:
            return f"(«{author_display(self._author)}» no tiene canciones que coincidan)"
        return "(sin resultados)"

    def _refill(self, update: bool = True) -> None:
        filters = {"author": self._author} if self._author else None
        songs = self.db.list_songs(self._query, filters)   # favoritos primero
        if self._tab == "favorites":
            songs = [s for s in songs if s["favorite"]]
        if songs:
            self._list.controls = [self._song_tile(s) for s in songs]
        else:
            self._list.controls = [ft.Container(
                key="empty", padding=20,
                content=ft.Text(self._empty_message(), color=theme.THEME["text_muted"]))]
        if update:
            self._safe_update(self._list)

    # ------------------------------------------------------------------
    # Tarjeta de canción
    # ------------------------------------------------------------------
    def _song_tile(self, song: dict) -> ft.Control:
        sid = song["id"]
        if sid == self._confirm_delete_id:
            return self._confirm_tile(song)
        fav = bool(song.get("favorite"))
        # `key` estable: sin ella Flet reconcilia los hijos por posición y, al
        # cambiar el largo de la lista (p. ej. Biblioteca → Favoritos), reutiliza
        # controles de otra canción arrastrando sus handlers.
        return ft.Container(
            key=f"song-{sid}",
            bgcolor=theme.THEME["surface"], border_radius=14,
            padding=ft.Padding.symmetric(horizontal=4, vertical=6),
            margin=ft.Margin.symmetric(horizontal=12, vertical=5),
            content=ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=2,
                controls=[
                    self._star(sid, fav),
                    ft.Container(
                        expand=True, ink=True, border_radius=10,
                        on_click=lambda _e: self.on_open_song(sid),
                        padding=ft.Padding.symmetric(horizontal=4, vertical=4),
                        content=self._info(song)),
                    self._key_badge(song.get("key")),
                    self._menu(sid, fav),
                ],
            ),
        )

    def _star(self, sid: int, fav: bool) -> ft.Control:
        """★ si es favorita, ♪ si no. Tocarla alterna el favorito."""
        return ft.IconButton(
            icon=ft.Icons.STAR if fav else ft.Icons.MUSIC_NOTE,
            icon_color=theme.THEME["accent"] if fav else theme.THEME["text_muted"],
            icon_size=22,
            tooltip="Quitar de favoritos" if fav else "Marcar favorito",
            on_click=lambda _e: self._toggle_favorite(sid, not fav))

    def _info(self, song: dict) -> ft.Control:
        """Título, autor (o «Desconocido») y ritmo."""
        return ft.Column([
            ft.Text(song["title"], size=16, weight=ft.FontWeight.W_500,
                    color=theme.THEME["text"], no_wrap=True),
            ft.Text(song.get("author") or "Desconocido", size=12,
                    color=theme.THEME["text_muted"], no_wrap=True),
            ft.Row([
                ft.Icon(ft.Icons.GRAPHIC_EQ, size=12, color=theme.THEME["text_muted"]),
                ft.Text(song.get("rhythm") or "—", size=11,
                        color=theme.THEME["text_muted"]),
            ], spacing=4, tight=True),
        ], spacing=1, tight=True)

    def _key_badge(self, key: str | None) -> ft.Control:
        """Badge redondeado con el tono de la canción."""
        return ft.Container(
            width=52, height=52,
            border=ft.Border.all(1, theme.THEME["chord"]),
            border_radius=12, bgcolor=theme.THEME["chord_bg"],
            alignment=ft.Alignment.CENTER,
            content=ft.Column([
                ft.Text(key or "—", size=17, weight=ft.FontWeight.BOLD,
                        color=theme.THEME["chord"]),
                ft.Text("Tono", size=8, color=theme.THEME["text_muted"]),
            ], spacing=0, tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )

    def _menu(self, sid: int, fav: bool) -> ft.Control:
        return ft.PopupMenuButton(
            icon=ft.Icons.MORE_VERT, icon_color=theme.THEME["text_muted"],
            items=[
                ft.PopupMenuItem(content="Editar", icon=ft.Icons.EDIT,
                                 on_click=lambda _e: self.on_edit_song(sid)),
                ft.PopupMenuItem(content="Exportar", icon=ft.Icons.UPLOAD,
                                 on_click=self._export_handler(sid)),
                ft.PopupMenuItem(
                    content="Quitar de favoritos" if fav else "Marcar favorito",
                    icon=ft.Icons.STAR_BORDER if fav else ft.Icons.STAR,
                    on_click=lambda _e: self._toggle_favorite(sid, not fav)),
                ft.PopupMenuItem(content="Eliminar", icon=ft.Icons.DELETE,
                                 on_click=lambda _e: self._ask_delete(sid)),
            ])

    def _export_handler(self, sid: int):
        """Handler async para el ítem «Exportar» del menú."""
        async def handler(_e=None):
            await self.on_export_song(sid)
        return handler

    def _confirm_tile(self, song: dict) -> ft.Control:
        sid = song["id"]
        return ft.Container(
            key=f"confirm-{sid}",
            bgcolor=theme.THEME["surface"], border_radius=14,
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            margin=ft.Margin.symmetric(horizontal=12, vertical=5),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text(f"¿Eliminar «{song['title']}»?", size=14,
                            color=theme.THEME["danger"], no_wrap=True, expand=True),
                    ft.Row([
                        ft.TextButton("Sí, eliminar", on_click=lambda _e: self._do_delete(sid)),
                        ft.TextButton("No", on_click=lambda _e: self._cancel_delete()),
                    ], tight=True),
                ],
            ),
        )

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def _toggle_favorite(self, sid: int, value: bool) -> None:
        self.db.set_favorite(sid, value)
        self._refill(update=True)      # reordena: los favoritos suben

    def _ask_delete(self, sid: int) -> None:
        self._confirm_delete_id = sid
        self._refill(update=True)

    def _cancel_delete(self) -> None:
        self._confirm_delete_id = None
        self._refill(update=True)

    def _do_delete(self, sid: int) -> None:
        self.db.delete_song(sid)
        self._confirm_delete_id = None
        self._refill(update=True)
