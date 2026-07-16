"""Pantalla de autores: mismo estilo de tarjeta que las canciones.

Ícono de perfil (dorado si el autor es favorito) · nombre · badge con el número
de canciones · menú ⋮ (Editar nombre / Exportar / Favorito / Eliminar).

El autor no es una entidad propia (es un campo de ``songs``): su marca de
favorito vive en la tabla ``author_favorites``, referenciada por nombre.
Eliminar un autor borra **todas sus canciones**, por eso pide confirmación
diciendo cuántas son.
"""

from __future__ import annotations
from typing import Callable
import flet as ft

import theme
from database.db import author_display
from views.bottom_bar import build_bottom_bar
from views.widgets import show_toast, segmented_toggle
from views.search_field import search_pill


class AuthorsScreen:
    """Lista de autores con favorito, renombrar, exportar y eliminar."""

    def __init__(self, page: ft.Page, db,
                 on_open_author: Callable[[str], None],
                 on_back: Callable[[], None],
                 on_export_author: Callable,
                 on_tab: Callable[[str], None] | None = None) -> None:
        self.page = page
        self.db = db
        self.on_open_author = on_open_author      # ver las canciones de ese autor
        self.on_back = on_back
        self.on_export_author = on_export_author  # async: exporta su cancionero
        self.on_tab = on_tab
        self._confirm_delete: str | None = None
        self._query = ""
        self._list = ft.ListView(expand=True, controls=[])

    # ------------------------------------------------------------------
    def build(self) -> ft.Control:
        self._refill(update=False)
        # Mismo header que el inicio: solo el logo (la pestaña «Autores» del toggle
        # ya indica dónde estamos, así que no se repite el título).
        header = ft.Container(
            padding=ft.Padding.only(top=16, bottom=6),
            alignment=ft.Alignment.CENTER,
            content=ft.Image(src=theme.logo(), height=52, fit=ft.BoxFit.CONTAIN),
        )
        # Toggle Autores | Canciones (Autores activa aquí); a «Canciones» vuelve a la
        # biblioteca. Reemplaza al chip y al embudo de filtros.
        search = search_pill("Buscar autor…", self._on_query)
        toggle = segmented_toggle("Autores", "Canciones", active="left",
                                  on_left=lambda: None, on_right=lambda: self.on_back())
        children: list[ft.Control] = [header, search, toggle, self._list]
        if self.on_tab is not None:
            children.append(build_bottom_bar("library", self.on_tab))
        return ft.Column(children, expand=True, spacing=0)

    def _set_status(self, text: str) -> None:
        show_toast(self.page, text)       # confirmación flotante (toast)

    def _on_query(self, e) -> None:
        self._query = (e.control.value or "").strip()
        self._confirm_delete = None
        self._refill(update=True)

    def _refill(self, update: bool = True) -> None:
        authors = self.db.list_authors()
        if self._query:
            needle = self._query.lower()
            authors = [a for a in authors if needle in author_display(a["name"]).lower()]
        if authors:
            self._list.controls = [self._author_tile(a) for a in authors]
        else:
            self._list.controls = [ft.Container(
                key="empty", padding=20, content=ft.Text(
                    "(sin resultados)" if self._query else "(no hay canciones)",
                    color=theme.THEME["text_muted"]))]
        if update:
            _safe_update(self._list)

    # ------------------------------------------------------------------
    # Tarjeta de autor
    # ------------------------------------------------------------------
    def _author_tile(self, author: dict) -> ft.Control:
        name = author["name"]
        if name == self._confirm_delete:
            return self._confirm_tile(author)
        fav = bool(author["favorite"])
        unknown = bool(author.get("unknown"))
        return ft.Container(
            key=f"author-{name}",
            bgcolor=theme.THEME["surface"], border_radius=14,
            padding=ft.Padding.symmetric(horizontal=4, vertical=6),
            margin=ft.Margin.symmetric(horizontal=12, vertical=5),
            content=ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=2,
                controls=[
                    self._avatar(name, fav, unknown),
                    ft.Container(
                        expand=True, ink=True, border_radius=10,
                        on_click=lambda _e: self.on_open_author(name),
                        padding=ft.Padding.symmetric(horizontal=4, vertical=4),
                        content=self._info(name, author["song_count"])),
                    self._menu(name, fav, unknown),
                ],
            ),
        )

    def _info(self, name: str, count: int) -> ft.Control:
        """Mismo formato de tres líneas que la barra de canción: nombre arriba,
        la etiqueta «Canciones:» donde va el autor, y el número donde va el ritmo."""
        return ft.Column([
            ft.Text(author_display(name), size=16, weight=ft.FontWeight.W_500,
                    color=theme.THEME["text"], no_wrap=True),
            ft.Text("Canciones:", size=12, color=theme.THEME["text_muted"],
                    no_wrap=True),
            ft.Row([
                ft.Icon(ft.Icons.LIBRARY_MUSIC_OUTLINED, size=12,
                        color=theme.THEME["text_muted"]),
                ft.Text(str(count), size=11, color=theme.THEME["text_muted"]),
            ], spacing=4, tight=True),
        ], spacing=1, tight=True)

    def _avatar(self, name: str, fav: bool, unknown: bool = False) -> ft.Control:
        """Ícono de perfil; dorado si es favorito. Tocarlo alterna el favorito.

        «Desconocido» no es un autor real, así que su ícono es estático (no se
        puede marcar como favorito).
        """
        if unknown:
            return ft.Container(
                width=48, height=48, alignment=ft.Alignment.CENTER,
                content=ft.Icon(ft.Icons.PERSON_OFF_OUTLINED, size=22,
                                color=theme.THEME["text_muted"]))
        return ft.IconButton(
            icon=ft.Icons.PERSON if fav else ft.Icons.PERSON_OUTLINE,
            icon_color=theme.THEME["accent"] if fav else theme.THEME["text_muted"],
            icon_size=22,
            tooltip="Quitar de favoritos" if fav else "Añadir a favoritos",
            on_click=lambda _e: self._toggle_favorite(name, not fav))

    def _menu(self, name: str, fav: bool, unknown: bool = False) -> ft.Control:
        # «Desconocido» no se puede renombrar ni marcar favorito (no es un autor);
        # sí exportar sus canciones y eliminarlas.
        if unknown:
            items = [
                ft.PopupMenuItem(content="Exportar", icon=ft.Icons.UPLOAD,
                                 on_click=self._export_handler(name)),
                ft.PopupMenuItem(content="Eliminar", icon=ft.Icons.DELETE,
                                 on_click=lambda _e: self._ask_delete(name)),
            ]
        else:
            items = [
                ft.PopupMenuItem(content="Editar nombre", icon=ft.Icons.EDIT,
                                 on_click=lambda _e: self._ask_rename(name)),
                ft.PopupMenuItem(content="Exportar", icon=ft.Icons.UPLOAD,
                                 on_click=self._export_handler(name)),
                ft.PopupMenuItem(
                    content="Quitar de favoritos" if fav else "Añadir a favoritos",
                    icon=ft.Icons.STAR_BORDER if fav else ft.Icons.STAR,
                    on_click=lambda _e: self._toggle_favorite(name, not fav)),
                ft.PopupMenuItem(content="Eliminar", icon=ft.Icons.DELETE,
                                 on_click=lambda _e: self._ask_delete(name)),
            ]
        return ft.PopupMenuButton(icon=ft.Icons.MORE_VERT,
                                  icon_color=theme.THEME["text_muted"], items=items)

    def _export_handler(self, name: str):
        async def handler(_e=None):
            self._set_status(await self.on_export_author(name))
        return handler

    def _confirm_tile(self, author: dict) -> ft.Control:
        """Eliminar un autor borra sus canciones: se dice cuántas."""
        name = author["name"]
        n = author["song_count"]
        if author.get("unknown"):
            pregunta = (f"¿Eliminar la canción sin autor?" if n == 1
                        else f"¿Eliminar las {n} canciones sin autor?")
        else:
            cuantas = "su única canción" if n == 1 else f"sus {n} canciones"
            pregunta = f"¿Eliminar «{name}» y {cuantas}?"
        return ft.Container(
            key=f"confirm-{name}",
            bgcolor=theme.THEME["surface"], border_radius=14,
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            margin=ft.Margin.symmetric(horizontal=12, vertical=5),
            content=ft.Column(spacing=6, controls=[
                ft.Text(pregunta, size=14, color=theme.THEME["danger"]),
                ft.Row(alignment=ft.MainAxisAlignment.END, tight=True, controls=[
                    ft.TextButton("Sí, eliminar", on_click=lambda _e: self._do_delete(name)),
                    ft.TextButton("No", on_click=lambda _e: self._cancel_delete()),
                ]),
            ]),
        )

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def _toggle_favorite(self, name: str, value: bool) -> None:
        self.db.set_author_favorite(name, value)
        self._refill(update=True)      # reordena: los favoritos suben

    def _ask_delete(self, name: str) -> None:
        self._confirm_delete = name
        self._refill(update=True)

    def _cancel_delete(self) -> None:
        self._confirm_delete = None
        self._refill(update=True)

    def _do_delete(self, name: str) -> None:
        deleted = self.db.delete_author(name)
        self._confirm_delete = None
        self._refill(update=True)
        self._set_status(f"✓ Eliminadas {deleted} canción(es) de «{author_display(name)}»")

    def _ask_rename(self, name: str) -> None:
        """Diálogo con esquinas redondeadas para escribir el nombre nuevo."""
        field = ft.TextField(value=name, autofocus=True, dense=True,
                             border_color=theme.THEME["border"],
                             focused_border_color=theme.THEME["accent"],
                             color=theme.THEME["text"])

        def save(_e=None) -> None:
            new = (field.value or "").strip()
            self.page.pop_dialog()
            if not new or new == name:
                return
            self.db.rename_author(name, new)
            self._refill(update=True)
            self._set_status(f"✓ Autor renombrado a «{new}»")

        dialog = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=18),
            bgcolor=theme.THEME["surface2"],
            title=ft.Text("Editar nombre", color=theme.THEME["text"]),
            content=field,
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _e: self.page.pop_dialog()),
                ft.TextButton("Guardar", on_click=save),
            ],
        )
        field.on_submit = save
        self.page.show_dialog(dialog)


def _safe_update(control: ft.Control) -> None:
    """Repinta un control; ignora el caso «aún no está en la página»."""
    try:
        control.update()
    except Exception:
        pass
