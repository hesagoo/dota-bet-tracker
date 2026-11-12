"""Настройки внешнего вида (хранятся в таблице settings той же базы). Без зависимостей от остального интерфейса."""

ACCENTS = {                      # ключ: (название, цвет)
    "ice": ("Лёд", "#7C9CFF"),
    "silver": ("Серебро", "#CFD5E4"),
    "mint": ("Мята", "#5BD3AE"),
    "amethyst": ("Аметист", "#A98BFF"),
    "amber": ("Янтарь", "#E6B24B"),
}
THEMES = {"dark": "Графит", "black": "Чёрная", "light": "Светлая"}
GLASS_PRESETS = [("Непрозрачный", 0), ("Лёгкая", 30), ("Средняя", 55), ("Повышенная", 80)]
BACKDROPS = {"off": "Выключено", "mica": "Mica (мягкое)", "acrylic": "Acrylic (размытие)"}


class Appearance:
    def __init__(self):
        self.theme, self.accent, self.glass = "dark", "ice", 30
        self.glow, self.trail, self.anim, self.backdrop = True, True, True, "off"

    def load(self, db):
        g = db.get_setting
        t = g("theme")
        self.theme = t if t in THEMES else "dark"
        a = g("accent")
        self.accent = a if a in ACCENTS else "ice"
        try:
            self.glass = max(0, min(100, int(g("glass"))))
        except (TypeError, ValueError):
            self.glass = 30
        self.glow = g("fx_glow") != "0"
        self.trail = g("fx_trail") != "0"
        self.anim = g("fx_anim") != "0"
        b = g("backdrop")
        self.backdrop = b if b in BACKDROPS else "off"
        return self

    @property
    def accent_hex(self):
        return ACCENTS[self.accent][1]

    def ms(self, base: int) -> int:
        """Длительность анимации: 0, если декоративные анимации выключены."""
        return base if self.anim else 0


A = Appearance()
