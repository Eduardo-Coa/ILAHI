"""Genera la pista del metrónomo como un WAV listo para reproducir en bucle.

Por qué existe: disparar un click por golpe desde Python suena a destiempo. Cada
``play()`` es un mensaje que viaja hasta el motor de audio y tarda algo distinto
cada vez, así que el ritmo lo terminaba marcando el transporte y no el reloj del
metrónomo (el oído nota variaciones de 20–30 ms de sobra).

La solución es no disparar golpes: se graba la pista con los clicks ya puestos en
su sitio (acento incluido) y se deja que el motor de audio la repita en bucle. El
tempo lo lleva el audio nativo con precisión de sample, sin un solo mensaje por
golpe.

Dos detalles que costaron caro y conviene no deshacer:

- La pista dura ``LOOP_SECONDS``, no un compás: el motor no reinicia el bucle sin
  costura, y con un compás suelto ese corte se comía el golpe 1 en cada vuelta.
- Se entrega por RUTA de archivo (ver ``write_measure``), nunca en bytes ni como
  nombre de asset.

Solo biblioteca estándar (``wave`` + ``io``): se prueba sin UI ni dispositivo.
"""

from __future__ import annotations
import io
import math
import wave
from pathlib import Path

from database.config import data_dir

# Los clicks viven en assets/ (ver tools/prepare_clicks.py). Se leen de disco en
# vez de bundlearlos aquí para que el usuario pueda cambiarlos sin tocar código.
ASSETS = Path(__file__).resolve().parent.parent / "assets"
CLICK_HI = ASSETS / "click_hi.wav"     # acento (golpe 1)
CLICK_LO = ASSETS / "click_lo.wav"     # golpe normal

# Segundos que dura la pista: NO se graba un compás suelto, sino todos los que
# quepan aquí. El motor de audio no reinicia el bucle sin costura (mete una
# micro-pausa), y con un compás de 3 s eso arruinaba el golpe 1 —se atrasaba y el
# final se desvanecía— veinte veces por minuto. Con la pista larga el corte pasa
# a ocurrir una vez cada dos minutos. El peso en disco (~11 MB) da igual: el
# archivo no viaja, se abre por ruta.
LOOP_SECONDS = 120.0


class ClickTrackError(RuntimeError):
    """Los clicks no se pueden leer o no son compatibles entre sí."""


def _read_click(path: Path) -> tuple[bytes, int]:
    """Muestras PCM y sample rate de un click. Exige PCM 16-bit mono."""
    try:
        with wave.open(str(path), "rb") as w:
            if w.getsampwidth() != 2 or w.getnchannels() != 1:
                raise ClickTrackError(
                    f"{path.name}: se espera PCM 16-bit mono "
                    f"(ver tools/prepare_clicks.py)")
            return w.readframes(w.getnframes()), w.getframerate()
    except ClickTrackError:
        raise
    except Exception as ex:                     # archivo ausente o corrupto
        raise ClickTrackError(f"{path.name}: no se pudo leer ({ex})") from ex


def write_measure(bpm: int, beats: int = 0) -> Path:
    """Escribe el compás en la carpeta de datos y devuelve su ruta ABSOLUTA.

    Se entrega como RUTA DE ARCHIVO, y no de las otras dos formas que se probaron
    y fallaron:

    - ``bytes`` por el canal de Flet: ``TimeoutException``; el WAV pesa cientos de
      KB y no cabe en un mensaje del protocolo.
    - nombre de asset: Flutter fija su lista de assets al COMPILAR, así que un
      archivo escrito en runtime no lo sirve (queda mudo, y encima sin error).

    Con la ruta, el motor de audio abre el archivo directo del dispositivo: nada
    pesado cruza el protocolo y el tamaño deja de importar.

    Cada tempo escribe su propio archivo (para que no se reutilice uno cacheado) y
    los anteriores se borran.
    """
    data = build_measure(bpm, beats)
    carpeta = data_dir()
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"metro_{bpm}_{max(1, beats)}.wav"
    destino.write_bytes(data)
    for viejo in carpeta.glob("metro_*.wav"):
        if viejo.name != destino.name:
            try:
                viejo.unlink()
            except OSError:
                pass
    return destino


def build_measure(bpm: int, beats: int = 0,
                  hi: Path | None = None, lo: Path | None = None,
                  seconds: float = LOOP_SECONDS) -> bytes:
    """WAV (bytes) con la pista del metrónomo al tempo dado, para poner en bucle.

    ``beats`` son los golpes del compás (4 en un 4/4). Con 2 o más, el primero
    lleva el click del acento y el resto el normal; con 0 o 1 no hay acento y
    todos los golpes suenan iguales.

    Se graban TODOS los compases que quepan en ``seconds`` (no uno solo): el
    motor no reinicia el bucle sin costura, y con un compás suelto ese corte se
    comía el golpe 1 en cada vuelta. Siempre se cierra en un número entero de
    compases, para que al repetir el acento caiga a tiempo.

    Si un click no cabe entero antes del golpe siguiente (tempos muy rápidos) se
    recorta: nunca se solapa con el que viene.
    """
    hi_frames, rate = _read_click(hi or CLICK_HI)
    lo_frames, rate_lo = _read_click(lo or CLICK_LO)
    if rate != rate_lo:
        raise ClickTrackError(
            f"los clicks tienen sample rates distintos ({rate} vs {rate_lo})")
    if bpm <= 0:
        raise ClickTrackError(f"BPM inválido: {bpm}")

    n_beats = max(1, beats)
    acentuar = beats > 1                       # sin compás definido, todos iguales
    step = rate * 60.0 / bpm                   # muestras entre golpe y golpe
    compas_s = (60.0 / bpm) * n_beats
    compases = max(1, math.ceil(max(0.0, seconds) / compas_s))
    golpes = n_beats * compases
    total = int(round(step * golpes))          # entero de compases: el bucle cuadra
    buf = bytearray(total * 2)                 # silencio (PCM 16-bit)

    for i in range(golpes):
        src = hi_frames if (i % n_beats == 0 and acentuar) else lo_frames
        start = int(round(step * i)) * 2       # ×2: cada muestra son 2 bytes
        cabe = min(len(src), len(buf) - start)
        if cabe > 0:
            buf[start:start + cabe] = src[:cabe]

    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(buf))
    return out.getvalue()
