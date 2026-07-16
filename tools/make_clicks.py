"""Genera los clicks del metrónomo: assets/click_hi.wav (acento) y click_lo.wav.

Solo biblioteca estándar (``wave`` + ``math`` + ``random``); se corre una vez en
desarrollo:

    python tools/make_clicks.py

El objetivo es el «tock» seco de un metrónomo mecánico tradicional, NO un beep
tonal. Para eso cada click combina tres cosas:

1. Un transitorio de «click» (ruido que se apaga en ~3 ms): el golpe seco del
   arranque, lo que da el carácter percusivo de madera/plástico.
2. Un cuerpo tonal con parciales INARMÓNICOS (f, 2.76f, 5.2f): un tono puro
   suena a pito; los parciales corridos suenan a madera golpeada.
3. Un decaimiento exponencial MUY rápido: el sonido dura ~20–30 ms audibles, así
   se percibe como «tick» y no se vuelve molesto al repetirse.

El acento (golpe 1) es un poco más brillante y bastante más fuerte que el golpe
normal; ambos son graves comparados con la versión anterior (que era demasiado
aguda). Perillas fáciles de ajustar: FREQ_HI/FREQ_LO (qué tan agudo) y DECAY
(qué tan seco/corto).
"""

from __future__ import annotations
import math
import random
import struct
import wave
from pathlib import Path

RATE = 44100          # muestras por segundo
DURATION = 0.06       # segundos de ventana (el decaimiento lo apaga mucho antes)
ATTACK = 0.0006       # segundos de rampa inicial (anti-«pop»), muy corta = seco
DECAY = 150.0         # constante del decaimiento del cuerpo (mayor = más corto/seco)
CLICK_DECAY = 900.0   # constante del transitorio de ruido (muy rápido: ~3 ms)

# Frecuencias fundamentales (Hz). Graves respecto a la versión vieja (1568/1046)
# para que no resulten agudas ni molestas al repetirse.
FREQ_HI = 900.0       # acento (golpe 1): apenas más brillante
FREQ_LO = 680.0       # golpe normal
# Parciales inarmónicos que dan el timbre de «madera» (múltiplos no enteros). Se
# omite a propósito el parcial muy alto (5×): aportaba brillo agudo que molestaba.
PARTIALS = ((1.0, 1.0), (2.76, 0.5))


def make_click(path: Path, freq: float, amp: float, click_amp: float) -> None:
    """Escribe un click WAV mono 16-bit tipo «woodblock» de metrónomo.

    ``freq`` es la fundamental; ``amp`` la amplitud del cuerpo tonal; ``click_amp``
    la del transitorio percusivo inicial. La suma se limita a [-1, 1]."""
    rng = random.Random(int(freq))        # ruido reproducible entre corridas
    n = int(RATE * DURATION)
    attack_n = max(1, int(RATE * ATTACK))
    norm = sum(a for _, a in PARTIALS)    # normaliza el cuerpo a ~[-1, 1]
    frames = bytearray()
    for i in range(n):
        t = i / RATE
        # Cuerpo de madera: fundamental + parciales inarmónicos, decaimiento rápido.
        body = sum(a * math.sin(2 * math.pi * freq * mult * t)
                   for mult, a in PARTIALS) / norm
        body *= math.exp(-t * DECAY)
        # Transitorio seco: ruido que muere en ~3 ms (el «clack» del arranque).
        transient = rng.uniform(-1.0, 1.0) * math.exp(-t * CLICK_DECAY)
        v = amp * body + click_amp * transient
        # Rampa de ataque cortísima para no arrancar con un salto (pop).
        if i < attack_n:
            v *= i / attack_n
        frames += struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32767))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))
    print(f"{path}  ({freq:.0f} Hz, {len(frames)//2} muestras)")


def main() -> None:
    """Genera los dos clicks en la carpeta assets del proyecto."""
    assets = Path(__file__).resolve().parent.parent / "assets"
    assets.mkdir(exist_ok=True)
    make_click(assets / "click_hi.wav", freq=FREQ_HI, amp=0.80, click_amp=0.26)  # acento
    make_click(assets / "click_lo.wav", freq=FREQ_LO, amp=0.55, click_amp=0.16)  # normal


if __name__ == "__main__":
    main()
