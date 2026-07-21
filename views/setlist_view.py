"""Pantallas de listas (setlists) — Fase 4/4b.

- ``build_setlists``: índice de listas (+ crear nueva).
- ``SetlistDetailScreen``: detalle con modos TOCAR y EDITAR (renombrar, quitar, fijar
  tono, y **arrastrar para reordenar** con ``ReorderableListView``). Autosave.
- ``SongPickerScreen``: selector para agregar canciones, con **buscador** y **filtro
  por artista** (``ft.Dropdown``).
"""

from __future__ import annotations
from typing import Callable
import flet as ft

from models.setlist import SetlistItem
from models.transposer import transpose_chord, transpose_song
from views.bottom_bar import build_bottom_bar
from views.widgets import (centered_header, back_button, square_button, show_toast,
                           logo_header, _safe_update, key_badge, accent_fab,
                           confirm_dialog, list_row_card, FAB_CLEARANCE)
from views.search_field import search_pill
import theme


# ---------------------------------------------------------------------------
# Índice de listas
# ---------------------------------------------------------------------------

def _setlist_tile(setlist: dict, on_open: Callable[[int], None],
                  menu: ft.Control | None = None) -> ft.Control:
    """Barra de lista con el mismo formato y dimensiones que la de canción/autor:
    ícono a la izquierda · info de tres líneas (nombre · «Canciones:» · número) · ⋮."""
    n = setlist.get("song_count", 0)
    controls: list[ft.Control] = [
        # Ícono de lista (como el ♪ de canciones y el perfil de autores).
        ft.Container(width=48, height=48, alignment=ft.Alignment.CENTER,
                     content=ft.Icon(ft.Icons.QUEUE_MUSIC, size=22,
                                     color=theme.THEME["accent"])),
        ft.Container(
            expand=True, ink=True, border_radius=10,
            on_click=lambda _e: on_open(setlist["id"]),
            padding=ft.Padding.symmetric(horizontal=4, vertical=4),
            content=ft.Column([
                ft.Text(setlist["name"], size=16, weight=ft.FontWeight.W_500,
                        color=theme.THEME["text"], no_wrap=True),
                ft.Text("Canciones:", size=12, color=theme.THEME["text_muted"],
                        no_wrap=True),
                ft.Row([
                    ft.Icon(ft.Icons.LIBRARY_MUSIC_OUTLINED, size=12,
                            color=theme.THEME["text_muted"]),
                    ft.Text(str(n), size=11, color=theme.THEME["text_muted"]),
                ], spacing=4, tight=True),
            ], spacing=1, tight=True)),
    ]
    if menu is not None:            # ⋮ con opciones (editar nombre / eliminar)
        controls.append(menu)
    return list_row_card(controls, key=f"setlist-{setlist['id']}")


def _setlist_menu(setlist: dict, page, db, refresh) -> ft.Control | None:
    """Menú ⋮ de una lista: editar nombre / eliminar (con confirmación)."""
    if page is None or db is None or refresh is None:
        return None
    sid, name = setlist["id"], setlist["name"]

    def ask_rename(_e=None) -> None:
        field = ft.TextField(value=name, autofocus=True, dense=True,
                             border_color=theme.THEME["border"],
                             focused_border_color=theme.THEME["accent"],
                             color=theme.THEME["text"])

        def save(_e2=None) -> None:
            nuevo = (field.value or "").strip()
            page.pop_dialog()
            if not nuevo or nuevo == name:
                return
            setlist_obj = db.load_setlist(sid)
            setlist_obj.name = nuevo
            db.save_setlist(setlist_obj)          # conserva las canciones
            refresh(f"✓ Lista renombrada a «{nuevo}»")

        field.on_submit = save
        page.show_dialog(confirm_dialog(
            "Editar nombre", field,
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _e: page.pop_dialog()),
                ft.TextButton("Guardar", on_click=save),
            ]))

    def ask_delete(_e=None) -> None:
        def do_delete(_e2=None) -> None:
            page.pop_dialog()
            db.delete_setlist(sid)
            refresh(f"✓ Lista «{name}» eliminada")

        page.show_dialog(confirm_dialog(
            "Eliminar lista",
            ft.Text(f"¿Eliminar la lista «{name}»? Las canciones no se borran.",
                    color=theme.THEME["text_muted"]),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _e: page.pop_dialog()),
                ft.TextButton("Eliminar", on_click=do_delete),
            ]))

    return ft.PopupMenuButton(
        icon=ft.Icons.MORE_VERT, icon_color=theme.THEME["text_muted"],
        items=[
            ft.PopupMenuItem(content="Editar nombre", icon=ft.Icons.EDIT,
                             on_click=ask_rename),
            ft.PopupMenuItem(content="Eliminar", icon=ft.Icons.DELETE,
                             on_click=ask_delete),
        ])


def build_setlists(setlists: list[dict], on_open: Callable[[int], None],
                   on_back: Callable[[], None], on_new: Callable[[], None],
                   on_tab: Callable[[str], None] | None = None,
                   status: str = "", page=None, db=None,
                   refresh: Callable[[str], None] | None = None,
                   embedded: bool = False, external_search: bool = False,
                   query: str = "") -> ft.Control:
    """Índice de listas + botón para crear una nueva + barra inferior.

    ``page``/``db``/``refresh`` habilitan el menú ⋮ por lista (editar nombre /
    eliminar); ``refresh(status)`` vuelve a construir la vista tras un cambio.
    ``embedded``: dentro del shell, el logo y el ＋ los fija el shell (aquí se
    omiten). ``external_search``: el buscador también es del shell; el filtro llega
    en ``query`` y aquí no se dibuja la píldora.
    """
    # Aire abajo para que el ＋ flotante no tape la última lista.
    lv = ft.ListView(expand=True, controls=[],
                     padding=ft.Padding.only(bottom=FAB_CLEARANCE))

    def render(query: str = "") -> None:
        needle = (query or "").strip().lower()
        matches = [s for s in setlists if needle in s["name"].lower()] if needle else setlists
        if matches:
            lv.controls = [
                _setlist_tile(s, on_open, _setlist_menu(s, page, db, refresh))
                for s in matches
            ]
        else:
            lv.controls = [ft.Container(padding=20, content=ft.Text(
                "(sin resultados)" if needle
                else "(no hay listas — crea una con el botón ＋)",
                color=theme.THEME["text_muted"]))]
        _safe_update(lv)

    render(query)                        # filtro inicial (del buscador fijo, si lo hay)

    # Las confirmaciones se muestran como toast flotante (ver ``show_toast``), no
    # inline; ``status`` se mantiene por compatibilidad de firma.
    children: list[ft.Control] = []
    if not embedded:                     # embebida: el logo lo fija el shell
        children.append(logo_header())
    if not external_search:              # embebida: el buscador fijo lo pone el shell
        children.append(search_pill("Buscar lista…",
                                    lambda e: render(e.control.value or "")))
    children.append(lv)
    if on_tab is not None:
        children.append(build_bottom_bar("setlists", on_tab))
    column = ft.Column(children, expand=True, spacing=0)
    if embedded:                         # embebida: el ＋ es fijo y lo pone el shell
        return column

    # FAB «＋» dorado, igual al de «nueva canción» del inicio; crea una lista nueva.
    fab = ft.Container(
        right=18, bottom=90 if on_tab is not None else 24,
        content=accent_fab(ft.Icons.ADD, "Nueva lista", lambda _e: on_new()),
    )
    return ft.Stack(expand=True, controls=[column, fab])


# ---------------------------------------------------------------------------
# Detalle de lista: canciones (estilo biblioteca) + agregar (＋) + reproducir (▶)
# ---------------------------------------------------------------------------

class SetlistDetailScreen:
    """Detalle de una lista: ← volver · título centrado · ＋ agregar (arriba dcha) ·
    filas estilo biblioteca (autor, ritmo y badge de tono) · ▶ reproducir (abajo
    dcha). Reordenar: mantener presionada una canción y arrastrarla (el hueco marca
    dónde caerá). Quitar: en el ⋮ de la fila. Autosave en cada cambio.

    Sin modo edición: renombrar/eliminar la lista viven en el ⋮ del índice."""

    def __init__(self, db, setlist, on_back: Callable[[], None],
                 on_play_item: Callable[[object, int], None],
                 on_add: Callable[[int], None],
                 on_deleted: Callable[[], None], editing: bool = False,
                 on_present: Callable[[object, int], None] | None = None,
                 page=None) -> None:
        self.db = db
        self.setlist = setlist
        self.on_back = on_back
        self.on_play_item = on_play_item      # tocar una fila → vista de canción
        self.on_present = on_present          # ▶ → escenario a pantalla completa
        self.on_add = on_add
        self.on_deleted = on_deleted          # (compat) eliminar la lista es del índice
        self.page = page                      # para toasts y el diálogo de reemplazar
        self._root = ft.Column([], expand=True, spacing=0)
        self._stack = ft.Stack(expand=True, controls=[self._root])

    def build(self) -> ft.Control:
        self._root.controls = [self._header(), self._build_list()]
        self._stack.controls = self._stack_children()
        return self._stack

    def _rebuild(self) -> None:
        self._root.controls = [self._header(), self._build_list()]
        self._stack.controls = self._stack_children()
        _safe_update(self._stack)

    def _stack_children(self) -> list[ft.Control]:
        # El ▶ solo se agrega si hay canciones; nunca metemos un contenedor vacío al
        # Stack (eso taparía y bloquearía los clics del encabezado).
        children: list[ft.Control] = [self._root]
        play = self._play_fab()
        if play is not None:
            children.append(play)
        return children

    def _save(self) -> None:
        for i, it in enumerate(self.setlist.items):
            it.position = i
        self.db.save_setlist(self.setlist)

    # -- encabezado: ← volver · título centrado · ＋ agregar (arriba a la derecha) --
    def _header(self) -> ft.Control:
        agregar = square_button(ft.Icons.ADD, "Agregar canciones",
                                lambda: self.on_add(self.setlist.id))
        return centered_header(self.setlist.name,
                               left=back_button(self.on_back), right=agregar)

    # -- lista de canciones (estilo biblioteca) con arrastre por mantener-presionado --
    def _build_list(self) -> ft.Control:
        items = self.setlist.items
        if not items:
            return ft.Container(padding=24, expand=True, content=ft.Text(
                "(lista vacía — toca ＋ arriba para agregar canciones)",
                color=theme.THEME["text_muted"]))
        # ReorderableListView: en el teléfono se mantiene presionada la fila para
        # arrastrarla y el hueco muestra dónde va a caer (ayuda visual integrada).
        return ft.ReorderableListView(
            expand=True, on_reorder=self._on_reorder,
            show_default_drag_handles=True, spacing=0,
            padding=ft.Padding.only(top=4, bottom=FAB_CLEARANCE),
            controls=[self._song_tile(i, it) for i, it in enumerate(items)])

    def _song_tile(self, i: int, item: SetlistItem) -> ft.Control:
        # El badge muestra el tono con el que va a sonar (tono + transposición fija).
        key = item.key
        if key and item.transpose:
            key = transpose_chord(key, item.transpose)
        info = ft.Column([
            ft.Text(item.title, size=16, weight=ft.FontWeight.W_500,
                    color=theme.THEME["text"], no_wrap=True),
            ft.Text(item.author or "Desconocido", size=12,
                    color=theme.THEME["text_muted"], no_wrap=True),
            ft.Row([
                ft.Icon(ft.Icons.GRAPHIC_EQ, size=12, color=theme.THEME["text_muted"]),
                ft.Text(item.rhythm or "—", size=11, color=theme.THEME["text_muted"]),
            ], spacing=4, tight=True),
        ], spacing=1, tight=True)
        return list_row_card([
            # ♪ (sin favorito) — solo indica que es una canción
            ft.Container(width=40, alignment=ft.Alignment.CENTER,
                         content=ft.Icon(ft.Icons.MUSIC_NOTE, size=22,
                                         color=theme.THEME["text_muted"])),
            ft.Container(
                expand=True, ink=True, border_radius=10,
                on_click=lambda _e, k=i: self.on_play_item(self.setlist, k),
                padding=ft.Padding.symmetric(horizontal=4, vertical=4),
                content=info),
            key_badge(key),
            self._song_menu(i),
        ], key=str(id(item)))                     # clave estable para reordenar

    def _song_menu(self, i: int) -> ft.Control:
        """⋮ de cada fila: reemplazar el original (si el tono difiere) · quitar."""
        opciones: list[ft.Control] = []
        # La canción de la lista es una COPIA con su propio tono; si difiere del
        # original, se puede volcar ese tono a la canción original.
        if self.setlist.items[i].transpose and self.page is not None:
            opciones.append(ft.PopupMenuItem(
                content="Reemplazar original", icon=ft.Icons.PUBLISHED_WITH_CHANGES,
                on_click=lambda _e, k=i: self._ask_replace(k)))
        opciones.append(ft.PopupMenuItem(
            content="Quitar de la lista", icon=ft.Icons.PLAYLIST_REMOVE,
            on_click=lambda _e, k=i: self._remove(k)))
        return ft.PopupMenuButton(icon=ft.Icons.MORE_VERT,
                                  icon_color=theme.THEME["text_muted"], items=opciones)

    def _ask_replace(self, i: int) -> None:
        """Confirma volcar el tono de la copia a la canción original (destructivo)."""
        item = self.setlist.items[i]

        def do_replace(_e=None) -> None:
            self.page.pop_dialog()
            song = transpose_song(self.db.load_song(item.song_id), item.transpose)
            self.db.save_song(song)          # la canción original queda en este tono
            item.key = song.key              # el badge pasa a mostrar el tono nuevo
            item.transpose = 0               # la copia ya coincide con el original
            self._save()
            self._rebuild()
            show_toast(self.page, f"✓ Original de «{item.title}» actualizado al tono de la lista")

        self.page.show_dialog(confirm_dialog(
            "Reemplazar original",
            ft.Text(
                f"El tono de «{item.title}» en esta lista pasará a ser el de la canción "
                "original (cambia la canción en toda la app). ¿Continuar?",
                color=theme.THEME["text_muted"]),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _e: self.page.pop_dialog()),
                ft.TextButton("Reemplazar", on_click=do_replace),
            ]))

    # -- ▶ reproducir la lista (esquina inferior derecha, color del ＋) --
    def _play_fab(self) -> ft.Control | None:
        if not self.setlist.items:
            return None
        # ▶ lanza el escenario a pantalla completa desde la 1ª canción.
        reproducir = self.on_present or self.on_play_item
        return ft.Container(
            right=18, bottom=24,
            content=accent_fab(ft.Icons.PLAY_ARROW, "Reproducir la lista (escenario)",
                               lambda _e: reproducir(self.setlist, 0)),
        )

    # -- acciones --
    def _on_reorder(self, e) -> None:
        item = self.setlist.items.pop(e.old_index)
        self.setlist.items.insert(e.new_index, item)
        self._save()
        self._rebuild()

    def _remove(self, i: int) -> None:
        del self.setlist.items[i]
        self._save()
        self._rebuild()


# ---------------------------------------------------------------------------
# Selector de canciones (buscador + filtro por artista)
# ---------------------------------------------------------------------------

class SongPickerScreen:
    """Selector de canciones para agregar a una lista, con el diseño de la biblioteca.

    ← volver · título centrado · barra de búsqueda y barra de artista tipo píldora ·
    filas como el inicio (sin favorito ni ritmo) con un ＋ (badge) para agregar. Se
    pueden agregar varias antes de volver."""

    def __init__(self, db, setlist_id: int, on_back: Callable[[], None],
                 page=None) -> None:
        self.db = db
        self.setlist_id = setlist_id
        self.on_back = on_back
        self.page = page
        self._query = ""
        self._author = ""            # "" = todos los artistas
        # Canciones que ya están en la lista: no vuelven a aparecer como opción.
        self._in_list = {it.song_id for it in db.load_setlist(setlist_id).items}
        self._artist_label = ft.Text("Todos los artistas", size=15, expand=True,
                                     no_wrap=True, color=theme.THEME["text"])
        self._list = ft.ListView(expand=True, controls=[])

    def build(self) -> ft.Control:
        header = centered_header("Agregar canciones", left=back_button(self.on_back))
        search = search_pill("Buscar canción…", self._on_query, ft.Container(width=2))
        self._refill()
        return ft.Column([header, search, self._artist_bar(), self._list],
                         expand=True, spacing=0)

    # -- barra de artista (mismo diseño de píldora que la búsqueda) --
    def _artist_bar(self) -> ft.Control:
        items = [ft.PopupMenuItem(content="Todos los artistas",
                                  on_click=lambda _e: self._set_author(""))]
        items += [ft.PopupMenuItem(content=a, on_click=lambda _e, a=a: self._set_author(a))
                  for a in self.db.distinct_values("author")]
        return ft.Container(
            margin=ft.Margin.only(left=12, right=12, bottom=6),
            padding=ft.Padding.only(left=16, right=6),
            bgcolor=theme.THEME["surface"], border_radius=28,
            border=ft.Border.all(1, theme.THEME["border"]),
            content=ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8,
                controls=[
                    ft.Icon(ft.Icons.PERSON_OUTLINE, size=20,
                            color=theme.THEME["text_muted"]),
                    self._artist_label,
                    ft.PopupMenuButton(icon=ft.Icons.ARROW_DROP_DOWN,
                                       icon_color=theme.THEME["text_muted"],
                                       tooltip="Filtrar por artista", items=items),
                ],
            ),
        )

    def _set_author(self, author: str) -> None:
        self._author = author
        self._artist_label.value = author or "Todos los artistas"
        _safe_update(self._artist_label)
        self._refill(update=True)

    def _on_query(self, e) -> None:
        self._query = e.control.value or ""
        self._refill(update=True)

    def _refill(self, update: bool = False) -> None:
        filters = {"author": self._author} if self._author else None
        # Excluir las que ya están en la lista.
        songs = [s for s in self.db.list_songs(self._query, filters)
                 if s["id"] not in self._in_list]
        if songs:
            self._list.controls = [self._tile(s) for s in songs]
        else:
            self._list.controls = [ft.Container(padding=20, content=ft.Text(
                "(no hay más canciones para agregar)", color=theme.THEME["text_muted"]))]
        if update:
            _safe_update(self._list)

    # -- fila estilo biblioteca: ♪ · título/autor (sin ritmo) · ＋ (badge) --
    def _tile(self, song: dict) -> ft.Control:
        info = ft.Column([
            ft.Text(song["title"], size=16, weight=ft.FontWeight.W_500,
                    color=theme.THEME["text"], no_wrap=True),
            ft.Text(song.get("author") or "Desconocido", size=12,
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
        ])

    def _add_badge(self, song: dict) -> ft.Control:
        """Botón ＋ con el mismo diseño del badge de tono (reemplaza «＋ Agregar»)."""
        return ft.Container(
            width=52, height=52, ink=True,
            border=ft.Border.all(1, theme.THEME["chord"]),
            border_radius=12, bgcolor=theme.THEME["chord_bg"],
            alignment=ft.Alignment.CENTER, tooltip="Agregar a la lista",
            on_click=lambda _e, s=song: self._add(s),
            content=ft.Column([
                ft.Icon(ft.Icons.ADD, size=20, color=theme.THEME["chord"]),
                ft.Text("Agregar", size=8, color=theme.THEME["text_muted"]),
            ], spacing=0, tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )

    def _add(self, song: dict) -> None:
        setlist = self.db.load_setlist(self.setlist_id)
        setlist.items.append(SetlistItem(
            id=None, song_id=song["id"], position=len(setlist.items),
            transpose=0, title=song["title"], key=song.get("key")))
        self.db.save_setlist(setlist)
        self._in_list.add(song["id"])     # ya no vuelve a aparecer como opción
        self._refill(update=True)
        if self.page is not None:
            show_toast(self.page, f"✓ Agregada «{song['title']}»")
