"""Pruebas de la ventana deslizante (WindowedList) y de los índices de la BD.

Ambos existen por la misma razón: con 600+ himnos la app se arrastraba. En Flet cada
control vive en Python y viaja al cliente, así que el costo depende de cuántas filas
EXISTEN, no de cuántas se ven; y cargar una canción escaneaba las tablas hijas enteras
por falta de índices.
"""

from __future__ import annotations
import flet as ft

from database.config import DBConfig
from database.db import Database
from views.widgets import WindowedList, SONG_ROW_EXTENT


ALTO = 80.0          # alto de fila usado en las pruebas (números redondos)
VENTANA = 900.0      # alto de la pantalla visible


class _Scroll:
    """Evento de on_scroll: posición, largo total y alto de la ventana visible."""
    def __init__(self, pixels: float, max_extent: float = 100_000.0,
                 viewport: float = VENTANA) -> None:
        self.pixels = pixels
        self.max_scroll_extent = max_extent
        self.viewport_dimension = viewport


def _win(n_items: int, overscan: int = 15):
    lv = ft.ListView(controls=[])
    w = WindowedList(lv, lambda i: ft.Text(f"item-{i}"), row_height=ALTO,
                     overscan=overscan)
    w._viewport = VENTANA
    w.reset(list(range(n_items)))
    return lv, w


def _filas(lv):
    """Las tarjetas armadas (ya no hay controles espaciadores: el hueco es padding)."""
    return lv.controls


def _alto_declarado(lv, pad_bottom=0.0):
    """Alto total que la lista le declara al scroll: hueco de arriba + filas + hueco
    de abajo. Debe coincidir siempre con el de TODAS las canciones."""
    return (lv.padding.top + len(lv.controls) * ALTO
            + lv.padding.bottom - pad_bottom)


def test_solo_arma_una_ventana_no_la_biblioteca_entera():
    lv, w = _win(2000)
    assert w.count == 2000
    # Acotado: ~11 visibles + un colchón de overscan a cada lado. Lo que importa es
    # que NO crezca con la biblioteca (2000 canciones, la misma ventana chica).
    assert w.live < 130
    assert len(_filas(lv)) == w.live


def test_la_ventana_no_crece_con_la_biblioteca():
    _, chica = _win(200)
    _, grande = _win(5000)
    assert grande.live == chica.live      # 200 o 5000 canciones: misma ventana


def test_el_hueco_reservado_cubre_lo_no_armado():
    """Sin esto la barra de scroll saltaría: el total debe seguir siendo el de todas."""
    lv, w = _win(1000)
    assert _alto_declarado(lv) == 1000 * ALTO


def test_al_bajar_la_ventana_se_mueve_y_no_crece():
    """Lo esencial: recorrer la biblioteca entera NO va acumulando filas vivas.
    (Arriba de todo hay algunas menos porque no existe margen por encima.)"""
    lv, w = _win(2000)
    for p in range(0, 2000 * int(ALTO), 5_000):
        w.on_scroll(_Scroll(pixels=float(p)))
        assert w.live < 130, f"se acumularon {w.live} filas en {p}px"
    # y al final las armadas son las de por allí, no las del principio
    assert w._start > 400


def test_el_hueco_de_arriba_crece_al_bajar():
    """El fallo que costó tres intentos: el hueco de arriba se quedaba en 0, así que
    las filas se dibujaban al principio del todo mientras la pantalla estaba miles de
    píxeles más abajo, y solo se veía negro. Con espaciadores no se aplicaba; con
    padding del ListView sí, porque es una propiedad del propio scroll."""
    lv, w = _win(2000)
    assert lv.padding.top == 0
    w.on_scroll(_Scroll(pixels=40_000))
    assert lv.padding.top > 30_000        # el hueco de arriba de verdad se reserva
    assert _alto_declarado(lv) == 2000 * ALTO


def test_el_alto_declarado_no_cambia_al_desplazarse():
    """Lo que rompía la app: el alto total se encogía mientras bajabas (medido: de
    51.118 a 27.092 px) y el final de la lista se te venía encima."""
    lv, w = _win(1000)
    for p in (0.0, 5_000.0, 20_000.0, 60_000.0, 81_000.0):
        w.on_scroll(_Scroll(pixels=p))
        assert _alto_declarado(lv) == 1000 * ALTO, f"se descuadró en {p}px"


def test_un_salto_enorme_no_deja_hueco():
    """La ventana se DEDUCE de la posición, así que un deslizamiento rápido no puede
    dejar huecos: no hay nada que 'venga cargándose por detrás'."""
    lv, w = _win(2000)
    w.on_scroll(_Scroll(pixels=1000 * ALTO))     # de golpe a la mitad
    primera = w._start
    ultima = w._end
    assert primera <= 1000 <= ultima             # lo que se ve está armado
    assert w.live < 130


def test_al_volver_arriba_se_rearman_las_primeras():
    lv, w = _win(2000)
    w.on_scroll(_Scroll(pixels=40_000))
    assert w._start > 0
    w.on_scroll(_Scroll(pixels=0))
    assert w._start == 0
    assert w.live < 130


def test_las_filas_que_siguen_a_la_vista_se_reusan():
    """Un desplazamiento corto no debe rehacer las tarjetas que ya estaban."""
    lv, w = _win(2000)
    antes = {id(c) for c in _filas(lv)}
    w.on_scroll(_Scroll(pixels=3 * ALTO))        # baja 3 filas
    despues = {id(c) for c in _filas(lv)}
    assert len(antes & despues) > 20             # la mayoría son las mismas


def test_sin_elementos_muestra_el_mensaje_de_vacio():
    lv = ft.ListView(controls=[])
    w = WindowedList(lv, lambda i: ft.Text("x"), row_height=ALTO)
    vacio = ft.Text("(sin resultados)")
    w.reset([], empty=vacio)
    assert lv.controls == [vacio]


def test_drop_saca_una_fila_y_ajusta_el_alto():
    lv, w = _win(500)
    w.drop(lambda i: i == 10)
    assert w.count == 499
    assert _alto_declarado(lv) == 499 * ALTO


def test_drop_del_ultimo_muestra_el_vacio():
    lv = ft.ListView(controls=[])
    w = WindowedList(lv, lambda i: ft.Text(str(i)), row_height=ALTO)
    vacio = ft.Text("(sin resultados)")
    w.reset([1], empty=vacio)
    w.drop(lambda i: i == 1)
    assert lv.controls == [vacio]


def test_drop_de_algo_inexistente_no_hace_nada():
    lv, w = _win(100)
    assert w.drop(lambda i: i == 9999) is False
    assert w.count == 100


def test_una_busqueda_nueva_vuelve_arriba_y_una_accion_en_el_lugar_no():
    lv, w = _win(2000)
    w.on_scroll(_Scroll(pixels=40_000))
    hondo = w._start
    w.reset(list(range(2000)), keep_position=True)      # p. ej. borrar una canción
    assert w._start == hondo
    w.reset(list(range(2000)))                          # búsqueda nueva
    assert w._start == 0


def test_item_of_y_tile_of_encuentran_lo_armado():
    lv, w = _win(500)
    assert w.item_of(lambda i: i == 3) == 3
    assert w.tile_of(lambda i: i == 3) is not None
    assert w.tile_of(lambda i: i == 400) is None       # fuera de la ventana
    assert w.item_of(lambda i: i == 400) == 400        # el dato sí está


def test_el_alto_de_fila_de_cancion_incluye_el_margen():
    """La cuenta posición ↔ índice solo sale si el alto declarado es el real."""
    assert SONG_ROW_EXTENT == 72 + 10


def test_init_schema_crea_los_indices_de_las_tablas_hijas(tmp_path):
    """Sin estos índices, cargar UNA canción escanea sections/lines/syllables/chords
    enteros y el costo crece con la biblioteca (20 ms con 600 himnos, 100 ms con 2000)."""
    db = Database(DBConfig(path=tmp_path / "t.db"))
    db.init_schema()
    cur = db._connect().cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indices = {row[0] for row in cur.fetchall()}
    assert {"idx_sections_song", "idx_lines_section",
            "idx_syllables_line", "idx_chords_syllable"} <= indices
    db.close()


def test_wal_activo_para_que_los_commits_no_esperen_al_disco(tmp_path):
    db = Database(DBConfig(path=tmp_path / "w.db"))
    db.init_schema()
    modo = db._connect().execute("PRAGMA journal_mode").fetchone()[0]
    assert modo.lower() == "wal"
    db.close()


def test_los_favoritos_ya_no_alteran_el_orden(tmp_path):
    """Marcar favorito conserva la posición: reordenar obligaba a rearmar la lista
    entera y movía la canción de lugar mientras la estabas mirando."""
    from models.song import Song
    db = Database(DBConfig(path=tmp_path / "o.db"))
    db.init_schema()
    for t in ("Cristo", "Aleluya", "Bendito"):
        db.save_song(Song(id=None, title=t, author="A", key="G"))
    orden = [s["title"] for s in db.list_songs()]
    assert orden == ["Aleluya", "Bendito", "Cristo"]
    db.set_favorite([s for s in db.list_songs() if s["title"] == "Cristo"][0]["id"], True)
    assert [s["title"] for s in db.list_songs()] == orden   # no se movió
    db.close()
