"""Deja los clicks del metrónomo en un formato que Android sí reproduce.

Convierte assets/click_hi.wav y click_lo.wav (que pueden venir de una extracción
de video en WAV float 32-bit, estéreo) a **PCM 16-bit mono**, recortando la cola
sobrante con un pequeño *fade-out* para que el golpe quede seco y no se solape a
BPM altos. Guarda una copia de los originales en assets/originales/ antes de
sobrescribir. Solo biblioteca estándar (``wave`` + ``struct``).

    python tools/prepare_clicks.py

Android (flet-audio → audioplayers) garantiza WAV PCM entero; el WAV float no.
Por eso la conversión es lo que hace que el click suene en el APK.
"""

from __future__ import annotations
import shutil
import struct
import wave
from pathlib import Path

TAIL_MARGIN_MS = 20    # margen que se deja tras el último sample audible
FADE_MS = 8            # fade-out final para no cortar con un «clic» seco
AUDIBLE = 0.02         # umbral (fracción del pico) para considerar «hay sonido»


def _read_samples(path: Path) -> tuple[list[float], int]:
    """Lee un WAV (PCM o float) y devuelve (muestras mono en [-1,1], sample rate).

    Recorre los chunks RIFF a mano para hallar ``fmt``/``data`` aunque haya chunks
    intermedios (``LIST``, ``fact``…). Soporta float 32/64 y PCM 16/32."""
    raw = path.read_bytes()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError(f"{path.name}: no es un WAV RIFF")
    pos, fmt, data = 12, None, None
    while pos + 8 <= len(raw):
        cid = raw[pos:pos + 4]
        size = struct.unpack_from("<L", raw, pos + 4)[0]
        if cid == b"fmt ":
            fmt = struct.unpack_from("<HHLLHH", raw, pos + 8)
        elif cid == b"data":
            data = (pos + 8, size)
        pos += 8 + size + (size & 1)
    if fmt is None or data is None:
        raise ValueError(f"{path.name}: faltan chunks fmt/data")
    tag, ch, rate, _, _, bits = fmt
    off, dsize = data
    n = dsize // (ch * (bits // 8))
    if tag == 3 and bits == 32:
        flat = struct.unpack_from(f"<{n * ch}f", raw, off)
    elif tag == 3 and bits == 64:
        flat = struct.unpack_from(f"<{n * ch}d", raw, off)
    elif tag == 1 and bits == 16:
        flat = [s / 32768.0 for s in struct.unpack_from(f"<{n * ch}h", raw, off)]
    elif tag == 1 and bits == 32:
        flat = [s / 2147483648.0 for s in struct.unpack_from(f"<{n * ch}i", raw, off)]
    else:
        raise ValueError(f"{path.name}: formato no soportado (tag={tag}, bits={bits})")
    mono = [sum(flat[k:k + ch]) / ch for k in range(0, len(flat), ch)]
    return mono, rate


def _trim_tail(mono: list[float], rate: int) -> list[float]:
    """Recorta la cola tras el último sample audible y aplica un fade-out corto."""
    pico = max((abs(x) for x in mono), default=0.0) or 1.0
    fin = max((k for k, x in enumerate(mono) if abs(x) > AUDIBLE * pico), default=len(mono) - 1)
    cut = min(len(mono), fin + int(rate * TAIL_MARGIN_MS / 1000))
    out = mono[:cut]
    fade = min(int(rate * FADE_MS / 1000), len(out))
    for i in range(fade):
        out[len(out) - fade + i] *= 1.0 - (i + 1) / fade
    return out


def _write_pcm16(path: Path, mono: list[float], rate: int) -> None:
    """Escribe PCM 16-bit mono (clamp a [-1,1])."""
    frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, x)) * 32767))
                      for x in mono)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)


def prepare(path: Path, backup_dir: Path, trim: bool = True) -> None:
    """Convierte ``path`` in situ a PCM 16-bit mono (con copia previa del original)."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_dir / path.name)
    mono, rate = _read_samples(path)
    dur_antes = len(mono) / rate * 1000
    if trim:
        mono = _trim_tail(mono, rate)
    _write_pcm16(path, mono, rate)
    print(f"{path.name}: {dur_antes:.0f} ms -> {len(mono) / rate * 1000:.0f} ms "
          f"· PCM 16-bit mono {rate} Hz")


def main() -> None:
    assets = Path(__file__).resolve().parent.parent / "assets"
    backup = assets / "originales"
    for nombre in ("click_hi.wav", "click_lo.wav"):
        prepare(assets / nombre, backup, trim=True)
    print(f"Originales guardados en {backup}")


if __name__ == "__main__":
    main()
