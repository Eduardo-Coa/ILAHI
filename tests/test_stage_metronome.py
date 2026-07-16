"""Pruebas del metrónomo integrado en el modo escenario (``PresentScreen``).

Headless: no se ejecuta la app real, solo se construye el árbol de controles con
una página falsa (sin ventana) y se inspecciona su estructura, igual que
``test_stage_align.py`` hace con la alineación de acordes.
"""

from __future__ import annotations

import flet as ft

from models.song import Song
from views.stage_view import PresentScreen, StageScreen, _USER_GRACE
import theme


class _FakePage:
    width = 412
    bgcolor = None

    def update(self):
        pass

    def run_task(self, fn, *a):
        pass


def _rows_column(screen: PresentScreen) -> ft.Column:
    """Column de filas (velocidad / fuente / metrónomo) dentro del panel fijo.

    Se toma el panel de ``_panel_box`` (y no navegando el árbol por índices) para
    que la prueba no dependa de cómo esté armado el layout: el título pasó a
    flotar en un ``Stack`` y el panel dejó de ser el 3er hijo de una Column.
    """
    screen.build()
    return screen._panel_box.content.controls[0]


def test_panel_agrega_la_fila_del_metronomo_con_bpm_valido():
    """Con BPM: velocidad + metrónomo (el tamaño de fuente se hereda, no se edita aquí)."""
    song = Song(id=1, title="X", bpm=90, rhythm="4/4", sections=[])
    screen = PresentScreen(_FakePage(), song, 0, on_exit=lambda: None)

    filas = _rows_column(screen)

    assert len(filas.controls) == 2


def test_panel_sin_bpm_solo_tiene_la_fila_de_velocidad():
    """Sin BPM: solo velocidad; la fila del metrónomo ni se construye."""
    song = Song(id=2, title="Y", bpm=None, rhythm="4/4", sections=[])
    screen = PresentScreen(_FakePage(), song, 0, on_exit=lambda: None)

    filas = _rows_column(screen)

    assert len(filas.controls) == 1


def test_el_escenario_hereda_el_tamano_de_fuente_de_la_vista_de_cancion():
    """El «Aa» vive solo en la vista de canción: esta le pasa su tamaño al ▶.

    Se comprueba de punta a punta: se sube la fuente en la vista de canción, se
    pulsa su ▶ y el tamaño que viaja al escenario es el que quedó puesto.
    """
    song = Song(id=3, title="Z", sections=[])
    recibido = {}
    stage = StageScreen(_FakePage(), song, on_back=lambda: None,
                        on_present=lambda s, o, size: recibido.update(size=size))
    stage.build()
    stage._set_size(26)
    fab_play = stage._fabs().content.controls[-1]
    fab_play.on_click(None)

    assert recibido["size"] == 26
    assert PresentScreen(_FakePage(), song, 0, on_exit=lambda: None, size=26).size == 26


def test_cambiar_el_tamano_notifica_para_persistirlo():
    """El «Aa» avisa el tamaño nuevo (``main`` lo guarda en preferencias).

    Se comprueba también que avisa el valor YA recortado al rango permitido: lo que
    se persiste nunca debe dejar la letra ilegible.
    """
    guardados: list[int] = []
    stage = StageScreen(_FakePage(), Song(id=5, title="V", sections=[]),
                        on_back=lambda: None, size=20,
                        on_size_change=guardados.append)
    stage.build()

    stage._resize(2)
    stage._resize(-4)
    stage._set_size(999)          # fuera de rango: se recorta antes de avisar

    assert guardados == [22, 18, 48]


def test_stage_screen_arranca_con_el_tamano_guardado():
    """El tamaño recordado se inyecta al construir la vista (no vuelve al base)."""
    stage = StageScreen(_FakePage(), Song(id=6, title="U", sections=[]),
                        on_back=lambda: None, size=30)

    assert stage.size == 30


def test_el_escenario_sin_tamano_explicito_usa_el_base():
    """El ▶ del detalle de una lista no viene de una vista de canción."""
    song = Song(id=4, title="W", sections=[])
    screen = PresentScreen(_FakePage(), song, 0, on_exit=lambda: None)

    assert screen.size == theme.SIZE_STAGE


def test_tocar_la_pantalla_nunca_mueve_el_scroll():
    """Regresión: ocultar/mostrar el chrome no debe tocar el scroll.

    Antes se «reanclaba» el scroll tras el toggle (necesario cuando el chrome vivía
    en la Column y ocultarlo redimensionaba el cuerpo). Con el chrome flotando eso
    sobra y corría la pantalla: ``_pixels`` llega con retraso (on_scroll está
    limitado a 50 ms), así que al tocar durante la inercia devolvía la letra a una
    posición vieja.
    """
    movimientos: list[float] = []

    class _Body:
        async def scroll_to(self, offset, duration=None):
            movimientos.append(offset)

    class _PageConTareas(_FakePage):
        def __init__(self):
            self.tareas = []

        def run_task(self, fn, *a):
            self.tareas.append(fn)

    page = _PageConTareas()
    screen = PresentScreen(page, Song(id=7, title="T", sections=[]),
                           0, on_exit=lambda: None)
    screen.build()
    screen._body = _Body()
    screen._pixels = 120.0            # valor viejo: el ListView ya va más abajo

    for _ in range(5):                # taps aleatorios, como los del reporte
        screen._toggle_panel()

    assert movimientos == []          # ni un solo scroll forzado
    assert page.tareas == []          # tampoco se agenda nada que lo mueva
    assert screen._chrome_visible is False   # 5 taps: sigue alternando


def _scroll_event(tipo, pixels, direction=None):
    """Evento de scroll como los que manda Flet (ver ``PresentScreen._on_scroll``)."""
    return type("E", (), {"event_type": tipo, "pixels": pixels,
                          "max_scroll_extent": 1000.0, "direction": direction})()


def test_mover_la_pantalla_a_mano_manda_sobre_el_autoscroll():
    """Con el autoscroll activo, el usuario arrastra y el scroll sigue desde ahí.

    Antes la pantalla volvía de golpe a donde iba: con ``_playing`` la posición real
    nunca se sincronizaba. La inercia posterior a soltar no debe cortarse: cada
    movimiento renueva el turno del usuario.
    """
    screen = PresentScreen(_FakePage(), Song(id=8, title="S", sections=[]),
                           0, on_exit=lambda: None)
    screen._playing = True
    screen._pixels = 800.0

    screen._on_scroll(_scroll_event(ft.ScrollType.USER, 800.0,
                                    ft.ScrollDirection.FORWARD))
    assert screen._user_moving() is True
    screen._on_scroll(_scroll_event(ft.ScrollType.UPDATE, 50.0))   # arrastra al inicio
    assert screen._pixels == 50.0
    screen._on_scroll(_scroll_event(ft.ScrollType.USER, 50.0,
                                    ft.ScrollDirection.IDLE))      # suelta
    screen._on_scroll(_scroll_event(ft.ScrollType.UPDATE, 5.0))    # inercia
    assert screen._pixels == 5.0 and screen._user_moving() is True
    screen._on_scroll(_scroll_event(ft.ScrollType.END, 0.0))       # se detiene

    assert screen._pixels == 0.0                # el autoscroll seguirá desde el inicio
    assert screen._user_moving() is False       # el turno se cierra al detenerse


def test_el_turno_del_usuario_caduca_solo_sin_evento_final():
    """Regresión: el autoscroll no puede quedarse colgado si se pierde el ``END``.

    ``scroll_interval`` limita los eventos y puede descartar el final; antes eso
    dejaba el mando trabado en el usuario y el autoscroll no volvía a arrancar (solo
    se destrababa moviendo la rueda, que generaba otro ``END``). El turno debe
    caducar solo pasado ``_USER_GRACE``.
    """
    screen = PresentScreen(_FakePage(), Song(id=10, title="Q", sections=[]),
                           0, on_exit=lambda: None)
    screen._playing = True
    screen._pixels = 800.0

    screen._on_scroll(_scroll_event(ft.ScrollType.USER, 800.0,
                                    ft.ScrollDirection.FORWARD))
    screen._on_scroll(_scroll_event(ft.ScrollType.UPDATE, 0.0))    # suelta; sin END
    assert screen._user_moving() is True        # manda el usuario mientras se mueva

    screen._user_hold -= _USER_GRACE + 0.01     # simula el paso del tiempo

    assert screen._user_moving() is False       # el turno caducó: el autoscroll retoma
    assert screen._pixels == 0.0                # y lo hace desde donde el usuario la dejó


def test_la_animacion_del_autoscroll_no_frena_su_propio_avance():
    """Las posiciones a mitad de la animación no deben pisar la posición objetivo."""
    screen = PresentScreen(_FakePage(), Song(id=9, title="R", sections=[]),
                           0, on_exit=lambda: None)
    screen._playing = True
    screen._pixels = 500.0

    screen._on_scroll(_scroll_event(ft.ScrollType.UPDATE, 503.0))

    assert screen._pixels == 500.0


def test_on_metro_beat_acento_en_el_primer_golpe():
    song = Song(id=1, title="X", bpm=90, rhythm="4/4", sections=[])
    screen = PresentScreen(_FakePage(), song, 0, on_exit=lambda: None)
    screen.build()

    screen._on_metro_beat(0)
    assert screen._metro_dot.bgcolor == theme.THEME["accent"]

    screen._on_metro_beat(1)
    assert screen._metro_dot.bgcolor == theme.THEME["chord"]
