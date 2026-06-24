"""
Кулинарная книга «200 Шедевров» — v5.0
Glassmorphism · Калории · Поиск по ингредиентам · Планировщик · Список покупок
"""
import os, json, re, random



# ── PDF с Unicode/CIDFont + реальные ширины глифов ───────────
import struct as _struct, re as _re

def _read_ttf(data):
    """Возвращает (umap: {codepoint->glyph_id}, glyph_widths: {glyph_id->pdf_width}, upm)"""
    def u16(d,o): return _struct.unpack_from('>H',d,o)[0]
    def u32(d,o): return _struct.unpack_from('>I',d,o)[0]
    num_t = u16(data,4); tables={}
    for i in range(num_t):
        tag=data[12+i*16:16+i*16]; tables[tag]=(u32(data,20+i*16),u32(data,24+i*16))
    # head -> upm
    upm = u16(data, tables[b'head'][0]+18)
    # hhea -> num_hmetrics
    nhm = u16(data, tables[b'hhea'][0]+34)
    # hmtx -> advance widths
    hoff = tables[b'hmtx'][0]
    raw_w = [u16(data, hoff+i*4) for i in range(nhm)]
    # Конвертируем в PDF units (1000/upm)
    gw = {i: round(raw_w[i]*1000/upm) for i in range(nhm)}
    last_w = raw_w[-1]*1000//upm
    # cmap format4
    umap={}
    if b'cmap' not in tables: return umap, gw, upm
    co=tables[b'cmap'][0]
    for i in range(u16(data,co+2)):
        base=co+4+i*8; plat=u16(data,base); enc=u16(data,base+2)
        off=u32(data,base+4); sub=co+off; fmt=u16(data,sub)
        if fmt==4 and plat==3 and enc==1:
            sc=u16(data,sub+6)//2
            ea=[u16(data,sub+14+j*2) for j in range(sc)]
            sa=[u16(data,sub+16+sc*2+j*2) for j in range(sc)]
            da=[u16(data,sub+16+sc*4+j*2) for j in range(sc)]
            ra=[u16(data,sub+16+sc*6+j*2) for j in range(sc)]
            gb=sub+16+sc*6
            for j in range(sc):
                for cp in range(sa[j],ea[j]+1):
                    if ra[j]==0: gid=(cp+da[j])&0xFFFF
                    else:
                        idx=gb+j*2+ra[j]+(cp-sa[j])*2
                        gid=u16(data,idx) if idx+1<len(data) else 0
                        if gid: gid=(gid+da[j])&0xFFFF
                    if gid: umap[cp]=gid
    return umap, gw, upm

def _clean(s):
    """Убирает эмодзи и символы вне BMP."""
    return ''.join(ch for ch in str(s) if ord(ch) <= 0xFFFF).strip()

def _text_width(s, size, umap, gw):
    """Ширина строки в PDF points."""
    return sum(gw.get(umap.get(ord(ch), 0), 500) for ch in s) * size / 1000

def _wrap_text(text, size, umap, gw, max_w, indent=0):
    """Разбивает текст на строки чтобы каждая влезала в max_w - indent."""
    avail = max_w - indent
    words = _clean(text).split(' ')
    lines_out = []
    cur = ''
    for word in words:
        test = (cur + ' ' + word).strip()
        if _text_width(test, size, umap, gw) <= avail:
            cur = test
        else:
            if cur:
                lines_out.append(cur)
            # Если одно слово не влезает — режем посимвольно
            if _text_width(word, size, umap, gw) > avail:
                part = ''
                for ch in word:
                    if _text_width(part + ch, size, umap, gw) <= avail:
                        part += ch
                    else:
                        if part:
                            lines_out.append(part)
                        part = ch
                cur = part
            else:
                cur = word
    if cur:
        lines_out.append(cur)
    return lines_out if lines_out else ['']

def _make_pdf(path, lines):
    import os, sys
    ttf_path=None; search=[]
    if getattr(sys,'frozen',False):
        # _MEIPASS - temp folder where PyInstaller unpacks bundled files
        mei = getattr(sys,'_MEIPASS','')
        exe_dir = os.path.dirname(sys.executable)
        search += [
            os.path.join(mei,     'arial.ttf'),      # bundled inside exe
            os.path.join(mei,     'fonts','arial.ttf'),
            os.path.join(exe_dir, 'arial.ttf'),       # next to exe
            os.path.join(exe_dir, 'fonts','arial.ttf'),
        ]
    # System fonts fallback
    search += [
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/calibri.ttf',
        'C:/Windows/Fonts/verdana.ttf',
        'C:/Windows/Fonts/tahoma.ttf',
    ]
    for c in search:
        if os.path.isfile(c): ttf_path=c; break
    if not ttf_path:
        raise RuntimeError(
            'Font not found.\n'
            'Copy arial.ttf next to the exe file.')
    with open(ttf_path, 'rb') as _f:
        ttf_data = _f.read()
    umap,gw,upm=_read_ttf(ttf_data)
    # Собираем нужные codepoints (только BMP)
    all_cps=sorted({ord(ch) for text,*_ in lines
                    for ch in _clean(str(text)) if ord(ch) in umap})
    # ToUnicode CMap
    cml=[b'/CIDInit /ProcSet findresource begin',b'12 dict begin',b'begincmap',
         b'/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def',
         b'/CMapName /Adobe-Identity-UCS def',b'/CMapType 2 def',
         b'1 begincodespacerange',b'<0000> <FFFF>',b'endcodespacerange']
    for ch in [all_cps[i:i+100] for i in range(0,len(all_cps),100)]:
        cml.append(str(len(ch)).encode()+b' beginbfchar')
        for cp in ch:
            cml.append(b'<'+format(umap[cp],'04X').encode()+b'> <'+format(cp,'04X').encode()+b'>')
        cml.append(b'endbfchar')
    cml+=[b'endcmap',b'CMapName currentdict /CMap defineresource pop',b'end',b'end']
    cmap_data=b'\n'.join(cml)
    # Widths array для CIDFont
    if all_cps:
        min_gid=min(umap[cp] for cp in all_cps); max_gid=max(umap[cp] for cp in all_cps)
        gid_to_w={umap[cp]:gw.get(umap[cp],500) for cp in all_cps}
        w_arr=b'['+str(min_gid).encode()+b' ['+b' '.join(
            str(gid_to_w.get(g,500)).encode() for g in range(min_gid,max_gid+1))+b']]'
    else:
        w_arr=b'[]'
    W,H,ML,MT,MB=595,842,50,50,40
    objs={}; ctr=[1]
    def add(c): i=ctr[0]; ctr[0]+=1; objs[i]=c; return i
    ttf_id=add(b'<< /Length '+str(len(ttf_data)).encode()+b' >>\nstream\n'+ttf_data+b'\nendstream')
    fd_id=add(b'<< /Type /FontDescriptor /FontName /CF /Flags 32 '
              b'/FontBBox [-665 -210 2000 728] /ItalicAngle 0 '
              b'/Ascent 728 /Descent -210 /CapHeight 716 /StemV 80 '
              b'/FontFile2 '+str(ttf_id).encode()+b' 0 R >>')
    cid_id=add(b'<< /Type /Font /Subtype /CIDFontType2 /BaseFont /CF '
               b'/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> '
               b'/FontDescriptor '+str(fd_id).encode()+b' 0 R '
               b'/DW 500 /W '+w_arr+b' >>')
    cm_id=add(b'<< /Length '+str(len(cmap_data)).encode()+b' >>\nstream\n'+cmap_data+b'\nendstream')
    font_id=add(b'<< /Type /Font /Subtype /Type0 /BaseFont /CF '
                b'/Encoding /Identity-H '
                b'/DescendantFonts ['+str(cid_id).encode()+b' 0 R] '
                b'/ToUnicode '+str(cm_id).encode()+b' 0 R >>')
    def etxt(s):
        r=b'<'
        for ch in _clean(s):
            cp=ord(ch); r+=format(umap.get(cp,umap.get(63,0)),'04X').encode()
        return r+b'>'
    # Разбиваем длинные строки с переносом слов
    # Arial ~15% шире Liberation Sans (тестовый шрифт) — берём 85%
    max_w = int((W - ML - 50) * 0.85)
    pages_data,cur,y=[],[],H-MT
    for text,size,bold,clr,ind in lines:
        lh=size+7
        t=_clean(text)
        if not t:
            if y-lh<MB: pages_data.append(cur); cur=[]; y=H-MT
            cur.append(('',size,clr,ind,y)); y-=lh
            continue
        for wline in _wrap_text(t,size,umap,gw,max_w,ind):
            if y-lh<MB: pages_data.append(cur); cur=[]; y=H-MT
            cur.append((wline,size,clr,ind,y)); y-=lh
    pages_data.append(cur)
    page_ids=[]
    for plines in pages_data:
        cmds=[]
        for text,size,clr,ind,py in plines:
            t=_clean(text)
            if not t: continue
            r2,g2,b2=clr
            cmds+=[(str(round(r2/255,3))+' '+str(round(g2/255,3))+' '+str(round(b2/255,3))+' rg').encode(),
                b'BT',b'/F0 '+str(size).encode()+b' Tf',
                (str(ML+ind)+' '+str(py)+' Td').encode(),
                etxt(t)+b' Tj',b'ET']
        s=b'\n'.join(cmds)
        sid=add(b'<< /Length '+str(len(s)).encode()+b' >>\nstream\n'+s+b'\nendstream')
        pid=add(b'<< /Type /Page /Parent __PG__ /MediaBox [0 0 595 842] '
                b'/Contents '+str(sid).encode()+b' 0 R '
                b'/Resources << /Font << /F0 '+str(font_id).encode()+b' 0 R >> >> >>')
        page_ids.append(pid)
    kids=b' '.join(str(i).encode()+b' 0 R' for i in page_ids)
    pgs_id=add(b'<< /Type /Pages /Kids ['+kids+b'] /Count '+str(len(page_ids)).encode()+b' >>')
    for pid in page_ids: objs[pid]=objs[pid].replace(b'__PG__',str(pgs_id).encode()+b' 0 R')
    cat_id=add(b'<< /Type /Catalog /Pages '+str(pgs_id).encode()+b' 0 R >>')
    out=b'%PDF-1.4\n'; offs={}
    for i in sorted(objs): offs[i]=len(out); out+=str(i).encode()+b' 0 obj\n'+objs[i]+b'\nendobj\n'
    xp=len(out); n=max(objs)+1
    out+=b'xref\n0 '+str(n).encode()+b'\n0000000000 65535 f \n'
    for i in range(1,n): out+=(str(offs.get(i,0)).zfill(10)+' 00000 n \n').encode()
    out+=(b'trailer\n<< /Size '+str(n).encode()+b' /Root '+str(cat_id).encode()+
          b' 0 R >>\nstartxref\n'+str(xp).encode()+b'\n%%EOF\n')
    with open(path,'wb') as f: f.write(out)


from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QScrollArea, QFrame, QGridLayout,
    QFileDialog, QMessageBox, QApplication, QComboBox, QDialog,
    QTextEdit, QListWidget, QListWidgetItem, QSplitter, QStackedWidget,
    QCheckBox, QSpinBox, QTabWidget, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import (QColor, QPixmap, QPainter, QBrush, QCursor,
                         QLinearGradient, QFont, QPen, QIcon, QPainterPath)
from database import db_manager


# gui/ лежит рядом с database/ — sys.path настроен в main.py
try:
    from calories import calculate_nutrition, calories_for_servings
except (ImportError, ModuleNotFoundError):
    # Встроенный минимальный калькулятор (fallback)
    def calculate_nutrition(ings, srv): return {"calories": 0, "proteins": 0, "fats": 0, "carbs": 0}
    def calories_for_servings(r, s): return {"calories": 0, "proteins": 0, "fats": 0, "carbs": 0}
try:
    from cuisines import CUISINES, MAIN_CUISINE_NAMES
except (ImportError, ModuleNotFoundError):
    CUISINES = [
        ("🇷🇺","Российская"),("🇮🇹","Итальянская"),("🇫🇷","Французская"),
        ("🇯🇵","Японская"),("🇨🇳","Китайская"),("🇬🇧","Британская"),
        ("🇺🇸","Американская"),("🇬🇪","Грузинская"),("🇹🇭","Тайская"),
        ("🇮🇳","Индийская"),("🇪🇸","Испанская"),("🇰🇷","Корейская"),
        ("🇸🇪","Скандинавская"),("🇹🇷","Турецкая"),("🇮🇱","Израильская"),
        ("🇲🇽","Мексиканская"),("🇻🇳","Вьетнамская"),("🇲🇦","Марокканская"),
        ("🇵🇪","Перуанская"),("🇬🇷","Греческая"),("🇺🇿","Узбекская"),
    ]
    MAIN_CUISINE_NAMES = {name for _, name in CUISINES}


ASSETS   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
NO_IMAGE = os.path.join(ASSETS, "no_image.png")

# ── Палитра Glassmorphism ─────────────────────────────────────
DARK = {
    "bg":      "#060913",
    "surface": "#0d1117",
    "card":    "#111827",
    "card2":   "#1a2035",
    "sidebar": "#0a0e1a",
    "border":  "#1e2d4a",
    "border2": "#243558",
    "text":    "#e2e8f8",
    "sub":     "#a8b8d8",
    "accent":  "#6c63ff",
    "accent2": "#ff6584",
    "green":   "#10b981",
    "gold":    "#f59e0b",
    "hover":   "#ffffff0d",
    "glass":   "rgba(255,255,255,0.04)",
    "glass2":  "rgba(108,99,255,0.08)",
    "surf2":   "#141d2e",
    "surf3":   "#1e2d4a",
}
LIGHT = {
    "bg":      "#f0f4ff",
    "surface": "#ffffff",
    "card":    "#ffffff",
    "card2":   "#f8faff",
    "sidebar": "#fafbff",
    "border":  "#e2e8f4",
    "border2": "#c7d2e8",
    "text":    "#1a202c",
    "sub":     "#64748b",
    "accent":  "#6c63ff",
    "accent2": "#ff6584",
    "green":   "#059669",
    "gold":    "#d97706",
    "hover":   "#00000008",
    "glass":   "rgba(0,0,0,0.02)",
    "glass2":  "rgba(108,99,255,0.06)",
    "surf2":   "#f1f5fd",
    "surf3":   "#e8eef8",
}

DIFF_COLOR = {
    "Лёгкое":"#10b981","Easy":"#10b981",
    "Среднее":"#f59e0b","Medium":"#f59e0b",
    "Сложное":"#ef4444","Hard":"#ef4444",
}

def _msg(parent, title, text, kind="info"):
    """Clean centered dialog - replaces QMessageBox to avoid layout issues."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setModal(True)
    dlg.setMinimumWidth(360)
    dlg.setStyleSheet("""
        QDialog { background:#111827; color:#e2e8f8; }
        QLabel  { color:#e2e8f8; }
        QPushButton {
            background:#6c63ff; color:#ffffff; border:none;
            border-radius:8px; padding:8px 32px; font-size:12px; font-weight:700;
        }
        QPushButton:hover { background:#5a52e0; }
    """)
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(28, 24, 28, 20)
    lay.setSpacing(14)

    # Icon + title row
    icon_map = {"info": "ℹ️", "warning": "⚠️", "critical": "❌"}
    hdr = QHBoxLayout(); hdr.setSpacing(10)
    ico = QLabel(icon_map.get(kind, "ℹ️"))
    ico.setStyleSheet("font-size:22px; background:transparent;")
    hdr.addWidget(ico)
    ttl = QLabel(f"<b>{title}</b>")
    ttl.setStyleSheet("font-size:14px; font-weight:700; color:#e2e8f8; background:transparent;")
    hdr.addWidget(ttl, 1)
    lay.addLayout(hdr)

    # Message text - centered, wrapped
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("font-size:12px; color:#c8d4ee; background:transparent; line-height:1.5;")
    lay.addWidget(lbl)

    # OK button centered
    btn_row = QHBoxLayout()
    btn_row.addStretch()
    ok_btn = QPushButton("OK")
    ok_btn.setFixedWidth(100)
    ok_btn.clicked.connect(dlg.accept)
    btn_row.addWidget(ok_btn)
    btn_row.addStretch()
    lay.addLayout(btn_row)

    dlg.exec()



def _load_pixmap(path, w, h):
    pix = QPixmap()
    if path and os.path.isfile(path):
        pix.load(path)
    if pix.isNull() and os.path.isfile(NO_IMAGE):
        pix.load(NO_IMAGE)
    if pix.isNull():
        pix = QPixmap(w, h); pix.fill(QColor("#111827"))
        return pix
    return pix.scaled(w, h,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation)


# ── Фоновая загрузка БД ──────────────────────────────────────
class LoaderThread(QThread):
    done = pyqtSignal(list)
    def __init__(self, kwargs):
        super().__init__()
        self.kwargs = kwargs
    def run(self):
        try:
            data = db_manager.get_all_recipes_fast(**self.kwargs)
        except Exception:
            data = []
        self.done.emit(data)


# ── Карточка рецепта ─────────────────────────────────────────
class RecipeCard(QWidget):
    CARD_W = 170
    CARD_H = 260
    IMG_H  = 150
    clicked_signal = pyqtSignal(dict)

    def __init__(self, recipe, colors, search_text="", parent=None):
        super().__init__(parent)
        self.recipe = recipe
        self.c = colors
        self.search_text = search_text.lower().strip()
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._build()

    def _build(self):
        c = self.c
        self.setStyleSheet(f"""
            RecipeCard {{
                background:{c['card']};
                border-radius:14px;
                border:1px solid {c['border']};
            }}
            RecipeCard:hover {{
                border-color:{c['accent']}88;
                background:{c['card2']};
            }}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(0)

        # Фото
        self.img_container = QFrame(self)
        self.img_container.setFixedSize(self.CARD_W, self.IMG_H)
        self.img_container.setStyleSheet("background:transparent;")
        self.img_lbl = QLabel(self.img_container)
        self.img_lbl.setFixedSize(self.CARD_W, self.IMG_H)
        self.img_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._load_image()

        # Кнопка избранного
        is_fav = self.recipe.get("is_favorite", False)
        self.fav_btn = QPushButton("♥" if is_fav else "♡", self.img_container)
        self.fav_btn.setFixedSize(22,22)
        self.fav_btn.move(6,6)
        self.fav_btn.raise_()
        self._style_fav(is_fav)
        self.fav_btn.clicked.connect(self._on_fav)
        self.fav_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Бейдж калорий
        cal = self.recipe.get("calories_per_serving", 0)
        if cal > 0:
            cal_lbl = QLabel(f"🔥{cal}", self.img_container)
            cal_lbl.setStyleSheet("""
                background:rgba(0,0,0,0.65); color:#f59e0b;
                border-radius:7px; font-size:8px; font-weight:700;
                padding:2px 5px;
            """)
            cal_lbl.adjustSize()
            cal_lbl.move(6, self.IMG_H - cal_lbl.height() - 5)
            cal_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        root.addWidget(self.img_container)

        # Текст
        body = QWidget()
        body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(7,5,7,6)
        bl.setSpacing(2)

        title = QLabel(self.recipe["title"])
        title.setWordWrap(True)
        title.setMaximumHeight(32)
        title.setStyleSheet(f"font-size:9px;font-weight:700;color:{c['text']};background:transparent;")
        bl.addWidget(title)

        chef = QLabel(f"{self.recipe.get('chef_country','🌍')} {self.recipe.get('chef','')[:22]}")
        chef.setStyleSheet(f"font-size:10px;color:{c['text']};background:transparent;")
        bl.addWidget(chef)

        # Бейдж «найдено в ...» когда совпадение не в названии
        if self.search_text:
            title_lo = self.recipe.get("title", "").lower()
            ings_lo  = " ".join(self.recipe.get("ingredients", [])).lower()
            desc_lo  = (self.recipe.get("description") or "").lower()
            if self.search_text not in title_lo:
                if self.search_text in ings_lo:
                    hint = QLabel("🥕 в ингредиентах")
                elif self.search_text in desc_lo:
                    hint = QLabel("📝 в описании")
                else:
                    hint = None
                if hint:
                    hint.setStyleSheet(
                        f"font-size:8px;font-weight:700;"
                        f"color:{c['accent']};background:{c['accent']}18;"
                        f"border-radius:4px;padding:1px 5px;"
                    )
                    hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                    bl.addWidget(hint)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{c['border']};margin:0;")
        bl.addWidget(sep)

        # Чипы
        chips = QHBoxLayout(); chips.setSpacing(3)
        diff = self.recipe.get("difficulty","")
        dc = DIFF_COLOR.get(diff, c['sub'])
        for txt, bg, fg in [
            (f"⏱{self.recipe.get('total_time',0)}м", c['surf3'], c['sub']),
            (f"★{self.recipe.get('rating',0):.1f}",  c['surf3'], c['gold']),
            (diff[:6] or "—",                         dc+"33",    dc),
        ]:
            ch = QLabel(txt)
            ch.setStyleSheet(f"font-size:8px;font-weight:700;color:{fg};background:{bg};border-radius:4px;padding:1px 4px;")
            chips.addWidget(ch)
        chips.addStretch()
        bl.addLayout(chips)

        root.addWidget(body, 1)

    def _load_image(self):
        pix = _load_pixmap(self.recipe.get("image_path",""), self.CARD_W, self.IMG_H)
        # Закруглённые верхние углы
        rounded = QPixmap(self.CARD_W, self.IMG_H)
        rounded.fill(Qt.GlobalColor.transparent)
        p = QPainter(rounded)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.CARD_W, self.IMG_H, 14, 14)
        # Срезаем нижние углы
        from PyQt6.QtCore import QRectF
        path.addRect(0, self.IMG_H-14, self.CARD_W, 14)
        p.setClipPath(path)
        p.drawPixmap(0, 0, pix)
        p.end()
        self.img_lbl.setPixmap(rounded)

    def _style_fav(self, active):
        if active:
            self.fav_btn.setStyleSheet("QPushButton{background:rgba(255,101,132,0.85);border:none;border-radius:7px;color:white;font-size:11px;}QPushButton:hover{background:#ff6584;}")
        else:
            self.fav_btn.setStyleSheet("QPushButton{background:rgba(0,0,0,0.5);border:none;border-radius:7px;color:#ffffff88;font-size:11px;}QPushButton:hover{background:rgba(255,101,132,0.7);color:white;}")

    def _on_fav(self):
        new_fav = db_manager.toggle_favorite(self.recipe["id"])
        self.recipe["is_favorite"] = new_fav
        self._style_fav(new_fav)
        self.fav_btn.setText("♥" if new_fav else "♡")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if not self.fav_btn.geometry().contains(e.pos()):
                self.clicked_signal.emit(self.recipe)
        super().mousePressEvent(e)


# ── Боковая панель ────────────────────────────────────────────
class Sidebar(QWidget):
    nav_changed    = pyqtSignal(str)
    export_clicked = pyqtSignal()
    import_clicked = pyqtSignal()

    def __init__(self, colors, dark, parent=None):
        super().__init__(parent)
        self.c = colors; self.dark = dark
        self.setFixedWidth(185)
        self._build()

    def _build(self):
        c = self.c
        self.setStyleSheet(f"Sidebar{{background:{c['sidebar']};border-right:1px solid {c['border']};}}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)
        lay.setSpacing(0)

        # Верх: лого + навигация
        top = QWidget()
        top.setStyleSheet(f"background:{c['sidebar']};")
        tl = QVBoxLayout(top)
        tl.setContentsMargins(12,20,12,8)
        tl.setSpacing(3)

        # Лого
        logo_row = QHBoxLayout()
        logo = QLabel("👨‍🍳")
        logo.setStyleSheet("font-size:22px;background:transparent;")
        logo_row.addWidget(logo)
        col = QVBoxLayout(); col.setSpacing(0)
        t = QLabel("200 Шедевров")
        t.setStyleSheet(f"font-size:12px;font-weight:900;color:{c['text']};background:transparent;")
        s = QLabel("v5.0 · Glassmorphism")
        s.setStyleSheet(f"font-size:7px;color:{c['accent']};background:transparent;")
        col.addWidget(t); col.addWidget(s)
        logo_row.addLayout(col); logo_row.addStretch()
        tl.addLayout(logo_row)
        tl.addSpacing(14)

        # Навигация
        tl.addWidget(self._sep("НАВИГАЦИЯ"))
        tl.addSpacing(4)
        nav_items = [
            ("all",       "🍽️", "Все рецепты"),
            ("favorites", "♥",  "Избранное"),
            ("my",        "✏️", "Мои рецепты"),
            ("planner",   "📅", "Планировщик"),
            ("shopping",  "🛒", "Покупки"),
            ("search_ing","🔍", "По ингредиентам"),
        ]
        for key, icon, lbl in nav_items:
            btn = self._nav_btn(icon, lbl, key=="all")
            btn.clicked.connect(lambda _, k=key: self.nav_changed.emit(k))
            tl.addWidget(btn)
        tl.addSpacing(10)
        tl.addWidget(self._sep("КУХНИ МИРА"))
        tl.addSpacing(4)
        lay.addWidget(top)

        # Скролл кухонь
        try: counts = db_manager.get_cuisine_counts()
        except Exception: counts = {}

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea{{border:none;background:{c['sidebar']};}}
            QWidget{{background:{c['sidebar']};}}
            QScrollBar:vertical{{background:transparent;width:3px;}}
            QScrollBar::handle:vertical{{background:{c['border2']};border-radius:2px;min-height:16px;}}
            QScrollBar::handle:vertical:hover{{background:{c['accent']};}}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}
        """)
        cw = QWidget()
        cl = QVBoxLayout(cw)
        cl.setContentsMargins(12,0,8,4)
        cl.setSpacing(1)
        for flag, name in CUISINES:
            n = counts.get(name, 0)
            btn = self._cuisine_btn(flag, name, n)
            btn.clicked.connect(lambda _, n=name: self.nav_changed.emit(f"cuisine:{n}"))
            cl.addWidget(btn)
        other_count = sum(v for k,v in counts.items() if k not in MAIN_CUISINE_NAMES)
        ob = self._cuisine_btn("🌐","Другая",other_count)
        ob.clicked.connect(lambda: self.nav_changed.emit("cuisine:__other__"))
        cl.addWidget(ob)
        cl.addStretch()
        scroll.setWidget(cw)
        lay.addWidget(scroll, 1)

        # Низ
        bot = QWidget()
        bot.setStyleSheet(f"background:{c['sidebar']};border-top:1px solid {c['border']};")
        bl = QVBoxLayout(bot)
        bl.setContentsMargins(12,8,12,16)
        bl.setSpacing(4)
        bl.addWidget(self._sep("БАЗА ДАННЫХ"))
        bl.addSpacing(3)
        db_row = QHBoxLayout(); db_row.setSpacing(6)
        for txt, sig in [("📤 Экспорт", self.export_clicked),
                         ("📥 Импорт",  self.import_clicked)]:
            b = QPushButton(txt)
            b.setFixedHeight(24)
            b.setStyleSheet(self._ghost_style())
            b.clicked.connect(sig.emit)
            db_row.addWidget(b)
        bl.addLayout(db_row)
        bl.addSpacing(4)
        lay.addWidget(bot)

    def _ghost_style(self):
        c = self.c
        return f"""QPushButton{{background:transparent;border:1px solid {c['border2']};
            border-radius:7px;padding:2px 4px;color:{c['sub']};font-size:9px;text-align:center;}}
            QPushButton:hover{{background:{c['hover']};color:{c['text']};border-color:{c['accent']}88;}}"""

    def _sep(self, txt):
        l = QLabel(txt)
        l.setStyleSheet(f"font-size:7px;font-weight:700;color:{self.c['sub']};letter-spacing:1px;background:transparent;")
        return l

    def _nav_btn(self, icon, label, active=False):
        c = self.c
        gold   = c.get('gold', '#f59e0b')
        normal_color = c['accent'] if active else c['text']

        btn = QPushButton()
        btn.setFixedHeight(28)
        btn.setStyleSheet(f"""QPushButton{{
            background:{'rgba(108,99,255,0.12)' if active else 'transparent'};
            border:{'1px solid '+c['accent']+'44' if active else '1px solid transparent'};
            border-radius:8px;padding:0;
            color:{normal_color};
            font-size:11px;font-weight:{'700' if active else '400'};text-align:left;}}
            QPushButton:hover{{background:{c['accent']}22;border-color:{c['accent']}66;}}""")
        lay = QHBoxLayout(btn)
        lay.setContentsMargins(8,0,6,0); lay.setSpacing(5)
        il = QLabel(icon)
        il.setStyleSheet(f"background:transparent;font-size:12px;color:{normal_color};")
        il.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay.addWidget(il)
        nl = QLabel(label)
        nl.setStyleSheet(f"background:transparent;font-size:11px;font-weight:{'700' if active else '400'};color:{normal_color};")
        nl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay.addWidget(nl, 1)

        # При наведении — жёлтый фон, чёрный текст у дочерних меток
        def on_enter(e, _il=il, _nl=nl):
            _il.setStyleSheet("background:transparent;font-size:12px;color:#ffffff;")
            _nl.setStyleSheet("background:transparent;font-size:11px;font-weight:700;color:#ffffff;")
        def on_leave(e, _il=il, _nl=nl, _c=normal_color):
            _il.setStyleSheet(f"background:transparent;font-size:12px;color:{_c};")
            _nl.setStyleSheet(f"background:transparent;font-size:11px;font-weight:{'700' if active else '400'};color:{_c};")
        btn.enterEvent = on_enter
        btn.leaveEvent = on_leave
        return btn

    def _cuisine_btn(self, flag, name, count=0):
        c = self.c
        gold = c.get('gold', '#f59e0b')
        btn = QPushButton()
        btn.setFixedHeight(30)
        btn.setStyleSheet(f"""QPushButton{{background:transparent;border:none;
            border-radius:8px;padding:0;text-align:left;}}
            QPushButton:hover{{background:{gold};}}""")
        lay = QHBoxLayout(btn)
        lay.setContentsMargins(10,0,8,0); lay.setSpacing(6)
        fl = QLabel(flag)
        fl.setStyleSheet("background:transparent;font-size:14px;")
        fl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay.addWidget(fl)
        nl = QLabel(name)
        nl.setStyleSheet(f"background:transparent;color:{c['text']};font-size:12px;")
        nl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay.addWidget(nl, 1)
        cl = None
        if count > 0:
            cl = QLabel(str(count))
            cl.setStyleSheet(f"background:{c['accent']}33;color:#ffffff;border-radius:8px;font-size:9px;font-weight:700;padding:2px 6px;")
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            lay.addWidget(cl)

        # enterEvent/leaveEvent — жёлтый фон, чёрный текст (QLabel не реагируют на CSS hover родителя)
        def on_enter(e, _fl=fl, _nl=nl, _cl=cl):
            _fl.setStyleSheet("background:transparent;font-size:14px;color:#000000;")
            _nl.setStyleSheet("background:transparent;font-size:12px;font-weight:700;color:#000000;")
            if _cl:
                _cl.setStyleSheet("background:#00000022;color:#000000;border-radius:8px;font-size:9px;font-weight:700;padding:2px 6px;")

        def on_leave(e, _fl=fl, _nl=nl, _cl=cl, _tc=c['text']):
            _fl.setStyleSheet("background:transparent;font-size:14px;")
            _nl.setStyleSheet(f"background:transparent;color:{_tc};font-size:12px;")
            if _cl:
                _cl.setStyleSheet(f"background:{c['accent']}33;color:#ffffff;border-radius:8px;font-size:9px;font-weight:700;padding:2px 6px;")

        btn.enterEvent = on_enter
        btn.leaveEvent = on_leave
        return btn


# ── Топ-бар ───────────────────────────────────────────────────
class TopBar(QWidget):
    search_changed     = pyqtSignal(str)
    difficulty_changed = pyqtSignal(str)
    add_clicked        = pyqtSignal()
    surprise_clicked   = pyqtSignal()

    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.c = colors
        self.setFixedHeight(46)
        self._build()

    def _build(self):
        c = self.c
        self.setStyleSheet(f"background:{c['surface']};border-bottom:1px solid {c['border']};")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16,0,16,0)
        lay.setSpacing(10)

        self.title_lbl = QLabel("Все рецепты")
        self.title_lbl.setStyleSheet(f"font-size:14px;font-weight:900;color:{c['text']};background:transparent;")
        lay.addWidget(self.title_lbl)
        lay.addStretch()

        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Название, ингредиент, описание...")
        self.search.setFixedSize(180,28)
        self.search.setStyleSheet(f"""QLineEdit{{
            background:{c['surf2']};border:1px solid {c['border']};
            border-radius:14px;padding:0 12px;color:{c['text']};font-size:11px;}}
            QLineEdit:focus{{border-color:{c['accent']};background:{c['card2']};}}""")
        timer = QTimer(self); timer.setSingleShot(True); timer.setInterval(300)
        self.search.textChanged.connect(lambda: timer.start())
        timer.timeout.connect(lambda: self.search_changed.emit(self.search.text()))
        lay.addWidget(self.search)

        self.diff_combo = QComboBox()
        self.diff_combo.addItems(["Все уровни","Лёгкое","Среднее","Сложное"])
        self.diff_combo.setFixedSize(110,28)
        self.diff_combo.setStyleSheet(f"""QComboBox{{
            background:{c['surf2']};border:1px solid {c['border']};
            border-radius:10px;padding:0 6px;color:{c['text']};font-size:10px;}}
            QComboBox::drop-down{{border:none;width:16px;}}
            QComboBox QAbstractItemView{{background:{c['surface']};border:1px solid {c['border']};
            color:{c['text']};selection-background-color:{c['accent']};}}""")
        self.diff_combo.currentTextChanged.connect(
            lambda t: self.difficulty_changed.emit("" if t=="Все уровни" else t))
        lay.addWidget(self.diff_combo)

        surprise = QPushButton("🎲")
        surprise.setFixedSize(28,28)
        surprise.setToolTip("Удиви меня — случайный рецепт!")
        surprise.setStyleSheet(f"""QPushButton{{background:{c['gold']}22;border:1px solid {c['gold']}55;
            border-radius:8px;color:{c['gold']};font-size:14px;}}
            QPushButton:hover{{background:{c['gold']}44;}}""")
        surprise.clicked.connect(self.surprise_clicked.emit)
        lay.addWidget(surprise)

        add = QPushButton("＋  Добавить")
        add.setFixedHeight(28)
        add.setStyleSheet(f"""QPushButton{{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {c['accent']},stop:1 {c['accent2']});
            border:none;border-radius:14px;color:white;font-size:10px;font-weight:700;padding:0 14px;}}
            QPushButton:hover{{opacity:0.9;}}""")
        add.clicked.connect(self.add_clicked.emit)
        lay.addWidget(add)


# ── Панель фильтров ───────────────────────────────────────────
class FilterBar(QWidget):
    tag_clicked = pyqtSignal(str)

    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.c = colors
        self.setFixedHeight(36)
        self._build()

    def _build(self):
        c = self.c
        gold = "#f59e0b"
        self.setStyleSheet(f"background:{c['surface']};border-bottom:1px solid {c['border']};")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16,0,16,0); lay.setSpacing(6)
        self.count_lbl = QLabel("...")
        self.count_lbl.setStyleSheet(f"font-size:12px;font-weight:700;color:{c['text']};background:transparent;")
        lay.addWidget(self.count_lbl)
        lay.addSpacing(8)
        for lbl in ["Все","Суп","Паста","Десерт","Рыба","Гриль","Завтрак","Быстро","Мясо"]:
            btn = QPushButton(lbl)
            btn.setFixedHeight(22)
            btn.setStyleSheet(f"""QPushButton{{background:{c['surf2']};border:1px solid {c['border']};
                border-radius:7px;padding:0 10px;color:{c['text']};font-size:11px;font-weight:600;}}
                QPushButton:hover{{background:{gold};border-color:{gold};color:#000000;}}""")
            btn.clicked.connect(lambda _, l=lbl: self.tag_clicked.emit(l))
            lay.addWidget(btn)
        lay.addStretch()


# ── Футер ─────────────────────────────────────────────────────
class Footer(QWidget):
    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.c = colors
        self.setFixedHeight(34)
        self._build()

    def _build(self):
        c = self.c
        self.setStyleSheet(f"background:{c['sidebar']};border-top:1px solid {c['border']};")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(6)

        # ShashevPro — бренд
        brand = QLabel("ShashevPro")
        brand.setStyleSheet(
            f"font-size:10px;font-weight:900;letter-spacing:1px;"
            f"color:{c['accent']};background:transparent;"
        )
        lay.addWidget(brand)

        # Разделитель
        def _dot():
            d = QLabel("·")
            d.setStyleSheet(f"font-size:10px;color:{c['sub']};background:transparent;")
            return d

        lay.addWidget(_dot())

        # Разработчик — кликабельная ссылка
        author = QLabel(
            '<a href="https://vk.com/andrey_shashev" '
            'style="color:#6b7fa8;text-decoration:none;font-size:10px;">'
            'Шашев Андрей Сергеевич</a>'
        )
        author.setStyleSheet("background:transparent;")
        author.setOpenExternalLinks(True)
        author.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        lay.addWidget(author)

        lay.addWidget(_dot())

        # Почта — кликабельная ссылка
        mail = QLabel(
            '<a href="mailto:programmer@shashevpro.ru" '
            'style="color:#6b7fa8;text-decoration:none;font-size:10px;">'
            'programmer@shashevpro.ru</a>'
        )
        mail.setStyleSheet("background:transparent;")
        mail.setOpenExternalLinks(True)
        mail.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        lay.addWidget(mail)

        lay.addStretch()

        # Бейдж версии
        ver = QLabel("v5.0")
        ver.setStyleSheet(
            f"font-size:8px;font-weight:700;color:white;"
            f"background:{c['accent']};border-radius:4px;padding:1px 5px;"
        )
        lay.addWidget(ver)


# ── Планировщик меню ──────────────────────────────────────────
class PlannerWidget(QWidget):
    def __init__(self, colors, dark, parent=None):
        super().__init__(parent)
        self.c = colors; self.dark = dark
        self._recipes = []
        self._build()

    def _build(self):
        c = self.c
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16,16,16,16); lay.setSpacing(10)

        hdr = QLabel("📅  Планировщик меню на неделю")
        hdr.setStyleSheet(f"font-size:15px;font-weight:900;color:{c['text']};background:transparent;")
        lay.addWidget(hdr)

        hint = QLabel("Клик — добавить рецепт  |  ПКМ на ячейке — удалить")
        hint.setStyleSheet(f"font-size:10px;color:{c['sub']};background:transparent;")
        lay.addWidget(hint)

        days  = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
        meals = [("breakfast","🌅 Завтрак"),("lunch","☀️ Обед"),("dinner","🌙 Ужин")]

        grid_w = QWidget()
        grid_w.setStyleSheet(f"background:{c['surface']};border-radius:14px;border:1px solid {c['border']};")
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(10,10,10,10); grid.setSpacing(4)

        # Заголовки дней
        for col, day in enumerate(days):
            lbl = QLabel(day)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"font-size:10px;font-weight:700;color:{c['accent']};background:{c['glass2']};border-radius:6px;padding:4px;")
            grid.addWidget(lbl, 0, col+1)

        # Строки приёмов пищи
        try:
            plan = db_manager.get_meal_plan(0)
        except AttributeError:
            from database import db_manager as _dm
            import importlib; importlib.reload(_dm)
            plan = {}
        self._cells = {}
        for row, (meal_key, meal_name) in enumerate(meals):
            ml = QLabel(meal_name)
            ml.setStyleSheet(f"font-size:9px;font-weight:700;color:{c['sub']};background:transparent;")
            grid.addWidget(ml, row+1, 0)
            for col, day_idx in enumerate(range(7)):
                cell_data = plan.get((day_idx, meal_key))
                btn = QPushButton()
                btn.setFixedHeight(36)
                if cell_data:
                    btn.setText(f"{cell_data['emoji']} {cell_data['title'][:14]}")
                    btn.setStyleSheet(self._cell_style(True))
                else:
                    btn.setText("＋")
                    btn.setStyleSheet(self._cell_style(False))
                btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                btn.clicked.connect(lambda _, d=day_idx, m=meal_key, b=btn: self._pick_recipe(d, m, b))
                btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                btn.customContextMenuRequested.connect(lambda _, d=day_idx, m=meal_key, b=btn: self._clear_cell(d, m, b))
                grid.addWidget(btn, row+1, col+1)
                self._cells[(day_idx, meal_key)] = btn

        lay.addWidget(grid_w)

        # Суммарные калории недели
        self.cal_lbl = QLabel()
        self.cal_lbl.setStyleSheet(f"font-size:10px;color:{c['sub']};background:transparent;")
        lay.addWidget(self.cal_lbl)
        self._update_calories(plan)
        lay.addStretch()

    def _cell_style(self, filled):
        c = self.c
        if filled:
            return f"""QPushButton{{background:{c['accent']}22;border:1px solid {c['accent']}55;
                border-radius:8px;color:{c['text']};font-size:8px;font-weight:700;}}
                QPushButton:hover{{background:{c['accent']}44;}}"""
        return f"""QPushButton{{background:{c['surf2']};border:1px dashed {c['border2']};
            border-radius:8px;color:{c['sub']};font-size:14px;}}
            QPushButton:hover{{background:{c['accent']}11;border-color:{c['accent']};color:{c['accent']};}}"""

    def _clear_cell(self, day, meal_type, btn):
        db_manager.clear_meal_slot(day, meal_type, 0)
        btn.setText("＋")
        btn.setStyleSheet(self._cell_style(False))
        plan = db_manager.get_meal_plan(0)
        self._update_calories(plan)

    def _pick_recipe(self, day, meal_type, btn):
        dlg = RecipePickerDialog(self._recipes, self.c, self.dark, self)
        if dlg.exec():
            recipe = dlg.selected
            if recipe:
                db_manager.set_meal_plan(day, meal_type, recipe["id"], 0)
                btn.setText(f"{recipe['emoji']} {recipe['title'][:14]}")
                btn.setStyleSheet(self._cell_style(True))
                plan = db_manager.get_meal_plan(0)
                self._update_calories(plan)

    def _update_calories(self, plan):
        total = sum(v.get("calories_per_serving",0) for v in plan.values())
        self.cal_lbl.setText(f"🔥 Калорий за неделю (1 порция/приём): ~{total} ккал")

    def set_recipes(self, recipes):
        self._recipes = recipes


# ── Диалог выбора рецепта ──────────────────────────────────
class RecipePickerDialog(QDialog):
    def __init__(self, recipes, colors, dark, parent=None):
        super().__init__(parent)
        self.selected = None
        self.c = colors
        self.setWindowTitle("Выберите рецепт")
        self.resize(400, 500)
        self.setStyleSheet(f"QDialog{{background:{colors['bg']};}} QLineEdit,QListWidget{{background:{colors['card']};color:{colors['text']};border:1px solid {colors['border']};border-radius:8px;padding:4px;}}")
        lay = QVBoxLayout(self)
        search = QLineEdit(); search.setPlaceholderText("Поиск...")
        lay.addWidget(search)
        self.lst = QListWidget()
        self.lst.setStyleSheet(f"QListWidget::item{{padding:8px;}}QListWidget::item:selected{{background:{colors['accent']}33;color:{colors['text']};}}")
        lay.addWidget(self.lst)
        self._recipes = recipes
        self._fill(recipes)
        def _picker_filter(t):
            t = t.lower().strip()
            if not t:
                self._fill(recipes)
                return
            result = []
            for r in recipes:
                title = (r.get("title") or "").lower()
                ings  = " ".join(r.get("ingredients") or []).lower()
                desc  = (r.get("description") or "").lower()
                if t in title or t in ings or t in desc:
                    result.append(r)
            # Sort: title matches first, then ingredients, then description
            def _rank(r):
                t2 = (r.get("title") or "").lower()
                if t in t2: return 0
                return 1
            result.sort(key=_rank)
            self._fill(result)
        search.textChanged.connect(_picker_filter)
        self.lst.itemDoubleClicked.connect(self._pick)
        ok = QPushButton("✓ Выбрать")
        ok.setStyleSheet(f"QPushButton{{background:{colors['accent']};color:white;border:none;border-radius:8px;padding:8px;font-weight:700;}}QPushButton:hover{{opacity:.9;}}")
        ok.clicked.connect(lambda: self._pick(self.lst.currentItem()))
        lay.addWidget(ok)

    def _fill(self, recipes):
        self.lst.clear()
        for r in recipes:
            item = QListWidgetItem(f"{r['emoji']}  {r['title']}")
            item.setData(Qt.ItemDataRole.UserRole, r)
            self.lst.addItem(item)

    def _pick(self, item):
        if item:
            self.selected = item.data(Qt.ItemDataRole.UserRole)
            self.accept()


# ── Список покупок ────────────────────────────────────────────
class ShoppingWidget(QWidget):
    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.c = colors
        self._build()

    def _build(self):
        c = self.c
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16,16,16,16); lay.setSpacing(10)

        hdr = QLabel("🛒  Список покупок")
        hdr.setStyleSheet(f"font-size:15px;font-weight:900;color:{c['text']};background:transparent;")
        lay.addWidget(hdr)

        # Добавить вручную
        add_row = QHBoxLayout()
        self.new_item = QLineEdit()
        self.new_item.setPlaceholderText("Добавить продукт...")
        self.new_item.setStyleSheet(f"""QLineEdit{{background:{c['surf2']};border:1px solid {c['border']};
            border-radius:10px;padding:0 12px;color:{c['text']};font-size:11px;height:28px;}}
            QLineEdit:focus{{border-color:{c['accent']};}}""")
        self.new_item.returnPressed.connect(self._add_manual)
        add_row.addWidget(self.new_item, 1)
        add_btn = QPushButton("＋")
        add_btn.setFixedSize(28,28)
        add_btn.setStyleSheet(f"QPushButton{{background:{c['accent']};border:none;border-radius:8px;color:white;font-size:16px;font-weight:900;}}QPushButton:hover{{opacity:.9;}}")
        add_btn.clicked.connect(self._add_manual)
        add_row.addWidget(add_btn)
        lay.addLayout(add_row)

        # Список
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(f"QScrollArea{{border:none;background:transparent;}}")
        self.list_w = QWidget()
        self.list_w.setStyleSheet("background:transparent;")
        self.list_lay = QVBoxLayout(self.list_w)
        self.list_lay.setContentsMargins(0,0,0,0); self.list_lay.setSpacing(3)
        self.list_lay.addStretch()
        self.scroll.setWidget(self.list_w)
        lay.addWidget(self.scroll, 1)

        # Кнопки управления
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        for txt, fn in [("✓ Убрать отмеченные", self._clear_checked),
                        ("🗑 Очистить всё",      self._clear_all)]:
            b = QPushButton(txt)
            b.setStyleSheet(f"""QPushButton{{background:{c['surf2']};border:1px solid {c['border']};
                border-radius:8px;padding:6px 12px;color:{c['sub']};font-size:10px;}}
                QPushButton:hover{{border-color:{c['accent']};color:{c['accent']};}}""")
            b.clicked.connect(fn)
            btn_row.addWidget(b)
        pdf_export_btn = QPushButton("📄 Экспорт в PDF")
        pdf_export_btn.setStyleSheet(f"""QPushButton{{background:{c['accent']};border:none;
            border-radius:8px;padding:6px 14px;color:white;font-size:10px;font-weight:700;}}
            QPushButton:hover{{background:#f59e0b;color:#000000;}}""")
        pdf_export_btn.clicked.connect(self._export_shopping_pdf)
        btn_row.addWidget(pdf_export_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self.refresh()

    def refresh(self):
        # Очищаем список (кроме stretch)
        while self.list_lay.count() > 1:
            item = self.list_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        items = db_manager.get_shopping_list()
        for it in items:
            row = self._make_row(it)
            self.list_lay.insertWidget(self.list_lay.count()-1, row)

    def _make_row(self, it):
        c = self.c
        w = QWidget()
        w.setStyleSheet(f"background:{c['surf2']};border-radius:8px;")
        lay = QHBoxLayout(w); lay.setContentsMargins(10,5,10,5); lay.setSpacing(8)
        cb = QCheckBox()
        cb.setChecked(it["checked"])
        cb.setStyleSheet(f"""QCheckBox::indicator{{width:16px;height:16px;border-radius:8px;
            border:2px solid {c['border2']};background:{c['surf3']};}}
            QCheckBox::indicator:checked{{background:{c['green']};border-color:{c['green']};}}""")
        cb.stateChanged.connect(lambda _, i=it["id"]: (db_manager.toggle_shopping_item(i), self.refresh()))
        lay.addWidget(cb)
        lbl = QLabel(it["text"])
        lbl.setStyleSheet(f"font-size:11px;color:{'#666' if it['checked'] else c['text']};background:transparent;"
                          + ("text-decoration:line-through;" if it["checked"] else ""))
        lay.addWidget(lbl, 1)
        if it.get("source"):
            src = QLabel(it["source"][:20])
            src.setStyleSheet(f"font-size:8px;color:{c['sub']};background:transparent;")
            lay.addWidget(src)
        return w

    def _add_manual(self):
        t = self.new_item.text().strip()
        if t:
            db_manager.add_shopping_items([t])
            self.new_item.clear()
            self.refresh()

    def _clear_checked(self):
        db_manager.clear_checked_shopping()
        self.refresh()

    def _clear_all(self):
        db_manager.clear_all_shopping()
        self.refresh()

    def add_from_recipe(self, recipe):
        db_manager.add_shopping_items(recipe["ingredients"], recipe["title"])
        self.refresh()

    def _export_shopping_pdf(self):
        import os, datetime
        items = db_manager.get_shopping_list()
        if not items:
            _msg(self, "Список пуст", "Добавьте товары перед экспортом.")
            return
        fname = "список_покупок_" + datetime.date.today().strftime("%d-%m-%Y") + ".pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить список покупок",
            os.path.join(os.path.expanduser("~"), "Desktop", fname),
            "PDF файлы (*.pdf)")
        if not path:
            return
        try:
            self._generate_shopping_pdf(items, path)
            _msg(self, "Готово", "Список сохранён:\n" + path)
        except Exception as ex:
            import traceback
            _msg(self, "Ошибка PDF", traceback.format_exc(), "critical")

    def _generate_shopping_pdf(self, items, path):
        import datetime
        today = datetime.date.today().strftime("%d.%m.%Y")
        total = len(items)
        done  = sum(1 for i in items if i["checked"])
        groups = {}
        for it in items:
            src = (it.get("source") or "").strip() or "Вручную"
            groups.setdefault(src, []).append(it)

        lines = []
        lines.append(("Список покупок",                              22, False, (26, 32, 44),    0))
        lines.append((today + "   Всего: " + str(total) + "   Куплено: " + str(done),
                                                                     10, False, (100,116,139), 0))
        lines.append(("",                                             6, False, (255,255,255),  0))

        for src, grp in groups.items():
            lines.append((src,                                       11, True,  (108, 99,255),  0))
            for it in grp:
                mark = "[x]" if it["checked"] else "[ ]"
                clr  = (148,163,184) if it["checked"] else (30, 41, 59)
                lines.append((mark + "  " + it["text"],             12, False, clr,            10))
            lines.append(("",                                         5, False, (255,255,255),  0))

        lines.append(("",                                             8, False, (255,255,255),  0))
        lines.append(("200 Шедевров  |  Разработчик: Шашев Андрей Сергеевич  |  " + today,
                                                                      8, False, (148,163,184),  0))
        _make_pdf(path, lines)


# ── Поиск по ингредиентам

# ── Поиск по ингредиентам ─────────────────────────────────────
class IngredientSearchWidget(QWidget):
    recipe_selected = pyqtSignal(dict)

    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.c = colors
        self._build()

    def _build(self):
        c = self.c
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16,16,16,16); lay.setSpacing(10)

        hdr = QLabel("🔍  Поиск по ингредиентам")
        hdr.setStyleSheet(f"font-size:15px;font-weight:900;color:{c['text']};background:transparent;")
        lay.addWidget(hdr)

        hint = QLabel("Введите что есть в холодильнике через запятую → найдём рецепты")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"font-size:10px;color:{c['sub']};background:transparent;")
        lay.addWidget(hint)

        inp_row = QHBoxLayout()
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("курица, чеснок, лимон, сливки...")
        self.inp.setStyleSheet(f"""QLineEdit{{background:{c['surf2']};border:2px solid {c['border']};
            border-radius:12px;padding:0 14px;color:{c['text']};font-size:12px;height:34px;}}
            QLineEdit:focus{{border-color:{c['accent']};}}""")
        self.inp.returnPressed.connect(self._search)
        self.inp.textChanged.connect(lambda t: self._clear_results() if not t.strip() else None)
        inp_row.addWidget(self.inp, 1)
        btn = QPushButton("🔍 Найти")
        btn.setFixedHeight(34)
        btn.setStyleSheet(f"""QPushButton{{background:{c['accent']};border:none;border-radius:12px;
            color:white;font-size:11px;font-weight:700;padding:0 18px;}}
            QPushButton:hover{{opacity:.9;}}""")
        btn.clicked.connect(self._search)
        inp_row.addWidget(btn)
        lay.addLayout(inp_row)

        # Популярные теги
        popular_row = QHBoxLayout(); popular_row.setSpacing(5)
        popular_row.addWidget(QLabel("Быстрый выбор:"))
        for tag in ["курица","говядина","рыба","яйца","картофель","паста","томаты"]:
            tb = QPushButton(tag)
            tb.setStyleSheet(f"""QPushButton{{background:{c['glass2']};border:1px solid {c['accent']}44;
                border-radius:10px;color:{c['accent']};font-size:9px;padding:2px 8px;}}
                QPushButton:hover{{background:{c['accent']}22;}}""")
            tb.clicked.connect(lambda _, t=tag: (
                self.inp.setText((self.inp.text()+", "+t).lstrip(", ")),
                self._search()
            ))
            popular_row.addWidget(tb)
        popular_row.addStretch()
        lay.addLayout(popular_row)

        # Результаты
        self.result_lbl = QLabel("")
        self.result_lbl.setStyleSheet(f"font-size:10px;color:{c['sub']};background:transparent;")
        lay.addWidget(self.result_lbl)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self.results_w = QWidget(); self.results_w.setStyleSheet("background:transparent;")
        self.results_lay = QVBoxLayout(self.results_w)
        self.results_lay.setContentsMargins(0,0,0,0); self.results_lay.setSpacing(6)
        self.results_lay.addStretch()
        scroll.setWidget(self.results_w)
        lay.addWidget(scroll, 1)

    def _clear_results(self):
        while self.results_lay.count() > 1:
            item = self.results_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.result_lbl.setText("")

    def _search(self):
        text = self.inp.text().strip()
        if not text:
            self._clear_results()
            return
        ingredients = [t.strip() for t in text.split(",") if t.strip()]
        results = db_manager.search_by_ingredients(ingredients)

        self._clear_results()

        self.result_lbl.setText(f"Найдено: {len(results)} рецептов")
        c = self.c
        for r in results[:30]:
            row = QWidget()
            row.setStyleSheet(f"background:{c['surf2']};border-radius:10px;border:1px solid {c['border']};")
            rl = QHBoxLayout(row); rl.setContentsMargins(12,8,12,8); rl.setSpacing(10)
            em = QLabel(r.get("emoji","🍽️")); em.setStyleSheet("font-size:20px;background:transparent;")
            rl.addWidget(em)
            info = QVBoxLayout(); info.setSpacing(2)
            tl = QLabel(r["title"]); tl.setStyleSheet(f"font-size:12px;font-weight:700;color:{c['text']};background:transparent;")
            cl2 = QLabel(f"⏱{r.get('total_time',0)}м  🍴{r.get('cuisine','')}  🔥{r.get('calories_per_serving',0)}ккал")
            cl2.setStyleSheet(f"font-size:9px;color:{c['sub']};background:transparent;")
            info.addWidget(tl); info.addWidget(cl2)
            rl.addLayout(info, 1)
            matches = r.get("_matches", 0)
            match_lbl = QLabel(f"✓ {matches}")
            match_lbl.setStyleSheet(f"font-size:11px;font-weight:700;color:{c['green']};background:{c['green']}22;border-radius:8px;padding:2px 8px;")
            rl.addWidget(match_lbl)
            open_btn = QPushButton("→")
            open_btn.setFixedSize(28,28)
            open_btn.setStyleSheet(f"QPushButton{{background:{c['accent']};border:none;border-radius:8px;color:white;font-size:14px;}}QPushButton:hover{{opacity:.9;}}")
            open_btn.clicked.connect(lambda _, rec=r: self.recipe_selected.emit(rec))
            rl.addWidget(open_btn)
            self.results_lay.insertWidget(self.results_lay.count()-1, row)


# ── Грид с рецептами ──────────────────────────────────────────
class RecipeGrid(QWidget):
    recipe_clicked = pyqtSignal(dict)

    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.c = colors
        self._cards = []
        self._search_text = ""
        self._build()

    def _build(self):
        c = self.c
        self.setStyleSheet(f"background:{c['bg']};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(f"""QScrollArea{{border:none;background:{c['bg']};}}
            QScrollBar:vertical{{background:transparent;width:5px;border-radius:3px;}}
            QScrollBar::handle:vertical{{background:{c['border2']};border-radius:3px;min-height:20px;}}
            QScrollBar::handle:vertical:hover{{background:{c['accent']};}}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}""")

        self.content = QWidget(); self.content.setStyleSheet(f"background:{c['bg']};")
        self.grid = QGridLayout(self.content)
        self.grid.setSpacing(8)
        self.grid.setContentsMargins(10,10,10,10)
        self.scroll.setWidget(self.content)
        outer.addWidget(self.scroll)

    def show_recipes(self, recipes, search_text=""):
        self._search_text = search_text
        # Удаляем старые карточки
        for card in self._cards:
            self.grid.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        # Сбрасываем все rowStretch перед перестройкой
        for i in range(self.grid.rowCount()):
            self.grid.setRowStretch(i, 0)

        avail = max(self.scroll.width() - 28, RecipeCard.CARD_W * 2)
        cols  = max(2, min(9, avail // (RecipeCard.CARD_W + 8)))

        for i, r in enumerate(recipes):
            card = RecipeCard(r, self.c, search_text=self._search_text)
            card.clicked_signal.connect(self.recipe_clicked.emit)
            self.grid.addWidget(card, i // cols, i % cols)
            self._cards.append(card)

        # Растягиватель
        if recipes:
            self.grid.setRowStretch(self.grid.rowCount(), 1)

    def _reflow(self):
        """Перестраивает колонки без обращения к БД."""
        if not self._cards:
            return
        avail = max(self.scroll.width() - 28, RecipeCard.CARD_W * 2)
        cols  = max(2, min(9, avail // (RecipeCard.CARD_W + 8)))
        for i in range(self.grid.rowCount()):
            self.grid.setRowStretch(i, 0)
        for i, card in enumerate(self._cards):
            self.grid.removeWidget(card)
            self.grid.addWidget(card, i // cols, i % cols)
        self.grid.setRowStretch(self.grid.rowCount(), 1)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if self._cards:
            self._reflow()


# ── Дашборд статистики ────────────────────────────────────────
class StatsWidget(QWidget):
    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.c = colors
        self._build()

    def _build(self):
        c = self.c
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16,16,16,16); lay.setSpacing(12)

        hdr = QLabel("📊  Статистика кулинарной книги")
        hdr.setStyleSheet(f"font-size:15px;font-weight:900;color:{c['text']};background:transparent;")
        lay.addWidget(hdr)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none;background:{c['bg']};}}")
        sw = QWidget(); sw.setStyleSheet(f"background:{c['bg']};")
        sl = QVBoxLayout(sw); sl.setContentsMargins(0,0,0,0); sl.setSpacing(10)

        # Топ блюд по приготовлениям
        top = db_manager.get_top_recipes(5)
        if top:
            top_frame = QFrame()
            top_frame.setStyleSheet(f"QFrame{{background:{c['card']};border-radius:12px;border:1px solid {c['border']};}}")
            tfl = QVBoxLayout(top_frame); tfl.setContentsMargins(14,12,14,12); tfl.setSpacing(6)
            lbl = QLabel("🏆  Топ-5 любимых блюд")
            lbl.setStyleSheet(f"font-size:12px;font-weight:700;color:{c['text']};background:transparent;")
            tfl.addWidget(lbl)
            for i, r in enumerate(top):
                row = QHBoxLayout(); row.setSpacing(8)
                rank = QLabel(["🥇","🥈","🥉","4️⃣","5️⃣"][i])
                rank.setStyleSheet("font-size:14px;background:transparent;")
                row.addWidget(rank)
                title = QLabel(r.get("title","")[:30])
                title.setStyleSheet(f"font-size:11px;color:{c['text']};background:transparent;")
                row.addWidget(title, 1)
                cnt = QLabel(f"🍳×{r.get('cook_count',0)}")
                cnt.setStyleSheet(f"font-size:10px;font-weight:700;color:{c['green']};background:{c['green']}22;border-radius:6px;padding:2px 8px;")
                row.addWidget(cnt)
                tfl.addLayout(row)
            sl.addWidget(top_frame)

        # Общая статистика
        try:
            session = db_manager.get_session()
            try:
                from models import Recipe
            except (ImportError, ModuleNotFoundError):
                from models import Recipe
            total = session.query(Recipe).count()
            favs  = session.query(Recipe).filter(Recipe.is_favorite==True).count()
            mine  = session.query(Recipe).filter(Recipe.is_user_added==True).count()
            cooked= session.query(Recipe).filter(Recipe.cook_count > 0).count()
            total_cooks = session.query(Recipe).all()
            total_cooks_sum = sum(r.cook_count or 0 for r in total_cooks)
            session.close()
        except Exception:
            total = favs = mine = cooked = total_cooks_sum = 0

        stats_data = [
            ("📚 Всего рецептов", str(total), c['accent']),
            ("♥ Избранных", str(favs), c['accent2']),
            ("✏️ Моих", str(mine), c['green']),
            ("🍳 Готовил", str(cooked), c['gold']),
            ("🔥 Раз готовил", str(total_cooks_sum), c['accent']),
        ]
        stats_frame = QFrame()
        stats_frame.setStyleSheet(f"QFrame{{background:{c['card']};border-radius:12px;border:1px solid {c['border']};}}")
        sfl = QVBoxLayout(stats_frame); sfl.setContentsMargins(14,12,14,12); sfl.setSpacing(6)
        lbl2 = QLabel("📋  Общая статистика")
        lbl2.setStyleSheet(f"font-size:12px;font-weight:700;color:{c['text']};background:transparent;")
        sfl.addWidget(lbl2)
        from PyQt6.QtWidgets import QGridLayout as QGL2
        sg = QWidget(); sg.setStyleSheet("background:transparent;")
        sgg = QGL2(sg); sgg.setSpacing(6); sgg.setContentsMargins(0,0,0,0)
        for i,(label,val,color) in enumerate(stats_data):
            cell = QFrame()
            cell.setStyleSheet(f"QFrame{{background:{color}11;border:1px solid {color}33;border-radius:8px;}}")
            cl = QVBoxLayout(cell); cl.setContentsMargins(10,8,10,8); cl.setSpacing(2)
            vl = QLabel(val); vl.setStyleSheet(f"font-size:18px;font-weight:900;color:{color};background:transparent;"); vl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ll = QLabel(label); ll.setStyleSheet(f"font-size:9px;color:{c['sub']};background:transparent;"); ll.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(vl); cl.addWidget(ll)
            sgg.addWidget(cell, i//3, i%3)
        sfl.addWidget(sg)
        sl.addWidget(stats_frame)
        sl.addStretch()
        scroll.setWidget(sw)
        lay.addWidget(scroll,1)

    def refresh(self):
        # Пересоздать содержимое
        while self.layout().count():
            item = self.layout().takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._build()


# ── Главное окно ──────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dark = True
        self.c = DARK.copy()
        self._current_nav = "all"
        self._search_text = ""
        self._difficulty  = ""
        self._tag         = ""
        self._all_recipes = []
        self._loader      = None

        self.setWindowTitle("200 Шедевров v5.0")
        self.resize(910, 580)
        self.setMinimumSize(720, 480)
        self._apply_theme()
        self._build_ui()

        # Запуск загрузки БД в фоне
        QTimer.singleShot(0, self._start_load)

    # ── Тема ─────────────────────────────────────────────────
    def _apply_theme(self):
        c = self.c
        self.setStyleSheet(f"QMainWindow{{background:{c['bg']};}}")

    # ── Построение UI ────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar(self.c, self.dark)
        self.sidebar.nav_changed.connect(self._on_nav)
        self.sidebar.export_clicked.connect(self._export_db)
        self.sidebar.import_clicked.connect(self._import_db)
        root.addWidget(self.sidebar)

        # Правая часть
        right = QWidget()
        right.setStyleSheet(f"background:{self.c['bg']};")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0,0,0,0); rl.setSpacing(0)

        self.topbar = TopBar(self.c)
        self.topbar.search_changed.connect(self._on_search)
        self.topbar.difficulty_changed.connect(self._on_diff)
        self.topbar.add_clicked.connect(self._add_recipe)
        self.topbar.surprise_clicked.connect(self._surprise_me)
        rl.addWidget(self.topbar)

        self.filterbar = FilterBar(self.c)
        self.filterbar.tag_clicked.connect(self._on_tag)
        rl.addWidget(self.filterbar)

        # Стек страниц
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background:{self.c['bg']};")

        self.recipe_grid = RecipeGrid(self.c)
        self.recipe_grid.recipe_clicked.connect(self._open_recipe)
        self.stack.addWidget(self.recipe_grid)   # 0

        self.planner_w = PlannerWidget(self.c, self.dark)
        self.stack.addWidget(self.planner_w)     # 1

        self.shopping_w = ShoppingWidget(self.c)
        self.stack.addWidget(self.shopping_w)    # 2

        self.ing_search_w = IngredientSearchWidget(self.c)
        self.ing_search_w.recipe_selected.connect(self._open_recipe)
        self.stack.addWidget(self.ing_search_w)  # 3

        self.stats_w = StatsWidget(self.c)
        self.stack.addWidget(self.stats_w)        # 4

        rl.addWidget(self.stack, 1)
        rl.addWidget(Footer(self.c))
        root.addWidget(right, 1)

    # ── Загрузка данных ──────────────────────────────────────
    def _start_load(self):
        kwargs = {}
        if self._current_nav == "favorites":
            kwargs["favorites_only"] = True
        elif self._current_nav == "my":
            kwargs["my_only"] = True
        elif self._current_nav.startswith("cuisine:"):
            kwargs["cuisine"] = self._current_nav[8:]
        if self._search_text:
            kwargs["search"] = self._search_text
        if self._difficulty:
            kwargs["difficulty"] = self._difficulty
        if self._tag and self._tag != "Все":
            kwargs["tag"] = self._tag

        self._loader = LoaderThread(kwargs)
        self._loader.done.connect(self._on_loaded)
        self._loader.start()

    def _on_loaded(self, recipes):
        self._all_recipes = recipes
        self.recipe_grid.show_recipes(recipes, search_text=self._search_text)
        self.filterbar.count_lbl.setText(f"{len(recipes)} рецептов")
        # Планировщик всегда получает ВСЕ рецепты без фильтров
        # Не передаём recipes (они могут быть отфильтрованы)
        # set_recipes будет вызван отдельно с полным списком при переходе на вкладку
        if not self._search_text and not self._difficulty and not self._tag:
            self.planner_w.set_recipes(recipes)

    # ── Навигация ────────────────────────────────────────────
    def _on_nav(self, key):
        self._current_nav = key
        titles = {
            "all":       "Все рецепты",
            "favorites": "♥  Избранное",
            "my":        "✏️  Мои рецепты",
            "planner":   "📅  Планировщик меню",
            "shopping":  "🛒  Список покупок",
            "search_ing":"🔍  Поиск по ингредиентам",
        }
        if key.startswith("cuisine:"):
            self.topbar.title_lbl.setText(f"🌍  {key[8:]}")
        else:
            self.topbar.title_lbl.setText(titles.get(key, key))

        if key == "planner":
            # Всегда подгружаем полный список без фильтров для планировщика
            from database import db_manager as _dbm
            try:
                all_r = _dbm.get_all_recipes_fast()
            except Exception:
                all_r = self._all_recipes
            self.planner_w.set_recipes(all_r)
            self.stack.setCurrentIndex(1)
        elif key == "shopping":
            self.stack.setCurrentIndex(2)
            self.shopping_w.refresh()
        elif key == "search_ing":
            self.stack.setCurrentIndex(3)
        elif key == "stats":
            self.stack.setCurrentIndex(4)
            self.stats_w.refresh()
        else:
            self.stack.setCurrentIndex(0)
            self._start_load()

    def _surprise_me(self):
        """Открывает случайный рецепт."""
        import random
        if self._all_recipes:
            recipe = random.choice(self._all_recipes)
        else:
            try:
                recipes = db_manager.get_all_recipes_fast()
                recipe = random.choice(recipes) if recipes else None
            except Exception:
                recipe = None
        if recipe:
            self._open_recipe(recipe)

    def _on_search(self, text):
        self._search_text = text
        self._start_load()

    def _on_diff(self, diff):
        self._difficulty = diff
        self._start_load()

    def _on_tag(self, tag):
        self._tag = tag if tag != "Все" else ""
        self._start_load()

    # ── Открыть рецепт ───────────────────────────────────────
    def _open_recipe(self, recipe):
        try:
            dlg = RecipeDetailDialog(recipe, self.dark, self)
            dlg.rated.connect(db_manager.update_rating)
            dlg.deleted.connect(lambda _: self._start_load())
            dlg.edited.connect(self._start_load)
            dlg.add_to_shopping.connect(lambda r: (
                self.shopping_w.add_from_recipe(r),
                _msg(self, "Покупки", f"Ингредиенты {r['title']} добавлены в список!")
            ))
            dlg.cooked_signal.connect(lambda rid: db_manager.mark_cooked(rid))
            dlg.exec()
            self._start_load()
        except Exception as e:
            import traceback
            _msg(self, "Ошибка при открытии рецепта",
                f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")

    # ── Добавить рецепт ──────────────────────────────────────
    def _add_recipe(self):
        from add_recipe_dialog import AddRecipeDialog
        dlg = AddRecipeDialog(self.dark, self)
        if dlg.exec():
            self._start_load()

    # ── Тема ────────────────────────────────────────────────
    def _toggle_theme(self):
        self.dark = not self.dark
        self.c = DARK.copy() if self.dark else LIGHT.copy()
        _msg(self, "Тема", "Перезапустите программу для применения темы.")

    # ── Экспорт / Импорт ────────────────────────────────────
    def _export_db(self):
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт базы данных", "cookbook_backup.db", "База данных (*.db)")
        if path:
            try:
                db_manager.export_database(path)
                _msg(self, "Экспорт", f"База данных сохранена:\n{path}")
            except Exception as e:
                _msg(self, "Ошибка экспорта", str(e), "critical")

    def _import_db(self):
        path, _ = QFileDialog.getOpenFileName(self, "Импорт базы данных", "", "База данных (*.db)")
        if path:
            qbox = QMessageBox(self)
            qbox.setWindowTitle("Импорт")
            qbox.setText("Заменить текущую базу данных?")
            qbox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            qbox.setDefaultButton(QMessageBox.StandardButton.No)
            qbox.setStyleSheet("""
                QMessageBox{background:#111827;color:#e2e8f8;}
                QLabel{color:#e2e8f8;font-size:12px;}
                QPushButton{background:#6c63ff;color:#ffffff;border:none;
                    border-radius:6px;padding:6px 20px;font-weight:700;}
                QPushButton:hover{background:#5a52e0;}
            """)
            reply = qbox.exec()
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    db_manager.import_database(path)
                    self._start_load()
                except Exception as e:
                    _msg(self, "Ошибка импорта", str(e), "critical")

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        # Только перестраиваем колонки грида — без запроса к БД
        if hasattr(self, 'recipe_grid') and self.stack.currentIndex() == 0:
            QTimer.singleShot(50, self.recipe_grid._reflow)


# ═══════════════════════════════════════════════════════════════
#  ДИАЛОГ РЕЦЕПТА v5.0
#  КБЖУ-слайдер · Достижения · AI-советник · Покупки · Статистика
# ═══════════════════════════════════════════════════════════════
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QWidget, QPushButton, QTextEdit, QFrame, QFileDialog,
    QMessageBox, QSlider, QTabWidget, QSpinBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QRect, QEasingCurve
from PyQt6.QtGui import QPixmap, QPainter, QBrush, QColor, QCursor, QPainterPath, QLinearGradient, QFont, QPen




# ── AI-советы шефа (случайные по категориям) ─────────────────
CHEF_TIPS = {
    "Суп":      ["Добавьте щепотку сахара — нейтрализует кислоту томатов.",
                 "Наваристость бульона зависит от холодного старта варки.",
                 "Финальная зелень — только после огня, иначе горчит."],
    "Мясо":     ["Мясо должно быть комнатной температуры перед готовкой.",
                 "Дайте мясу «отдохнуть» 5–10 минут после жарки.",
                 "Соль добавляйте только в конце — она вытягивает сок."],
    "Рыба":     ["Рыба готова, когда мякоть легко отслаивается вилкой.",
                 "Лимонный сок добавляйте за 2 минуты до подачи.",
                 "Не переворачивайте рыбу более одного раза."],
    "Десерт":   ["Все ингредиенты должны быть одной температуры.",
                 "Мука — лишь треть успеха; остальное — техника.",
                 "Переохлаждение теста делает текстуру шелковистой."],
    "Паста":    ["Вода должна быть солёной, как море.",
                 "Паста доходит в соусе — так она впитывает вкус.",
                 "Оставьте стакан воды от пасты — крахмал свяжет соус."],
    "default":  ["Mis en place — подготовьте всё заранее.",
                 "Вкус рождается в текстуре, запахе и балансе.",
                 "Лучший инструмент шефа — терпение.",
                 "Пробуйте на каждом этапе и доверяйте интуиции."],
}

# ── Достижения ───────────────────────────────────────────────
ACHIEVEMENTS = [
    {"id": "first_cook",   "icon": "🎯", "title": "Первый шаг",     "desc": "Приготовил первый раз",   "cond": lambda c: c >= 1},
    {"id": "cook_5",       "icon": "🍳", "title": "Повторное дело", "desc": "Приготовил 5 раз",         "cond": lambda c: c >= 5},
    {"id": "cook_10",      "icon": "👨‍🍳", "title": "Шеф дома",      "desc": "Приготовил 10 раз",        "cond": lambda c: c >= 10},
    {"id": "cook_25",      "icon": "🏆", "title": "Мастер кулинар", "desc": "Приготовил 25 раз",        "cond": lambda c: c >= 25},
]


def _load_pixmap(path, w, h, radius=0):
    pix = QPixmap()
    if path and os.path.isfile(path):
        pix.load(path)
    if pix.isNull() and os.path.isfile(NO_IMAGE):
        pix.load(NO_IMAGE)
    if pix.isNull():
        pix = QPixmap(w, h)
        pix.fill(QColor("#111827"))
        if radius > 0:
            return pix
    pix = pix.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                     Qt.TransformationMode.SmoothTransformation)
    if pix.width() > w or pix.height() > h:
        x = (pix.width() - w) // 2
        y = (pix.height() - h) // 2
        pix = pix.copy(x, y, w, h)
    if radius > 0:
        result = QPixmap(w, h)
        result.fill(Qt.GlobalColor.transparent)
        p = QPainter(result)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(pix))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, radius, radius)
        p.end()
        return result
    return pix


def _scale_ingredient(text, factor):
    def rep(m):
        val = float(m.group()) * factor
        return str(int(val)) if val == int(val) else f"{val:.1f}"
    return re.sub(r'\d+\.?\d*', rep, text)


# ── Анимированный бейдж калорий ──────────────────────────────
class CalorieBadge(QWidget):
    def __init__(self, recipe, dark, parent=None):
        super().__init__(parent)
        self.recipe = recipe
        self.dark = dark
        self.servings = 1  # показываем на 1 порцию при открытии
        self._per_serving = self._calc_per_serving()
        self._nutrition = self._calc()
        self._build()

    def _calc_per_serving(self):
        """Возвращает КБЖУ строго на 1 порцию."""
        if self.recipe.get("calories_per_serving", 0) > 0:
            return {
                "calories": self.recipe["calories_per_serving"],
                "proteins": self.recipe.get("proteins_per_serving", 0),
                "fats":     self.recipe.get("fats_per_serving", 0),
                "carbs":    self.recipe.get("carbs_per_serving", 0),
            }
        ings = self.recipe.get("ingredients", [])
        srv  = self.recipe.get("default_servings", 4) or 4
        return calculate_nutrition(ings, srv)

    def _calc(self):
        """Возвращает КБЖУ на текущее количество порций."""
        n = self._per_serving
        return {
            "calories": round(n["calories"] * self.servings),
            "proteins": round(n["proteins"] * self.servings, 1),
            "fats":     round(n["fats"]     * self.servings, 1),
            "carbs":    round(n["carbs"]    * self.servings, 1),
        }
    

    def _build(self):
        bg  = "#0d1117" if self.dark else "#f0f4ff"
        brd = "#1e2d4a" if self.dark else "#e2e8f4"
        sub = "#6b7fa8" if self.dark else "#64748b"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        self._val_widgets = []
        n = self._nutrition
        for val, unit, color, icon, label in [
            (n["calories"], "ккал", "#f59e0b", "🔥", "Калории"),
            (n["proteins"], "г",    "#10b981", "💪", "Белки"),
            (n["fats"],     "г",    "#ef4444", "🥑", "Жиры"),
            (n["carbs"],    "г",    "#6c63ff", "⚡", "Углеводы"),
        ]:
            row = QFrame()
            row.setStyleSheet(f"QFrame{{background:{bg};border:1px solid {brd};border-radius:8px;padding:0px;}}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 4, 8, 4); rl.setSpacing(6)
            ico = QLabel(icon)
            ico.setStyleSheet("background:transparent;font-size:13px;")
            rl.addWidget(ico)
            name_lbl = QLabel(label)
            name_lbl.setStyleSheet(f"font-size:10px;color:{sub};background:transparent;")
            rl.addWidget(name_lbl)
            rl.addStretch()
            val_lbl = QLabel(f"{val} {unit}")
            val_lbl.setStyleSheet(f"font-size:12px;font-weight:900;color:{color};background:transparent;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            rl.addWidget(val_lbl)
            lay.addWidget(row)
            self._val_widgets.append((val_lbl, unit))

    def update_servings(self, servings):
        self.servings = max(1, servings)
        self._nutrition = self._calc()
        n = self._nutrition
        vals  = [n["calories"], n["proteins"], n["fats"], n["carbs"]]
        units = ["ккал", "г", "г", "г"]
        for i, (vl, unit) in enumerate(self._val_widgets):
            if i < len(vals):
                vl.setText(f"{vals[i]} {units[i]}")

    def get_calories(self):
        return self._nutrition["calories"]


# ── Таймер шага ──────────────────────────────────────────────
class TimerWidget(QWidget):
    def __init__(self, seconds, label="", dark=True):
        super().__init__()
        self.total = max(seconds, 0)
        self.remain = self.total
        self.running = False
        self.dark = dark
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self._build(label)

    @property
    def _bg(self):  return "#1e2d45" if self.dark else "#eff6ff"
    @property
    def _brd(self): return "#3b82f6" if self.dark else "#bfdbfe"
    @property
    def _clr(self): return "#60a5fa" if self.dark else "#2563eb"
    @property
    def _sub(self): return "#93c5fd" if self.dark else "#3b82f6"

    def _build(self, label):
        self.setStyleSheet(f"TimerWidget{{background:{self._bg};border-radius:10px;border:1px solid {self._brd};}}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 5, 10, 5)
        lay.setSpacing(6)
        icon = QLabel("⏱")
        icon.setStyleSheet("font-size:14px;background:transparent;")
        lay.addWidget(icon)
        name = QLabel(label or "Таймер")
        name.setStyleSheet(f"color:{self._sub};font-size:10px;font-weight:700;background:transparent;")
        lay.addWidget(name)
        lay.addStretch()
        self.display = QLabel(self._fmt(self.total))
        self.display.setStyleSheet(f"color:{self._clr};font-size:18px;font-weight:900;font-family:'Courier New',monospace;min-width:65px;background:transparent;")
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.display)
        self.start_btn = QPushButton("▶")
        self.start_btn.setFixedSize(28, 28)
        self._style_start(False)
        self.start_btn.clicked.connect(self._toggle)
        lay.addWidget(self.start_btn)
        reset_btn = QPushButton("↺")
        reset_btn.setFixedSize(28, 28)
        reset_btn.setStyleSheet("QPushButton{background:#475569;border:none;border-radius:8px;color:white;font-size:12px;}QPushButton:hover{background:#334155;}")
        reset_btn.clicked.connect(self._reset)
        lay.addWidget(reset_btn)

    def _fmt(self, s):
        m, sec = divmod(s, 60); h, m2 = divmod(m, 60)
        return f"{h:02d}:{m2:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"

    def _style_start(self, paused):
        if paused:
            self.start_btn.setText("⏸")
            self.start_btn.setStyleSheet("QPushButton{background:#f59e0b;border:none;border-radius:8px;color:white;font-size:11px;}QPushButton:hover{background:#d97706;}")
        else:
            self.start_btn.setText("▶")
            self.start_btn.setStyleSheet("QPushButton{background:#3b82f6;border:none;border-radius:8px;color:white;font-size:11px;}QPushButton:hover{background:#2563eb;}")

    def _toggle(self):
        if self.running:
            self.timer.stop(); self.running = False; self._style_start(False)
        elif self.remain > 0:
            self.timer.start(1000); self.running = True; self._style_start(True)

    def _tick(self):
        self.remain -= 1
        self.display.setText(self._fmt(self.remain))
        if self.remain <= 0:
            self.timer.stop(); self.running = False
            self._style_start(False)
            self.display.setStyleSheet(f"color:#10b981;font-size:18px;font-weight:900;font-family:'Courier New',monospace;min-width:65px;background:transparent;")
            self.display.setText("✓ Готово!")

    def _reset(self):
        self.timer.stop(); self.running = False; self.remain = self.total
        self.display.setText(self._fmt(self.total))
        self.display.setStyleSheet(f"color:{self._clr};font-size:18px;font-weight:900;font-family:'Courier New',monospace;min-width:65px;background:transparent;")
        self._style_start(False)


# ═══════════════════════════════════════════════════════════════
#  ГЛАВНЫЙ ДИАЛОГ РЕЦЕПТА v5
# ═══════════════════════════════════════════════════════════════
class RecipeDetailDialog(QDialog):
    rated          = pyqtSignal(int, int)
    deleted        = pyqtSignal(int)
    edited         = pyqtSignal()
    add_to_shopping = pyqtSignal(dict)
    cooked_signal  = pyqtSignal(int)

    def __init__(self, recipe, dark=True, parent=None):
        super().__init__(parent)
        self.recipe   = recipe
        self.dark     = dark
        self.portions = recipe.get("default_servings", 4) or 4

        # Цвета
        if dark:
            self.bg    = "#060913"; self.surf  = "#0d1117"; self.surf2 = "#111827"
            self.brd   = "#1e2d4a"; self.txt   = "#e2e8f8"; self.sub   = "#a8b8d8"
            self.acc   = "#6c63ff"; self.acc2  = "#ff6584"; self.gold  = "#f59e0b"
            self.green = "#10b981"
        else:
            self.bg    = "#f0f4ff"; self.surf  = "#ffffff"; self.surf2 = "#f8faff"
            self.brd   = "#e2e8f4"; self.txt   = "#1a202c"; self.sub   = "#64748b"
            self.acc   = "#6c63ff"; self.acc2  = "#ff6584"; self.gold  = "#d97706"
            self.green = "#059669"

        self.setWindowTitle(f"🍽  {recipe['title']}")
        self.setModal(True)
        self.resize(700, 580)
        self.setStyleSheet(f"QDialog{{background:{self.bg};}}")
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Левая панель (шапка + инфо) ─────────────────────
        left = QWidget()
        left.setFixedWidth(220)
        left.setStyleSheet(f"background:{self.surf};border-right:1px solid {self.brd};")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)

        # Фото
        self.img_lbl = QLabel()
        self.img_lbl.setFixedSize(220, 160)
        self.img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._reload_image()
        ll.addWidget(self.img_lbl)

        # Инфо-панель
        info_w = QWidget()
        info_w.setStyleSheet(f"background:{self.surf};")
        il = QVBoxLayout(info_w)
        il.setContentsMargins(14, 12, 14, 10)
        il.setSpacing(6)

        # Emoji + название
        title_row = QHBoxLayout()
        em = QLabel(self.recipe.get("image_emoji", "🍽️"))
        em.setStyleSheet("font-size:26px;background:transparent;")
        title_row.addWidget(em)
        tl = QLabel(self.recipe["title"])
        tl.setWordWrap(True)
        tl.setStyleSheet(f"font-size:12px;font-weight:900;color:{self.txt};background:transparent;")
        title_row.addWidget(tl, 1)
        il.addLayout(title_row)

        # Шеф
        chef_lbl = QLabel(f"{self.recipe.get('chef_country','🌍')} {self.recipe.get('chef','Неизвестно')}")
        chef_lbl.setStyleSheet(f"font-size:10px;color:{self.sub};background:transparent;")
        il.addWidget(chef_lbl)

        # Чипы сложности / времени / кухни — оранжевый фон, чёрный текст
        chips_row = QHBoxLayout(); chips_row.setSpacing(3)
        diff  = self.recipe.get("difficulty","")
        gold  = "#f59e0b"
        chip_style = (
            "font-size:9px;font-weight:700;color:#000000;"
            f"background:{gold};border-radius:5px;padding:2px 5px;"
        )
        cuisine_raw = self.recipe.get("cuisine_type", self.recipe.get("cuisine", ""))
        # Словарь сокращений для длинных названий кухонь
        cuisine_short_map = {
            "Скандинавская": "Скандинав.",
            "Американская":  "Американс.",
            "Израильская":   "Израильск.",
            "Марокканская":  "Марокканс.",
            "Британская":    "Британск.",
            "Грузинская":    "Грузинск.",
            "Итальянская":   "Итальянск.",
            "Французская":   "Французск.",
            "Мексиканская":  "Мексиканс.",
            "Вьетнамская":   "Вьетнамск.",
            "Перуанская":    "Перуанск.",
            "Узбекская":     "Узбекск.",
            "Корейская":     "Корейск.",
            "Испанская":     "Испанск.",
            "Индийская":     "Индийск.",
            "Китайская":     "Китайск.",
            "Японская":      "Японск.",
            "Тайская":       "Тайск.",
            "Турецкая":      "Турецк.",
            "Греческая":     "Греческ.",
            "Российская":    "Российск.",
        }
        cuisine_short = cuisine_short_map.get(cuisine_raw, cuisine_raw[:9]) if cuisine_raw else ""
        time_val = self.recipe.get("total_time", 0)
        time_txt = f"⏱{time_val}м" if time_val else ""
        for txt in [time_txt, diff or "", cuisine_short]:
            if not txt.strip(): continue
            ch = QLabel(txt)
            ch.setStyleSheet(chip_style)
            ch.setSizePolicy(ch.sizePolicy().horizontalPolicy(),
                             ch.sizePolicy().verticalPolicy())
            chips_row.addWidget(ch)
        chips_row.addStretch()
        il.addLayout(chips_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{self.brd};max-height:1px;")
        il.addWidget(sep)

        # ── КБЖУ-блок с СЛАЙДЕРОМ порций ──────────────────
        srv_row = QHBoxLayout(); srv_row.setSpacing(6)
        srv_lbl = QLabel("Порций:")
        srv_lbl.setStyleSheet(f"font-size:10px;font-weight:700;color:{self.sub};background:transparent;")
        srv_row.addWidget(srv_lbl)

        self.srv_minus = QPushButton("−")
        self.srv_minus.setFixedSize(22, 22)
        self.srv_minus.setStyleSheet(self._btn_style(self.brd, self.sub))
        self.srv_minus.clicked.connect(lambda: self._change_portions(-1))
        srv_row.addWidget(self.srv_minus)

        self.srv_num = QLabel(str(self.portions))
        self.srv_num.setFixedWidth(26)
        self.srv_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.srv_num.setStyleSheet(f"font-size:13px;font-weight:900;color:{self.acc};background:transparent;")
        srv_row.addWidget(self.srv_num)

        self.srv_plus = QPushButton("＋")
        self.srv_plus.setFixedSize(22, 22)
        self.srv_plus.setStyleSheet(self._btn_style(self.acc, self.acc))
        self.srv_plus.clicked.connect(lambda: self._change_portions(+1))
        srv_row.addWidget(self.srv_plus)
        srv_row.addStretch()
        il.addLayout(srv_row)

        # КБЖУ-бейдж
        self.cal_badge = CalorieBadge(self.recipe, self.dark)
        il.addWidget(self.cal_badge)

        # ── Счётчик приготовлений ──────────────────────────
        cook_count = self.recipe.get("cook_count", 0)
        self.cook_lbl = QLabel(f"🍳 Приготовлено: {cook_count} раз")
        self.cook_lbl.setStyleSheet(f"font-size:9px;color:{self.sub};background:transparent;")
        il.addWidget(self.cook_lbl)

        # Достижения
        self.achiev_row = QHBoxLayout(); self.achiev_row.setSpacing(3)
        self._render_achievements(cook_count)
        il.addLayout(self.achiev_row)

        # ── Кнопки действий ───────────────────────────────
        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"background:{self.brd};max-height:1px;")
        il.addWidget(sep2)

        # Кнопка "Приготовил!"
        self.cooked_btn = QPushButton("🍳  Я приготовил!")
        self.cooked_btn.setFixedHeight(30)
        self.cooked_btn.setStyleSheet(f"""QPushButton{{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {self.green},stop:1 {self.acc});
            border:none;border-radius:10px;color:white;font-size:10px;font-weight:700;}}
            QPushButton:hover{{opacity:.9;}}""")
        self.cooked_btn.clicked.connect(self._on_cooked)
        il.addWidget(self.cooked_btn)

        # Добавить в покупки
        shop_btn = QPushButton("🛒  В список покупок")
        shop_btn.setFixedHeight(28)
        shop_btn.setStyleSheet(self._ghost_btn())
        shop_btn.clicked.connect(lambda: self.add_to_shopping.emit(self.recipe))
        il.addWidget(shop_btn)

        # Фото / Редактировать / Удалить
        act_row = QHBoxLayout(); act_row.setSpacing(4)
        for txt, fn in [("📷", self._change_photo), ("✏️", self._edit_recipe), ("🗑", self._delete_recipe)]:
            b = QPushButton(txt)
            b.setFixedSize(28, 28)
            b.setStyleSheet(self._ghost_btn(size=14))
            b.clicked.connect(fn)
            act_row.addWidget(b)

        pdf_btn = QPushButton("📄 PDF")
        pdf_btn.setFixedHeight(28)
        pdf_btn.setStyleSheet(self._ghost_btn())
        pdf_btn.clicked.connect(self._export_pdf)
        act_row.addWidget(pdf_btn, 1)
        il.addLayout(act_row)

        il.addStretch()
        ll.addWidget(info_w, 1)

        root.addWidget(left)

        # ── Правая часть (табы) ──────────────────────────────
        right = QWidget()
        right.setStyleSheet(f"background:{self.bg};")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        # AI совет
        self.tip_banner = self._make_tip_banner()
        rl.addWidget(self.tip_banner)

        # Табы
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""QTabWidget::pane{{
            background:{self.bg};border:none;border-top:1px solid {self.brd};}}
            QTabBar::tab{{background:{self.surf};border:none;padding:8px 14px;
            color:{self.sub};font-size:10px;font-weight:700;min-width:70px;}}
            QTabBar::tab:selected{{color:{self.acc};border-bottom:2px solid {self.acc};background:{self.bg};}}
            QTabBar::tab:hover{{color:{self.txt};}}""")

        # Вкладки
        self.tabs.addTab(self._make_tab_ingredients(), "🥕  Ингредиенты")
        self.tabs.addTab(self._make_tab_steps(),       "👨‍🍳  Шаги")
        self.tabs.addTab(self._make_tab_notes(),       "📝  Заметки")
        self.tabs.addTab(self._make_tab_stats(),       "📊  Статистика")
        self.tabs.addTab(self._make_tab_rating(),      "⭐  Оценить")

        rl.addWidget(self.tabs, 1)
        root.addWidget(right, 1)

    # ── AI-советник ──────────────────────────────────────────
    def _make_tip_banner(self):
        banner = QFrame()
        banner.setFixedHeight(42)
        banner.setStyleSheet(f"QFrame{{background:{self.acc}18;border-bottom:1px solid {self.acc}44;}}")
        lay = QHBoxLayout(banner)
        lay.setContentsMargins(14, 6, 14, 6)
        lay.setSpacing(8)

        icon = QLabel("🤖")
        icon.setStyleSheet("font-size:16px;background:transparent;")
        lay.addWidget(icon)

        # Выбираем совет по тегам рецепта
        tags = self.recipe.get("tags", [])
        tip_key = "default"
        for key in CHEF_TIPS:
            if any(key in str(t).lower() or key.lower() in str(t).lower() for t in tags):
                tip_key = key
                break
        tip = random.choice(CHEF_TIPS[tip_key])

        tip_lbl = QLabel(f"Совет шефа: {tip}")
        tip_lbl.setStyleSheet(f"font-size:10px;color:{self.txt};background:transparent;font-style:italic;")
        lay.addWidget(tip_lbl, 1)

        # Обновить совет
        refresh = QPushButton("🔄")
        refresh.setFixedSize(26, 26)
        refresh.setStyleSheet(f"QPushButton{{background:transparent;border:1px solid {self.acc}55;border-radius:8px;color:{self.acc};font-size:12px;}}QPushButton:hover{{background:{self.acc}22;}}")
        refresh.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        refresh.clicked.connect(lambda: tip_lbl.setText(f"Совет шефа: {random.choice(CHEF_TIPS[tip_key])}"))
        lay.addWidget(refresh)
        return banner

    # ── Вкладка ингредиентов ─────────────────────────────────
    def _make_tab_ingredients(self):
        w = QWidget(); w.setStyleSheet(f"background:{self.bg};")
        lay = QVBoxLayout(w); lay.setContentsMargins(14, 10, 14, 10); lay.setSpacing(4)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none;background:{self.bg};}}")
        sw = QWidget(); sw.setStyleSheet(f"background:{self.bg};")
        self.ing_layout = QVBoxLayout(sw)
        self.ing_layout.setContentsMargins(0, 0, 0, 0); self.ing_layout.setSpacing(4)
        self._render_ingredients()
        scroll.setWidget(sw)
        lay.addWidget(scroll)
        return w

    def _render_ingredients(self):
        while self.ing_layout.count() > 0:
            item = self.ing_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        ingredients = self.recipe.get("ingredients", [])
        base_srv = self.recipe.get("default_servings", 4) or 4
        factor = self.portions / base_srv

        for i, ing in enumerate(ingredients):
            scaled = _scale_ingredient(ing, factor)
            row = QFrame()
            row.setStyleSheet(f"QFrame{{background:{'#0d1117' if self.dark else '#f8faff'};border-radius:8px;border:1px solid {self.brd};}}")
            rl = QHBoxLayout(row); rl.setContentsMargins(10, 6, 10, 6); rl.setSpacing(10)

            num = QLabel(str(i + 1))
            num.setFixedSize(20, 20)
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num.setStyleSheet(f"background:{self.acc}33;color:{self.acc};border-radius:10px;font-size:9px;font-weight:700;")
            rl.addWidget(num)

            lbl = QLabel(scaled)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"font-size:12px;color:{self.txt};background:transparent;")
            rl.addWidget(lbl, 1)

            # Мини-калории за ингредиент
            single = calculate_nutrition([ing], 1)
            if single["calories"] > 0:
                cal_ing = QLabel(f"~{round(single['calories'] * factor)} ккал")
                cal_ing.setStyleSheet(f"font-size:8px;color:{self.gold};background:{self.gold}22;border-radius:5px;padding:2px 5px;")
                rl.addWidget(cal_ing)

            self.ing_layout.addWidget(row)

        self.ing_layout.addStretch()

    # ── Вкладка шагов ────────────────────────────────────────
    def _make_tab_steps(self):
        w = QWidget(); w.setStyleSheet(f"background:{self.bg};")
        lay = QVBoxLayout(w); lay.setContentsMargins(14, 10, 14, 10); lay.setSpacing(4)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none;background:{self.bg};}}")
        sw = QWidget(); sw.setStyleSheet(f"background:{self.bg};")
        sl = QVBoxLayout(sw); sl.setContentsMargins(0, 0, 0, 0); sl.setSpacing(8)
        self._render_steps(sl)
        scroll.setWidget(sw)
        lay.addWidget(scroll)
        return w

    def _render_steps(self, layout):
        instructions = self.recipe.get("instructions", [])
        step_timers  = self.recipe.get("step_timers", [])
        for i, step in enumerate(instructions):
            frame = QFrame()
            frame.setStyleSheet(f"QFrame{{background:{self.surf2};border-radius:12px;border:1px solid {self.brd};}}")
            fl = QVBoxLayout(frame); fl.setContentsMargins(12, 10, 12, 10); fl.setSpacing(6)
            row = QHBoxLayout(); row.setSpacing(10)
            num = QLabel(str(i + 1)); num.setFixedSize(28, 28)
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num.setStyleSheet(f"background:{self.acc};color:white;border-radius:14px;font-size:12px;font-weight:900;")
            row.addWidget(num, 0, Qt.AlignmentFlag.AlignTop)
            step_lbl = QLabel(step); step_lbl.setWordWrap(True)
            step_lbl.setStyleSheet(f"font-size:12px;color:{self.txt};background:transparent;line-height:1.5;")
            row.addWidget(step_lbl, 1)
            fl.addLayout(row)
            secs = step_timers[i] if i < len(step_timers) else 0
            if secs == 0:
                # Берём последнее число перед «час/мин» чтобы не суммировать диапазоны вида «15-20 мин»
                h_matches = re.findall(r'(\d+)\s*час', step)
                m_matches = re.findall(r'(\d+)\s*мин', step)
                if h_matches:
                    secs += int(h_matches[-1]) * 3600
                if m_matches:
                    secs += int(m_matches[-1]) * 60
            if secs > 0:
                fl.addWidget(TimerWidget(secs, f"Шаг {i+1}", self.dark))
            layout.addWidget(frame)
        layout.addStretch()

    # ── Вкладка заметок ──────────────────────────────────────
    def _make_tab_notes(self):
        w = QWidget(); w.setStyleSheet(f"background:{self.bg};")
        lay = QVBoxLayout(w); lay.setContentsMargins(14, 10, 14, 10); lay.setSpacing(8)

        lbl = QLabel("📝  Личные заметки к рецепту")
        lbl.setStyleSheet(f"font-size:12px;font-weight:700;color:{self.sub};background:transparent;")
        lay.addWidget(lbl)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Ваши наблюдения, изменения, секреты...")
        self.notes_edit.setStyleSheet(f"""QTextEdit{{
            background:{self.surf2};border:2px solid {self.brd};border-radius:12px;
            padding:10px;color:{self.txt};font-size:13px;}}
            QTextEdit:focus{{border-color:{self.acc};}}""")
        saved = db_manager.get_note(self.recipe["id"])
        if saved: self.notes_edit.setPlainText(saved)
        lay.addWidget(self.notes_edit, 1)

        save_btn = QPushButton("💾  Сохранить заметку")
        save_btn.setFixedHeight(34)
        save_btn.setStyleSheet(f"""QPushButton{{background:{self.acc};border:none;border-radius:10px;
            color:white;font-size:12px;font-weight:700;}}QPushButton:hover{{opacity:.9;}}""")
        save_btn.clicked.connect(self._save_note)
        lay.addWidget(save_btn)
        return w

    # ── Вкладка статистики ───────────────────────────────────
    def _make_tab_stats(self):
        w = QWidget(); w.setStyleSheet(f"background:{self.bg};")
        lay = QVBoxLayout(w); lay.setContentsMargins(14, 10, 14, 10); lay.setSpacing(10)

        cook_count = self.recipe.get("cook_count", 0)
        last_cooked = self.recipe.get("last_cooked", None)

        hdr = QLabel("📊  Ваша статистика по рецепту")
        hdr.setStyleSheet(f"font-size:13px;font-weight:900;color:{self.txt};background:transparent;")
        lay.addWidget(hdr)

        # Прогресс-бар к следующему достижению
        next_target = None
        for ach in ACHIEVEMENTS:
            if not ach["cond"](cook_count):
                # Найти сколько раз нужно
                for count_needed in [1, 5, 10, 25]:
                    if count_needed > cook_count:
                        next_target = count_needed
                        break
                break

        if next_target:
            prog_frame = QFrame()
            prog_frame.setStyleSheet(f"QFrame{{background:{self.surf2};border-radius:12px;border:1px solid {self.brd};}}")
            pfl = QVBoxLayout(prog_frame); pfl.setContentsMargins(14, 10, 14, 10); pfl.setSpacing(6)
            prog_lbl = QLabel(f"🎯 До следующего достижения: {cook_count}/{next_target}")
            prog_lbl.setStyleSheet(f"font-size:11px;font-weight:700;color:{self.txt};background:transparent;")
            pfl.addWidget(prog_lbl)

            # Нарисовать progress bar через QLabel + stylesheet
            progress_pct = min(100, int(cook_count / next_target * 100))
            bar_container = QFrame()
            bar_container.setFixedHeight(8)
            bar_container.setStyleSheet(f"QFrame{{background:{self.brd};border-radius:4px;}}")
            bfl = QHBoxLayout(bar_container); bfl.setContentsMargins(0, 0, 0, 0); bfl.setSpacing(0)
            fill = QFrame()
            fill.setFixedHeight(8)
            fill.setMinimumWidth(max(8, int(progress_pct * 2.2)))
            fill.setStyleSheet(f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {self.acc},stop:1 {self.acc2});border-radius:4px;}}")
            bfl.addWidget(fill); bfl.addStretch()
            pfl.addWidget(bar_container)
            lay.addWidget(prog_frame)

        # Статистика карточки
        stats = [
            ("🍳 Приготовлено раз",   str(cook_count)),
            ("⭐ Рейтинг",            f"{self.recipe.get('rating', 0):.1f} / 5.0"),
            ("⏱ Время приготовления", f"{self.recipe.get('total_time', 0)} мин"),
            ("🔥 Калорий / порция",   f"{self.recipe.get('calories_per_serving', 0)} ккал"),
            ("🥕 Ингредиентов",       str(len(self.recipe.get("ingredients", [])))),
            ("📋 Шагов",              str(len(self.recipe.get("instructions", [])))),
        ]
        if last_cooked:
            from datetime import datetime
            if isinstance(last_cooked, str):
                try: last_cooked = datetime.fromisoformat(last_cooked)
                except Exception: pass
            if hasattr(last_cooked, "strftime"):
                stats.insert(1, ("📅 Последний раз", last_cooked.strftime("%d.%m.%Y")))

        grid = QWidget(); grid.setStyleSheet("background:transparent;")
        from PyQt6.QtWidgets import QGridLayout
        gl = QGridLayout(grid); gl.setSpacing(6); gl.setContentsMargins(0, 0, 0, 0)
        for i, (label, val) in enumerate(stats):
            card = QFrame()
            card.setStyleSheet(f"QFrame{{background:{self.surf2};border-radius:8px;border:1px solid {self.brd};}}")
            cl = QHBoxLayout(card); cl.setContentsMargins(10, 8, 10, 8); cl.setSpacing(6)
            ll = QLabel(label); ll.setStyleSheet(f"font-size:10px;color:{self.sub};background:transparent;")
            vl = QLabel(val); vl.setStyleSheet(f"font-size:11px;font-weight:700;color:{self.txt};background:transparent;")
            cl.addWidget(ll); cl.addStretch(); cl.addWidget(vl)
            gl.addWidget(card, i // 2, i % 2)
        lay.addWidget(grid)
        lay.addStretch()
        return w

    # ── Вкладка оценки ───────────────────────────────────────
    def _make_tab_rating(self):
        w = QWidget(); w.setStyleSheet(f"background:{self.bg};")
        lay = QVBoxLayout(w); lay.setContentsMargins(20, 16, 20, 16); lay.setSpacing(12)

        hdr = QLabel("⭐  Оценить рецепт")
        hdr.setStyleSheet(f"font-size:14px;font-weight:900;color:{self.txt};background:transparent;")
        lay.addWidget(hdr)

        cur = QLabel(f"Текущий рейтинг: {self.recipe.get('rating', 0):.1f} ⭐  ({self.recipe.get('rating_count', 0)} оценок)")
        cur.setStyleSheet(f"font-size:11px;color:{self.sub};background:transparent;")
        lay.addWidget(cur)

        stars_frame = QFrame()
        stars_frame.setStyleSheet(f"QFrame{{background:{self.surf2};border-radius:14px;border:1px solid {self.brd};}}")
        sfl = QVBoxLayout(stars_frame); sfl.setContentsMargins(20, 16, 20, 16); sfl.setSpacing(10)

        prompt = QLabel("Нажмите на звезду чтобы поставить оценку:")
        prompt.setStyleSheet(f"font-size:11px;color:{self.sub};background:transparent;")
        sfl.addWidget(prompt)

        stars_row = QHBoxLayout(); stars_row.setSpacing(6)
        for s in range(1, 6):
            btn = QPushButton("★")
            btn.setFixedSize(44, 44)
            btn.setStyleSheet(f"""QPushButton{{background:transparent;border:none;font-size:30px;
                color:{'#374151' if self.dark else '#d1d5db'};}}
                QPushButton:hover{{color:{self.gold};}}""")
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda _, r=s: (
                self.rated.emit(self.recipe["id"], r),
                _msg(self, "Спасибо!", f"Вы поставили {r} звёзд"),
                self.accept()
            ))
            stars_row.addWidget(btn)
        stars_row.addStretch()
        sfl.addLayout(stars_row)
        lay.addWidget(stars_frame)
        lay.addStretch()
        return w

    # ── Достижения ───────────────────────────────────────────
    def _render_achievements(self, cook_count):
        while self.achiev_row.count():
            item = self.achiev_row.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        for ach in ACHIEVEMENTS:
            unlocked = ach["cond"](cook_count)
            badge = QLabel(ach["icon"])
            badge.setFixedSize(22, 22)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setToolTip(f"{ach['title']}: {ach['desc']}")
            badge.setStyleSheet(f"""font-size:13px;
                background:{'#2d4a2d' if unlocked else self.brd};
                border-radius:11px;
                opacity:{'1' if unlocked else '0.3'};""")
            if not unlocked:
                badge.setStyleSheet(f"font-size:13px;background:{self.brd};border-radius:11px;color:{'#444' if self.dark else '#ccc'};")
            self.achiev_row.addWidget(badge)
        self.achiev_row.addStretch()

    # ── Вспомогательные методы ───────────────────────────────
    def _btn_style(self, border_color, text_color):
        return f"""QPushButton{{background:transparent;border:1px solid {border_color};
            border-radius:8px;color:{text_color};font-size:14px;font-weight:900;}}
            QPushButton:hover{{background:{text_color}22;}}"""

    def _ghost_btn(self, size=10):
        return f"""QPushButton{{background:transparent;border:1px solid {self.brd};
            border-radius:8px;padding:3px 8px;color:{self.txt};font-size:{size}px;}}
            QPushButton:hover{{background:{self.acc}22;border-color:{self.acc}66;color:#ffffff;}}"""

    def _reload_image(self):
        pix = _load_pixmap(self.recipe.get("image_path", ""), 220, 160, radius=0)
        self.img_lbl.setPixmap(pix)

    def _change_portions(self, delta):
        self.portions = max(1, min(30, self.portions + delta))
        self.srv_num.setText(str(self.portions))
        self.cal_badge.update_servings(self.portions)
        self._render_ingredients()

    def _on_cooked(self):
        rid = self.recipe["id"]
        db_manager.mark_cooked(rid)
        self.cooked_signal.emit(rid)
        # Обновляем счётчик в UI
        self.recipe["cook_count"] = self.recipe.get("cook_count", 0) + 1
        cnt = self.recipe["cook_count"]
        self.cook_lbl.setText(f"🍳 Приготовлено: {cnt} раз")
        self._render_achievements(cnt)
        self.cooked_btn.setText("✅  Отмечено!")
        QTimer.singleShot(2000, lambda: self.cooked_btn.setText("🍳  Я приготовил!"))

    def _change_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать фото", "", "Изображения (*.png *.jpg *.jpeg *.webp *.bmp)")
        if path:
            self.recipe["image_path"] = path
            db_manager.update_image_path(self.recipe["id"], path)
            self._reload_image()

    def _edit_recipe(self):
        try:
            from add_recipe_dialog import AddRecipeDialog
            dlg = AddRecipeDialog(self.dark, self, recipe=self.recipe)
            if dlg.exec():
                self.edited.emit()
                self.accept()
        except Exception as e:
            _msg(self, "Ошибка", str(e), "warning")

    def _delete_recipe(self):
        qbox = QMessageBox(self)
        qbox.setWindowTitle("Удалить рецепт")
        qbox.setText(f"Удалить «{self.recipe['title']}»?\nЭто действие нельзя отменить.")
        qbox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        qbox.setDefaultButton(QMessageBox.StandardButton.No)
        qbox.setStyleSheet("""
            QMessageBox{background:#111827;color:#e2e8f8;}
            QLabel{color:#e2e8f8;font-size:12px;}
            QPushButton{background:#ef4444;color:#ffffff;border:none;
                border-radius:6px;padding:6px 20px;font-weight:700;}
            QPushButton:hover{background:#dc2626;}
        """)
        if qbox.exec() == QMessageBox.StandardButton.Yes:
            db_manager.delete_recipe(self.recipe["id"])
            self.deleted.emit(self.recipe["id"])
            self.accept()

    def _save_note(self):
        db_manager.save_note(self.recipe["id"], self.notes_edit.toPlainText())
        _msg(self, "Сохранено", "Заметка сохранена!")

    def _export_pdf(self):
        import os
        safe = "".join(c for c in self.recipe['title'] if c.isalnum() or c in " _-")
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить как PDF",
            os.path.join(os.path.expanduser("~"), "Desktop", safe + ".pdf"),
            "PDF файлы (*.pdf)")
        if not path:
            return
        try:
            self._do_export_recipe_pdf(path)
            _msg(self, "Готово", "PDF сохранён:\n" + path)
        except Exception as ex:
            import traceback
            _msg(self, "Ошибка PDF", traceback.format_exc(), "warning")

    def _do_export_recipe_pdf(self, path):
        import datetime
        r        = self.recipe
        base_srv = r.get("default_servings", 4) or 4
        factor   = self.portions / base_srv
        cal      = self.cal_badge.get_calories()
        today    = datetime.date.today().strftime("%d.%m.%Y")

        lines = []
        lines.append((r["title"],                                    20, False, (108, 99,255),  0))
        lines.append((r.get("cuisine","") + "  |  " + r.get("difficulty","") +
                       "  |  " + str(r.get("total_time",0)) + " мин  |  " +
                       str(cal) + " ккал/порция",                   10, False, (100,116,139),  0))
        lines.append((r.get("chef",""),
                                                                     10, False, (100,116,139),  0))
        lines.append(("",                                             6, False, (255,255,255),  0))
        if r.get("description"):
            lines.append((r["description"],                          11, False, ( 71, 85,105),  0))
            lines.append(("",                                         6, False, (255,255,255),  0))

        lines.append(("Ингредиенты  (" + str(self.portions) + " порц.)",
                                                                     13, True,  (108, 99,255),  0))
        lines.append(("",                                             4, False, (255,255,255),  0))
        for ing in r.get("ingredients", []):
            lines.append(("•  " + _scale_ingredient(ing, factor),   11, False, ( 30, 41, 59), 10))
        lines.append(("",                                             8, False, (255,255,255),  0))

        lines.append(("Приготовление",                               13, True,  (108, 99,255),  0))
        lines.append(("",                                             4, False, (255,255,255),  0))
        for i, step in enumerate(r.get("instructions", []), 1):
            lines.append((str(i) + ".  " + step,                    11, False, ( 30, 41, 59),  0))
            lines.append(("",                                         4, False, (255,255,255),  0))

        lines.append(("",                                             8, False, (255,255,255),  0))
        lines.append(("200 Шедевров  |  Разработчик: Шашев Андрей Сергеевич  |  " + today,
                                                                      8, False, (148,163,184),  0))
        _make_pdf(path, lines)