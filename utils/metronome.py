"""Lógica del metrónomo para la vista de escenario.

Metrónomo asíncrono con agenda por deadline: cada golpe se programa a partir
del deadline TEÓRICO anterior (no del instante real en que sonó el golpe
previo), así el tempo no acumula deriva aunque el bucle se atrase. Es 100%
stdlib (``asyncio`` + ``time``) y no depende de Flet ni de ningún widget: se
puede probar por completo sin UI inyectando un reloj y un ``sleep`` simulados.
"""

from __future__ import annotations

import asyncio
import math
import re
import time
from collections.abc import Awaitable, Callable

# Rango de tempo aceptado: fuera de este rango no tiene sentido práctico para
# un ensayo o un servicio.
BPM_MIN = 30
BPM_MAX = 300

# Quebrado N/M con espacios tolerados alrededor de los números y de la barra.
_RHYTHM_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")


def valid_bpm(value: object) -> int | None:
    """Valida y normaliza un BPM.

    Acepta ``int``, ``float`` o ``str`` numérico. Devuelve el valor como
    ``int`` si cae en ``[BPM_MIN, BPM_MAX]``; en cualquier otro caso (``None``,
    texto no numérico, o fuera de rango) devuelve ``None``. ``bool`` se
    rechaza explícitamente, porque en Python es subclase de ``int`` y de otro
    modo ``True``/``False`` colarían como 1/0.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = value
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(number):
        return None
    rounded = round(number)
    return rounded if BPM_MIN <= rounded <= BPM_MAX else None


def beats_per_measure(rhythm: str | None) -> int:
    """Golpes por compás a partir de un ritmo tipo ``"4/4"``, ``"3/4"``, ``"6/8"``.

    Devuelve el numerador si el texto es exactamente un quebrado ``N/M`` con
    ``2 <= N <= 12`` (tolera espacios alrededor de los números y de la barra).
    En cualquier otro caso (``None``, vacío, texto libre como "balada", o un
    numerador fuera de rango) devuelve ``0``, que significa "sin acento".
    """
    if not rhythm:
        return 0
    match = _RHYTHM_RE.match(rhythm)
    if not match:
        return 0
    beats = int(match.group(1))
    return beats if 2 <= beats <= 12 else 0


class Metronome:
    """Metrónomo asíncrono con agenda por deadline (sin deriva acumulada).

    ``clock`` y ``sleep`` son inyectables para poder probar el bucle con un
    reloj simulado y determinista, sin esperas reales.
    """

    def __init__(
        self,
        bpm: int,
        on_beat: Callable[[int], None],
        beats: int = 0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Crea el metrónomo. No arranca el bucle: para eso usar ``run``.

        ``on_beat`` recibe el índice del golpe dentro del compás (0 = primer
        golpe = acento). Si ``beats <= 1`` no hay acento y el índice siempre
        es 0.
        """
        self._bpm: int = valid_bpm(bpm) or BPM_MIN
        self.on_beat = on_beat
        self.beats = beats
        self.clock = clock
        self.sleep = sleep
        self.playing: bool = False

    def set_bpm(self, bpm: int) -> None:
        """Cambia el tempo en vivo; afecta los deadlines a partir del próximo golpe.

        Ignora valores que ``valid_bpm`` rechace (conserva el tempo anterior).
        """
        validated = valid_bpm(bpm)
        if validated is not None:
            self._bpm = validated

    def stop(self) -> None:
        """Apaga la bandera de reproducción; ``run`` termina en el siguiente ciclo."""
        self.playing = False

    async def run(self) -> None:
        """Corre el bucle del metrónomo hasta ``stop()`` o una excepción en ``on_beat``.

        El primer golpe suena de inmediato. Cada golpe siguiente se agenda en
        ``deadline = golpe_anterior + 60/bpm``, calculado siempre desde el
        deadline TEÓRICO (no desde el instante real en que sonó el golpe
        anterior) — así el tempo no acumula deriva si el proceso se atrasa.
        Si el reloj ya pasó el deadline, el golpe suena de inmediato y el
        siguiente deadline se re-ancla desde ``clock()`` en vez de seguir
        sumando intervalos, para no disparar una ráfaga de golpes de
        recuperación.

        Si ``on_beat`` lanza una excepción, el bucle se detiene (``playing``
        queda en ``False``) y la excepción se propaga — no queda un bucle roto
        corriendo en silencio infinito.

        No permite dos ejecuciones simultáneas: si ya está corriendo, retorna
        de inmediato sin hacer nada.
        """
        if self.playing:
            return
        self.playing = True
        try:
            beat_index = 0
            self.on_beat(beat_index)
            interval = 60.0 / self._bpm
            deadline = self.clock() + interval
            while self.playing:
                delay = deadline - self.clock()
                if delay > 0:
                    await self.sleep(delay)
                    if not self.playing:
                        break
                beat_index = (beat_index + 1) % self.beats if self.beats > 1 else 0
                self.on_beat(beat_index)
                interval = 60.0 / self._bpm
                next_deadline = deadline + interval
                now = self.clock()
                if next_deadline < now:
                    next_deadline = now + interval  # re-ancla: evita ráfaga de recuperación
                deadline = next_deadline
        finally:
            self.playing = False
