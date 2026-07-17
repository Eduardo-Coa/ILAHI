"""Editar letra trae los acordes al texto (Cifra Club) y no los pierde al editar.

- Cada línea de letra con acordes lleva su fila de acordes alineada encima.
- Los interludios/casillas siguen apareciendo como secuencia con guiones (`G - Bm`).
- Editar una línea conserva sus acordes (viajan en el texto).
"""

from utils.lyrics_parser import parse_lyrics, prepend_intro, merge_lyrics, is_chord_line
from views.edit_view import reconstruct_lyrics


def _cancion():
    txt = ("[Estrofa]\nG            D          Em        C\n"
           "Cristo es mi fiel amigo y mi salvador\n"
           "G          D      C\nen el vive mi esperanza\n"
           "\nBm - A - D - A - G\n"
           "[Coro]\nAm         F\ncantaré por siempre")
    song = parse_lyrics(txt)
    prepend_intro(song)
    return song


def _chords(line):
    return [(s.text.strip(), s.chord.value) for s in line.syllables if s.chord]


def _line(song, pref):
    return next(l for sec in song.sections for l in sec.lines
               if "".join(x.text for x in l.syllables).strip().startswith(pref))


def test_reconstruct_trae_acordes_encima_de_la_letra():
    txt = reconstruct_lyrics(_cancion())
    filas = txt.splitlines()
    i = filas.index("Cristo es mi fiel amigo y mi salvador")
    assert "G" in filas[i - 1] and "Em" in filas[i - 1]


def test_reconstruct_mantiene_interludio_con_guiones():
    txt = reconstruct_lyrics(_cancion())
    assert "Bm - A - D - A - G" in txt


def test_reconstruct_incluye_la_introduccion_con_sus_guiones():
    """La Introducción se ve y se edita: sus casillas viajan como guiones.

    Antes se omitía del texto y se conservaba aparte, así que editarla no tenía
    efecto y escribirla a mano no creaba casillas. Ahora lo que se ve es lo que hay.
    """
    txt = reconstruct_lyrics(_cancion())
    assert "[Introducción]" in txt
    # Las casillas vacías se muestran como una fila de guiones, una por casilla.
    assert "- - - - -" in txt


def test_roundtrip_sin_editar_conserva_acordes_en_las_mismas_silabas():
    song = _cancion()
    merged = merge_lyrics(song, reconstruct_lyrics(song))
    assert _chords(_line(merged, "Cristo")) == _chords(_line(song, "Cristo"))
    inter = next(l for sec in merged.sections if sec.label == "Interludio"
                 for l in sec.lines if is_chord_line(l) and any(s.chord for s in l.syllables))
    assert [s.chord.value for s in inter.syllables if s.chord] == ["Bm", "A", "D", "A", "G"]


def test_editar_una_linea_conserva_sus_acordes():
    song = _cancion()
    txt = reconstruct_lyrics(song)
    editado = txt.replace("en el vive mi esperanza", "en el habita por siempre mi esperanza")
    merged = merge_lyrics(song, editado)
    linea = _line(merged, "en el habita")
    assert len(_chords(linea)) == 3, "los acordes no se pierden al editar la línea"
