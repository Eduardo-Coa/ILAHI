"""Pruebas del importador desde enlace (Cifra Club).

No tocan la red: se le inyecta un HTML fijo a ``import_song`` y se prueba la extracción
en piezas de HTML sintético. Cada caso refleja algo que se vio en canciones reales de
Cifra Club durante la exploración (ver memoria import-desde-cifra-club).
"""

from __future__ import annotations

import pytest

from utils.web_import import (
    import_song, extract_cifra, is_supported, SongImportError, ImportedSong,
)
from utils.lyrics_parser import parse_lyrics


def _pagina(pre: str, title: str = "Tu Fidelidad - Marcos Witt - Cifra Club") -> str:
    """HTML mínimo de una página de Cifra Club: un <title> y un <pre> con la cifra."""
    return f"<html><head><title>{title}</title></head><body>" \
           f"<pre>{pre}</pre></body></html>"


# -- reconocer el enlace --------------------------------------------------

def test_reconoce_cifra_club():
    assert is_supported("https://www.cifraclub.com/marcos-witt/tu-fidelidad/")
    assert is_supported("https://www.cifraclub.com.br/hillsong/oceans/")


def test_no_reconoce_otros_sitios():
    assert not is_supported("https://tabs.ultimate-guitar.com/tab/123")
    assert not is_supported("https://ejemplo.com/cancion")


def test_url_de_otro_sitio_da_mensaje_claro():
    with pytest.raises(SongImportError) as exc:
        import_song("https://ultimate-guitar.com/x", fetch=lambda u: "")
    assert "Cifra Club" in exc.value.message


def test_url_vacia_o_sin_esquema():
    with pytest.raises(SongImportError):
        import_song("", fetch=lambda u: "")
    with pytest.raises(SongImportError):
        import_song("cifraclub.com/x", fetch=lambda u: "")   # sin http(s)


# -- extracción -----------------------------------------------------------

def test_extrae_titulo_artista_y_cifra():
    pre = " C        Am7\nTu fidelidad es grande"
    cancion = import_song("https://www.cifraclub.com/marcos-witt/tu-fidelidad/",
                          fetch=lambda u: _pagina(pre))
    assert cancion.title == "Tu Fidelidad"
    assert cancion.artist == "Marcos Witt"
    assert "Tu fidelidad es grande" in cancion.text
    assert cancion.source_url.endswith("tu-fidelidad/")


def test_quita_etiquetas_html_de_los_acordes():
    # Cifra pone los acordes en <b>; deben quedar como texto plano alineado.
    pre = " <b>C</b>        <b>Am7</b>\nTu fidelidad es grande"
    song = extract_cifra(_pagina(pre))
    assert "<b>" not in song.text
    assert "C" in song.text and "Am7" in song.text


def test_desescapa_entidades():
    song = extract_cifra(_pagina("Se&ntilde;or, gracias"))
    assert "Señor, gracias" in song.text


def test_pagina_de_artista_sin_pre_da_error_claro():
    html = "<html><head><title>Marcos Witt - Cifra Club</title></head>" \
           "<body>no hay cifra aquí</body></html>"
    with pytest.raises(SongImportError) as exc:
        extract_cifra(html)
    assert "artista" in exc.value.message.lower()


# -- limpieza del anuncio (lo más frecuente: 4 de 6 canciones) ------------

def test_quita_el_anuncio_conservando_alineacion():
    # El anuncio va pegado al principio de una línea de acordes; al quitarlo, los
    # acordes NO deben correrse (así siguen cayendo sobre su sílaba).
    pre = ("      Am       B7\n"
           "Dios sabe lo que hay\n"
           "Continúa después del anuncio     Am       B7\n"
           "Dios ve tu angustia")
    song = extract_cifra(_pagina(pre))
    assert "anuncio" not in song.text.lower()
    # La línea del anuncio y la de arriba tienen los acordes en la MISMA columna.
    lineas = song.text.split("\n")
    linea_limpia = next(l for l in lineas if "Am" in l and "B7" in l and "Dios" not in l)
    assert linea_limpia.index("Am") == 6          # misma columna que la primera


def test_quita_el_anuncio_en_portugues():
    pre = "Continua após o anúncio   G   D\nletra"
    song = extract_cifra(_pagina(pre))
    assert "anúncio" not in song.text.lower()
    assert "G" in song.text and "D" in song.text


# -- el texto importado alimenta el parser real ---------------------------

def test_el_texto_importado_lo_procesa_parse_lyrics():
    pre = ("[Coro]\n"
           " C        G        Am\n"
           "Grande es tu fidelidad\n"
           "Continúa después del anuncio  F   C\n"
           "Grande es tu amor")
    song = import_song("https://www.cifraclub.com/x/y/", fetch=lambda u: _pagina(pre))
    cancion = parse_lyrics(song.text, song.title)
    assert cancion.sections                       # armó al menos una sección
    assert cancion.sections[0].label == "Coro"
    # y sin rastro del anuncio en la letra
    todo = " ".join(s.text for sec in cancion.sections
                     for ln in sec.lines for s in ln.syllables)
    assert "anuncio" not in todo.lower()
