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
}

# --- MEDIANOCHE: oscuro «dim». Azul profundo de la marca, menos contraste duro
# que el negro; para ensayar de noche con la vista descansada.
MIDNIGHT: dict[str, str] = {
    "bg":            "#161624",   # el Fondo GENERAL de la marca como base
    "surface":       "#19284b",   # paneles en el navy (R25 G40 B75)
    "surface2":      "#223159",
    "border":        "#2e3f6b",
    "text":          "#e8e4d8",
    "text_muted":    "#8a93b2",
    "chord":         "#f3d365",   # oro claro: más luz sobre el navy
    "chord_bg":      "#101a33",
    "verse_bg":      "#1b1b30",
    "chorus_bg":     "#1a2440",
    "section_label": "#66719a",
    "accent":        "#f3d365",
    "danger":        "#d97b7b",
}

# --- PERGAMINO: claro cálido. Papel crema de la marca, tinta azul marino y
# acordes marrón sobre oro: estética de himnario clásico, para día/exterior.
PARCHMENT: dict[str, str] = {
    "bg":            "#f8e9c2",   # crema de la marca (R248 G233 B194)
    "surface":       "#fffbee",   # tarjetas «papel» más claras que el fondo
    "surface2":      "#fff4d6",
    "border":        "#e2d3a8",
    "text":          "#19284b",   # tinta navy de la marca
    "text_muted":    "#6e6749",
    "chord":         "#573814",   # marrón de la marca (R87 G56 B20)
    "chord_bg":      "#f3d365",   # badge dorado
    "verse_bg":      "#fff9e8",
    "chorus_bg":     "#fbf0d4",
    "section_label": "#a39668",
    "accent":        "#ad6023",   # ámbar de la marca (R173 G96 B35)
    "danger":        "#b04030",
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
}

# --- Registro ----------------------------------------------------------------
PALETTES: dict[str, dict[str, str]] = {
    "noche":      DARK,
    "medianoche": MIDNIGHT,
    "pergamino":  PARCHMENT,
    "alba":       DAWN,
}

# Nombre visible y personalidad (para el selector de tema en Ajustes).
LABELS: dict[str, str] = {
    "noche":      "Noche",
    "medianoche": "Medianoche",
    "pergamino":  "Pergamino",
    "alba":       "Alba",
}
DESCRIPTIONS: dict[str, str] = {
    "noche":      "Negro puro y oro; máximo contraste para tarima",
    "medianoche": "Azul profundo, más suave para ensayar de noche",
    "pergamino":  "Papel crema y tinta navy, como un himnario",
    "alba":       "Claro y neutro, con el azul de la marca",
}

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


def is_dark() -> bool:
    """¿El tema activo es oscuro? (por brillo percibido del fondo)."""
    hx = THEME["bg"].lstrip("#")
    r, g, b = (int(hx[i:i + 2], 16) for i in (0, 2, 4))
    return (r * 299 + g * 587 + b * 114) / 1000 < 128

# Familia monoespaciada (alineación acorde/letra). En Android se sustituye por una
# fuente bundleada (p. ej. JetBrains Mono) en la fase de empaque.
FONT_MONO = "monospace"

# Tamaños base en px (equivalen a los font sizes del escritorio).
SIZE_STAGE = 14          # letra en vista escenario
SIZE_CHORD_STAGE = 18    # acordes en vista escenario
SIZE_LIST = 16           # lista de canciones
SIZE_SECTION = 12        # etiquetas de sección
