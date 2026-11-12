"""Проверки нового оформления (версия 1.2.0): настройки вида, тема/прозрачность, эффекты, читаемость, скорость."""
import os, sys, tempfile, time
from decimal import Decimal as Dd
from pathlib import Path
tmp = tempfile.mkdtemp()
os.environ["DOTABETS_DATA_DIR"] = tmp
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtCore import QEvent, Qt, QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QPushButton
from core.models import OP_INITIAL
from main import open_database
from ui import theme, fx
from ui.appearance import A, ACCENTS, GLASS_PRESETS, THEMES
from ui.background import MAX_PARTICLES
from ui.main_window import MainWindow
from ui.state import AppState

app = QApplication([])
db, _ = open_database(Path(tmp)); db.add_op(OP_INITIAL, Dd("5000"))
state = AppState(db); theme.apply_theme(app); w = MainWindow(state, app); w.resize(1320, 860); w.show()
settle = lambda n=4: [app.processEvents() for _ in range(n)]
ok = lambda m: print("  OK:", m)

# 1. настройки по умолчанию и защита от мусора в базе
assert (A.theme, A.accent, A.glass, A.glow, A.trail, A.anim, A.backdrop) == ("dark", "ice", 30, True, True, True, "off")
db.set_setting("glass", "999"); db.set_setting("accent", "hacker"); db.set_setting("backdrop", "x"); db.set_setting("theme", "neon")
A.load(db); assert (A.glass, A.accent, A.backdrop, A.theme) == (100, "ice", "off", "dark")
db.set_setting("glass", "abc"); A.load(db); assert A.glass == 30
for k, v in (("glass", "30"), ("theme", "dark")): db.set_setting(k, v)
A.load(db); ok("значения по умолчанию, неверные значения в базе исправляются")

# 2. все темы × акценты × прозрачность: нет ошибок, читаемость сохраняется
def lum(c):
    f = lambda v: (v / 255 / 12.92) if v / 255 <= 0.03928 else (((v / 255) + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c.red()) + 0.7152 * f(c.green()) + 0.0722 * f(c.blue())
def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True); return (la + 0.05) / (lb + 0.05)
for t in THEMES:
    for acc in ACCENTS:
        for _, g in GLASS_PRESETS + [("max", 100)]:
            theme.apply_theme(app, t, acc, g)
            assert theme.G["card_alpha"] >= 130, "панели не должны становиться слишком прозрачными"
            # худший случай: панель с минимальной непрозрачностью поверх фона
            a = theme.G["card_alpha"] / 255
            bgc, cardc, txt = QColor(theme.P["bg"]), QColor(theme.P["card"]), QColor(theme.P["text"])
            blend = QColor(*(int(cardc.red() * a + bgc.red() * (1 - a)), int(cardc.green() * a + bgc.green() * (1 - a)), int(cardc.blue() * a + bgc.blue() * (1 - a))))
            assert contrast(txt, blend) >= 7, (t, acc, g, contrast(txt, blend))
            assert contrast(QColor(theme.P["muted"]), blend) >= 4.5, (t, acc, g)
            assert contrast(QColor(theme.P["on_accent"]), QColor(theme.P["accent"])) >= 4.5, (t, acc)
ok("3 темы × 5 акцентов × 5 уровней прозрачности: контраст текста ≥ 7:1, второстепенного ≥ 4,5:1, кнопки читаемы")

# 3. все страницы во всех темах и размерах окна
for t in ("dark", "black", "light"):
    w.apply_theme(t)
    for size in ((1320, 860), (1000, 660), (1600, 1000)):
        w.resize(*size); settle()
        for i in range(5): w.go(i, animate=False); settle(2)
        assert w.pages["dashboard"].widget().minimumSizeHint().width() <= size[0] - 224 + 2, (t, size)
w.resize(1320, 860); w.apply_theme("dark"); ok("5 страниц × 3 темы × 3 размера окна без ошибок, без горизонтальной прокрутки")

# 4. свечение: появляется при наведении, исчезает при уходе, отключается
A.anim = False
btn = w.add_btn
app.sendEvent(btn, QEvent(QEvent.Enter)); eff = btn.graphicsEffect()
assert isinstance(eff, QGraphicsDropShadowEffect) and eff.color().alpha() > 0
app.sendEvent(btn, QEvent(QEvent.Leave)); assert btn.graphicsEffect() is None
A.glow = False
app.sendEvent(btn, QEvent(QEvent.Enter)); assert btn.graphicsEffect() is None
A.glow = True; A.anim = True
app.sendEvent(btn, QEvent(QEvent.Enter)); settle(3); assert btn.graphicsEffect() is not None
app.sendEvent(btn, QEvent(QEvent.Leave))
for _ in range(40): app.processEvents(); time.sleep(0.01)
assert btn.graphicsEffect() is None
ok("свечение кнопок: появляется, плавно гаснет, при выключении настройки не появляется")

# 5. выбранный пункт меню светится постоянно
w.go(1, animate=False)
assert isinstance(w.nav[1][1].graphicsEffect(), QGraphicsDropShadowEffect) and w.nav[0][1].graphicsEffect() is None
w.go(0, animate=False); ok("активный пункт меню подсвечен")

# 6. след курсора: лимит частиц, отключение, нет нагрузки в покое
bg = w.bg
for i in range(500): bg._spawn(300 + i, 300)
assert len(bg.particles) <= MAX_PARTICLES
A.trail = False; bg.sync(); assert not bg.timer.isActive() and not bg.particles
A.trail = True; bg.sync(); assert bg.timer.isActive()
for _ in range(60): bg._tick()
assert not bg.particles, "частицы должны затухать"
bg._tick(); assert bg.timer.interval() >= 50, "в покое проверка идёт реже"
ok(f"след курсора: не более {MAX_PARTICLES} частиц, затухает, выключается, в покое не нагружает")

# 7. уведомления
A.anim = False; w.toast.show_message("Проверка"); assert w.toast.isVisible() and w.toast.text.text() == "Проверка"
state.toast.emit("Ещё одно"); assert w.toast.text.text() == "Ещё одно"; w.toast._hide(); assert not w.toast.isVisible(); A.anim = True
ok("уведомления показываются и скрываются")

# 8. размытие Windows: на других системах запасной вариант без ошибок
assert not fx.backdrop_supported() and fx.enable_backdrop(w, "acrylic") is False and w.backdrop_ok is False
ok("размытие Windows недоступно здесь → запасной вариант (обычный фон), без ошибок")

# 9. сохранение настроек через интерфейс и после «перезапуска»
sp = w.pages["settings"]; w.go(4, animate=False)
sp.glass_slider.setValue(80); sp.glass_timer.stop(); sp._fx_save("glass", "80")
sp._pick_accent("amethyst"); sp.fx_trail.setChecked(False); sp.fx_glow.setChecked(False); sp.fx_anim.setChecked(False)
sp.theme.set_value("black"); sp.theme.changed.emit("black")
sp.backdrop.setCurrentIndex(sp.backdrop.findData("mica")) if sp.backdrop.isEnabled() else sp._fx_save("backdrop", "mica", restart=True)
settle()
got = {k: db.get_setting(k) for k in ("glass", "accent", "fx_trail", "fx_glow", "fx_anim", "theme", "backdrop")}
assert got == {"glass": "80", "accent": "amethyst", "fx_trail": "0", "fx_glow": "0", "fx_anim": "0", "theme": "black", "backdrop": "mica"}, got
assert (A.glass, A.accent, A.trail, A.glow, A.anim, A.theme) == (80, "amethyst", False, False, False, "black")
w.close(); db.close()
db2, _ = open_database(Path(tmp)); s2 = AppState(db2)
assert (A.glass, A.accent, A.trail, A.glow, A.anim, A.theme, A.backdrop) == (80, "amethyst", False, False, False, "black", "mica")
theme.apply_theme(app); w2 = MainWindow(s2, app); w2.show(); settle()
assert w2.pages["settings"].fx_trail.isChecked() is False and w2.pages["settings"].swatches["amethyst"].isChecked()
assert not w2.bg.timer.isActive() and w2.backdrop_ok is False          # размытие недоступно на этой системе
ok("настройки внешнего вида сохраняются и восстанавливаются после перезапуска; при выключенных эффектах ничего не работает в фоне")

# 10. скорость
A.glow = A.trail = A.anim = True; A.glass = 55; A.backdrop = "off"; w2.apply_theme("dark"); w2.go(0, animate=False); settle()
for i in range(MAX_PARTICLES): w2.bg._spawn(400 + i * 8, 200)
t0 = time.perf_counter(); n = 20
for _ in range(n): w2.grab()
frame = (time.perf_counter() - t0) / n * 1000
t0 = time.perf_counter(); w2.bg._cache = None; w2.bg._build_cache(); cache = (time.perf_counter() - t0) * 1000
t0 = time.perf_counter()
for _ in range(100): w2.bg._tick()
tick = (time.perf_counter() - t0) / 100 * 1000
print(f"  производительность: полный кадр окна {frame:.1f} мс, пересборка фона {cache:.1f} мс, шаг следа {tick:.2f} мс")
assert frame < 250 and cache < 100 and tick < 5
w2.close()
print("ВСЕ ПРОВЕРКИ ОФОРМЛЕНИЯ ПРОЙДЕНЫ")
