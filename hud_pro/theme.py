"""Design tokens, estilos por estado, fuentes empaquetadas y hoja QSS."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from .qt_compat import QtGui
from .state import OrbState

RGB = Tuple[int, int, int]

# ── Tokens ────────────────────────────────────────────────────────────────
BG_0 = "#03060D"
BG_1 = "#060C18"
BG_PANEL = "rgba(9, 18, 34, 0.60)"  # más translúcido que 0.78: deja ver el
# vidrio esmerilado GPU de FASE D (`HoloStage._render_glass`) detrás del
# panel — con 0.78 el desenfoque quedaba prácticamente tapado y el efecto
# no se notaba.
BG_PANEL_SOLID = "#0A1426"
BG_INPUT = "rgba(4, 10, 22, 0.85)"
LINE = "rgba(110, 190, 255, 0.14)"
LINE_STRONG = "rgba(110, 190, 255, 0.32)"
TEXT = "#E6F1FF"
TEXT_DIM = "#93AACB"
TEXT_MUTED = "#5A7093"
ACCENT = "#38BDF8"
ACCENT_2 = "#22D3EE"
DANGER = "#FF5A7A"

CHAT_MAX_WIDTH = 760
CHAT_MIN_WIDTH = 420


@dataclass(frozen=True)
class StateStyle:
    """Parámetros visuales objetivo de cada estado (se interpolan en el orbe)."""

    primary: RGB
    secondary: RGB
    accent: RGB
    ui: str  # color para textos/chips de la UI
    glow: float  # intensidad del halo
    deform: float  # deformación orgánica del núcleo
    ring_speed: float  # multiplicador de rotación de anillos
    particle_speed: float
    spectrum: float  # visibilidad del anillo de espectro
    scanner: float  # visibilidad del barrido
    ripple: float  # ondas por segundo
    pulse_rate: float  # Hz
    pulse_depth: float
    core: float  # brillo del núcleo
    arcs: float  # arcos eléctricos por segundo (núcleo → borde); sólo THINKING


STATE_STYLES: dict[OrbState, StateStyle] = {
    OrbState.IDLE: StateStyle(
        primary=(40, 170, 255),
        secondary=(46, 92, 230),
        accent=(190, 236, 255),
        ui="#38BDF8",
        glow=0.70,
        deform=0.012,
        ring_speed=0.45,
        particle_speed=0.35,
        spectrum=0.10,
        scanner=0.30,
        ripple=0.0,
        pulse_rate=0.22,
        pulse_depth=0.06,
        core=0.70,
        arcs=0.0,
    ),
    OrbState.LISTENING: StateStyle(
        primary=(20, 215, 255),
        secondary=(30, 130, 255),
        accent=(210, 250, 255),
        ui="#22D3EE",
        glow=1.00,
        deform=0.024,
        ring_speed=0.90,
        particle_speed=0.80,
        spectrum=1.00,
        scanner=0.35,
        ripple=0.9,
        pulse_rate=0.9,
        pulse_depth=0.02,
        core=0.95,
        arcs=0.0,
    ),
    OrbState.THINKING: StateStyle(
        primary=(80, 125, 255),
        secondary=(40, 70, 210),
        accent=(200, 215, 255),
        ui="#7C9BFF",
        glow=0.85,
        deform=0.018,
        ring_speed=2.60,
        particle_speed=1.70,
        spectrum=0.15,
        scanner=1.00,
        ripple=0.0,
        pulse_rate=1.6,
        pulse_depth=0.045,
        core=0.85,
        arcs=4.0,
    ),
    OrbState.SPEAKING: StateStyle(
        primary=(0, 225, 255),
        secondary=(0, 140, 255),
        accent=(215, 252, 255),
        ui="#00E0FF",
        glow=1.05,
        deform=0.028,
        ring_speed=1.10,
        particle_speed=1.00,
        spectrum=0.75,
        scanner=0.30,
        ripple=1.4,
        pulse_rate=1.1,
        pulse_depth=0.03,
        core=1.00,
        arcs=0.0,
    ),
    OrbState.ERROR: StateStyle(
        primary=(255, 70, 110),
        secondary=(150, 30, 70),
        accent=(255, 205, 215),
        ui="#FF5A7A",
        glow=0.80,
        deform=0.040,
        ring_speed=0.30,
        particle_speed=0.30,
        spectrum=0.0,
        scanner=0.0,
        ripple=0.4,
        pulse_rate=2.2,
        pulse_depth=0.05,
        core=0.70,
        arcs=0.0,
    ),
}


# ── Fuentes ───────────────────────────────────────────────────────────────
FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

FONT_DISPLAY = "Orbitron"
FONT_UI = "Inter"
FONT_MONO = "JetBrains Mono"

_FALLBACK_UI = ["Inter", "Ubuntu", "Cantarell", "Noto Sans", "Segoe UI", "DejaVu Sans"]
_FALLBACK_MONO = ["JetBrains Mono", "Fira Code", "Ubuntu Mono", "DejaVu Sans Mono", "Monospace"]

_fonts_loaded = False


def load_fonts() -> None:
    """Registra las fuentes OFL empaquetadas. Idempotente y tolerante a fallos."""
    global _fonts_loaded
    if _fonts_loaded:
        return
    _fonts_loaded = True
    if not FONTS_DIR.is_dir():
        return
    for ttf in sorted(FONTS_DIR.glob("*.ttf")):
        QtGui.QFontDatabase.addApplicationFont(str(ttf))


def font(family: str, px: int, weight: QtGui.QFont.Weight | None = None, spacing: float = 0.0) -> QtGui.QFont:
    f = QtGui.QFont(family)
    fallbacks = _FALLBACK_MONO if family == FONT_MONO else _FALLBACK_UI
    if hasattr(f, "setFamilies"):
        f.setFamilies([family, *fallbacks])
    f.setPixelSize(px)
    if weight is not None:
        f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QtGui.QFont.SpacingType.AbsoluteSpacing, spacing)
    f.setHintingPreference(QtGui.QFont.HintingPreference.PreferNoHinting)
    return f


# ── QSS ───────────────────────────────────────────────────────────────────
def stylesheet() -> str:
    return f"""
    QMainWindow, QWidget#HudRoot {{ background: {BG_0}; }}
    QWidget {{ color: {TEXT}; font-family: "{FONT_UI}"; font-size: 14px; }}
    QToolTip {{
        background: {BG_PANEL_SOLID}; color: {TEXT}; border: 1px solid {LINE_STRONG};
        padding: 6px 8px; border-radius: 6px;
    }}

    /* ── Top bar ── */
    QLabel#Wordmark {{ color: {TEXT}; }}
    QLabel#WordmarkSub {{ color: {TEXT_MUTED}; }}
    QLabel#Metric {{ color: {TEXT_DIM}; font-family: "{FONT_MONO}"; font-size: 12px; }}
    QLabel#Clock {{ color: {TEXT}; font-family: "{FONT_MONO}"; font-size: 13px; }}
    QFrame#Divider {{ background: {LINE}; max-width: 1px; min-width: 1px; }}
    QFrame#StatusChip {{
        background: rgba(56, 189, 248, 0.08); border: 1px solid {LINE_STRONG}; border-radius: 13px;
    }}

    /* ── Status block ── */
    QLabel#StateHint {{ color: {TEXT_DIM}; }}
    QLabel#Transcript {{ color: {TEXT}; }}

    /* ── Chat panel ── */
    QFrame#ChatPanel {{
        background: {BG_PANEL}; border: 1px solid {LINE}; border-radius: 18px;
    }}
    QLabel#PanelTitle {{ color: {TEXT_DIM}; }}
    QLabel#PanelMeta {{ color: {TEXT_MUTED}; font-family: "{FONT_MONO}"; font-size: 11px; }}
    QFrame#PanelSeparator {{ background: {LINE}; max-height: 1px; min-height: 1px; border: none; }}
    QScrollArea#ChatScroll, QWidget#ChatViewport, QWidget#MessageList {{
        background: transparent; border: none;
    }}

    QFrame#BubbleUser {{
        background: rgba(56, 189, 248, 0.13); border: 1px solid rgba(56, 189, 248, 0.30);
        border-radius: 14px; border-bottom-right-radius: 4px;
    }}
    QFrame#BubbleAssistant {{
        background: rgba(255, 255, 255, 0.025); border: 1px solid {LINE};
        border-left: 2px solid {ACCENT}; border-radius: 10px;
    }}
    QFrame#BubbleSystem {{ background: transparent; border: none; }}
    QLabel#BubbleRole {{ font-family: "{FONT_MONO}"; font-size: 11px; color: {ACCENT}; }}
    QLabel#BubbleRoleUser {{ font-family: "{FONT_MONO}"; font-size: 11px; color: {TEXT_DIM}; }}
    QLabel#BubbleTime {{ font-family: "{FONT_MONO}"; font-size: 11px; color: {TEXT_MUTED}; }}
    QLabel#BubbleBody {{ color: {TEXT}; font-size: 14px; }}
    QLabel#SystemText {{ color: {TEXT_MUTED}; font-family: "{FONT_MONO}"; font-size: 12px; }}

    QLabel#EmptyState {{ color: {TEXT_MUTED}; font-size: 13px; }}

    /* ── Tarjeta de herramienta ── */
    QFrame#ToolCard {{
        background: rgba(56, 189, 248, 0.06); border: 1px solid {LINE}; border-radius: 10px;
    }}
    QFrame#ToolCard[state="ok"] {{ border: 1px solid rgba(56, 189, 248, 0.45); }}
    QFrame#ToolCard[state="error"] {{
        background: rgba(255, 90, 122, 0.07); border: 1px solid rgba(255, 90, 122, 0.45);
    }}
    QLabel#ToolCardName {{ color: {TEXT}; }}
    QLabel#ToolCardStatus {{ color: {TEXT_DIM}; }}

    /* ── Toast ── */
    QFrame#Toast {{
        background: {BG_PANEL_SOLID}; border: 1px solid {LINE_STRONG}; border-radius: 10px;
        border-left: 3px solid {ACCENT};
    }}
    QFrame#Toast[kind="error"] {{ border-left: 3px solid {DANGER}; }}
    QLabel#ToastText {{ color: {TEXT}; font-size: 12px; }}

    /* ── Chips de servicio ── */
    QFrame#ServiceChip {{
        background: rgba(56, 189, 248, 0.05); border: 1px solid {LINE}; border-radius: 11px;
    }}
    QLabel#ServiceChipLabel {{ color: {TEXT_DIM}; font-family: "{FONT_MONO}"; font-size: 10px; }}

    /* ── Panel plegable (acciones rápidas) ── */
    QToolButton#QuickAction {{
        background: transparent; border: 1px solid {LINE}; border-radius: 8px; padding: 4px 8px;
        color: {TEXT_DIM}; font-family: "{FONT_MONO}"; font-size: 11px;
    }}
    QToolButton#QuickAction:hover {{ border-color: {LINE_STRONG}; color: {TEXT}; }}
    QToolButton#QuickAction:checked {{
        background: rgba(56, 189, 248, 0.14); border-color: {ACCENT}; color: {ACCENT};
    }}

    /* ── Input ── */
    QFrame#InputBar {{
        background: {BG_INPUT}; border: 1px solid {LINE}; border-radius: 14px;
    }}
    QFrame#InputBar[focused="true"] {{ border: 1px solid rgba(56, 189, 248, 0.55); }}
    QLineEdit#ChatInput {{
        background: transparent; border: none; color: {TEXT}; font-size: 14px;
        selection-background-color: rgba(56, 189, 248, 0.35); padding: 0 4px;
    }}
    QToolButton#IconButton {{
        background: transparent; border: 1px solid transparent; border-radius: 10px;
    }}
    QToolButton#IconButton:hover {{ background: rgba(56, 189, 248, 0.10); border-color: {LINE}; }}
    QToolButton#IconButton:pressed {{ background: rgba(56, 189, 248, 0.18); }}
    QToolButton#MicButton {{
        background: rgba(56, 189, 248, 0.08); border: 1px solid {LINE}; border-radius: 12px;
    }}
    QToolButton#MicButton:hover {{ border-color: {LINE_STRONG}; }}
    QToolButton#MicButton:checked {{
        background: rgba(34, 211, 238, 0.22); border: 1px solid rgba(34, 211, 238, 0.75);
    }}
    QToolButton#SendButton {{
        background: {ACCENT}; border: none; border-radius: 12px;
    }}
    QToolButton#SendButton:hover {{ background: {ACCENT_2}; }}
    QToolButton#SendButton:disabled {{ background: rgba(56, 189, 248, 0.25); }}

    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 2px; }}
    QScrollBar::handle:vertical {{
        background: rgba(120, 180, 255, 0.22); border-radius: 3px; min-height: 36px;
    }}
    QScrollBar::handle:vertical:hover {{ background: rgba(120, 180, 255, 0.40); }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    """
