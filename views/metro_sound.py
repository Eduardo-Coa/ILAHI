"""Sonido del metrónomo: un compás en bucle, vía ``flet-audio``.

NO se dispara un click por golpe: eso sonaba a destiempo, porque cada ``play()``
es un mensaje que tarda algo distinto en llegar al motor de audio y el ritmo lo
acababa marcando el transporte. En vez de eso se arma UN compás completo (ver
``utils.click_track``) y se deja que el motor lo repita en bucle: el tempo lo
lleva el audio nativo con precisión de sample y no se manda ni un mensaje por
golpe.

El control ``Audio`` vive en el paquete ``flet-audio`` (declarado en
``pyproject.toml`` para que ``flet build`` lo compile dentro del APK). Si el
paquete no está, o el cliente no trae el plugin, todo degrada a no-op: el
metrónomo simplemente no suena y la vista nunca se rompe.
"""

from __future__ import annotations

import logging

from utils.click_track import write_measure, ClickTrackError

try:
    import flet_audio as _fta
except ImportError:                      # sin paquete: metrónomo mudo
    _fta = None

log = logging.getLogger(__name__)

# Etiqueta para encontrar (y reutilizar) el servicio ya creado en la página.
_TAG = "ilahi-metro"


class MetroSound:
    """Reproduce el compás del metrónomo en bucle.

    El ``Audio`` se crea UNA vez por página y se reutiliza entre visitas al
    escenario (se busca por su ``data``).
    """

    def __init__(self, page) -> None:
        self.page = page
        self._audio = None

    def _attach(self, ruta: str):
        """Crea el ``Audio`` con la fuente YA puesta y lo monta en la página.

        El ``src`` va en el constructor a propósito: crear el control vacío y luego
        mutar ``src`` + ``update()`` dejaba el ``play()`` esperando para siempre
        (``TimeoutException``), tanto con bytes como con una ruta. Por eso cada
        tempo descarta el control anterior y monta uno nuevo.
        """
        for viejo in [s for s in self.page.services
                      if getattr(s, "data", None) == _TAG]:
            self.page.services.remove(viejo)
        audio = _fta.Audio(src=ruta, volume=1.0,
                           release_mode=_fta.ReleaseMode.LOOP)
        audio.data = _TAG
        self.page.services.append(audio)
        # Montarlo YA: agregarlo a la lista no lo crea en el cliente, y sin eso
        # ``play()`` falla con «Control must be added to the page first».
        try:
            self.page.update()
        except Exception:
            pass
        return audio

    @property
    def enabled(self) -> bool:
        """¿Hay con qué sonar? (el paquete de audio está instalado)."""
        return _fta is not None

    def _avisar(self, texto: str) -> None:
        """Muestra el problema al usuario; nunca deja caer un error encima."""
        try:
            from views.widgets import show_toast
            show_toast(self.page, texto, seconds=6.0)
        except Exception:
            pass

    def start(self, bpm: int, beats: int = 0) -> None:
        """Arma el compás a ese tempo y lo lanza en bucle (reemplaza al anterior).

        Los errores se registran pero nunca se propagan: si el audio falla, el
        metrónomo queda mudo y la vista sigue funcionando."""
        if _fta is None:
            return
        try:
            # Se entrega la RUTA del archivo: mandarlo en bytes por el canal de Flet
            # daba TimeoutException (pesa cientos de KB) y como nombre de asset
            # quedaba mudo (Flutter fija sus assets al compilar). Ver write_measure.
            ruta = write_measure(bpm, beats)
            audio = self._attach(str(ruta))   # control NUEVO, con la fuente ya puesta
            self._audio = audio
        except Exception as ex:
            log.warning("no se pudo preparar el metrónomo: %r", ex)
            self._avisar(f"✗ Metrónomo: {type(ex).__name__}: {ex}")
            return

        async def _lanzar() -> None:
            try:
                await audio.play()
            except Exception as ex:
                # El fallo se AVISA en pantalla: en el APK ni los print ni el log
                # llegan a donde se puedan leer, así que un metrónomo mudo sin más
                # no da ninguna pista de qué pasó.
                log.warning("play() del metrónomo falló: %r", ex)
                self._avisar(f"✗ Metrónomo sin audio: {type(ex).__name__}: {ex}")

        try:
            self.page.run_task(_lanzar)
        except Exception as ex:
            log.warning("no se pudo agendar el arranque del metrónomo: %r", ex)

    def stop(self) -> None:
        """Detiene el bucle."""
        if self._audio is None:
            return
        audio = self._audio

        async def _parar() -> None:
            try:
                await audio.pause()
            except Exception as ex:
                log.warning("pause() del metrónomo falló: %r", ex)

        try:
            self.page.run_task(_parar)
        except Exception:
            pass
