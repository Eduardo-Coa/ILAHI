"""Pruebas del metrónomo (utils/metronome.py).

Cubre la validación de BPM, la extracción de golpes por compás a partir del
ritmo de texto, y el bucle asíncrono con agenda por deadline (usando un reloj
y un ``sleep`` simulados, deterministas y sin esperas reales).
"""

from __future__ import annotations

import asyncio
import pytest

from utils.metronome import BPM_MIN, BPM_MAX, Metronome, beats_per_measure, valid_bpm


# ============================================================================
# valid_bpm
# ============================================================================

def test_constantes_de_rango():
    assert BPM_MIN == 30
    assert BPM_MAX == 300


@pytest.mark.parametrize("value, expected", [
    (30, 30),
    (300, 300),
    (120, 120),
    ("95", 95),
    (95.0, 95),
])
def test_valid_bpm_acepta_valores_validos(value, expected):
    assert valid_bpm(value) == expected


@pytest.mark.parametrize("value", [
    None, "balada", True, False, 29, 301, "12x",
])
def test_valid_bpm_rechaza_valores_invalidos(value):
    assert valid_bpm(value) is None


# ============================================================================
# beats_per_measure
# ============================================================================

@pytest.mark.parametrize("rhythm, expected", [
    ("4/4", 4),
    ("3/4", 3),
    ("6/8", 6),
    (" 4 / 4 ", 4),
    (None, 0),
    ("", 0),
    ("balada", 0),
    ("1/4", 0),   # numerador fuera de rango (< 2)
    ("13/8", 0),  # numerador fuera de rango (> 12)
])
def test_beats_per_measure(rhythm, expected):
    assert beats_per_measure(rhythm) == expected


# ============================================================================
# Metronome — reloj y sleep simulados
# ============================================================================

class _FakeClock:
    """Reloj simulado: ``sleep`` avanza el reloj exactamente lo que se le pide.

    Determinista y sin esperas reales: ideal para probar la agenda del
    metrónomo sin depender de temporizadores del sistema.
    """

    def __init__(self) -> None:
        self.now = 0.0

    def clock(self) -> float:
        """Instante actual del reloj simulado."""
        return self.now

    async def sleep(self, delay: float) -> None:
        """"Duerme" avanzando el reloj simulado en ``delay`` segundos."""
        self.now += delay


def test_primer_golpe_es_inmediato():
    """El primer golpe suena en t=0, sin esperar ningún intervalo."""
    fc = _FakeClock()
    log: list[tuple[float, int]] = []

    def on_beat(index: int) -> None:
        log.append((fc.now, index))
        metro.stop()

    metro = Metronome(60, on_beat, clock=fc.clock, sleep=fc.sleep)
    asyncio.run(metro.run())

    assert log == [(0.0, 0)]


def test_indices_ciclan_con_beats():
    """Con beats=4 los índices ciclan 0,1,2,3,0,1,... (0 = acento)."""
    fc = _FakeClock()
    log: list[int] = []

    def on_beat(index: int) -> None:
        log.append(index)
        if len(log) >= 6:
            metro.stop()

    metro = Metronome(120, on_beat, beats=4, clock=fc.clock, sleep=fc.sleep)
    asyncio.run(metro.run())

    assert log == [0, 1, 2, 3, 0, 1]


def test_indices_siempre_cero_sin_beats():
    """Con beats=0 (sin acento) el índice siempre es 0."""
    fc = _FakeClock()
    log: list[int] = []

    def on_beat(index: int) -> None:
        log.append(index)
        if len(log) >= 5:
            metro.stop()

    metro = Metronome(120, on_beat, beats=0, clock=fc.clock, sleep=fc.sleep)
    asyncio.run(metro.run())

    assert log == [0, 0, 0, 0, 0]


def test_indices_siempre_cero_con_un_solo_beat():
    """Con beats=1 tampoco hay acento: el índice siempre es 0."""
    fc = _FakeClock()
    log: list[int] = []

    def on_beat(index: int) -> None:
        log.append(index)
        if len(log) >= 3:
            metro.stop()

    metro = Metronome(120, on_beat, beats=1, clock=fc.clock, sleep=fc.sleep)
    asyncio.run(metro.run())

    assert log == [0, 0, 0]


def test_deadlines_espaciados_sin_deriva():
    """Tras 15+ golpes, cada deadline queda exactamente a k*(60/bpm), sin deriva."""
    fc = _FakeClock()
    times: list[float] = []
    bpm = 100
    interval = 60.0 / bpm

    def on_beat(index: int) -> None:
        times.append(fc.now)
        if len(times) >= 15:
            metro.stop()

    metro = Metronome(bpm, on_beat, clock=fc.clock, sleep=fc.sleep)
    asyncio.run(metro.run())

    assert len(times) == 15
    for i, t in enumerate(times):
        assert t == pytest.approx(i * interval)


def test_set_bpm_cambia_el_intervalo_de_los_proximos_golpes():
    """set_bpm en vivo no afecta el golpe en curso, solo los siguientes."""
    fc = _FakeClock()
    times: list[float] = []

    def on_beat(index: int) -> None:
        times.append(fc.now)
        if len(times) == 2:
            metro.set_bpm(120)  # duplica el tempo a partir del próximo golpe
        if len(times) >= 4:
            metro.stop()

    metro = Metronome(60, on_beat, clock=fc.clock, sleep=fc.sleep)
    asyncio.run(metro.run())

    assert times[1] - times[0] == pytest.approx(1.0)   # a 60 bpm: 1s
    assert times[2] - times[1] == pytest.approx(0.5)   # ya en 120 bpm: 0.5s
    assert times[3] - times[2] == pytest.approx(0.5)


def test_set_bpm_ignora_valores_invalidos():
    """set_bpm con un valor fuera de rango deja el tempo anterior intacto."""
    fc = _FakeClock()
    times: list[float] = []

    def on_beat(index: int) -> None:
        times.append(fc.now)
        if len(times) == 1:
            metro.set_bpm(9999)  # inválido: se ignora
        if len(times) >= 3:
            metro.stop()

    metro = Metronome(60, on_beat, clock=fc.clock, sleep=fc.sleep)
    asyncio.run(metro.run())

    assert times[1] - times[0] == pytest.approx(1.0)
    assert times[2] - times[1] == pytest.approx(1.0)


def test_stop_termina_el_bucle():
    fc = _FakeClock()
    count = 0

    def on_beat(index: int) -> None:
        nonlocal count
        count += 1
        if count >= 3:
            metro.stop()

    metro = Metronome(200, on_beat, clock=fc.clock, sleep=fc.sleep)
    asyncio.run(metro.run())

    assert count == 3
    assert metro.playing is False


def test_excepcion_en_on_beat_termina_el_bucle():
    """Si on_beat lanza, el bucle se corta (playing=False) y la excepción se propaga."""
    fc = _FakeClock()

    def on_beat(index: int) -> None:
        raise RuntimeError("boom")

    metro = Metronome(120, on_beat, clock=fc.clock, sleep=fc.sleep)

    with pytest.raises(RuntimeError):
        asyncio.run(metro.run())

    assert metro.playing is False


def test_excepcion_en_golpe_posterior_tambien_detiene_el_bucle():
    """La excepción también corta el bucle si ocurre después del primer golpe."""
    fc = _FakeClock()
    count = 0

    def on_beat(index: int) -> None:
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError("boom")

    metro = Metronome(120, on_beat, clock=fc.clock, sleep=fc.sleep)

    with pytest.raises(RuntimeError):
        asyncio.run(metro.run())

    assert count == 2
    assert metro.playing is False


def test_run_no_permite_doble_ejecucion():
    """Si ya está corriendo, una segunda llamada a run() retorna sin hacer nada."""
    fc = _FakeClock()
    calls = 0

    def on_beat(index: int) -> None:
        nonlocal calls
        calls += 1

    metro = Metronome(120, on_beat, clock=fc.clock, sleep=fc.sleep)
    metro.playing = True  # simula que ya hay un run() en curso

    asyncio.run(metro.run())

    assert calls == 0             # no debió sonar ningún golpe
    assert metro.playing is True  # la llamada duplicada no tocó el estado
