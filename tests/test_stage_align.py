"""Alineación de acordes por palabra en la vista de canción/escenario.

Cuando dos sílabas seguidas tienen acorde y el primero es ancho, la palabra se
rellena con guiones para que cada acorde caiga sobre su sílaba (p. ej. «par--tir»);
con acordes cortos no se agrega ningún guión.
"""

from models.song import Syllable, Chord
from views.stage_view import _word_chord_lyric


def _word(*pairs):
    return [Syllable(id=None, position=i, text=t,
                     chord=Chord(id=None, value=c) if c else None)
            for i, (t, c) in enumerate(pairs)]


def test_acordes_anchos_insertan_guiones():
    chord, lyric = _word_chord_lyric(_word(("par", "G#m7"), ("tir", "C#7")))
    assert lyric == "par--tir"
    assert chord == "G#m7 C#7"
    # cada acorde cae sobre su sílaba
    assert lyric[chord.index("G#m7")] == "p"
    assert lyric[chord.index("C#7")] == "t"


def test_acordes_medianos_un_guion():
    chord, lyric = _word_chord_lyric(_word(("par", "Bm7"), ("tir", "E7")))
    assert lyric == "par-tir"
    assert lyric[chord.index("E7")] == "t"


def test_acordes_cortos_sin_guiones():
    chord, lyric = _word_chord_lyric(_word(("par", "A"), ("tir", "E")))
    assert lyric == "partir"
    assert lyric[chord.index("E")] == "t"


def test_acorde_solo_en_primera_silaba_no_cambia():
    chord, lyric = _word_chord_lyric(_word(("ho", "C"), ("la", None)))
    assert lyric == "hola"
    assert chord == "C"


def test_acorde_muy_largo_varios_guiones():
    chord, lyric = _word_chord_lyric(_word(("cie", "Cmaj7"), ("lo", "G")))
    assert lyric == "cie---lo"
    assert lyric[chord.index("G")] == "l"


def test_tres_silabas_cada_acorde_sobre_su_silaba():
    chord, lyric = _word_chord_lyric(
        _word(("ca", "G#m7"), ("mi", "C#7"), ("no", "F#")))
    assert lyric[chord.index("G#m7")] == "c"
    assert lyric[chord.index("C#7")] == "m"
    assert lyric[chord.index("F#")] == "n"


def test_slot_de_acorde_sin_letra_muestra_guion_con_aire():
    """La casilla de un acorde suelto es AIRE + guion, en ese orden.

    El espacio va delante para que el hueco quede parejo: con el aire detrás, la
    primera casilla se pegaba a la letra («me-») y solo las siguientes se separaban.
    Es espacio DURO porque uno normal al borde de un ``Text`` lo recorta el layout.
    El acorde se corre el mismo espacio, así sigue empezando sobre su guion.
    """
    chord, lyric = _word_chord_lyric(_word(("", "A")))
    assert lyric == "\u00a0-"
    assert chord == " A"
    assert lyric[chord.index("A")] == "-"     # acorde y guion, misma columna
