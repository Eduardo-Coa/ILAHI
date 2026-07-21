"""Contenedor de las vistas principales con barra inferior fija y swipe.

Las cinco vistas del panel principal se recorren como una SECUENCIA plana:

    Autores · Canciones · Favoritos · Listas · Ajustes
    └────── Biblioteca ──────┘

Se desliza de lado (o se toca una pestaña) para moverse entre ellas. La barra
inferior queda fija —solo se mueve el contenido— y resalta «Biblioteca» tanto en
Autores como en Canciones.

El deslizamiento lo hace ``ft.PageView``, o sea el PageView de Flutter: el arrastre
SIGUE AL DEDO y se acomoda al soltar con física nativa, todo del lado de Dart. Esto
es a propósito: la versión anterior animaba desde Python y mandaba actualizaciones
por el canal en cada cuadro, lo que en el teléfono se veía entrecortado. Aquí Python
solo se entera de que la vista cambió (``on_change``), una vez por swipe.

Las vistas VIVEN (no se reconstruyen al pasar de una a otra), porque armar la lista
de canciones cuesta en proporción a la biblioteca —con mil himnos son cientos de ms—
y pagarlo en cada swipe congelaba el gesto. Se construyen la primera vez que hacen
falta, junto con sus vecinas, así la de al lado ya está lista cuando el dedo la
asoma. Una vista se marca «sucia» cuando su contenido dejó de reflejar el estado
limpio (p. ej. quedó filtrada por lo tipeado) y se rehace recién cuando vuelve a
hacer falta.

El chrome FIJO (no se mueve) es: el logo (siempre), y —solo en Biblioteca— el toggle
Autores|Canciones y el buscador (cambia su placeholder, no se recrea, así mantiene el
foco). Lo único que se desliza es el cuerpo (chip del autor + lista).

El shell no conoce las pantallas: recibe ``build_page(i, query)`` que arma el cuerpo
de la vista ``i`` filtrado por ``query``, y ``search_hint(i)`` para el placeholder.
Así se prueba la lógica de índices sin UI.
"""

from __future__ import annotations
from typing import Callable
import flet as ft

import theme
from views.bottom_bar import build_bottom_bar, fill_bar
from views.widgets import logo_header, SlidingToggle
from views.search_field import search_pill

# Secuencia plana. Cada índice sabe qué pestaña de la barra inferior resalta:
# Autores y Canciones son ambos «Biblioteca».
TAB_OF = ["library", "library", "favorites", "setlists", "settings"]
# Pestaña -> índice al que salta tocarla (Biblioteca abre Canciones, no Autores).
INDEX_OF_TAB = {"library": 1, "favorites": 2, "setlists": 3, "settings": 4}
# Índice de Canciones: el «hogar» del panel (a donde vuelve el «atrás» del sistema).
HOME_INDEX = 1


class MainShell:
    """Sostiene las vistas principales; desliza entre ellas con swipe y barra fija."""

    def __init__(self, page, build_page: Callable[[int, str], ft.Control],
                 search_hint: Callable[[int], str | None] | None = None,
                 on_navigate: Callable[[int], None] | None = None,
                 fab_action: Callable[[int], Callable[[], None] | None] | None = None,
                 index: int = HOME_INDEX) -> None:
        self.page = page
        # build_page(i, query) -> contenido (cuerpo) de la vista i filtrado por query.
        self.build_page = build_page
        # search_hint(i) -> placeholder del buscador FIJO en la vista i, o None si esa
        # vista no lleva buscador en el chrome (p. ej. Ajustes, o las que traen el suyo).
        self.search_hint = search_hint or (lambda i: None)
        # on_navigate(i) -> aviso a main de que la vista cambió a i (deslizando/tocando
        # pestaña). Lo usa para soltar estado ligado a otra vista (p. ej. el autor
        # elegido en Autores). No se dispara en refresh/rebuild (mismo índice).
        self.on_navigate = on_navigate or (lambda i: None)
        # fab_action(i) -> qué hace el botón ＋ FIJO en la vista i, o None si esa vista
        # no lo lleva (Autores, Ajustes). El ＋ es del shell porque lo comparten
        # Canciones, Favoritos y Listas (3 vistas seguidas).
        self.fab_action = fab_action or (lambda i: None)
        self.index = max(0, min(len(TAB_OF) - 1, index))
        # Una funda por vista; su ``content`` es el cuerpo, que se llena al vuelo.
        self._slots = [ft.Container(expand=True) for _ in TAB_OF]
        self._built: set[int] = set()       # vistas con el cuerpo ya armado
        self._dirty: set[int] = set()       # armadas pero desactualizadas (p. ej. filtradas)
        self._bar_row = ft.Row(spacing=0)
        # Buscador FIJO del chrome: UN solo campo (con el estilo de search_pill) que
        # sobrevive al cambio de vista —mantiene el foco al escribir—; solo cambia su
        # placeholder y se limpia al cambiar de vista. Lo tipeado filtra el cuerpo actual.
        self._query = ""
        self._search_holder = search_pill("", self._on_search_change)
        self._search_field = self._search_holder.content.controls[1]

    # ------------------------------------------------------------------
    def build(self) -> ft.Control:
        # El PageView se lleva el gesto: no hay GestureDetector nuestro. Flutter ya
        # distingue el arrastre horizontal (cambiar de vista) del vertical (scroll).
        self._pv = ft.PageView(
            expand=True, controls=self._slots, selected_index=self.index,
            on_change=self._on_page_change)
        self._ensure_around(self.index)
        # Chrome FIJO (no se desliza): logo siempre; y —solo en Biblioteca— el toggle
        # Autores|Canciones y el buscador. Lo único que se desliza es el cuerpo (chip
        # del autor + lista). El toggle y el buscador viven en contenedores cuya
        # visibilidad/placeholder se ajustan al cambiar de vista.
        # Toggle PERSISTENTE: no se reconstruye al cambiar de vista (por eso su
        # píldora puede deslizarse en vez de saltar); solo se le mueve el lado activo.
        self._toggle = SlidingToggle(
            "Autores", "Canciones",
            on_left=lambda: self.goto(0), on_right=lambda: self.goto(1),
            active="right" if self.index == 1 else "left")
        self._toggle_holder = ft.Container(
            content=self._toggle.build(),
            visible=self._shows_toggle(self.index))
        self._sync_search(self.index)          # placeholder y visibilidad del buscador
        # Botón ＋ FIJO, flotante abajo a la derecha (por encima de la barra). Su acción
        # y visibilidad dependen de la vista actual (fab_action).
        self._fab = ft.Container(
            right=18, bottom=90, visible=self.fab_action(self.index) is not None,
            content=ft.FloatingActionButton(
                icon=ft.Icons.ADD, tooltip="Añadir",
                bgcolor=theme.THEME["accent"], foreground_color=theme.THEME["bg"],
                shape=ft.RoundedRectangleBorder(radius=18),
                on_click=lambda _e: self._fab_click()))
        bar = build_bottom_bar(TAB_OF[self.index], self._on_tab, row=self._bar_row)
        columna = ft.Column([
            logo_header(),
            self._toggle_holder,
            self._search_holder,
            ft.Container(self._pv, expand=True),
            bar,
        ], expand=True, spacing=0)
        # El ＋ flota SOBRE todo (incluida la barra) en un Stack.
        return ft.Stack(expand=True, controls=[columna, self._fab])

    def _fab_click(self) -> None:
        action = self.fab_action(self.index)
        if action is not None:
            action()

    # -- cuerpos de las vistas (se arman una vez y viven) ---------------
    def _ensure_page(self, i: int) -> None:
        """Arma el cuerpo de la vista ``i`` si falta o quedó desactualizado.

        Solo la vista actual se arma con lo tipeado en el buscador; las vecinas se
        arman limpias, que es como se van a ver cuando se llegue a ellas."""
        if i in self._built and i not in self._dirty:
            return
        self._slots[i].content = self.build_page(i, self._query if i == self.index else "")
        self._built.add(i)
        self._dirty.discard(i)
        self._safe_update(self._slots[i])

    def _ensure_around(self, i: int) -> None:
        """Arma la vista ``i`` y sus vecinas: al arrastrar, la de al lado asoma ENSEGUIDA,
        así que tiene que estar lista antes de que el dedo la muestre."""
        for j in (i, i - 1, i + 1):
            if 0 <= j < len(TAB_OF):
                self._ensure_page(j)

    # -- chrome fijo (logo siempre; toggle solo en Biblioteca) ---------
    def _shows_toggle(self, i: int) -> bool:
        """El toggle Autores|Canciones solo tiene sentido en Biblioteca (índices 0 y 1)."""
        return i in (0, 1)

    def _sync_chrome(self, i: int) -> None:
        """Ajusta el chrome fijo a la vista ``i``: toggle, buscador y pestaña resaltada."""
        self._toggle_holder.visible = self._shows_toggle(i)
        if self._shows_toggle(i):
            # El toggle NO se reconstruye: solo se le manda el lado activo y su píldora
            # se desliza sola hasta ahí.
            self._toggle.set_active("right" if i == 1 else "left")
        self._sync_search(i)
        self._fab.visible = self.fab_action(i) is not None
        fill_bar(self._bar_row, TAB_OF[i], self._on_tab)
        self._safe_update(self._toggle_holder)
        self._safe_update(self._fab)
        self._safe_update(self._bar_row)

    # -- buscador fijo -------------------------------------------------
    def _sync_search(self, i: int) -> None:
        """Placeholder y visibilidad del buscador fijo para la vista ``i``; limpia lo
        tipeado (cada vista arranca sin filtro). Si la vista no lleva buscador en el
        chrome (search_hint devuelve None), se oculta."""
        hint = self.search_hint(i)
        self._search_holder.visible = hint is not None
        if hint is not None:
            self._search_field.hint_text = hint
        self._query = ""
        self._search_field.value = ""
        self._safe_update(self._search_holder)

    def _on_search_change(self, e) -> None:
        """Filtra el cuerpo actual con lo tipeado. El campo NO se reconstruye (vive en
        el chrome), así que no pierde el foco; solo se rehace la lista."""
        self._query = (getattr(e, "control", None).value if e is not None else "") or ""
        # Filtrada, esta vista ya no muestra su estado limpio: al dejarla habrá que
        # rehacerla antes de volver a mostrarla.
        self._dirty.add(self.index)
        self._rebuild_body()

    def _rebuild_body(self) -> None:
        self._slots[self.index].content = self.build_page(self.index, self._query)
        self._built.add(self.index)
        self._safe_update(self._slots[self.index])

    def refresh(self) -> None:
        """Re-sincroniza el buscador y reconstruye el cuerpo, sin cambiar de índice.
        Para cuando main altera la vista actual (p. ej. entrar o salir del filtro por
        autor: el placeholder cambia y el cuerpo pasa de autores a canciones)."""
        self._sync_search(self.index)
        self._rebuild_body()

    def rebuild(self) -> None:
        """Reconstruye la vista actual en el sitio. Para refrescar tras un cambio de
        datos (p. ej. borrar una lista). Conserva el filtro tipeado.

        Las otras quedan marcadas para rehacerse: puede que el cambio también las
        afecte (marcar un favorito toca Canciones y Favoritos a la vez)."""
        self._rebuild_body()
        self._dirty.update(i for i in self._built if i != self.index)
        self._ensure_around(self.index)

    # -- navegación ----------------------------------------------------
    def _on_tab(self, key: str) -> None:
        self.goto(INDEX_OF_TAB.get(key, self.index))

    def goto(self, new_index: int) -> None:
        """Va a otra vista (tocar una pestaña o el toggle). Si ya es la actual, no hace
        nada.

        Navega fijando ``selected_index`` + ``update()``, la forma documentada y
        garantizada de mover el PageView por código: salta sin animación (el slide lo
        da el gesto nativo al arrastrar). NO se usa ``go_to_page``: en esta versión de
        Flet no movía la vista al tocar la pestaña. Además, entre pestañas no contiguas
        (p. ej. 1→4) un salto se ve más limpio que deslizar por las del medio."""
        n = max(0, min(len(TAB_OF) - 1, new_index))
        if n == self.index:
            return
        self._ensure_page(n)                 # que esté armada antes de mostrarla
        self._commit(n)                      # el chrome responde YA
        self._pv.selected_index = n
        self._safe_update(self._pv)

    def _page_index(self, e) -> int:
        """Índice al que quedó el PageView, según el evento (o el actual si no se sabe)."""
        candidatos = (getattr(getattr(e, "control", None), "selected_index", None),
                      getattr(e, "data", None))
        for v in candidatos:
            try:
                if v is not None:
                    return int(v)
            except (TypeError, ValueError):
                continue
        return self.index

    def _on_page_change(self, e=None) -> None:
        """Llega DESPUÉS de que el arrastre se acomodó en otra vista. Es lo único que
        Python escucha del gesto: el deslizamiento en sí corrió entero en Flutter."""
        n = max(0, min(len(TAB_OF) - 1, self._page_index(e)))
        # Sincroniza el modelo con la página real: el arrastre la cambió sin pasar por
        # ``selected_index``, y si queda desfasado, un toque posterior a ESA misma
        # página no se detectaría como cambio y no navegaría.
        self._pv.selected_index = n
        if n != self.index:
            self._commit(n)

    def _commit(self, n: int) -> None:
        """Asienta el cambio a la vista ``n``: avisa a main, ajusta el chrome y deja
        listas las vecinas para el próximo arrastre."""
        anterior = self.index
        self.index = n
        self.on_navigate(n)                  # main suelta lo que era de la vista vieja
        self._sync_chrome(n)                 # (limpia lo tipeado, entre otras cosas)
        if anterior in self._dirty:
            self._ensure_page(anterior)      # quedó filtrada: dejarla limpia otra vez
        self._ensure_around(n)

    def _safe_update(self, control: ft.Control) -> None:
        try:
            control.update()
        except Exception:
            pass
