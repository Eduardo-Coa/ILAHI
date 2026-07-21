"""Sistema de temas de Ilahi móvil (Flet).

Varios temas construidos sobre la paleta de la marca (PDF «Ilahi - RGB codigos»).
Cada tema es un dict con las MISMAS claves; ``THEME`` es el tema activo (una
copia mutable). Toda la app lee ``theme.THEME[...]`` al momento de pintar, así
que ``set_theme(nombre)`` (que muta ``THEME`` en sitio) + reconstruir la vista
actual re-tematiza toda la UI. La preferencia se persiste en ``utils/prefs.py``.

Los widgets Material (Slider, Switch, botones de diálogo) no leen este dict;
``main._apply_page_theme`` les aplica un ``ColorScheme`` acorde a nivel de página.

Las fuentes se expresan como familia + tamaño (px) porque Flet los toma por
separado; la familia monoespaciada alinea los acordes sobre la letra.
"""

from __future__ import annotations

# --- NOCHE: el tema principal (tarima). Negro puro + paneles azul-tinta + oro.
DARK: dict[str, str] = {
    # Colores base
    "bg":            "#000000",   # Fondo: negro puro (como «Lights out» de X)
    "surface":       "#161624",   # Barras y paneles: búsqueda, tarjetas, headers, toggle (R22 G22 B36)
    "surface2":      "#222222",
    "border":        "#2e2e2e",
    "text":          "#e8e4d8",
    "text_muted":    "#777777",
    # Acorde: recuadro (fondo) + borde y texto en el dorado de la marca
    "chord":         "#e6af34",   # borde + fuente del acorde (R230 G175 B52)
    "chord_bg":      "#191829",   # Recuadros (R25 G24 B41)
    # Secciones
    "verse_bg":      "#1a1a1a",
    "chorus_bg":     "#161e1c",
    "section_label": "#555555",
    # Acento de botones (tab activo, pill activo, FAB «＋») / peligro
    "accent":        "#f3d365",   # (R243 G211 B101)
    "danger":        "#c06060",
    # Pulso del metrónomo en el golpe 1: verde, para distinguir el acento de un
    # vistazo sin confundirlo con el dorado de los acordes.
    "beat_one":      "#5fd38a",
}

# --- OSCURO: negro absoluto de alto contraste. Fondo y paneles negros, texto/acento/
# bordes en blanco (look «contorno») y acordes en naranja. Definido con el editor de
# temas sobre el teléfono.
OSCURO: dict[str, str] = {
    "bg":            "#000000",
    "surface":       "#0c0b0c",   # paneles/tarjetas: apenas sobre el negro
    "surface2":      "#0c0b0c",
    "border":        "#ffffff",
    "text":          "#ffffff",
    "text_muted":    "#777777",
    "accent":        "#ffffff",
    "chord":         "#f18000",
    "chord_bg":      "#000000",
    "verse_bg":      "#000000",
    "chorus_bg":     "#000000",
    "section_label": "#555555",
    "danger":        "#ff0000",
    "beat_one":      "#5fd38a",
}

# --- MEDIANOCHE: fondo negro con paneles navy y acento azul frío; acordes en
# verde-azulado. Afinado con el editor de temas sobre el teléfono.
MIDNIGHT: dict[str, str] = {
    "bg":            "#000000",
    "surface":       "#19284b",   # paneles en el navy (R25 G40 B75)
    "surface2":      "#223159",
    "border":        "#2e3f6b",
    "text":          "#e8e4d8",
    "text_muted":    "#8a93b2",
    "chord":         "#37a095",   # verde-azulado
    "chord_bg":      "#171100",
    "verse_bg":      "#000000",
    "chorus_bg":     "#000000",
    "section_label": "#747171",
    "accent":        "#a2b7ff",   # azul frío
    "danger":        "#c03638",
    "beat_one":      "#5fd38a",   # pulso del golpe 1
}

# --- ALBA: claro frío. Blanco/gris azulado con el navy de la marca como única
# tinta de acento: limpio y neutro, tipo app de productividad.
DAWN: dict[str, str] = {
    "bg":            "#f2f4f8",
    "surface":       "#ffffff",
    "surface2":      "#e9edf4",
    "border":        "#d4dae5",
    "text":          "#1b2437",
    "text_muted":    "#5e6a80",
    "chord":         "#19284b",   # navy de la marca
    "chord_bg":      "#e4eaf6",
    "verse_bg":      "#ffffff",
    "chorus_bg":     "#edf1f7",
    "section_label": "#97a2b8",
    "accent":        "#19284b",
    "danger":        "#b03a3a",
    "beat_one":      "#2e8b57",   # pulso del golpe 1: verde oscuro, se ve sobre el claro
}

# --- SCRATCH: paleta de PRUEBAS del editor de temas (solo desarrollo). Arranca
# como copia de Noche; sirve para inventar temas sin tocar los cuatro definitivos.
# No aparece en el selector del usuario (ver USER_THEMES); solo la ve el editor.
SCRATCH: dict[str, str] = dict(DARK)

# --- Registro ----------------------------------------------------------------
PALETTES: dict[str, dict[str, str]] = {
    "noche":      DARK,
    "oscuro":     OSCURO,
    "medianoche": MIDNIGHT,
    "alba":       DAWN,
    "scratch":    SCRATCH,
}

# Los temas que el usuario final ve en Ajustes (scratch queda fuera: es del editor).
USER_THEMES: list[str] = ["noche", "oscuro", "medianoche", "alba"]

# Nombre visible y personalidad (para el selector de tema en Ajustes).
LABELS: dict[str, str] = {
    "noche":      "Noche",
    "oscuro":     "Oscuro",
    "medianoche": "Medianoche",
    "alba":       "Alba",
    "scratch":    "Scratch",
}
DESCRIPTIONS: dict[str, str] = {
    "noche":      "Negro puro y oro; máximo contraste para tarima",
    "oscuro":     "Negro absoluto, texto blanco y acordes naranja",
    "medianoche": "Negro con azul frío, suave para ensayar de noche",
    "alba":       "Claro y neutro, con el azul de la marca",
    "scratch":    "Paleta de pruebas del editor",
}

# Editor de temas: solo en desarrollo. Con esto en False, la fila de Ajustes que lo
# abre desaparece (la maquinaria queda inerte). Ponerlo en False antes de publicar.
DEV_THEME_EDITOR = True

# Colores editables, en orden, con su etiqueta legible (para el editor). Son todas
# las claves de una paleta: si se agrega una clave nueva a los dicts de arriba, hay
# que sumarla aquí para poder tocarla desde el editor.
EDITABLE_COLORS: list[tuple[str, str]] = [
    ("bg",            "Fondo"),
    ("surface",       "Paneles y tarjetas"),
    ("surface2",      "Panel secundario"),
    ("border",        "Bordes"),
    ("text",          "Texto"),
    ("text_muted",    "Texto tenue"),
    ("accent",        "Acento (tabs, FAB)"),
    ("chord",         "Acorde"),
    ("chord_bg",      "Fondo del acorde"),
    ("verse_bg",      "Fondo de verso"),
    ("chorus_bg",     "Fondo de coro"),
    ("section_label", "Etiqueta de sección"),
    ("danger",        "Peligro"),
    ("beat_one",      "Metrónomo · golpe 1"),
]

# Nombre de la variable Python de cada paleta (para exportar un snippet pegable).
_VAR_OF: dict[str, str] = {
    "noche": "DARK", "oscuro": "OSCURO", "medianoche": "MIDNIGHT",
    "alba": "DAWN", "scratch": "SCRATCH",
}

# Logos de la marca (en assets/). OJO con los nombres: «claro»/«oscuro» describen
# el color del LOGO, no el del tema. El claro (texto crema) es el que se ve sobre
# fondo oscuro; el oscuro (texto navy) sobre fondo claro. Ver ``logo()``.
LOGO_ON_DARK = "Ilahi-claro.png"
LOGO_ON_LIGHT = "Ilahi-oscuro.png"

DEFAULT_THEME = "noche"
_active: str = DEFAULT_THEME

# Tema activo: SIEMPRE una copia (mutarla nunca corrompe las paletas originales).
THEME: dict[str, str] = dict(DARK)


def set_theme(name: str) -> None:
    """Activa un tema por nombre, mutando ``THEME`` en sitio (así lo ven tanto
    quienes hacen ``theme.THEME`` como quienes guardaron una referencia)."""
    global _active
    if name not in PALETTES:
        raise ValueError(f"Tema desconocido: {name!r} (hay: {', '.join(PALETTES)})")
    THEME.clear()
    THEME.update(PALETTES[name])
    _active = name


def active_theme() -> str:
    """Nombre del tema activo (clave de ``PALETTES``)."""
    return _active


# --- Utilidades de color ------------------------------------------------------
def hex_to_rgb(value: str) -> tuple[int, int, int]:
    """``#rrggbb`` → (r, g, b). Tolera hex sin ``#`` o con alfa (usa los 6 primeros);
    ante algo inválido devuelve negro en vez de reventar."""
    h = value.lstrip("#")[:6].ljust(6, "0")
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return 0, 0, 0


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return "#%02x%02x%02x" % (int(r), int(g), int(b))


# --- Editor de temas (solo desarrollo) ---------------------------------------
def set_active_color(key: str, value: str) -> None:
    """Cambia un color del tema ACTIVO en vivo: lo escribe tanto en ``THEME`` (lo que
    pinta la app ahora) como en su paleta de origen (para que persista y se exporte)."""
    if key not in THEME:
        return
    THEME[key] = value
    PALETTES[_active][key] = value


def reset_palette(name: str) -> None:
    """Devuelve una paleta a sus valores de fábrica (los definidos en este archivo)."""
    original = _ORIGINALS.get(name)
    if original is None:
        return
    PALETTES[name].clear()
    PALETTES[name].update(original)
    if name == _active:
        THEME.clear()
        THEME.update(PALETTES[name])


def export_palettes() -> dict[str, dict[str, str]]:
    """Foto serializable de todas las paletas (para guardar en preferencias)."""
    return {name: dict(pal) for name, pal in PALETTES.items()}


def apply_overrides(data: dict) -> None:
    """Aplica ajustes guardados (de ``export_palettes``) sobre las paletas. Tolerante:
    ignora nombres/claves que ya no existen. Refresca el tema activo si cambió."""
    if not isinstance(data, dict):
        return
    for name, palette in data.items():
        if name in PALETTES and isinstance(palette, dict):
            for k, v in palette.items():
                if k in PALETTES[name] and isinstance(v, str):
                    PALETTES[name][k] = v
    THEME.clear()
    THEME.update(PALETTES[_active])


def palette_source_snippet() -> str:
    """Las paletas como código Python pegable en este archivo (bloques ``VAR = {…}``)."""
    lineas: list[str] = ["# Paletas exportadas desde el editor de temas.", ""]
    width = max(len(k) for k, _ in EDITABLE_COLORS) + 2
    for name in PALETTES:
        lineas.append(f"{_VAR_OF.get(name, name.upper())}: dict[str, str] = {{")
        for key, label in EDITABLE_COLORS:
            clave = f'"{key}":'.ljust(width + 3)
            lineas.append(f'    {clave} "{PALETTES[name][key]}",   # {label}')
        lineas.append("}")
        lineas.append("")
    return "\n".join(lineas)


# Copia intacta de cada paleta al importar el módulo: es el "de fábrica" al que vuelve
# ``reset_palette``. Se toma ANTES de aplicar cualquier ajuste guardado.
_ORIGINALS: dict[str, dict[str, str]] = {name: dict(pal)
                                         for name, pal in PALETTES.items()}


def is_dark() -> bool:
    """¿El tema activo es oscuro? (por brillo percibido del fondo)."""
    hx = THEME["bg"].lstrip("#")
    r, g, b = (int(hx[i:i + 2], 16) for i in (0, 2, 4))
    return (r * 299 + g * 587 + b * 114) / 1000 < 128


def logo() -> str:
    """Archivo del logo que contrasta con el fondo del tema activo.

    En los temas claros el logo crema desaparecería sobre el fondo, así que se usa
    la versión de texto navy."""
    return LOGO_ON_DARK if is_dark() else LOGO_ON_LIGHT

# Familia monoespaciada (alineación acorde/letra). En Android se sustituye por una
# fuente bundleada (p. ej. JetBrains Mono) en la fase de empaque.
FONT_MONO = "monospace"

# Tamaños base en px (equivalen a los font sizes del escritorio).
SIZE_STAGE = 14          # letra en vista escenario
SIZE_CHORD_STAGE = 18    # acordes en vista escenario
SIZE_LIST = 16           # lista de canciones
SIZE_SECTION = 12        # etiquetas de sección
