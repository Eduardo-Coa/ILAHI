"""Tests del sonido del metrónomo (con y sin flet-audio instalado)."""

from __future__ import annotations
from pathlib import Path
import wave

import views.metro_sound as ms
from views.metro_sound import MetroSound


class _FakePage:
    """Página mínima: junta servicios y tareas agendadas, sin UI real."""

    def __init__(self) -> None:
        self.services: list = []
        self.tasks: list = []

    def run_task(self, fn, *args) -> None:
        self.tasks.append(fn)

    def update(self) -> None:
        pass


def test_crea_servicios_y_los_reutiliza():
    """Dos Audio (acento y normal) por página; otra visita no los duplica."""
    page = _FakePage()
    s1 = MetroSound(page)
    assert s1.enabled
    assert len(page.services) == 2
    s2 = MetroSound(page)              # segunda visita al escenario
    assert s2.enabled
    assert len(page.services) == 2     # reutilizados, no duplicados


def test_click_agenda_play_por_golpe():
    page = _FakePage()
    sound = MetroSound(page)
    sound.click(0)                     # acento
    sound.click(1)
    sound.click(2)
    assert len(page.tasks) == 3


def test_sin_flet_audio_es_noop(monkeypatch):
    """Sin el paquete, el metrónomo sigue (solo visual) y nada explota."""
    monkeypatch.setattr(ms, "_fta", None)
    page = _FakePage()
    sound = MetroSound(page)
    assert not sound.enabled
    sound.click(0)                     # no lanza ni agenda nada
    assert page.tasks == []
    assert page.services == []


def test_assets_de_click_existen_y_son_wav_validos():
    """Los WAV generados por tools/make_clicks.py están en assets y se pueden leer."""
    assets = Path(__file__).resolve().parent.parent / "assets"
    for nombre in ("click_hi.wav", "click_lo.wav"):
        ruta = assets / nombre
        assert ruta.exists(), f"falta {nombre} (correr tools/make_clicks.py)"
        with wave.open(str(ruta), "rb") as w:
            # PCM entero (Android no garantiza WAV float), mono y con contenido.
            # El sample rate puede ser 44100 (clicks sintéticos) o 48000 (audio
            # propio convertido con tools/prepare_clicks.py): ambos valen.
            assert w.getnchannels() == 1
            assert w.getsampwidth() == 2          # 16-bit PCM
            assert w.getframerate() > 0
            assert w.getnframes() > 0
