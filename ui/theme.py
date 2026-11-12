"""Цвета и стили: три темы (Графит, Чёрная, Светлая), акцентные цвета, «стеклянная» прозрачность."""
from string import Template

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QPolygonF

from core.paths import data_dir
from .appearance import A, ACCENTS

DARK = dict(
    bg="#0B0D12", sidebar="#0F1218", card="#151922", card2="#1C212C", input="#10131A",
    border="#2A303E", border_soft="#1D222D", text="#EEF0F5", muted="#9098AC", faint="#5C647A",
    win="#52C79A", loss="#E5646E", refund="#E3B341", pending="#8FA3C7",
)
BLACK = dict(
    bg="#040406", sidebar="#08090C", card="#0F1015", card2="#171920", input="#0A0B0F",
    border="#262832", border_soft="#16181F", text="#F2F3F7", muted="#9A9FAF", faint="#585D6D",
    win="#52C79A", loss="#E5646E", refund="#E3B341", pending="#8FA3C7",
)
LIGHT = dict(
    bg="#F2F3F7", sidebar="#FFFFFF", card="#FFFFFF", card2="#EEF0F6", input="#F6F7FB",
    border="#DFE2EB", border_soft="#ECEEF4", text="#1B1F2B", muted="#6B7389", faint="#A0A6B8",
    win="#1FA971", loss="#D8444F", refund="#B9830A", pending="#6B7FA6",
)
PALETTES = {"dark": DARK, "black": BLACK, "light": LIGHT}
P: dict = {}          # сплошные цвета (графики, рисование)
G: dict = {}          # параметры «стекла» для собственной отрисовки
THEME = "dark"


def tint(hexcolor: str, alpha: float) -> str:
    c = QColor(hexcolor)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


def mix(a: str, b: str, t: float) -> str:
    ca, cb = QColor(a), QColor(b)
    return QColor(int(ca.red() + (cb.red() - ca.red()) * t), int(ca.green() + (cb.green() - ca.green()) * t),
                  int(ca.blue() + (cb.blue() - ca.blue()) * t)).name()


def luminance(hexcolor: str) -> float:
    c = QColor(hexcolor)
    return (0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()) / 255


def tone_color(tone: str) -> str:
    return P.get(tone or "", P["text"])


def _icons():
    d = data_dir() / "cache"
    d.mkdir(parents=True, exist_ok=True)

    def chevron(path, color):
        pm = QPixmap(24, 24)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(color), 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline(QPolygonF([QPointF(6, 9), QPointF(12, 15), QPointF(18, 9)]))
        p.end()
        pm.save(str(path))

    def tick(path):
        pm = QPixmap(24, 24)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(P["on_accent"]), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline(QPolygonF([QPointF(6, 12.5), QPointF(10.5, 17), QPointF(18, 7.5)]))
        p.end()
        pm.save(str(path))

    a, t = d / f"arrow_{THEME}.png", d / f"tick_{THEME}_{P['accent'][1:]}.png"
    chevron(a, P["muted"])
    tick(t)
    return a.as_posix(), t.as_posix()


QSS = Template("""
QWidget { color: $text; font-size: 13px; }
QMainWindow, QDialog { background: $bg; }
QLabel { background: transparent; }
QToolTip { background: $card2; color: $text; border: 1px solid $line; padding: 6px 8px; border-radius: 6px; }

#Sidebar { background: $glass_sidebar; border-right: 1px solid $line; }
#Logo { font-size: 17px; font-weight: 700; letter-spacing: 0.3px; }
QLabel[role="pagetitle"] { font-size: 24px; font-weight: 700; }
QLabel[role="pagesub"] { color: $muted; font-size: 12px; }
QLabel[role="dialogtitle"] { font-size: 19px; font-weight: 700; }
QLabel[role="cardhead"] { font-size: 14px; font-weight: 600; }
QLabel[role="cardtitle"] { color: $muted; font-size: 12px; font-weight: 500; }
QLabel[role="value"] { font-size: 21px; font-weight: 700; }
QLabel[role="valuehero"] { font-size: 28px; font-weight: 700; }
QLabel[role="sub"], QLabel[role="muted"] { color: $muted; font-size: 12px; }
QLabel[role="field"] { color: $muted; font-size: 12px; font-weight: 500; }
QLabel[role="error"] { color: $loss; font-size: 12px; }
QLabel[role="preview"] { color: $muted; font-size: 12px; }
QLabel[role="hint"] { color: $faint; font-size: 11px; }
QLabel[tone="win"] { color: $win; }
QLabel[tone="loss"] { color: $loss; }
QLabel[tone="refund"] { color: $refund; }
QLabel[tone="pending"] { color: $pending; }
QLabel[tone="accent"] { color: $accent; }
QLabel[tone="muted"] { color: $muted; }

#Toast { background: $glass_toast; border: 1px solid $accent_bd; border-radius: 12px; }
#PendingRow { background: $glass_card2; border: 1px solid $line_soft; border-radius: 10px; }

QPushButton { background: $glass_card2; border: 1px solid $line; border-radius: 9px; padding: 8px 14px; font-weight: 500; }
QPushButton:hover { border-color: $accent_bd; background: $btn_hover; }
QPushButton:pressed { background: $accent_bg; border-color: $accent; }
QPushButton:disabled { color: $faint; border-color: $line_soft; }
QPushButton[variant="primary"] { background: $accent; border: 1px solid $accent; color: $on_accent; font-weight: 600; padding: 9px 18px; }
QPushButton[variant="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[variant="primary"]:pressed { background: $accent; }
QPushButton[variant="primary"]:disabled { background: $card2; border-color: $line_soft; color: $faint; }
QPushButton[variant="danger"] { color: $loss; }
QPushButton[variant="danger"]:hover { border-color: $loss; }
QPushButton[variant="ghost"] { background: transparent; border: none; color: $muted; padding: 6px 8px; }
QPushButton[variant="ghost"]:hover { color: $text; background: transparent; }
QPushButton[variant="mini"] { padding: 4px 10px; font-size: 12px; border-radius: 7px; }
QPushButton[variant="mini"][tone="win"] { color: $win; }
QPushButton[variant="mini"][tone="loss"] { color: $loss; }
QPushButton[variant="mini"][tone="refund"] { color: $refund; }
QPushButton[variant="mini"][tone="win"]:hover { border-color: $win; }
QPushButton[variant="mini"][tone="loss"]:hover { border-color: $loss; }
QPushButton[variant="mini"][tone="refund"]:hover { border-color: $refund; }
QPushButton[nav="true"] { text-align: left; padding: 11px 14px; border: 1px solid transparent; background: transparent; color: $muted; border-radius: 11px; font-weight: 500; }
QPushButton[nav="true"]:hover { background: $btn_hover; color: $text; border-color: $line_soft; }
QPushButton[nav="true"]:checked { background: $accent_bg; color: $accent; font-weight: 600; border: 1px solid $accent_bd; }
QPushButton[seg="true"] { background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 6px 14px; color: $muted; font-weight: 500; }
QPushButton[seg="true"]:hover { color: $text; background: transparent; border-color: transparent; }
QPushButton[seg="true"]:checked { background: $accent_bg; color: $text; border: 1px solid $accent_bd; }
QPushButton[seg="true"][tone="win"]:checked { background: $win_bg; color: $win; border: 1px solid $win_bd; }
QPushButton[seg="true"][tone="loss"]:checked { background: $loss_bg; color: $loss; border: 1px solid $loss_bd; }
QPushButton[seg="true"][tone="refund"]:checked { background: $refund_bg; color: $refund; border: 1px solid $refund_bd; }
QPushButton[seg="true"][tone="pending"]:checked { background: $pending_bg; color: $pending; border: 1px solid $pending_bd; }
#SegWrap { background: $glass_input; border: 1px solid $line; border-radius: 11px; }
QPushButton[variant="tile"] { text-align: left; padding: 0; border-radius: 12px; background: $glass_card2; border: 1px solid $line; }
QPushButton[variant="tile"][rec="true"] { border: 1px solid $accent_bd; }
QPushButton[variant="tile"]:hover { border-color: $accent_bd; }
QPushButton[variant="tile"]:checked { background: $accent_bg; border: 1px solid $accent; }
QPushButton[variant="tile"]:disabled { background: $glass_card; }
QPushButton[variant="chip"] { padding: 4px 10px; font-size: 12px; border-radius: 12px; background: $glass_card2; }
QPushButton[variant="chip"]:hover { border-color: $accent; color: $accent; }
QPushButton[swatch="true"] { padding: 0; border-radius: 15px; border: 2px solid $line; }
QPushButton[swatch="true"]:hover { border-color: $faint; }
QPushButton[swatch="true"]:checked { border: 2px solid $text; }

QLineEdit, QDateEdit, QDateTimeEdit, QComboBox, QSpinBox, QPlainTextEdit {
    background: $glass_input; border: 1px solid $line; border-radius: 9px; padding: 8px 10px; selection-background-color: $accent; selection-color: $on_accent; }
QLineEdit:hover, QDateEdit:hover, QDateTimeEdit:hover, QComboBox:hover, QSpinBox:hover { border-color: $line_hover; }
QLineEdit:focus, QDateEdit:focus, QDateTimeEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus { border: 1px solid $accent; background: $input; }
QComboBox::drop-down, QDateEdit::drop-down, QDateTimeEdit::drop-down { border: none; width: 26px; }
QComboBox::down-arrow, QDateEdit::down-arrow, QDateTimeEdit::down-arrow { image: url($arrow); width: 12px; height: 12px; }
QComboBox QAbstractItemView, QListView { background: $card; border: 1px solid $line; selection-background-color: $accent_bg; selection-color: $text; padding: 4px; outline: 0; }
QSpinBox::up-button, QSpinBox::down-button { width: 0; }
QCalendarWidget QWidget { background: $card; }
QCalendarWidget QAbstractItemView { selection-background-color: $accent; selection-color: $on_accent; }
QCalendarWidget QToolButton { background: transparent; border: none; padding: 4px 8px; }

QSlider::groove:horizontal { height: 6px; background: $input; border: 1px solid $line; border-radius: 4px; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 4px; }
QSlider::handle:horizontal { width: 16px; height: 16px; margin: -7px 0; border-radius: 9px; background: $text; border: 2px solid $accent; }
QSlider::handle:horizontal:hover { background: $accent; }

QCheckBox { spacing: 10px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid $line_hover; border-radius: 5px; background: $input; }
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; image: url($tick); }

QTableWidget { background: transparent; border: none; gridline-color: transparent; selection-background-color: transparent; alternate-background-color: transparent; }
QTableWidget::item { padding: 4px 8px; border-bottom: 1px solid $line_soft; }
QTableWidget::item:selected { background: $accent_bg; color: $text; }
QTableWidget::item:hover { background: $btn_hover; }
QHeaderView { background: transparent; }
QHeaderView::section { background: transparent; color: $muted; border: none; border-bottom: 1px solid $line; padding: 10px 8px; font-weight: 600; font-size: 12px; }
QTableCornerButton::section { background: transparent; border: none; }

QTabWidget::pane { border: none; top: 8px; }
QTabBar::tab { background: transparent; color: $muted; padding: 8px 16px; margin-right: 4px; border-radius: 9px; font-weight: 500; border: 1px solid transparent; }
QTabBar::tab:selected { background: $accent_bg; color: $text; border: 1px solid $accent_bd; }
QTabBar::tab:hover:!selected { color: $text; background: $btn_hover; }

QProgressBar { background: $input; border: 1px solid $line; border-radius: 4px; }
QProgressBar::chunk { background: $accent; border-radius: 3px; }

QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $line_hover; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $faint; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $line_hover; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QMenu { background: $card; border: 1px solid $line_hover; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 8px 18px; border-radius: 6px; }
QMenu::item:selected { background: $accent_bg; }
QMenu::separator { height: 1px; background: $line; margin: 4px 8px; }
QMessageBox { background: $bg; }
QMessageBox QLabel { color: $text; }
""")


def apply_theme(app, name: str = None, accent: str = None, glass: int = None):
    """Применяет тему. Параметры по умолчанию берутся из настроек внешнего вида (appearance.A)."""
    global THEME
    if name is not None:
        A.theme = name if name in PALETTES else "dark"
    if accent is not None and accent in ACCENTS:
        A.accent = accent
    if glass is not None:
        A.glass = max(0, min(100, int(glass)))
    THEME = A.theme if A.theme in PALETTES else "dark"
    light = THEME == "light"
    P.clear()
    P.update(PALETTES[THEME])
    acc = A.accent_hex
    P["accent"] = acc
    P["accent_hover"] = mix(acc, "#FFFFFF" if not light else "#000000", 0.18)
    P["on_accent"] = "#0D1020" if luminance(acc) > 0.55 else "#FFFFFF"
    g = A.glass / 100
    a_card = 1 - (0.38 if light else 0.46) * g          # даже при максимуме панели остаются плотными (читаемость)
    G.clear()
    G.update(light=light, card_alpha=int(255 * a_card), sheen=int(255 * (0.05 if not light else 0.5)),
             line=QColor(0, 0, 0, 26) if light else QColor(255, 255, 255, 24),
             line_hover=QColor(0, 0, 0, 52) if light else QColor(255, 255, 255, 52), glass=g)
    arrow, tick = _icons()
    line_rgb = "0,0,0" if light else "255,255,255"
    vals = dict(
        P, arrow=arrow, tick=tick,
        accent_bg=tint(acc, 0.16), accent_bg0=tint(acc, 0.10), accent_bd=tint(acc, 0.50),
        line=f"rgba({line_rgb},{0.10 if light else 0.09})", line_hover=f"rgba({line_rgb},{0.20 if light else 0.18})",
        line_soft=f"rgba({line_rgb},{0.06 if light else 0.05})", btn_hover=f"rgba({line_rgb},{0.07 if light else 0.06})",
        glass_card=tint(P["card"], round(a_card, 2)), glass_card2=tint(P["card2"], round(min(1, a_card + 0.08), 2)),
        glass_input=tint(P["input"], round(min(1, a_card + 0.12), 2)),
        glass_sidebar=tint(P["sidebar"], round(1 - (0.5 if not light else 0.35) * g, 2)),
        glass_toast=tint(P["card"], 0.94),
    )
    for k in ("win", "loss", "refund", "pending"):
        vals[k + "_bg"] = tint(P[k], 0.14)
        vals[k + "_bd"] = tint(P[k], 0.45)
    f = QFont()
    f.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Inter", "Noto Sans", "DejaVu Sans"])
    f.setPixelSize(13)
    app.setFont(f)
    app.setStyleSheet(QSS.safe_substitute(vals))
