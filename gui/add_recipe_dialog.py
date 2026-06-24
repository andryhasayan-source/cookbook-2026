"""
Диалог добавления / редактирования рецепта — v4.0
Поддерживает таймеры для каждого шага приготовления
"""
import os, json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QComboBox, QSpinBox, QPushButton, QScrollArea,
    QWidget, QFrame, QFileDialog, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QBrush, QColor, QCursor, QFont

import db_manager
try:
    from cuisines import CUISINE_COMBO_ITEMS
except (ImportError, ModuleNotFoundError):
    CUISINE_COMBO_ITEMS = [
        "Российская","Итальянская","Французская","Японская","Китайская",
        "Британская","Американская","Грузинская","Тайская","Индийская",
        "Испанская","Корейская","Скандинавская","Турецкая","Израильская",
        "Мексиканская","Вьетнамская","Марокканская","Перуанская","Греческая",
        "Узбекская","Другая"
    ]

ASSETS   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
NO_IMAGE = os.path.join(ASSETS, "no_image.png")


def _load_thumb(path, w, h):
    pix = QPixmap()
    if path and os.path.isfile(path):
        pix.load(path)
    if pix.isNull() and os.path.isfile(NO_IMAGE):
        pix.load(NO_IMAGE)
    if pix.isNull():
        pix = QPixmap(w, h); pix.fill(QColor("#1e2940"))
    pix = pix.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                     Qt.TransformationMode.SmoothTransformation)
    if pix.width() > w or pix.height() > h:
        x = (pix.width() - w) // 2; y = (pix.height() - h) // 2
        pix = pix.copy(x, y, w, h)
    result = QPixmap(w, h); result.fill(Qt.GlobalColor.transparent)
    p = QPainter(result); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(pix)); p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, w, h, 10, 10); p.end()
    return result


# ─────────────────────────────────────────────────────────────
#  Виджет одного шага приготовления с таймером
# ─────────────────────────────────────────────────────────────
class StepWidget(QWidget):
    remove_requested = pyqtSignal(object)

    def __init__(self, number, text="", hours=0, minutes=0, colors=None, parent=None):
        super().__init__(parent)
        self.c = colors or {}
        self._build(number, text, hours, minutes)

    def _build(self, number, text, hours, minutes):
        c = self.c
        bg     = c.get("surf2","#16213e")
        brd    = c.get("border","#252843")
        txt    = c.get("text","#f0f2ff")
        sub    = c.get("sub","#8892b0")
        acc    = c.get("accent","#e94560")
        blue   = c.get("blue","#4f8ef7")

        self.setStyleSheet(f"""
            StepWidget {{
                background:{bg}; border:1px solid {brd}; border-radius:10px;
            }}
        """)
        main = QVBoxLayout(self)
        main.setContentsMargins(12, 10, 12, 10)
        main.setSpacing(8)

        # Строка заголовка
        top = QHBoxLayout(); top.setSpacing(8)

        num_lbl = QLabel(str(number))
        num_lbl.setFixedSize(28, 28)
        num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num_lbl.setStyleSheet(f"background:{acc}; color:white; border-radius:14px; font-size:13px; font-weight:900;")
        top.addWidget(num_lbl)
        self.num_lbl = num_lbl  # сохраняем ссылку для перенумерации

        step_lbl = QLabel(f"Шаг {number}")
        step_lbl.setStyleSheet(f"font-size:11px; font-weight:700; color:{sub}; background:transparent;")
        top.addWidget(step_lbl)
        self.step_lbl = step_lbl  # сохраняем ссылку для перенумерации
        top.addStretch()

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(24, 24)
        del_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:1px solid {brd};
                border-radius:6px; color:{sub}; font-size:11px; }}
            QPushButton:hover {{ border-color:{acc}; color:{acc}; }}
        """)
        del_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        top.addWidget(del_btn)
        main.addLayout(top)

        # Текст шага
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Опишите шаг приготовления...")
        self.text_edit.setPlainText(text)
        self.text_edit.setFixedHeight(72)
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background:{c.get('surf3','#212340')}; border:1px solid {brd};
                border-radius:8px; color:{txt}; font-size:12px; padding:6px 10px;
            }}
            QTextEdit:focus {{ border-color:{acc}; }}
        """)
        main.addWidget(self.text_edit)

        # Строка таймера
        timer_row = QHBoxLayout(); timer_row.setSpacing(6)

        timer_icon = QLabel("⏱")
        timer_icon.setStyleSheet(f"font-size:14px; background:transparent; color:{blue};")
        timer_row.addWidget(timer_icon)

        timer_lbl = QLabel("Таймер:")
        timer_lbl.setStyleSheet(f"font-size:11px; color:{sub}; background:transparent;")
        timer_row.addWidget(timer_lbl)

        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(0, 23)
        self.hours_spin.setValue(hours)
        self.hours_spin.setSuffix(" ч")
        self.hours_spin.setFixedSize(72, 30)
        self.hours_spin.setStyleSheet(self._spin_style(c))
        timer_row.addWidget(self.hours_spin)

        self.min_spin = QSpinBox()
        self.min_spin.setRange(0, 59)
        self.min_spin.setValue(minutes)
        self.min_spin.setSuffix(" мин")
        self.min_spin.setFixedSize(82, 30)
        self.min_spin.setStyleSheet(self._spin_style(c))
        timer_row.addWidget(self.min_spin)

        hint = QLabel("(0 = без таймера)")
        hint.setStyleSheet(f"font-size:10px; color:{sub}; background:transparent;")
        timer_row.addWidget(hint)
        timer_row.addStretch()
        main.addLayout(timer_row)

    def _spin_style(self, c):
        return f"""
            QSpinBox {{
                background:{c.get('surf3','#212340')};
                border:1px solid {c.get('border','#252843')};
                border-radius:7px; color:{c.get('text','#f0f2ff')};
                font-size:12px; padding:0 6px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width:16px; background:{c.get('border','#252843')}55; border-radius:4px;
            }}
        """

    def get_data(self):
        """Возвращает (text, total_seconds)."""
        txt  = self.text_edit.toPlainText().strip()
        secs = self.hours_spin.value() * 3600 + self.min_spin.value() * 60
        return txt, secs


# ─────────────────────────────────────────────────────────────
#  ДИАЛОГ ДОБАВЛЕНИЯ / РЕДАКТИРОВАНИЯ РЕЦЕПТА
# ─────────────────────────────────────────────────────────────
class AddRecipeDialog(QDialog):
    def __init__(self, dark=True, parent=None, recipe=None):
        super().__init__(parent)
        self.dark        = dark
        self.image_path  = recipe.get("image_path","") if recipe else ""
        self.recipe      = recipe  # None = добавление, dict = редактирование
        self._step_widgets = []

        # Цвета
        if dark:
            self.bg    = "#0b0c14"; self.surf  = "#13141f"
            self.surf2 = "#1a1c2e"; self.surf3 = "#212340"
            self.brd   = "#252843"; self.txt   = "#f0f2ff"
            self.sub   = "#8892b0"; self.acc   = "#e94560"
            self.blue  = "#4f8ef7"
        else:
            self.bg    = "#f4f6fb"; self.surf  = "#ffffff"
            self.surf2 = "#eef1f8"; self.surf3 = "#e4e8f5"
            self.brd   = "#dde2f0"; self.txt   = "#161829"
            self.sub   = "#6b7280"; self.acc   = "#e94560"
            self.blue  = "#2563eb"

        self.colors = {
            "bg":self.bg,"surf2":self.surf2,"surf3":self.surf3,
            "border":self.brd,"text":self.txt,"sub":self.sub,
            "accent":self.acc,"blue":self.blue,
        }

        mode = "Редактировать рецепт" if recipe else "Новый рецепт"
        self.setWindowTitle(mode)
        self.resize(660, 780)
        self.setMinimumSize(580, 640)
        self.setStyleSheet(f"""
            QDialog {{ background:{self.bg}; }}
            QLabel  {{ background:transparent; color:{self.txt}; }}
            QLineEdit, QComboBox, QSpinBox {{
                background:{self.surf2}; border:1px solid {self.brd};
                border-radius:8px; color:{self.txt}; font-size:12px;
                padding:5px 10px; selection-background-color:{self.acc};
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color:{self.acc}; }}
            QComboBox::drop-down {{ border:none; width:20px; }}
            QComboBox QAbstractItemView {{
                background:{self.surf}; border:1px solid {self.brd};
                color:{self.txt}; selection-background-color:{self.acc};
            }}
            QScrollBar:vertical {{
                background:{self.surf2}; width:5px; border-radius:3px;
            }}
            QScrollBar::handle:vertical {{ background:{self.brd}; border-radius:3px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        """)
        self._build()
        if recipe:
            self._fill_fields(recipe)

    # ── Построение UI ────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Шапка
        header = QWidget()
        header.setFixedHeight(54)
        header.setStyleSheet(f"background:{self.surf}; border-bottom:1px solid {self.brd};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)
        icon = "✏️" if self.recipe else "✨"
        mode = "Редактировать рецепт" if self.recipe else "Новый рецепт"
        t = QLabel(f"{icon}  {mode}")
        t.setStyleSheet(f"font-size:15px; font-weight:900; color:{self.txt};")
        hl.addWidget(t); hl.addStretch()
        x = QPushButton("✕")
        x.setFixedSize(28, 28)
        x.setStyleSheet(f"QPushButton{{background:transparent;border:1px solid {self.brd};border-radius:7px;color:{self.sub};font-size:13px;}}QPushButton:hover{{border-color:{self.acc};color:{self.acc};}}")
        x.clicked.connect(self.reject)
        hl.addWidget(x)
        root.addWidget(header)

        # Скролл
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none;background:{self.bg};}}")
        body = QWidget()
        body.setStyleSheet(f"background:{self.bg};")
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(20, 16, 20, 16)
        self.body_layout.setSpacing(12)
        bl = self.body_layout

        # ── Фото ─────────────────────────────────────────────
        photo_frame = QFrame()
        photo_frame.setStyleSheet(f"QFrame{{background:{self.surf2};border-radius:12px;border:2px dashed {self.brd};}}")
        photo_frame.setFixedHeight(148)
        pfl = QHBoxLayout(photo_frame)
        pfl.setContentsMargins(12, 12, 12, 12); pfl.setSpacing(14)

        self.img_lbl = QLabel()
        self.img_lbl.setFixedSize(190, 120)
        self.img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_lbl.setStyleSheet(f"background:{self.surf};border-radius:8px;border:1px solid {self.brd};")
        self._refresh_preview()
        pfl.addWidget(self.img_lbl)

        pr = QVBoxLayout(); pr.setSpacing(6)
        fl = QLabel("Фото блюда")
        fl.setStyleSheet(f"font-size:13px;font-weight:700;color:{self.txt};")
        pr.addWidget(fl)
        fh = QLabel("PNG, JPG, WEBP · Рекомендовано: 400×260")
        fh.setStyleSheet(f"font-size:10px;color:{self.sub};")
        pr.addWidget(fh)
        pr.addStretch()

        pick = QPushButton("📷  Выбрать фото")
        pick.setFixedHeight(32)
        pick.setStyleSheet(f"QPushButton{{background:{self.acc};border:none;border-radius:8px;color:white;font-size:12px;font-weight:700;}}QPushButton:hover{{background:{self.acc}cc;}}")
        pick.clicked.connect(self._pick_photo)
        pr.addWidget(pick)

        clr = QPushButton("✕  Удалить фото")
        clr.setFixedHeight(28)
        clr.setStyleSheet(f"QPushButton{{background:transparent;border:1px solid {self.brd};border-radius:7px;color:{self.sub};font-size:11px;}}QPushButton:hover{{border-color:{self.acc};color:{self.acc};}}")
        clr.clicked.connect(self._clear_photo)
        pr.addWidget(clr)
        pfl.addLayout(pr, 1)
        bl.addWidget(photo_frame)

        # ── Основные поля ─────────────────────────────────────
        bl.addWidget(self._lbl("Название рецепта *"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: Паста Карбонара")
        self.name_edit.setFixedHeight(36)
        bl.addWidget(self.name_edit)

        r1 = QHBoxLayout(); r1.setSpacing(12)
        c1 = QVBoxLayout(); c1.setSpacing(3)
        c1.addWidget(self._lbl("Шеф-повар"))
        self.chef_edit = QLineEdit()
        self.chef_edit.setPlaceholderText("Имя шефа")
        self.chef_edit.setFixedHeight(34)
        c1.addWidget(self.chef_edit)
        r1.addLayout(c1)

        c2 = QVBoxLayout(); c2.setSpacing(3)
        c2.addWidget(self._lbl("Кухня"))
        self.cuisine_combo = QComboBox()
        self.cuisine_combo.setFixedHeight(34)
        self.cuisine_combo.addItems(CUISINE_COMBO_ITEMS)
        c2.addWidget(self.cuisine_combo)
        r1.addLayout(c2)
        bl.addLayout(r1)

        r2 = QHBoxLayout(); r2.setSpacing(12)
        cd = QVBoxLayout(); cd.setSpacing(3)
        cd.addWidget(self._lbl("Сложность"))
        self.diff_combo = QComboBox()
        self.diff_combo.setFixedHeight(34)
        self.diff_combo.addItems(["Лёгкое","Среднее","Сложное"])
        cd.addWidget(self.diff_combo)
        r2.addLayout(cd)

        ce = QVBoxLayout(); ce.setSpacing(3)
        ce.addWidget(self._lbl("Эмодзи"))
        self.emoji_edit = QLineEdit("🍽️")
        self.emoji_edit.setFixedSize(70, 34)
        ce.addWidget(self.emoji_edit)
        r2.addLayout(ce)

        cp = QVBoxLayout(); cp.setSpacing(3)
        cp.addWidget(self._lbl("Подготовка (мин)"))
        self.prep_spin = QSpinBox()
        self.prep_spin.setRange(0, 1440); self.prep_spin.setValue(15)
        self.prep_spin.setFixedHeight(34)
        cp.addWidget(self.prep_spin)
        r2.addLayout(cp)

        ck = QVBoxLayout(); ck.setSpacing(3)
        ck.addWidget(self._lbl("Готовка (мин)"))
        self.cook_spin = QSpinBox()
        self.cook_spin.setRange(0, 1440); self.cook_spin.setValue(30)
        self.cook_spin.setFixedHeight(34)
        ck.addWidget(self.cook_spin)
        r2.addLayout(ck)
        bl.addLayout(r2)

        # Описание
        bl.addWidget(self._lbl("Описание блюда"))
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("Краткое описание рецепта...")
        self.desc_edit.setFixedHeight(64)
        self.desc_edit.setStyleSheet(f"""
            QTextEdit {{background:{self.surf2};border:1px solid {self.brd};
                border-radius:8px;color:{self.txt};font-size:12px;padding:6px 10px;}}
            QTextEdit:focus {{border-color:{self.acc};}}
        """)
        bl.addWidget(self.desc_edit)

        # Ингредиенты
        bl.addWidget(self._lbl("Ингредиенты * (каждый с новой строки)"))
        self.ing_edit = QTextEdit()
        self.ing_edit.setPlaceholderText("500г спагетти\n200г гуанчале\n4 яичных желтка\n100г пекорино романо")
        self.ing_edit.setFixedHeight(100)
        self.ing_edit.setStyleSheet(f"""
            QTextEdit {{background:{self.surf2};border:1px solid {self.brd};
                border-radius:8px;color:{self.txt};font-size:12px;padding:6px 10px;}}
            QTextEdit:focus {{border-color:{self.acc};}}
        """)
        bl.addWidget(self.ing_edit)

        # ── Шаги с таймерами ─────────────────────────────────
        steps_header = QHBoxLayout()
        steps_header.addWidget(self._lbl("Шаги приготовления *"))
        steps_header.addStretch()
        add_step_btn = QPushButton("＋  Добавить шаг")
        add_step_btn.setFixedHeight(28)
        add_step_btn.setStyleSheet(f"""
            QPushButton {{
                background:{self.blue}22; border:1px solid {self.blue}55;
                border-radius:7px; color:{self.blue};
                font-size:11px; font-weight:700; padding:0 12px;
            }}
            QPushButton:hover {{ background:{self.blue}33; }}
        """)
        add_step_btn.clicked.connect(lambda: self._add_step())
        steps_header.addWidget(add_step_btn)
        bl.addLayout(steps_header)

        # Контейнер шагов — QWidget чтобы динамически добавлять дочерние виджеты
        self.steps_widget = QWidget()
        self.steps_widget.setStyleSheet("background:transparent;")
        self.steps_container = QVBoxLayout(self.steps_widget)
        self.steps_container.setContentsMargins(0, 0, 0, 0)
        self.steps_container.setSpacing(8)
        bl.addWidget(self.steps_widget)

        # Добавляем первый пустой шаг
        self._add_step()

        # Теги
        bl.addWidget(self._lbl("Теги (через запятую)"))
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Паста, Итальянская, Быстро")
        self.tags_edit.setFixedHeight(34)
        bl.addWidget(self.tags_edit)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # Нижние кнопки
        footer = QWidget()
        footer.setFixedHeight(58)
        footer.setStyleSheet(f"background:{self.surf};border-top:1px solid {self.brd};")
        fl2 = QHBoxLayout(footer)
        fl2.setContentsMargins(20, 10, 20, 10); fl2.setSpacing(10)

        cancel = QPushButton("Отмена")
        cancel.setFixedHeight(36)
        cancel.setStyleSheet(f"QPushButton{{background:transparent;border:1px solid {self.brd};border-radius:9px;color:{self.sub};font-size:12px;padding:0 20px;}}QPushButton:hover{{border-color:{self.acc};color:{self.acc};}}")
        cancel.clicked.connect(self.reject)
        fl2.addWidget(cancel); fl2.addStretch()

        icon2 = "💾  Сохранить изменения" if self.recipe else "💾  Добавить рецепт"
        save = QPushButton(icon2)
        save.setFixedHeight(36)
        save.setStyleSheet(f"QPushButton{{background:{self.acc};border:none;border-radius:9px;color:white;font-size:13px;font-weight:700;padding:0 24px;}}QPushButton:hover{{background:{self.acc}cc;}}")
        save.clicked.connect(self._save)
        fl2.addWidget(save)
        root.addWidget(footer)

    # ── Шаги ─────────────────────────────────────────────────
    def _add_step(self, text="", hours=0, minutes=0):
        n = len(self._step_widgets) + 1
        sw = StepWidget(n, text, hours, minutes, self.colors, parent=self.steps_widget)
        sw.remove_requested.connect(self._remove_step)
        self._step_widgets.append(sw)
        self.steps_container.addWidget(sw)
        sw.show()

    def _remove_step(self, widget):
        if len(self._step_widgets) <= 1:
            QMessageBox.warning(self, "Ошибка", "Должен быть хотя бы один шаг!")
            return
        self._step_widgets.remove(widget)
        self.steps_container.removeWidget(widget)
        widget.hide()
        widget.deleteLater()
        self._renumber_steps()

    def _renumber_steps(self):
        for i, sw in enumerate(self._step_widgets):
            sw.num_lbl.setText(str(i + 1))
            sw.step_lbl.setText(f"Шаг {i + 1}")

    # ── Фото ─────────────────────────────────────────────────
    def _refresh_preview(self):
        pix = _load_thumb(self.image_path, 190, 120)
        self.img_lbl.setPixmap(pix)

    def _pick_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать фото", "",
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self.image_path = path
            self.img_lbl.setStyleSheet("")
            self._refresh_preview()

    def _clear_photo(self):
        self.image_path = ""
        self.img_lbl.setStyleSheet(f"background:{self.surf};border-radius:8px;border:1px solid {self.brd};")
        self._refresh_preview()

    # ── Заполнение полей при редактировании ──────────────────
    def _fill_fields(self, r):
        self.name_edit.setText(r.get("title",""))
        self.chef_edit.setText(r.get("chef",""))
        self.desc_edit.setPlainText(r.get("description",""))
        self.emoji_edit.setText(r.get("emoji","🍽️"))
        self.prep_spin.setValue(r.get("prep_time",0))
        self.cook_spin.setValue(r.get("cook_time",0))

        # Кухня
        idx = self.cuisine_combo.findText(r.get("cuisine",""))
        if idx >= 0: self.cuisine_combo.setCurrentIndex(idx)

        # Сложность
        idx2 = self.diff_combo.findText(r.get("difficulty",""))
        if idx2 >= 0: self.diff_combo.setCurrentIndex(idx2)

        # Ингредиенты
        ings = r.get("ingredients",[])
        self.ing_edit.setPlainText("\n".join(ings))

        # Шаги — удаляем дефолтный и добавляем из рецепта
        while self._step_widgets:
            sw = self._step_widgets.pop()
            self.steps_container.removeWidget(sw)
            sw.hide()
            sw.deleteLater()

        instructions = r.get("instructions",[])
        timers       = r.get("step_timers",[])  # список секунд

        for i, step_text in enumerate(instructions):
            secs = timers[i] if i < len(timers) else 0
            h    = secs // 3600
            m    = (secs % 3600) // 60
            self._add_step(step_text, h, m)

        if not self._step_widgets:
            self._add_step()

        # Теги
        tags = r.get("tags",[])
        self.tags_edit.setText(", ".join(tags) if tags else "")

    # ── Вспомогательные ──────────────────────────────────────
    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"font-size:11px;font-weight:700;color:{self.sub};letter-spacing:0.5px;")
        return l

    # ── Сохранение ───────────────────────────────────────────
    def _save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self,"Ошибка","Введите название рецепта!"); return

        ings_raw = self.ing_edit.toPlainText().strip()
        if not ings_raw:
            QMessageBox.warning(self,"Ошибка","Добавьте хотя бы один ингредиент!"); return

        # Собираем шаги и таймеры
        instructions = []
        step_timers  = []
        for sw in self._step_widgets:
            txt, secs = sw.get_data()
            if txt:
                instructions.append(txt)
                step_timers.append(secs)

        if not instructions:
            QMessageBox.warning(self,"Ошибка","Добавьте хотя бы один шаг!"); return

        ingredients = [l.strip() for l in ings_raw.splitlines() if l.strip()]
        tags        = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]

        data = {
            "title":        name,
            "chef":         self.chef_edit.text().strip() or "Мой рецепт",
            "cuisine":      self.cuisine_combo.currentText(),
            "difficulty":   self.diff_combo.currentText(),
            "prep_time":    self.prep_spin.value(),
            "cook_time":    self.cook_spin.value(),
            "description":  self.desc_edit.toPlainText().strip(),
            "ingredients":  ingredients,
            "instructions": instructions,
            "step_timers":  step_timers,
            "emoji":        self.emoji_edit.text().strip() or "🍽️",
            "tags":         tags,
            "image_path":   self.image_path,
        }

        try:
            if self.recipe:
                db_manager.update_recipe(self.recipe["id"], data)
                QMessageBox.information(self,"✅ Сохранено",f"Рецепт «{name}» обновлён!")
            else:
                db_manager.save_recipe(data)
                QMessageBox.information(self,"✅ Добавлен",f"Рецепт «{name}» добавлен!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self,"Ошибка сохранения",str(e))
