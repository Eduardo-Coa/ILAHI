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
from views.bottom_bar import build_bottom_bar, fill_bar
from views.search_field import search_pill, filter_chip
from views.widgets import (sheet_option as _sheet_option, show_toast,
                           segmented_toggle, logo_header, _safe_update, key_badge,
                           accent_fab, sheet_dialog, list_row_card, fill_list_card,
                           confirm_dialog, FAB_CLEARANCE, WindowedList,
                           SONG_ROW_HEIGHT, SONG_ROW_EXTENT)
from database.db import author_display, PINNED_ALBUM


def show_add_sheet(page, on_new: Callable[[], None], on_import: Callable,
                   on_export_all: Callable,
                   on_import_link: Callable[[], None] | None = None) -> None:
    """Cuadro flotante «Añadir»: nueva canción · importar desde enlace · importar
    archivo · exportar biblioteca.

    Vive a nivel de módulo (no en la pantalla) porque el botón ＋ ahora es fijo del
    shell y lo comparten Canciones y Favoritos; el shell lo abre desde aquí.
    ``on_import_link`` (importar desde un enlace de Cifra Club) es opcional para no
    obligar a los llamadores que no lo usan."""
    async def do_import(_e=None) -> None:
        page.pop_dialog()
        await on_import()

    async def do_export_all(_e=None) -> None:
        page.pop_dialog()
        await on_export_all()

    def do_new(_e=None) -> None:
        page.pop_dialog()
        on_new()

    def do_import_link(_e=None) -> None:
        page.pop_dialog()
        on_import_link()

    opciones = [
        _sheet_option(ft.Icons.ADD, "Nueva canción",
                      "Escribe o pega la letra", do_new),
    ]
    if on_import_link is not None:
        opciones.append(_sheet_option(
            ft.Icons.LINK, "Importar desde enlace",
            "Pega el link de una canción de Cifra Club", do_import_link))
    opciones += [
        _sheet_option(ft.Icons.DOWNLOAD, "Importar…",
                      "Una canción o un cancionero .ilahi", do_import),
        _sheet_option(ft.Icons.UPLOAD, "Exportar biblioteca",
                      "Todas tus canciones en un archivo", do_export_all),
    ]
    page.show_dialog(sheet_dialog(
        title="Añadir",
        content_padding=ft.Padding.only(left=8, right=8, bottom=8),
        content=ft.Column(tight=True, spacing=2, controls=opciones),
    ))


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
                 filtro: tuple[str, str] | None = None, embedded: bool = False,
                 external_search: bool = False, query: str = "",
                 on_clear_filter: Callable[[], None] | None = None,
                 on_data_changed: Callable[[], None] | None = None,
                 show_chip: bool = True) -> None:
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
        # Filtro activo (tipo, nombre): tipo es "author" o "album" — los dos campos
        # que ``Database._FILTER_COLUMNS`` acepta para esta pantalla.
        self._filtro = filtro
        # Embebida en el shell del panel principal: la barra inferior la pone el shell
        # (no esta pantalla) y el swipe entre vistas ya cubre Álbumes/Canciones.
        self.embedded = embedded
        # ``external_search``: el buscador lo pone el shell (fijo, arriba); aquí se
        # omite y el filtro llega en ``query``. ``on_clear_filter``: quitar el chip lo
        # maneja el shell (vuelve a la lista de álbumes/autores), no solo el refill interno.
        self.external_search = external_search
        self.on_clear_filter = on_clear_filter
        # El chip sobra cuando el nombre del grupo ya está en el encabezado de la
        # pantalla (la vista propia de un álbum/autor): ahí se apaga con show_chip.
        self.show_chip = show_chip
        # Aviso de que los datos cambiaron (favorito, borrado). Biblioteca y Favoritos
        # son pantallas distintas y vivas a la vez: sin esto, marcar un favorito aquí
        # no se veía allá hasta reiniciar la app.
        self.on_data_changed = on_data_changed or (lambda: None)
        self._query = query
        # El ＋ flotante del panel vive encima de la lista: se reserva aire abajo para
        # que el último elemento se pueda desplazar por encima del botón. Solo se
        # mantienen vivas las filas cercanas a lo que se ve (WindowedList): armarlas
        # todas hace que la app entera se arrastre, sin importar cómo se carguen.
        self._list = ft.ListView(expand=True, controls=[], scroll_interval=50,
                                 build_controls_on_demand=False)
        # El aire del ＋ flotante lo administra el filler: el padding de la lista es
        # justamente donde reserva el hueco de las filas no armadas.
        self._filler = WindowedList(self._list, self._song_tile,
                                    row_height=SONG_ROW_EXTENT, page=page,
                                    pad_bottom=FAB_CLEARANCE)
        self._list.on_scroll = self._filler.on_scroll
        self._bar = ft.Row(spacing=0)

    # ------------------------------------------------------------------
    def build(self) -> ft.Control:
        self._refill(update=False)
        # Embebida en el shell, el logo, el toggle Autores|Canciones y la barra
        # inferior son chrome FIJO que pone el shell; aquí solo va el cuerpo que se
        # desliza (filtro por autor + búsqueda + lista).
        children: list[ft.Control] = []
        if not self.embedded:
            children.append(logo_header())
        # El chip del filtro va arriba del cuerpo (queda justo debajo del buscador,
        # que embebido es fijo y lo pone el shell).
        if self.show_chip:
            children.append(self._filter_chip_row())
        if not self.external_search:             # el buscador fijo lo pone el shell
            children.append(self._search_field())
        if not self.embedded:
            children.append(self._toggle())      # Autores | Canciones, bajo la búsqueda
        children.append(self._list)
        if not self.embedded:
            children.append(self._bottom_bar())
        column = ft.Column(children, expand=True, spacing=0)
        if self.embedded:                    # embebida: el ＋ es fijo y lo pone el shell
            return column
        # El ＋ flota sobre la lista, justo encima de la barra inferior.
        return ft.Stack(expand=True, controls=[column, self._fab()])

    # ------------------------------------------------------------------
    # Filtro por álbum o autor
    # ------------------------------------------------------------------
    def _filtro_etiqueta(self) -> str:
        """Nombre a mostrar del filtro activo («Desconocido» solo aplica a autor;
        un álbum siempre tiene nombre real)."""
        if not self._filtro:
            return ""
        tipo, name = self._filtro
        return author_display(name) if tipo == "author" else name

    def _filter_chip_row(self) -> ft.Control:
        """Muestra el filtro activo (álbum o autor) y permite quitarlo."""
        es_album = bool(self._filtro) and self._filtro[0] == "album"
        self._chip_box = filter_chip(
            self._filtro_etiqueta(),
            self.on_clear_filter or self._clear_filter, visible=bool(self._filtro),
            icon=ft.Icons.ALBUM_OUTLINED if es_album else ft.Icons.PERSON_OUTLINE)
        self._chip_label = self._chip_box.content.controls[1]
        # Alineado a la izquierda: sin esto el chip ocuparía todo el ancho.
        return ft.Row([self._chip_box], tight=True)

    def _clear_filter(self) -> None:
        self._filtro = None
        self._chip_box.visible = False
        _safe_update(self._chip_box)
        self._refill(update=True)

    def _search_field(self) -> ft.Control:
        """Buscador tipo píldora (el filtro por álbum/autor ahora vive en el toggle)."""
        return search_pill("Buscar himno o autor…", self._on_query)

    def _toggle(self) -> ft.Control:
        """Barra Álbumes | Canciones (Canciones activa aquí); a Álbumes → su pantalla."""
        return segmented_toggle(
            "Álbumes", "Canciones", active="right",
            on_left=lambda: self.on_open_authors(), on_right=lambda: None)

    # ------------------------------------------------------------------
    # Botón ＋ (nueva / importar / exportar)
    # ------------------------------------------------------------------
    def _fab(self) -> ft.Control:
        """FAB flotante abajo a la derecha, por encima de la barra inferior."""
        return ft.Container(
            # Embebida, la barra inferior está fuera de esta pantalla (la pone el
            # shell), así que el FAB baja para no quedar flotando alto.
            right=18, bottom=90 if not self.embedded else 24,
            content=accent_fab(ft.Icons.ADD, "Añadir",
                               lambda _e: self._open_add_sheet()),
        )

    def _open_add_sheet(self) -> None:
        show_add_sheet(self.page, self.on_new_song, self.on_import, self.on_export_all)

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
        self._set_status("")
        self._refill(update=True)
        fill_bar(self._bar, self._tab, self._select_tab)
        _safe_update(self._bar)

    def _set_status(self, status: str) -> None:
        self.status = status
        show_toast(self.page, status)     # confirmación flotante (toast)

    def _on_query(self, e) -> None:
        self._query = e.control.value or ""
        self._refill(update=True)

    def browse_song_ids(self) -> list[int]:
        """Ids del recorrido que hereda la vista de canción para pasar a la anterior o
        la siguiente (arrastrando o con ‹/›), y del que sale el contador «142/628».

        Es la lista SIN la búsqueda, pero con el resto de sus filtros (la pestaña y el
        álbum/autor). La búsqueda sirve para ENCONTRAR una canción; una vez abierta se
        está dentro del álbum, no dentro del resultado: así el contador dice su
        posición en el himnario y arrastrar lleva al himno que le sigue, no al otro
        resultado (que estaría cientos de números más allá).
        """
        return [s["id"] for s in self._consultar("")]

    def _empty_message(self) -> str:
        if self._tab == "favorites" and not self._query:
            return "Aún no tienes favoritos. Toca la ♪ de una canción."
        if self._filtro:
            return f"(«{self._filtro_etiqueta()}» no tiene canciones que coincidan)"
        return "(sin resultados)"

    def _consultar(self, query: str) -> list[dict]:
        """Canciones de esta lista para ``query``, con sus demás filtros aplicados.

        ``exclude_album`` se decide con la búsqueda ACTUAL de la pantalla, no con
        ``query``: así el recorrido (que consulta con ``query=""``) sigue conteniendo
        la canción que se abrió desde una búsqueda en Canciones, aunque sea del
        cancionero incluido. Si se decidiera con ``query``, esa canción quedaría fuera
        de su propio recorrido y se perdería el contador.
        """
        filters = {self._filtro[0]: self._filtro[1]} if self._filtro else None
        # El Himnario Adventista no inunda "Canciones" al navegar sin filtro (son 628
        # de las ~635 canciones); en cuanto hay una búsqueda, un filtro activo o se está
        # en Favoritos, sí se busca/muestra ahí también — nada queda inalcanzable.
        exclude_album = (PINNED_ALBUM if self._tab == "library"
                         and not self._query and not self._filtro else None)
        songs = self.db.list_songs(query, filters, exclude_album)   # alfabético
        if self._tab == "favorites":
            songs = [s for s in songs if s["favorite"]]
        return songs

    def _refill(self, update: bool = True, keep_position: bool = False) -> None:
        """Relee la base y rearma la ventana visible. ``keep_position`` conserva el
        punto de scroll (acciones en el lugar, como borrar); una búsqueda o un cambio
        de pestaña arrancan arriba."""
        songs = self._consultar(self._query)
        self._filler.reset(
            songs, keep_position=keep_position,
            empty=ft.Container(
                key="empty", padding=20,
                content=ft.Text(self._empty_message(), color=theme.THEME["text_muted"])))
        if update:
            _safe_update(self._list)

    # ------------------------------------------------------------------
    # Tarjeta de canción
    # ------------------------------------------------------------------
    def _song_tile(self, song: dict) -> ft.Control:
        """Tarjeta de una canción, de alto fijo (lo exige la ventana deslizante).

        Las piezas que hacen falta después (la estrella y su ítem de menú) se guardan
        EN la propia tarjeta, no en diccionarios de la pantalla: al salir de la
        ventana, la tarjeta se suelta y con ella todo lo suyo. Con diccionarios por id
        quedarían retenidas y no se liberaría nada, que es justo lo que se busca.

        La `key` estable evita que Flet reconcilie por posición y, al cambiar el largo
        de la lista (p. ej. Biblioteca → Favoritos), reutilice controles de otra
        canción arrastrando sus handlers.
        """
        sid = song["id"]
        fav = bool(song.get("favorite"))
        card = list_row_card([], key=f"song-{sid}", height=SONG_ROW_HEIGHT)
        estrella = self._star(sid, fav)
        item_fav = self._fav_menu_item(sid, fav)
        fill_list_card(card, [
            estrella,
            ft.Container(
                expand=True, ink=True, border_radius=10,
                on_click=lambda _e: self.on_open_song(sid, self.browse_song_ids()),
                padding=ft.Padding.symmetric(horizontal=4, vertical=4),
                content=self._info(song)),
            key_badge(song.get("key")),
            self._menu(sid, item_fav),
        ])
        card.data = (estrella, item_fav)
        return card


    def _star(self, sid: int, fav: bool) -> ft.IconButton:
        """★ si es favorita, ♪ si no. Tocarla alterna el favorito."""
        return ft.IconButton(
            icon=ft.Icons.STAR if fav else ft.Icons.MUSIC_NOTE,
            icon_color=theme.THEME["accent"] if fav else theme.THEME["text_muted"],
            icon_size=22,
            tooltip="Quitar de favoritos" if fav else "Marcar favorito",
            on_click=lambda _e: self._toggle_favorite(sid, not fav))

    def _fav_menu_item(self, sid: int, fav: bool) -> ft.PopupMenuItem:
        return ft.PopupMenuItem(
            content="Quitar de favoritos" if fav else "Marcar favorito",
            icon=ft.Icons.STAR_BORDER if fav else ft.Icons.STAR,
            on_click=lambda _e: self._toggle_favorite(sid, not fav))

    def _info(self, song: dict) -> ft.Control:
        """Título, autor (o álbum si no tiene autor, o «Desconocido») y ritmo."""
        return ft.Column([
            ft.Text(song["title"], size=16, weight=ft.FontWeight.W_500,
                    color=theme.THEME["text"], no_wrap=True),
            ft.Text(song.get("author") or song.get("album") or "Desconocido", size=12,
                    color=theme.THEME["text_muted"], no_wrap=True),
            ft.Row([
                ft.Icon(ft.Icons.GRAPHIC_EQ, size=12, color=theme.THEME["text_muted"]),
                ft.Text(song.get("rhythm") or "—", size=11,
                        color=theme.THEME["text_muted"]),
            ], spacing=4, tight=True),
        ], spacing=1, tight=True)

    def _menu(self, sid: int, item_fav: ft.PopupMenuItem) -> ft.Control:
        return ft.PopupMenuButton(
            icon=ft.Icons.MORE_VERT, icon_color=theme.THEME["text_muted"],
            items=[
                ft.PopupMenuItem(content="Editar", icon=ft.Icons.EDIT,
                                 on_click=lambda _e: self.on_edit_song(sid)),
                ft.PopupMenuItem(content="Exportar", icon=ft.Icons.UPLOAD,
                                 on_click=self._export_handler(sid)),
                item_fav,
                ft.PopupMenuItem(content="Eliminar", icon=ft.Icons.DELETE,
                                 on_click=lambda _e: self._ask_delete(sid)),
            ])

    def _export_handler(self, sid: int):
        """Handler async para el ítem «Exportar» del menú."""
        async def handler(_e=None):
            await self.on_export_song(sid)
        return handler

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def _toggle_favorite(self, sid: int, value: bool) -> None:
        """Marca o desmarca, tocando SOLO esa fila.

        Antes se rearmaba la lista entera para que los favoritos subieran al momento;
        con la biblioteca ya scrolleada eran 9.000 controles nuevos hacia Flutter y el
        toque tardaba más de 5 s en el teléfono. El reordenamiento ahora se aplica en
        el próximo refresco natural (buscar, cambiar de pestaña, volver a entrar), que
        de todos modos relee la base.
        """
        self.db.set_favorite(sid, value)
        song = self._filler.item_of(lambda s: s["id"] == sid)
        if song is not None:
            song["favorite"] = 1 if value else 0
        # Las otras vistas (Favoritos y Biblioteca son pantallas distintas) quedan
        # desactualizadas: se rehacen al ir hacia ellas.
        self.on_data_changed()
        # En Favoritos, quitar la marca saca la canción de la lista.
        if self._tab == "favorites" and not value:
            self._filler.drop(lambda s: s["id"] == sid)
            _safe_update(self._list)
            return
        card = self._filler.tile_of(lambda s: s["id"] == sid)
        if card is None or not card.data:   # fuera de la ventana: nada que repintar
            return
        estrella, item = card.data
        estrella.icon = ft.Icons.STAR if value else ft.Icons.MUSIC_NOTE
        estrella.icon_color = (theme.THEME["accent"] if value
                               else theme.THEME["text_muted"])
        estrella.tooltip = item.content = ("Quitar de favoritos" if value
                                           else "Marcar favorito")
        item.icon = ft.Icons.STAR_BORDER if value else ft.Icons.STAR
        estrella.on_click = item.on_click = (
            lambda _e: self._toggle_favorite(sid, not value))
        _safe_update(card)                  # ~15 controles en vez de miles

    def _ask_delete(self, sid: int) -> None:
        """Pregunta antes de borrar, con el mismo cuadro que usan las listas.

        Antes la pregunta reemplazaba a la fila dentro de la lista. Con la lista
        armada por tandas eso dejó de verse: Flet no repinta de forma fiable un hijo
        sustituido (ni un contenido sustituido) dentro de un ListView largo, así que
        la confirmación no aparecía y la canción no se podía borrar. El cuadro modal
        no depende de repintar la lista y es lo que ya se usa para borrar listas.
        """
        song = self._filler.item_of(lambda s: s["id"] == sid) or {}
        titulo = song.get("title", "")

        def confirmar(_e=None) -> None:
            self.page.pop_dialog()
            self._do_delete(sid)

        self.page.show_dialog(confirm_dialog(
            "Eliminar canción",
            ft.Text(f"¿Eliminar «{titulo}»? No se puede deshacer.",
                    color=theme.THEME["text_muted"]),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _e: self.page.pop_dialog()),
                ft.TextButton("Eliminar", on_click=confirmar),
            ]))

    def _do_delete(self, sid: int) -> None:
        self.db.delete_song(sid)
        self._filler.drop(lambda s: s["id"] == sid)   # quitar sí se repinta
        _safe_update(self._list)
        self.on_data_changed()
        show_toast(self.page, "✓ Canción eliminada")

