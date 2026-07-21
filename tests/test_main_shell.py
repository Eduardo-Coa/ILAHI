"""Lógica del shell del panel principal: secuencia plana, índices y reconstrucciones.

Headless: no corre la app; usa una página falsa y un ``build_page`` de prueba que
registra con qué índice y qué filtro se le pide cada vista.

El deslizamiento en sí ya NO se prueba acá: lo hace ``ft.PageView`` (o sea Flutter) y
Python solo se entera al final por ``on_change``. Lo que sí importa probar es lo que
quedó del lado de Python: a qué vista se va, CUÁNDO se reconstruye un cuerpo (armar la
lista de canciones cuesta en proporción a la biblioteca, así que de más duele) y cómo
acompaña el chrome fijo.
"""

from __future__ import annotations
import flet as ft

from views.main_shell import MainShell, TAB_OF, INDEX_OF_TAB, HOME_INDEX


class _FakePage:
    def run_task(self, fn, *a):
        pass                     # el deslizamiento real no corre en las pruebas

    def update(self):
        pass


def _shell(index: int = HOME_INDEX):
    """Shell listo para usar + la lista de ``(índice, filtro)`` que se fue construyendo."""
    calls: list[tuple[int, str]] = []

    def build_page(i: int, query: str = "") -> ft.Control:
        calls.append((i, query))
        return ft.Text(f"page-{i}")

    shell = MainShell(_FakePage(), build_page, index=index)
    shell.build()                        # arma la vista inicial y sus vecinas
    calls.clear()                        # a partir de acá contamos solo lo que sigue
    return shell, calls


def _indices(calls) -> list[int]:
    return [i for i, _q in calls]


class _Swipe:
    """Evento de ``on_change`` del PageView: la vista donde quedó el arrastre."""
    def __init__(self, index: int) -> None:
        self.control = type("PV", (), {"selected_index": index})()
        self.data = index


def test_la_secuencia_y_el_mapeo_de_pestanas():
    """Autores y Canciones son «Biblioteca»; cada pestaña abre su vista."""
    assert TAB_OF == ["library", "library", "favorites", "setlists", "settings"]
    assert INDEX_OF_TAB == {"library": 1, "favorites": 2, "setlists": 3, "settings": 4}
    assert HOME_INDEX == 1               # Canciones es el «hogar» del panel


# -- qué se construye y cuándo -------------------------------------------------
def test_al_arrancar_se_arman_la_vista_actual_y_sus_vecinas():
    """Las vecinas asoman apenas se arrastra, así que tienen que estar listas antes."""
    calls: list[tuple[int, str]] = []
    shell = MainShell(_FakePage(), lambda i, q="": calls.append((i, q)) or ft.Text("x"),
                      index=1)
    shell.build()
    assert sorted(_indices(calls)) == [0, 1, 2]      # Canciones + Autores + Favoritos
    assert 3 not in _indices(calls)                   # Listas todavía no hace falta


def test_volver_a_una_vista_ya_armada_no_la_reconstruye():
    """El punto de todo el cambio: pasar de vista no debe costar rearmar la lista."""
    shell, calls = _shell(index=1)
    shell.goto(2)                        # Favoritos (ya estaba armada como vecina)
    assert _indices(calls) == [3]        # solo se suma la NUEVA vecina, Listas
    calls.clear()
    shell.goto(1)                        # y de vuelta: todas ya están armadas
    assert calls == []


def test_deslizar_arma_la_vecina_que_viene():
    """Al asentarse en una vista se prepara la siguiente, para el arrastre que sigue."""
    shell, calls = _shell(index=1)
    shell._on_page_change(_Swipe(2))     # el PageView avisa que quedó en Favoritos
    assert shell.index == 2
    assert _indices(calls) == [3]


def test_tocar_una_pestana_va_a_su_vista():
    shell, _ = _shell(index=1)
    shell._on_tab("setlists")            # → índice 3
    assert shell.index == 3
    # Regresión: tocar la pestaña debe MOVER el PageView, no solo el resaltado. La
    # navegación por código va por selected_index (go_to_page no movía la vista).
    assert shell._pv.selected_index == 3


def test_el_arrastre_sincroniza_el_selected_index_del_pageview():
    """Regresión: el arrastre cambia la página sin pasar por selected_index; si el
    modelo queda desfasado, un toque posterior a esa misma página no navegaría."""
    shell, _ = _shell(index=1)
    shell._on_page_change(_Swipe(2))     # arrastre nativo hasta Favoritos
    assert shell.index == 2
    assert shell._pv.selected_index == 2


def test_ir_a_la_misma_vista_no_hace_nada():
    shell, calls = _shell(index=1)
    shell.goto(1)
    assert calls == []
    assert shell.index == 1


def test_goto_recorta_al_rango_valido():
    shell, calls = _shell(index=1)
    shell.goto(99)                       # fuera de rango → última vista
    assert shell.index == len(TAB_OF) - 1
    assert 4 in _indices(calls)          # Ajustes, que aún no estaba armada


def test_el_aviso_del_pageview_con_la_vista_actual_se_ignora():
    """``on_change`` también llega tras un ``goto`` (que ya asentó): no rehacer nada."""
    shell, _ = _shell(index=1)
    shell.goto(2)
    navs: list[int] = []
    shell.on_navigate = navs.append
    shell._on_page_change(_Swipe(2))     # el eco de la animación que acaba de terminar
    assert navs == []


def test_rebuild_rehace_la_actual_y_marca_las_otras():
    """Tras cambiar datos (marcar un favorito) la vista actual se rehace ya, y las demás
    quedan marcadas porque el mismo cambio puede afectarlas."""
    shell, calls = _shell(index=1)
    shell.rebuild()
    assert _indices(calls) == [1, 0, 2]   # la actual, y sus vecinas al quedar marcadas


# -- chrome fijo ---------------------------------------------------------------
def test_el_toggle_fijo_solo_se_muestra_en_biblioteca():
    """Logo siempre fijo; el toggle Autores|Canciones solo en Biblioteca (0 y 1)."""
    shell, _ = _shell(index=1)
    assert shell._shows_toggle(0) is True    # Autores
    assert shell._shows_toggle(1) is True    # Canciones
    assert shell._shows_toggle(2) is False   # Favoritos
    assert shell._shows_toggle(3) is False   # Listas
    assert shell._shows_toggle(4) is False   # Ajustes


def test_al_deslizar_se_ajusta_la_visibilidad_del_toggle():
    """Ir a una vista sin toggle (Favoritos) lo oculta; volver a Biblioteca lo muestra."""
    shell, _ = _shell(index=1)               # Canciones: toggle visible
    assert shell._toggle_holder.visible is True
    shell.goto(2)                            # Favoritos
    assert shell._toggle_holder.visible is False
    shell.goto(1)                            # de nuevo a Canciones
    assert shell._toggle_holder.visible is True


def test_la_pildora_se_desliza_al_lado_de_la_vista_nueva():
    """Al cambiar entre Autores y Canciones la píldora se anima hasta el lado que toca
    (no salta): por eso el toggle vive una sola vez y no se reconstruye."""
    shell, _ = _shell(index=1)               # Canciones: píldora a la derecha
    assert shell._toggle._pill.offset.x == 1
    shell._on_page_change(_Swipe(0))         # arrastre hasta Autores
    assert shell._toggle._pill.offset.x == 0
    assert shell._toggle._pill.animate_offset is not None   # se desliza, no salta
    assert shell._toggle.active == "left"


class _Ev:
    """Evento de on_change con ``control.value``."""
    def __init__(self, value: str) -> None:
        self.control = type("C", (), {"value": value})()


def test_el_buscador_fijo_se_oculta_donde_no_hay_hint():
    """search_hint(i) None → el buscador del chrome no se muestra (esa vista trae el suyo)."""
    shell = MainShell(_FakePage(), lambda i, q="": ft.Text("x"),
                      search_hint=lambda i: None, index=2)
    shell.build()
    assert shell._search_holder.visible is False


def test_escribir_en_el_buscador_filtra_la_vista_actual():
    """Tipear rehace el cuerpo de la vista actual con la query (el campo no se recrea)."""
    seen: list[tuple[int, str]] = []
    shell = MainShell(_FakePage(), lambda i, q="": seen.append((i, q)) or ft.Text("x"),
                      search_hint=lambda i: "Buscar…", index=1)
    shell.build()
    seen.clear()
    shell._on_search_change(_Ev("luz"))
    assert seen == [(1, "luz")]


def test_la_vista_que_quedo_filtrada_se_limpia_al_dejarla():
    """Se navega con un filtro puesto: al volver, esa vista NO debe seguir filtrada."""
    shell, calls = _shell(index=1)
    shell._on_search_change(_Ev("luz"))       # Canciones queda filtrada
    calls.clear()
    shell.goto(2)                             # nos vamos a Favoritos
    assert (1, "") in calls                   # Canciones se rearma limpia
    assert shell._query == ""                 # y el buscador arranca vacío


def test_al_navegar_avisa_y_limpia_la_query():
    """Cambiar de vista avisa a main (on_navigate) y arranca sin filtro tipeado."""
    navs: list[int] = []
    shell, _ = _shell(index=1)
    shell.on_navigate = navs.append
    shell._query = "algo"
    shell.goto(2)
    assert navs == [2]                        # main se entera de la vista nueva
    assert shell._query == ""                 # la búsqueda arranca vacía


def test_el_boton_mas_se_muestra_solo_donde_hay_accion():
    """El ＋ fijo aparece en Canciones/Favoritos/Listas y se oculta en Autores/Ajustes."""
    tiene = {1, 2, 3}
    shell = MainShell(_FakePage(), lambda i, q="": ft.Text("x"),
                      fab_action=lambda i: (lambda: None) if i in tiene else None, index=1)
    shell.build()
    assert shell._fab.visible is True         # Canciones
    shell._sync_chrome(0)                     # Autores
    assert shell._fab.visible is False
    shell._sync_chrome(3)                     # Listas
    assert shell._fab.visible is True
    shell._sync_chrome(4)                     # Ajustes
    assert shell._fab.visible is False


def test_el_boton_mas_ejecuta_la_accion_de_la_vista_actual():
    llamado: list[int] = []
    shell = MainShell(_FakePage(), lambda i, q="": ft.Text("x"),
                      fab_action=lambda i: (lambda: llamado.append(i)) if i == 3 else None,
                      index=3)
    shell.build()
    shell._fab_click()
    assert llamado == [3]
