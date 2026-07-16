"""Sonido del metrónomo vía ``flet-audio`` (extensión opcional de Flet).

El control ``Audio`` ya no viene en el core de Flet: vive en el paquete
``flet-audio`` (declarado en ``pyproject.toml`` para que ``flet build`` lo
compile dentro del APK). Si el paquete no está instalado, o el cliente que
corre la app no trae el plugin de audio, TODO en este módulo degrada a no-op:
el metrónomo sigue funcionando con el pulso visual y la vista de escenario
nunca se rompe por el sonido.
"""

from __future__ import annotations

try:
    import flet_audio as _fta
except ImportError:                      # sin paquete: metrónomo solo visual
    _fta = None

# Etiquetas para encontrar (y reutilizar) los servicios ya creados en la página.
_TAG_HI = "ilahi-click-hi"
_TAG_LO = "ilahi-click-lo"


class MetroSound:
    """Par de clicks del metrónomo (acento / golpe normal) en ``page.services``.

    Los ``Audio`` se crean UNA sola vez por página y se reutilizan entre visitas
    al escenario (se buscan por su ``data``); ``ReleaseMode.STOP`` mantiene el
    sonido cargado para relanzarlo sin latencia en cada golpe.
    """

    def __init__(self, page) -> None:
        self.page = page
        self._hi = self._lo = None
        if _fta is None:
            return
        try:
            self._hi = self._attach(_TAG_HI, "click_hi.wav")
            self._lo = self._attach(_TAG_LO, "click_lo.wav")
        except Exception:                # cliente sin plugin de audio: no-op
            self._hi = self._lo = None

    def _attach(self, tag: str, src: str):
        """Devuelve el ``Audio`` ya anclado con esa etiqueta, o lo crea y ancla."""
        for svc in self.page.services:
            if getattr(svc, "data", None) == tag:
                return svc
        audio = _fta.Audio(src=src, volume=1.0,
                           release_mode=_fta.ReleaseMode.STOP)
        audio.data = tag
        self.page.services.append(audio)
        return audio

    @property
    def enabled(self) -> bool:
        """¿Hay con qué sonar? (paquete instalado y servicios creados)."""
        return self._hi is not None

    def click(self, index: int) -> None:
        """Suena el click del golpe ``index`` (0 = acento, más agudo y fuerte).

        ``play`` es async en flet-audio, así que se agenda con ``run_task``;
        cualquier error se ignora para que el pulso visual siga intacto."""
        audio = self._hi if index == 0 else self._lo
        if audio is None:
            return
        try:
            self.page.run_task(audio.play)
        except Exception:
            pass
