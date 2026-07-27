"""Pruebas del metrónomo integrado en el modo escenario (``PresentScreen``).

Headless: no se ejecuta la app real, solo se construye el árbol de controles con
una página falsa (sin ventana) y se inspecciona su estructura, igual que
``test_stage_align.py`` hace con la alineación de acordes.
"""

from __future__ import annotations

import asyncio

import flet as ft

from models.song import Song
from views.stage_view import PresentScreen, StageScreen, _USER_GRACE
import theme


class _RecordingBody:
    """ListView de mentira que anota los ``scroll_to`` (offset, ms, curva)."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def scroll_to(self, offset=None, duration=0, curve=None, **_kw):
        self.calls.append((offset, duration, curve))


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


def test_arrastrar_con_el_autoscroll_activo_relanza_al_soltar():
    """Regresión: con ▶ activo, arrastrar la pantalla (p. ej. al inicio) cancela la
    animación nativa; al soltar, el autoscroll debe RETOMAR solo, sin tener que mover el
    slider de velocidad. El relanzado se marca en el propio evento de scroll, así que no
    depende de que el supervisor observe el gesto a mitad de camino (un arrastre corto
    puede caber entre dos chequeos)."""
    screen = PresentScreen(_FakePage(), Song(id=15, title="D", sections=[]),
                           0, on_exit=lambda: None)
    screen._playing = True
    screen._needs_restart = False
    screen._pixels = 800.0

    screen._on_scroll(_scroll_event(ft.ScrollType.USER, 800.0,
                                    ft.ScrollDirection.REVERSE))    # agarra y arrastra
    screen._on_scroll(_scroll_event(ft.ScrollType.UPDATE, 0.0))    # hasta el inicio
    screen._on_scroll(_scroll_event(ft.ScrollType.END, 0.0))       # suelta

    assert screen._needs_restart is True        # el supervisor relanzará el glide
    assert screen._user_moving() is False       # ya soltó: nada le cede el mando
    assert screen._pixels == 0.0                # y retoma desde donde dejó la letra


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


def test_durante_la_animacion_se_sigue_la_posicion_real():
    """El deslizamiento es una sola animación nativa hacia un destino FIJO (el final),
    así que sus posiciones intermedias ya no frenan el avance y SÍ se siguen: hacen
    falta para pausar o cambiar la velocidad y continuar desde donde va la letra."""
    screen = PresentScreen(_FakePage(), Song(id=9, title="R", sections=[]),
                           0, on_exit=lambda: None)
    screen._playing = True
    screen._pixels = 500.0

    screen._on_scroll(_scroll_event(ft.ScrollType.UPDATE, 503.0))

    assert screen._pixels == 503.0


def test_el_glide_va_al_final_en_una_sola_animacion_lineal():
    """El corazón del arreglo: una única animación nativa hasta el final, con duración
    = distancia restante / velocidad y curva LINEAL (sin easing = sin pulso)."""
    screen = PresentScreen(_FakePage(), Song(id=11, title="G", sections=[]),
                           0, on_exit=lambda: None)
    screen._body = _RecordingBody()
    screen._playing = True
    screen._max_extent = 1000.0
    screen._pixels = 100.0
    screen._speed = 90.0                       # 900 px restantes ÷ 90 px/s = 10 s

    asyncio.run(screen._launch_glide())

    offset, ms, curve = screen._body.calls[-1]
    assert offset == 1000.0                    # una sola animación hasta el final
    assert ms == 10000                         # 10 s, del ritmo del slider
    assert curve == ft.AnimationCurve.LINEAR   # pareja de punta a punta


def test_pausar_corta_la_animacion_donde_va_la_letra():
    """Pausar reemplaza la animación nativa en curso por un salto de duración 0 a la
    posición actual: la letra se queda donde va, no donde arrancó el deslizamiento."""
    screen = PresentScreen(_FakePage(), Song(id=12, title="P", sections=[]),
                           0, on_exit=lambda: None)
    screen._body = _RecordingBody()
    screen._pixels = 640.0

    asyncio.run(screen._freeze())

    offset, ms, _curve = screen._body.calls[-1]
    assert offset == 640.0 and ms == 0


def test_cambiar_la_velocidad_mientras_toca_marca_relanzar():
    """Con el autoscroll activo, mover el slider relanza la animación (nueva duración)."""
    screen = PresentScreen(_FakePage(), Song(id=13, title="V", sections=[]),
                           0, on_exit=lambda: None)
    screen._playing = True
    screen._needs_restart = False

    screen._on_speed(type("E", (), {"control": type("C", (), {"value": 40.0})()})())

    assert screen._speed == 40.0
    assert screen._needs_restart is True


def test_cambiar_la_velocidad_en_pausa_no_relanza_nada():
    """Sin reproducir no hay animación que relanzar: solo se guarda la velocidad."""
    screen = PresentScreen(_FakePage(), Song(id=14, title="W", sections=[]),
                           0, on_exit=lambda: None)
    screen._playing = False
    screen._needs_restart = False

    screen._on_speed(type("E", (), {"control": type("C", (), {"value": 40.0})()})())

    assert screen._speed == 40.0
    assert screen._needs_restart is False


def test_tocar_la_pantalla_mientras_toca_marca_relanzar():
    """Regresión: con el autoscroll activo, tocar la pantalla para ocultar/mostrar el
    chrome dejaba la letra congelada (el ícono seguía en ⏸).

    El toque cancela la animación nativa —Flutter frena cualquier animación de scroll
    en cuanto un dedo toca la lista— y ``_on_scroll`` no lo cubría: solo marca el
    relanzado ante un ARRASTRE (movimiento con el turno del usuario abierto, o un
    evento USER con dirección), y un toque simple no produce ninguno de los dos.
    """
    screen = PresentScreen(_FakePage(), Song(id=16, title="T", sections=[]),
                           0, on_exit=lambda: None)
    screen._playing = True
    screen._needs_restart = False

    screen._toggle_panel()

    assert screen._needs_restart is True


def test_tocar_la_pantalla_en_pausa_no_relanza_nada():
    """Sin reproducir no hay animación que relanzar: tocar solo oculta el chrome."""
    screen = PresentScreen(_FakePage(), Song(id=17, title="U", sections=[]),
                           0, on_exit=lambda: None)
    screen._playing = False
    screen._needs_restart = False

    screen._toggle_panel()

    assert screen._needs_restart is False


def test_tocar_la_pantalla_no_mueve_la_letra():
    """El toque alterna el chrome y nada más: no debe tocar el scroll (ni reanclarlo),
    o la letra brincaría bajo el dedo."""
    screen = PresentScreen(_FakePage(), Song(id=18, title="V", sections=[]),
                           0, on_exit=lambda: None)
    screen._body = _RecordingBody()
    screen._playing = True
    screen._pixels = 250.0

    screen._toggle_panel()

    assert screen._body.calls == []            # ningún scroll_to
    assert screen._pixels == 250.0


def test_el_toggle_arranca_y_detiene_el_bucle_del_compas():
    """El compás suena en bucle desde el motor de audio; aquí solo se alterna.

    Ya no hay bucle de Python ni punto que late: disparar un click por golpe
    sonaba a destiempo (cada ``play()`` tardaba algo distinto en llegar al motor).
    """
    song = Song(id=1, title="X", bpm=90, rhythm="4/4", sections=[])
    screen = PresentScreen(_FakePage(), song, 0, on_exit=lambda: None)
    screen.build()
    llamadas: list = []
    screen._metro_sound.start = lambda bpm, beats: llamadas.append(("start", bpm, beats))
    screen._metro_sound.stop = lambda: llamadas.append(("stop",))

    screen._toggle_metro()
    assert screen._metro_on is True
    assert llamadas == [("start", 90, 4)]          # 4/4 → acento cada 4 golpes

    screen._toggle_metro()
    assert screen._metro_on is False
    assert llamadas[-1] == ("stop",)


def test_stop_apaga_el_metronomo_al_abandonar_la_pantalla():
    """Regresión: salir apaga el metrónomo, aunque no sea por la ✕.

    El «atrás» del sistema navega saltándose el ``_exit`` de la vista; por eso la
    parada vive en ``stop()``, que ``main`` llama al abandonar cualquier pantalla.
    Antes el metrónomo seguía sonando en la pantalla anterior.
    """
    song = Song(id=1, title="X", bpm=90, rhythm="4/4", sections=[])
    screen = PresentScreen(_FakePage(), song, 0, on_exit=lambda: None)
    screen.build()
    llamadas: list = []
    screen._metro_sound.start = lambda bpm, beats: llamadas.append("start")
    screen._metro_sound.stop = lambda: llamadas.append("stop")

    screen._toggle_metro()                         # queda sonando
    assert screen._metro_on is True

    screen.stop()                                  # al abandonar la pantalla
    assert screen._metro_on is False               # el metrónomo se apagó
    assert llamadas[-1] == "stop"
    assert screen._playing is False                # y el autoscroll también


def test_cambiar_el_tempo_rearma_el_compas_solo_si_esta_sonando():
    song = Song(id=2, title="Y", bpm=90, rhythm="4/4", sections=[])
    screen = PresentScreen(_FakePage(), song, 0, on_exit=lambda: None)
    screen.build()
    llamadas: list = []
    screen._metro_sound.start = lambda bpm, beats: llamadas.append(bpm)

    screen._adjust_metro_bpm(5)                    # detenido: no rearma nada
    assert llamadas == []
    assert screen._bpm == 95

    screen._metro_on = True
    screen._adjust_metro_bpm(5)                    # sonando: rearma al tempo nuevo
    assert llamadas == [100]
