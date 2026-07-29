"""Importar una canción desde un enlace (por ahora, Cifra Club).

Baja el HTML, extrae título/artista y la cifra (acordes sobre la letra), y limpia la
basura que la web inyecta. Devuelve el texto en el mismo formato que ya entiende
``utils.lyrics_parser.parse_lyrics`` —acordes en columnas—, así que NO reimplementa el
parseo; solo consigue el texto y lo deja limpio.

No guarda nada: el que llama lleva el resultado al editor para que el usuario revise
antes de guardar (las webs traen erratas y el import nunca sale perfecto).

Diseño para poder probarlo sin red: ``fetch_html`` (que sí usa internet) está separado
de ``extract_cifra`` (HTML → canción), y ``import_song`` acepta un ``fetch`` inyectable.
"""

from __future__ import annotations

import re
import html as _html
import urllib.request
import urllib.error
from dataclasses import dataclass
from urllib.parse import urlparse

# User-agent de navegador: sin él, Cifra a veces sirve HTML distinto o bloquea.
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

_TIMEOUT = 20

# Dominios de Cifra Club (internacional y Brasil).
_CIFRA_HOSTS = ("cifraclub.com", "cifraclub.com.br")

# Texto de anuncio que Cifra inyecta DENTRO de la cifra, casi siempre pegado al
# principio de una línea de acordes: «Continúa después del anuncio     Am   B7». Se
# reemplaza por espacios de igual largo para NO desalinear los acordes que le siguen.
_AD_RE = re.compile(
    r"Contin[uú]a\s+(?:despu[eé]s\s+del|ap[oó]s\s+o)\s+an[uú]ncio", re.IGNORECASE)


class SongImportError(Exception):
    """Falla de import con un mensaje listo para mostrarle al usuario (``message``)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class ImportedSong:
    """Resultado de un import: metadatos + texto para ``parse_lyrics``."""
    title: str
    artist: str
    text: str
    source_url: str


# ---------------------------------------------------------------------------
# Reconocer el enlace
# ---------------------------------------------------------------------------

def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def is_supported(url: str) -> bool:
    """¿El enlace es de un sitio que sabemos importar (hoy, Cifra Club)?"""
    return _host(url) in _CIFRA_HOSTS


# ---------------------------------------------------------------------------
# Bajar (la única parte que usa internet)
# ---------------------------------------------------------------------------

def fetch_html(url: str) -> str:
    """Descarga el HTML de ``url``. Lanza ``SongImportError`` con mensaje claro si algo
    falla (sin conexión, 404, bloqueo)."""
    req = urllib.request.Request(
        url, headers={"User-Agent": _UA, "Accept-Language": "es,pt;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise SongImportError("No se encontró esa página (404). Revisa el enlace.")
        raise SongImportError(f"La página respondió con un error ({e.code}).")
    except urllib.error.URLError:
        raise SongImportError("No pude conectar. Revisa tu conexión a internet.")
    except Exception:
        raise SongImportError("No pude descargar la página.")


# ---------------------------------------------------------------------------
# Extraer (HTML → canción), sin red
# ---------------------------------------------------------------------------

_PRE_RE = re.compile(r"<pre[^>]*>(.*?)</pre>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.DOTALL | re.IGNORECASE)


def _clean_ads(texto: str) -> str:
    """Quita el anuncio inyectado, dejando espacios en su lugar para no correr los
    acordes de columna. Después limpia líneas que quedaron solo con espacios."""
    lineas = []
    for linea in texto.split("\n"):
        linea = _AD_RE.sub(lambda m: " " * len(m.group()), linea)
        # Si la línea quedó vacía o solo con espacios por culpa del anuncio, va vacía.
        lineas.append("" if not linea.strip() else linea.rstrip())
    return "\n".join(lineas)


def _title_and_artist(html_txt: str) -> tuple[str, str]:
    """Título y artista desde el <title>: «Canción - Artista - Cifra Club»."""
    m = _TITLE_RE.search(html_txt)
    if not m:
        return ("", "")
    partes = [_html.unescape(p.strip()) for p in m.group(1).split(" - ")]
    titulo = partes[0] if partes else ""
    artista = partes[1] if len(partes) > 1 else ""
    return (titulo, artista)


def extract_cifra(html_txt: str, source_url: str = "") -> ImportedSong:
    """Extrae la canción del HTML de una página de Cifra Club. Lanza
    ``SongImportError`` si la página no trae la cifra (p. ej. es la página del
    artista, no la de una canción)."""
    m = _PRE_RE.search(html_txt)
    if not m:
        raise SongImportError(
            "Esa página no tiene la letra. Asegúrate de copiar el enlace de la "
            "canción, no el del artista.")
    cifra = _html.unescape(_TAG_RE.sub("", m.group(1))).strip("\n")
    cifra = _clean_ads(cifra)
    if not cifra.strip():
        raise SongImportError("La página no tiene acordes ni letra para importar.")
    titulo, artista = _title_and_artist(html_txt)
    return ImportedSong(title=titulo, artist=artista, text=cifra,
                        source_url=source_url)


# ---------------------------------------------------------------------------
# Todo junto
# ---------------------------------------------------------------------------

def import_song(url, fetch=fetch_html) -> ImportedSong:
    """Importa la canción del enlace: reconoce el sitio, baja y extrae.

    ``fetch`` es inyectable para poder probar sin red (se le pasa un HTML fijo).
    Lanza ``SongImportError`` (con ``.message``) ante cualquier problema.
    """
    url = (url or "").strip()
    if not url:
        raise SongImportError("Pega un enlace primero.")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise SongImportError("El enlace debe empezar con http:// o https://")
    if not is_supported(url):
        raise SongImportError(
            "Por ahora solo se pueden importar canciones de Cifra Club.")
    html_txt = fetch(url)
    return extract_cifra(html_txt, source_url=url)
