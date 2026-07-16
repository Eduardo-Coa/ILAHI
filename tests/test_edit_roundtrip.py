"""Round-trip de «Editar letra» (reconstruct_lyrics + merge_lyrics).

Regresión del bug donde, con varios interludios, escribir acordes en uno vaciaba
los de otro: los acordes de las casillas deben viajar en el texto editable y
conservarse tras guardar.
"""

from utils.lyrics_parser import (
    parse_lyrics, prepend_intro, merge_lyrics, is_chord_line,
)
from views.edit_view import reconstruct_lyrics


def _chords(line):
    return [s.chord.value for s in line.syllables if s.chord]


def _interludios(song):
    """Lista de secuencias de acordes de cada sección «Interludio»."""
    return [
        [_chords(l) for l in s.lines if is_chord_line(l) and _chords(l)]
        for s in song.sections if s.label == "Interludio"
    ]


def _cancion_dos_interludios() -> "Song":
    texto = (
        "G - Bm - A - D - A\n"
        "\n[Estrofa]\nG                    Bm\nPorque mis errores en el mar\n"
        "\n[Coro]\nD              A\nMi señor siempre estas\n"
        "\nG - Bm - A - D - A\n"          # interludio 1 (con acordes)
        "\n[Estrofa]\nA     G\nEn mi caminar\n"
        "\nBm - A - D - A - G\n"          # interludio 2 (con acordes)
    )
    song = parse_lyrics(texto)
    prepend_intro(song)
    return song


def test_texto_editable_muestra_los_acordes_del_interludio():
    song = _cancion_dos_interludios()
    txt = reconstruct_lyrics(song)
    assert "G - Bm - A - D - A" in txt
    assert "Bm - A - D - A - G" in txt


def test_editar_letra_sin_cambios_conserva_todos_los_interludios():
    song = _cancion_dos_interludios()
    antes = _interludios(song)
    merged = merge_lyrics(song, reconstruct_lyrics(song))
    assert _interludios(merged) == antes
    assert antes == [[["G", "Bm", "A", "D", "A"]], [["Bm", "A", "D", "A", "G"]]]


def test_escribir_acordes_en_un_interludio_no_borra_otro():
    # Interludio 1 vacío, interludio 2 con acordes; el usuario teclea acordes en el 1.
    texto = (
        "G - Bm - A - D - A\n"
        "\n[Estrofa]\nG                    Bm\nPorque mis errores en el mar\n"
        "\n[Coro]\nD              A\nMi señor siempre estas\n"
        "\n[Interludio]\n"                # interludio 1 VACÍO
        "\n[Estrofa]\nA     G\nEn mi caminar\n"
        "\nBm - A - D - A - G\n"          # interludio 2 con acordes
    )
    song = parse_lyrics(texto)
    prepend_intro(song)
    assert _interludios(song) == [[], [["Bm", "A", "D", "A", "G"]]]

    # El usuario abre "Editar letra" y escribe la secuencia en el interludio vacío.
    editado = reconstruct_lyrics(song).replace(
        "[Interludio]\n", "[Interludio]\nG - Bm - A - D - A\n", 1)
    merged = merge_lyrics(song, editado)

    # Ambos interludios conservan sus acordes.
    assert _interludios(merged) == [
        [["G", "Bm", "A", "D", "A"]],
        [["Bm", "A", "D", "A", "G"]],
    ]


def test_editar_acordes_del_interludio_en_el_texto_se_respeta():
    # Cambiar un acorde en el texto del interludio debe reflejarse (no lo pisa el viejo).
    song = _cancion_dos_interludios()
    editado = reconstruct_lyrics(song).replace(
        "Bm - A - D - A - G", "Bm - A - D - A - E", 1)
    merged = merge_lyrics(song, editado)
    assert _interludios(merged)[1] == [["Bm", "A", "D", "A", "E"]]
