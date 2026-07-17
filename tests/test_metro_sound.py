"""Tests del sonido del metrónomo: compás en bucle (con y sin flet-audio)."""

from __future__ import annotations
import array
import io
import struct
import wave
from pathlib import Path

import asyncio
import pytest

import views.metro_sound as ms
from views.metro_sound import MetroSound
import utils.click_track as ct
from utils.click_track import build_measure, write_measure, ClickTrackError, _shape


class _FakePage:
    """Página mínima: junta servicios y tareas agendadas, sin UI real."""

    def __init__(self) -> None:
        self.services: list = []
        self.tasks: list = []

    def run_task(self, fn, *args) -> None:
        self.tasks.append(fn)

    def update(self) -> None:
        pass


# ---------------------------------------------------------------------------
# El compás (utils/click_track.py)
# ---------------------------------------------------------------------------

def _golpes(data: bytes, umbral: int = 3000, min_gap: float = 0.2):
    """(instantes de los golpes, picos, duración). Un click cruza el umbral
    varias veces (ataque + cuerpo), así que se agrupan por cercanía."""
    with wave.open(io.BytesIO(data), "rb") as w:
        n, rate = w.getnframes(), w.getframerate()
        xs = struct.unpack(f"<{n}h", w.readframes(n))
    on: list[float] = []
    for i, v in enumerate(xs):
        if abs(v) > umbral:
            t = i / rate
            if not on or t - on[-1] > min_gap:
                on.append(t)
    picos = [max(abs(v) for v in xs[int(t * rate):int(t * rate) + 3000]) for t in on]
    return on, picos, n / rate


def test_los_golpes_van_espaciados_exacto_en_toda_la_pista():
    on, _, _ = _golpes(build_measure(72, 4))
    assert len(on) % 4 == 0                        # compases enteros
    for a, b in zip(on, on[1:]):
        assert abs((b - a) - 60 / 72) < 0.002      # 0,8333 s entre golpes


def test_el_bucle_cierra_en_un_numero_entero_de_compases():
    """Al repetirse, el golpe 1 cae a tiempo: si la pista durara de más o de menos,
    cada vuelta correría el ritmo."""
    dur = _golpes(build_measure(72, 4))[2]
    compas = (60 / 72) * 4
    assert abs(dur / compas - round(dur / compas)) < 0.001


def test_la_pista_es_larga_para_que_el_bucle_reinicie_poco():
    """Regresión: NO grabar un compás suelto.

    El motor no reinicia el bucle sin costura (mete una micro-pausa), y con un
    compás de ~3 s ese corte se comía el golpe 1 —se atrasaba y el final se
    desvanecía— en cada vuelta. Con la pista larga el corte pasa a ocurrir una vez
    cada dos minutos.
    """
    dur = _golpes(build_measure(72, 4))[2]
    assert dur >= 60, f"la pista dura {dur:.1f}s: el bucle reiniciaría demasiado"


def test_el_acento_cae_en_cada_primer_tiempo_de_toda_la_pista():
    """No solo en el primer compás: el patrón se repite en los 36 que trae."""
    on, picos, _ = _golpes(build_measure(72, 4))
    assert len(on) > 100                            # pista larga, no un compás
    acentos = [p for i, p in enumerate(picos) if i % 4 == 0]
    normales = [p for i, p in enumerate(picos) if i % 4 != 0]
    assert min(acentos) > max(normales)             # todo acento pega más que todo normal


def test_el_primer_golpe_del_compas_es_el_acento():
    _, picos, _ = _golpes(build_measure(72, 4))
    assert picos[0] > picos[1] * 1.2
    assert len(set(picos[1:4])) == 1               # los otros tres, todos iguales


def _samples(data: bytes) -> array.array:
    a = array.array("h")
    a.frombytes(data)
    return a


def test_shape_seca_el_click_y_baja_el_volumen():
    """`_shape` recorta la cola (queda SECO) y escala la amplitud."""
    rate = 48000
    largo = int(rate * 0.2)                         # click de 200 ms, amplitud 20000
    frames = struct.pack(f"<{largo}h", *([20000] * largo))

    seco = _samples(_shape(frames, rate, dry_ms=60.0))
    assert len(seco) <= int(rate * 0.061)          # recortado a ~60 ms (no 200)
    assert seco[-1] == 0                            # fundido de salida: cierra en 0

    bajo = _samples(_shape(frames, rate, gain=0.5))
    assert max(abs(v) for v in bajo) <= 10001       # a la mitad
    assert len(bajo) == largo                       # sin dry_ms no se recorta


def test_el_acento_es_seco_y_manda_sobre_los_normales():
    """Regresión del carácter: el 1 va SECO (sin cola) y pega más que los normales.

    Se mide en una pista lenta (los clicks no se pisan). La sequedad se comprueba
    contra el propio acento: pasada su ventana seca, su cola cae a silencio (no
    depende de la envolvente del golpe normal, que confundiría la medida).
    """
    data = build_measure(60, 4)                     # 1 s entre golpes: sin solape
    _, picos, _ = _golpes(data)
    assert picos[0] > max(picos[1:4]) * 1.5         # el acento resalta de sobra

    rate = 48000
    with wave.open(io.BytesIO(data), "rb") as w:
        xs = struct.unpack(f"<{w.getnframes()}h", w.readframes(w.getnframes()))

    def maxabs(desde_ms: float, hasta_ms: float) -> int:
        return max((abs(v) for v in xs[int(desde_ms / 1000 * rate):
                                       int(hasta_ms / 1000 * rate)]), default=0)

    ataque = maxabs(0, 30)                           # el golpe 1 empieza en t=0
    cola = maxabs(80, 130)                           # tras la ventana seca (~60 ms)
    assert cola < ataque * 0.1                       # la cola cayó a silencio: es seco


def test_sin_compas_definido_no_hay_acento():
    """Un ritmo que no es un quebrado (o vacío) suena parejo, sin acentuar."""
    on, picos, _ = _golpes(build_measure(90, 0))
    assert len(set(picos)) == 1                    # todos los golpes iguales
    for a, b in zip(on, on[1:]):
        assert abs((b - a) - 60 / 90) < 0.002


def test_tempo_rapido_no_solapa_los_clicks():
    on, _, _ = _golpes(build_measure(240, 4))
    for a, b in zip(on, on[1:]):
        assert abs((b - a) - 60 / 240) < 0.002     # 0,25 s: el click cabe justo


def test_bpm_invalido_falla_claro():
    with pytest.raises(ClickTrackError):
        build_measure(0, 4)


def test_click_que_no_es_pcm_16_falla_claro(tmp_path):
    """Los WAV deben venir de tools/prepare_clicks.py (PCM 16-bit mono)."""
    malo = tmp_path / "estereo.wav"
    with wave.open(str(malo), "wb") as w:
        w.setnchannels(2)                          # estéreo: no sirve
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(b"\x00" * 400)
    with pytest.raises(ClickTrackError):
        build_measure(90, 4, hi=malo, lo=malo)


def test_los_clicks_de_assets_existen_y_sirven():
    """Los assets reales arman un compás (no solo los de prueba)."""
    assert build_measure(72, 4)[:4] == b"RIFF"


# ---------------------------------------------------------------------------
# El servicio de audio (views/metro_sound.py)
# ---------------------------------------------------------------------------

def test_no_deja_mas_de_un_audio_montado(tmp_path, monkeypatch):
    """Cada tempo monta un Audio NUEVO (con su fuente ya puesta) y descarta el anterior.

    El ``src`` se pasa en el constructor porque mutarlo sobre un control ya montado
    dejaba el ``play()`` esperando para siempre (``TimeoutException``).
    """
    monkeypatch.setattr(ct, "data_dir", lambda: tmp_path)
    page = _FakePage()
    sound = MetroSound(page)
    assert sound.enabled

    sound.start(72, 4)
    assert len(page.services) == 1
    sound.start(90, 4)                             # cambiar de tempo
    assert len(page.services) == 1                 # no se acumulan controles


def test_start_y_stop_agendan_el_bucle():
    page = _FakePage()
    sound = MetroSound(page)
    sound.start(72, 4)
    sound.stop()
    assert len(page.tasks) == 2                    # lanzar + parar


def test_el_compas_se_entrega_como_ruta_de_archivo(tmp_path, monkeypatch):
    """El ``src`` debe ser la RUTA de un WAV en el dispositivo.

    Las otras dos formas fallaron: en bytes por el canal de Flet da
    ``TimeoutException`` (pesa cientos de KB), y como nombre de asset queda mudo
    (Flutter fija su lista de assets al compilar). Con la ruta no cruza nada
    pesado y el motor abre el archivo directo.
    """
    monkeypatch.setattr(ct, "data_dir", lambda: tmp_path)   # nunca la carpeta real
    page = _FakePage()
    sound = MetroSound(page)
    sound.start(72, 4)
    asyncio.run(page.tasks[0]())                   # ejecuta el lanzamiento
    audio = page.services[0]

    assert isinstance(audio.src, str)              # ruta, no bytes
    creado = Path(audio.src)
    assert creado.is_absolute() and creado.exists()
    with wave.open(str(creado), "rb") as w:        # es un WAV válido y con contenido
        assert w.getnframes() > 0


def test_cambiar_el_tempo_no_deja_compases_viejos(tmp_path, monkeypatch):
    """Cada tempo escribe su archivo (para que no se reutilice uno cacheado) y los
    anteriores se borran, para no llenar el almacenamiento del teléfono."""
    monkeypatch.setattr(ct, "data_dir", lambda: tmp_path)
    write_measure(72, 4)
    write_measure(90, 4)

    assert sorted(p.name for p in tmp_path.glob("metro_*.wav")) == ["metro_90_4.wav"]


def test_start_pone_el_compas_en_modo_bucle(tmp_path, monkeypatch):
    """El bucle lo lleva el motor nativo: es lo que da el tempo exacto."""
    monkeypatch.setattr(ct, "data_dir", lambda: tmp_path)
    page = _FakePage()
    MetroSound(page).start(72, 4)
    audio = page.services[0]
    assert audio.release_mode == ms._fta.ReleaseMode.LOOP
    assert audio.src                               # la fuente va desde el constructor


def test_sin_flet_audio_es_noop(monkeypatch):
    """Sin el paquete, el metrónomo queda mudo y nada explota."""
    monkeypatch.setattr(ms, "_fta", None)
    page = _FakePage()
    sound = MetroSound(page)
    assert not sound.enabled
    sound.start(72, 4)                             # no lanza ni agenda nada
    sound.stop()
    assert page.tasks == []
    assert page.services == []


def test_assets_de_click_existen_y_son_wav_validos():
    assets = Path(__file__).resolve().parent.parent / "assets"
    for nombre in ("click_hi.wav", "click_lo.wav"):
        ruta = assets / nombre
        assert ruta.exists(), f"falta {nombre} (correr tools/prepare_clicks.py)"
        with wave.open(str(ruta), "rb") as w:
            # PCM entero (Android no garantiza WAV float), mono y con contenido.
            assert w.getnchannels() == 1
            assert w.getsampwidth() == 2
            assert w.getframerate() > 0
            assert w.getnframes() > 0
