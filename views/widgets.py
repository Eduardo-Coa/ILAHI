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
