"""Piezas de UI compartidas entre pantallas: botones y encabezados.

Viven aquí para que la vista de canción y la de edición usen exactamente los
mismos botones (volver, editar) y el mismo título centrado.
"""

from __future__ import annotations
from typing import Callable
import asyncio
import flet as ft

from models.song import Syllable
import theme

# Aire que deben dejar ABAJO las listas que conviven con un botón flotante (el ＋ del
# panel principal o el ▶ del detalle de lista): sin él, el botón tapa el último
# elemento y no se puede llegar a tocarlo. Cubre la altura del botón más su margen.
FAB_CLEARANCE = 96


def _safe_update(control) -> None:
    """Repinta un control; ignora el caso «aún no está en la página»."""
    try:
        control.update()
    except Exception:
        pass


def show_toast(page, text: str, seconds: float = 3.0) -> None:
    """Muestra un mensaje flotante (toast) centrado en la parte inferior, sobre el
    FAB, y lo desvanece tras ``seconds`` (~3 s, estándar).

    Vive en ``page.overlay`` (flota sobre todo y sobrevive a que la vista se
    reconstruya). Sustituye a cualquier toast anterior para que no se apilen."""
    clean = (text or "").strip()
    if not clean:
        return
    for old in [c for c in page.overlay if getattr(c, "data", None) == "ilahi-toast"]:
        try:
            page.overlay.remove(old)
        except ValueError:
            pass

    toast = ft.Container(
        data="ilahi-toast",
        left=0, right=0, bottom=100,          # ancho completo → centrar; sobre el FAB
        alignment=ft.Alignment.CENTER,
        opacity=1, animate_opacity=350,       # ms del desvanecido
        content=status_banner(clean),
    )
    page.overlay.append(toast)
    _safe_update(page)

    async def _dismiss() -> None:
        await asyncio.sleep(seconds)
        toast.opacity = 0                     # dispara el fade-out
        _safe_update(toast)
        await asyncio.sleep(0.45)             # espera a que termine el desvanecido
        try:
            page.overlay.remove(toast)
        except ValueError:
            pass
        _safe_update(page)

    page.run_task(_dismiss)


def status_banner(text: str) -> ft.Control:
    """Mensaje de estado con el estilo del diseño: pill redondeado con ícono.

    Verde (``chord``) para confirmaciones («✓ …»); rojo (``danger``) para errores
    («✗ …»). El ícono ya comunica el resultado, así que se le quita ese prefijo al
    texto. Devuelve un contenedor vacío si no hay texto."""
    clean = (text or "").strip()
    if not clean:
        return ft.Container()
    is_error = clean[0] in ("✗", "✕", "×", "⚠")
    if clean[0] in ("✓", "✗", "✕", "×", "⚠", "✔"):
        clean = clean[1:].strip()
    color = theme.THEME["danger"] if is_error else theme.THEME["chord"]
    icon = ft.Icons.ERROR_OUTLINE if is_error else ft.Icons.CHECK_CIRCLE_OUTLINE
    return ft.Container(
        bgcolor=theme.THEME["surface2"] if is_error else theme.THEME["chord_bg"],
        border=ft.Border.all(1, color), border_radius=12,
        padding=ft.Padding.only(left=12, right=14, top=8, bottom=8),
        margin=ft.Margin.symmetric(horizontal=12, vertical=2),
        content=ft.Row(tight=True, spacing=8,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
            ft.Icon(icon, size=16, color=color),
            ft.Text(clean, size=13, color=color),
        ]),
    )


def segmented_toggle(left_label: str, right_label: str, active: str,
                     on_left: Callable[[], None], on_right: Callable[[], None]) -> ft.Control:
    """Barra de dos segmentos con píldora resaltada; se cambia tocando un segmento o
    arrastrando de lado. ``active`` es ``"left"`` o ``"right"``. Va centrada y algo
    más angosta que la barra de búsqueda."""
    def seg(label: str, is_active: bool, cb) -> ft.Control:
        return ft.Container(
            expand=True, ink=not is_active, border_radius=16,
            on_click=(lambda _e: cb()) if not is_active else None,
            bgcolor=theme.THEME["accent"] if is_active else None,
            padding=ft.Padding.symmetric(vertical=9),
            alignment=ft.Alignment.CENTER,
            content=ft.Text(label, size=14, weight=ft.FontWeight.W_600,
                            color=theme.THEME["bg"] if is_active
                            else theme.THEME["text_muted"]))

    inner = ft.Container(
        bgcolor=theme.THEME["surface"], border_radius=18,   # track navy, como las barras
        padding=ft.Padding.all(3),
        content=ft.Row([seg(left_label, active == "left", on_left),
                        seg(right_label, active == "right", on_right)], spacing=0))

    # Arrastrar de lado también cambia (por distancia, funciona con arrastre lento).
    state = {"dx": 0.0}
    def _start(_e): state["dx"] = 0.0
    def _track(e): state["dx"] += getattr(e, "primary_delta", None) or 0
    def _end(_e):
        d, state["dx"] = state["dx"], 0.0
        if d < -30 and active != "left":
            on_left()
        elif d > 30 and active != "right":
            on_right()

    return ft.Container(
        margin=ft.Margin.symmetric(horizontal=40, vertical=4),   # centrada, más angosta
        content=ft.GestureDetector(
            content=inner, on_horizontal_drag_start=_start,
            on_horizontal_drag_update=_track, on_horizontal_drag_end=_end))


class SlidingToggle:
    """Toggle de dos segmentos cuya píldora se DESLIZA al cambiar de lado.

    A diferencia de ``segmented_toggle`` (que se reconstruye y por eso salta), este
    vive una sola vez: ``set_active`` mueve la píldora y ella sola se anima.

    La píldora ocupa media pista —una celda ``expand=1`` de un Row de dos—, así su
    ``offset.x`` de 0 a 1 la corre exactamente al otro lado SIN necesidad de saber el
    ancho en píxeles (que en Flet no se conoce al construir).

    Se mueve con ``set_active``, tanto al tocar un segmento como cuando el shell
    termina de deslizarse a la otra vista.
    """

    _H = 34          # alto de la pista y de la píldora (deben coincidir)
    _ANIM = 220      # ms del deslizamiento cuando se toca (no cuando se arrastra)

    def __init__(self, left_label: str, right_label: str,
                 on_left: Callable[[], None], on_right: Callable[[], None],
                 active: str = "right") -> None:
        self.left_label, self.right_label = left_label, right_label
        self.on_left, self.on_right = on_left, on_right
        self.active = active
        self._pill = ft.Container(
            expand=1, height=self._H, border_radius=16,
            bgcolor=theme.THEME["accent"],
            offset=ft.Offset(1 if active == "right" else 0, 0),
            animate_offset=ft.Animation(self._ANIM, ft.AnimationCurve.EASE_OUT))
        self._left_txt = self._label(left_label, active == "left")
        self._right_txt = self._label(right_label, active == "right")

    def _label(self, text: str, is_active: bool) -> ft.Text:
        return ft.Text(text, size=14, weight=ft.FontWeight.W_600,
                       text_align=ft.TextAlign.CENTER,
                       color=theme.THEME["bg"] if is_active else theme.THEME["text_muted"])

    def _segment(self, txt: ft.Text, cb) -> ft.Control:
        return ft.Container(expand=1, height=self._H, border_radius=16, ink=True,
                            alignment=ft.Alignment.CENTER,
                            on_click=lambda _e: cb(), content=txt)

    def build(self) -> ft.Control:
        # Capa de la píldora DEBAJO y las etiquetas encima (por eso va primera).
        pista = ft.Row([self._pill, ft.Container(expand=1, height=self._H)], spacing=0)
        etiquetas = ft.Row([self._segment(self._left_txt, self.on_left),
                            self._segment(self._right_txt, self.on_right)], spacing=0)
        return ft.Container(
            margin=ft.Margin.symmetric(horizontal=40, vertical=4),
            padding=ft.Padding.all(3),
            bgcolor=theme.THEME["surface"], border_radius=18,
            content=ft.Stack([pista, etiquetas], height=self._H),
        )

    def _paint_labels(self, side: str) -> None:
        self._left_txt.color = (theme.THEME["bg"] if side == "left"
                                else theme.THEME["text_muted"])
        self._right_txt.color = (theme.THEME["bg"] if side == "right"
                                 else theme.THEME["text_muted"])
        _safe_update(self._left_txt)
        _safe_update(self._right_txt)

    def set_active(self, side: str) -> None:
        """Mueve la píldora al lado dado (se desliza sola) y recolorea las etiquetas."""
        if side not in ("left", "right"):
            return
        self.active = side
        self._pill.offset = ft.Offset(1 if side == "right" else 0, 0)
        _safe_update(self._pill)
        self._paint_labels(side)


def sheet_option(icon: str, title: str, subtitle: str, on_click) -> ft.Control:
    """Fila de un cuadro/menú (Añadir, Editar…): ícono, título y una línea de ayuda."""
    return ft.Container(
        ink=True, border_radius=12, on_click=on_click,
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        content=ft.Row(spacing=14, controls=[
            ft.Icon(icon, size=22, color=theme.THEME["accent"]),
            ft.Column(spacing=1, tight=True, controls=[
                ft.Text(title, size=15, color=theme.THEME["text"]),
                ft.Text(subtitle, size=11, color=theme.THEME["text_muted"]),
            ]),
        ]),
    )


# Ancho aproximado de un carácter monoespaciado como fracción del tamaño de fuente.
# Si parte líneas que sí cabían, bájalo un poco; si tarda en partir, súbelo.
_CHAR_W = 0.55


def wrap_lyric_line(syls: list[Syllable], size: int,
                    avail_px: float) -> list[list[Syllable]]:
    """Parte un renglón de letra largo en subrenglones por coma/«;», solo si se
    desborda del ancho disponible.

    Empaqueta las frases (texto entre puntuación) de forma codiciosa; los renglones
    que caben se dejan intactos y los acordes viajan con sus sílabas. Así una línea
    larga baja la frase completa después de la coma en vez de dejar la última palabra
    suelta. Lo usan tanto la vista de canción/escenario como la de edición."""
    max_chars = max(16, int(avail_px / (size * _CHAR_W))) if size else 999
    if sum(len(s.text) for s in syls) <= max_chars:
        return [syls]
    # Dividir en frases: cada una se cierra tras una sílaba terminada en «,» o «;».
    phrases: list[list[Syllable]] = []
    current: list[Syllable] = []
    for syl in syls:
        current.append(syl)
        if syl.text.rstrip().endswith((",", ";")):
            phrases.append(current)
            current = []
    if current:
        phrases.append(current)
    if len(phrases) <= 1:
        return [syls]                         # nada donde partir con elegancia
    # Empaquetar frases hasta llenar el ancho (sin partir una frase a la mitad).
    lines: list[list[Syllable]] = []
    acc: list[Syllable] = []
    acc_len = 0
    for phrase in phrases:
        plen = sum(len(s.text) for s in phrase)
        if acc and acc_len + plen > max_chars:
            lines.append(acc)
            acc, acc_len = [], 0
        acc.extend(phrase)
        acc_len += plen
    if acc:
        lines.append(acc)
    return lines


def square_button(icon: str, tooltip: str, on_click: Callable[[], None]) -> ft.Control:
    """Botón cuadrado de esquinas redondeadas (volver, editar…), 44 px."""
    return ft.Container(
        width=44, height=44, border_radius=14, ink=True,
        bgcolor=theme.THEME["surface"], alignment=ft.Alignment.CENTER,
        tooltip=tooltip, on_click=lambda _e: on_click(),
        content=ft.Icon(icon, size=20, color=theme.THEME["text"]),
    )


def back_button(on_back: Callable[[], None]) -> ft.Control:
    """Flecha ← arriba a la izquierda."""
    return square_button(ft.Icons.ARROW_BACK, "Volver", on_back)


def logo_header() -> ft.Control:
    """Panel superior con el logo de la marca centrado (la versión según el tema).

    Es el mismo en todas las vistas del panel principal; el shell lo fija arriba y
    las pantallas embebidas lo omiten (no se repite ni se desliza)."""
    return ft.Container(
        padding=ft.Padding.only(top=16, bottom=6),
        alignment=ft.Alignment.CENTER,
        content=ft.Image(src=theme.logo(), height=52, fit=ft.BoxFit.CONTAIN),
    )


def circle_button(label: str, on_click, diameter: int = 56,
                  bgcolor: str | None = None) -> ft.Control:
    """Botón redondo de los paneles (A− / A+, − / +).

    ``bgcolor`` debe contrastar con el fondo del panel que lo contiene: sobre
    ``surface2`` (el cuadro) va ``surface``, y sobre ``surface`` (el panel del
    escenario) va ``surface2``; si no, el círculo desaparece.
    """
    return ft.Container(
        width=diameter, height=diameter, border_radius=diameter // 2,
        bgcolor=bgcolor or theme.THEME["surface"], ink=True,
        alignment=ft.Alignment.CENTER, on_click=on_click,
        content=ft.Text(label, size=max(13, diameter // 3),
                        color=theme.THEME["text"]),
    )


def confirm_row_card(content: ft.Control, key=None) -> ft.Container:
    """Tarjeta de la fila «¿Eliminar…?» que reemplaza en el sitio a una fila de la lista.
    Mismo fondo y esquinas que ``list_row_card``, con más padding para que respire la
    pregunta. El CONTENIDO lo arma cada vista: la de canciones lo pone en fila y la de
    autores en columna (la pregunta es más larga)."""
    return ft.Container(
        key=key,
        bgcolor=theme.THEME["surface"], border_radius=14,
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        margin=ft.Margin.symmetric(horizontal=12, vertical=5),
        content=content,
    )


def stepper_row(minus_label: str, on_minus, center: ft.Control,
                plus_label: str, on_plus) -> ft.Row:
    """Fila «− valor +» de los cuadros (tamaño de letra, tono): dos botones redondos
    con el valor en el medio. El ± del metrónomo NO usa esto: va más chico y sobre otro
    fondo, dentro del panel del escenario."""
    return ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=24, controls=[
        circle_button(minus_label, on_minus),
        center,
        circle_button(plus_label, on_plus),
    ])


def list_row_card(controls: list[ft.Control], key=None) -> ft.Container:
    """Tarjeta de UNA fila de lista (canción, autor, lista, ítem de lista). Unifica el
    fondo, las esquinas y el padding/margen para que todas las listas de la app se vean
    iguales. La ``key`` estable evita que Flet reutilice controles al reordenar."""
    return ft.Container(
        key=key,
        bgcolor=theme.THEME["surface"], border_radius=14,
        padding=ft.Padding.symmetric(horizontal=4, vertical=6),
        margin=ft.Margin.symmetric(horizontal=12, vertical=5),
        content=ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=2,
                       controls=controls),
    )


def sheet_dialog(content: ft.Control, title: str | None = None,
                 content_padding=None, actions: list | None = None,
                 modal: bool = False) -> ft.AlertDialog:
    """Cuadro tipo «hoja» de la app: esquinas de 20, fondo ``surface2`` y título en
    negrita. Es el chrome de los cuadros de Añadir, Tema, Tono, Acerca de…

    ``content_padding=None`` y ``actions=[]`` son los defaults de ``AlertDialog``, así
    que omitirlos aquí deja el cuadro exactamente igual que sin pasarlos."""
    return ft.AlertDialog(
        modal=modal,
        shape=ft.RoundedRectangleBorder(radius=20),
        bgcolor=theme.THEME["surface2"],
        title=(ft.Text(title, size=18, weight=ft.FontWeight.BOLD,
                       color=theme.THEME["text"]) if title else None),
        content_padding=content_padding,
        content=content,
        actions=actions if actions is not None else [],
    )


def confirm_dialog(title: str, content: ft.Control, actions: list) -> ft.AlertDialog:
    """Cuadro de confirmación/pregunta: más chico (esquinas de 18), modal y con el
    título sin negrita. Para «¿Eliminar…?», «Editar nombre», «Nueva lista»…"""
    return ft.AlertDialog(
        modal=True, shape=ft.RoundedRectangleBorder(radius=18),
        bgcolor=theme.THEME["surface2"],
        title=ft.Text(title, color=theme.THEME["text"]),
        content=content, actions=actions)


def accent_fab(icon: str, tooltip: str, on_click) -> ft.Control:
    """Botón flotante (＋ / ▶) con el acento del tema. Solo el botón: cada vista lo
    envuelve en su propio contenedor, porque la posición cambia según lleve o no
    barra inferior debajo."""
    return ft.FloatingActionButton(
        icon=icon, tooltip=tooltip,
        bgcolor=theme.THEME["accent"], foreground_color=theme.THEME["bg"],
        shape=ft.RoundedRectangleBorder(radius=18),
        on_click=on_click)


def key_badge(key: str | None) -> ft.Control:
    """Badge redondeado con el tono de la canción (lista de canciones y detalle de
    lista lo comparten). Sin tono, muestra un guion."""
    return ft.Container(
        width=52, height=52,
        border=ft.Border.all(1, theme.THEME["chord"]),
        border_radius=12, bgcolor=theme.THEME["chord_bg"],
        alignment=ft.Alignment.CENTER,
        content=ft.Column([
            ft.Text(key or "—", size=17, weight=ft.FontWeight.BOLD,
                    color=theme.THEME["chord"]),
            ft.Text("Tono", size=8, color=theme.THEME["text_muted"]),
        ], spacing=0, tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER),
    )


def title_block(title: str, meta: list[str] | None = None) -> list[ft.Control]:
    """Título centrado y, si hay, la línea de datos (autor · ritmo · capo)."""
    controls: list[ft.Control] = [
        ft.Text(title, size=18, weight=ft.FontWeight.BOLD,
                color=theme.THEME["accent"], no_wrap=True,
                text_align=ft.TextAlign.CENTER),
    ]
    if meta:
        controls.append(ft.Text(" · ".join(meta), size=12,
                                color=theme.THEME["text_muted"], no_wrap=True,
                                text_align=ft.TextAlign.CENTER))
    return controls


def centered_header(title: str, meta: list[str] | None = None,
                    left: ft.Control | None = None,
                    right: ft.Control | None = None) -> ft.Control:
    """Encabezado: botón a cada lado y el título centrado entre ambos.

    Los dos lados ocupan 44 px aunque estén vacíos; ese hueco simétrico es lo
    que centra el título de verdad.
    """
    return ft.Container(
        # Panel superior: fondo propio y esquinas inferiores redondeadas.
        bgcolor=theme.THEME["surface"],
        border_radius=ft.BorderRadius.only(bottom_left=18, bottom_right=18),
        padding=ft.Padding.only(left=8, right=8, top=10, bottom=10),
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                left or ft.Container(width=44),
                ft.Column(title_block(title, meta), spacing=0, tight=True, expand=True,
                          horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                right or ft.Container(width=44),
            ],
        ),
    )


def floating_panel(content: ft.Control) -> ft.Container:
    """Panel flotante del patrón de la app: esquinas redondeadas y margen."""
    return ft.Container(
        margin=ft.Margin.only(left=10, right=10, bottom=10),
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        bgcolor=theme.THEME["surface2"], border_radius=20,
        border=ft.Border.all(1, theme.THEME["border"]),
        content=content,
    )
