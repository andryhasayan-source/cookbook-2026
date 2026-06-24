"""
Кулинарная книга «200 Шедевров» — v5.0
"""
import sys, os

# ── Настройка путей ──────────────────────────────────────────
if getattr(sys, 'frozen', False):
    # _MEIPASS = временная папка PyInstaller с кодом/ресурсами
    # EXE_DIR  = папка где лежит .exe (там хранится cookbook.db)
    APP_DIR = sys._MEIPASS
    EXE_DIR = os.path.dirname(sys.executable)
    os.chdir(EXE_DIR)  # cookbook.db создаётся рядом с exe
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_DIR = APP_DIR
    os.chdir(APP_DIR)

for _p in [APP_DIR,
           os.path.join(APP_DIR, 'database'),
           os.path.join(APP_DIR, 'gui')]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QLinearGradient, QRadialGradient, QIcon
from database import db_manager


def _icon_path() -> str:
    """Returns path to icon.ico - works both in source and frozen exe."""
    if getattr(sys, 'frozen', False):
        candidates = [
            # _MEIPASS first - this is where bundled files actually live at runtime
            os.path.join(sys._MEIPASS, 'icon.ico'),
            os.path.join(os.path.dirname(sys.executable), 'icon.ico'),
        ]
    else:
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico'),
        ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return ""


def _set_taskbar_icon(app_id: str = "ShashevPro.CookBook2026"):
    """Windows: привязывает AppUserModelID чтобы иконка корректно
    отображалась на панели задач (иначе Windows показывает иконку python.exe)."""
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass  # не Windows — просто пропускаем


def make_splash():
    pix = QPixmap(600, 380)
    p = QPainter(pix)
    grad = QLinearGradient(0, 0, 600, 380)
    grad.setColorAt(0.0, QColor("#060913"))
    grad.setColorAt(0.5, QColor("#0d1117"))
    grad.setColorAt(1.0, QColor("#1a0a2e"))
    p.fillRect(pix.rect(), grad)
    glow = QRadialGradient(300, 180, 220)
    glow.setColorAt(0.0, QColor(108, 99, 255, 40))
    glow.setColorAt(1.0, QColor(108, 99, 255, 0))
    p.setBrush(glow); p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(80, 60, 440, 260)
    f = QFont(); f.setPointSize(64)
    p.setFont(f)
    p.drawText(pix.rect().adjusted(0, 20, 0, -90), Qt.AlignmentFlag.AlignHCenter, "👨‍🍳")
    f.setPointSize(24); f.setBold(True); p.setFont(f)
    p.setPen(QColor("#e2e8f8"))
    p.drawText(pix.rect().adjusted(0, 160, 0, -60), Qt.AlignmentFlag.AlignHCenter, "200 Шедевров")
    p.setPen(Qt.PenStyle.NoPen)
    bar = QLinearGradient(190, 0, 410, 0)
    bar.setColorAt(0, QColor("#6c63ff")); bar.setColorAt(1, QColor("#ff6584"))
    p.setBrush(bar); p.drawRoundedRect(190, 308, 220, 4, 2, 2)
    p.end()
    return pix


def main():
    # Панель задач Windows: должен быть вызван ДО создания QApplication
    _set_taskbar_icon()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Устанавливаем иконку на уровне приложения — распространяется на все окна
    ico = _icon_path()
    if ico:
        app.setWindowIcon(QIcon(ico))

    splash = QSplashScreen(make_splash())
    splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
    splash.show(); app.processEvents()
    db_manager.init_db(); app.processEvents()
    from main_window import MainWindow
    window = MainWindow()
    # Явно дублируем иконку на главном окне (для надёжности на всех версиях Windows)
    if ico:
        window.setWindowIcon(QIcon(ico))
    QTimer.singleShot(400, lambda: (splash.finish(window), window.show()))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
