# -*- coding: utf-8 -*-
"""
Generates CookBook2026.spec for PyInstaller.
Run AFTER PyArmor obfuscation: python make_spec.py

KEY RULE: all app .py files must come from dist_pyarmor/
          NOT from the original source folders.
"""
import os, sys, subprocess

ROOT   = os.path.dirname(os.path.abspath(__file__))
OBFUSC = os.path.join(ROOT, 'dist_pyarmor')

def find_package(name):
    try:
        mod = __import__(name)
        path = os.path.dirname(mod.__file__)
        if os.path.isdir(path): return path
    except ImportError:
        pass
    try:
        out = subprocess.check_output(
            [sys.executable, '-m', 'pip', 'show', name],
            text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            if line.startswith('Location:'):
                path = os.path.join(line.split(':',1)[1].strip(), name)
                if os.path.isdir(path): return path
    except Exception:
        pass
    return None

sq_path = find_package('sqlalchemy')
gr_path = find_package('greenlet')

print(f'[*] sqlalchemy     : {sq_path}')
print(f'[*] greenlet       : {gr_path}')

if not sq_path:
    print('[ERROR] sqlalchemy not found!')
    sys.exit(1)
if not os.path.isdir(OBFUSC):
    print('[ERROR] dist_pyarmor not found! Run PyArmor BCC first.')
    sys.exit(1)

# -- Verify obfuscated files exist (not originals) -----------------
obf_main = os.path.join(OBFUSC, 'main.py')

# PyArmor preserves folder structure when passing folder as package.
# Find whichever layout was created.
def find_obf_pkg(name):
    direct = os.path.join(OBFUSC, name)
    if os.path.isdir(direct):
        return direct
    nested = os.path.join(OBFUSC, name, name)
    if os.path.isdir(nested):
        return nested
    return None

obf_database = find_obf_pkg('database')
obf_gui      = find_obf_pkg('gui')

print(f'[*] obf main.py    : {os.path.isfile(obf_main)}')
print(f'[*] obf database/  : {obf_database}')
print(f'[*] obf gui/       : {obf_gui}')

if not os.path.isfile(obf_main):
    print('[ERROR] dist_pyarmor/main.py not found!')
    sys.exit(1)
if not obf_database:
    print('[ERROR] Obfuscated database/ not found in dist_pyarmor!')
    print('        Ensure database/__init__.py exists before running PyArmor.')
    sys.exit(1)
if not obf_gui:
    print('[ERROR] Obfuscated gui/ not found in dist_pyarmor!')
    print('        Ensure gui/__init__.py exists before running PyArmor.')
    sys.exit(1)

# -- Find pyarmor_runtime ------------------------------------------
runtime_dir  = None
runtime_name = 'pyarmor_runtime_000000'
for entry in os.listdir(OBFUSC):
    if entry.startswith('pyarmor_runtime'):
        runtime_dir  = os.path.join(OBFUSC, entry)
        runtime_name = entry
        break
print(f'[*] pyarmor_runtime: {runtime_dir}')

if not runtime_dir:
    print('[ERROR] pyarmor_runtime not found in dist_pyarmor!')
    print('        PyArmor must have failed. Re-run BCC obfuscation.')
    sys.exit(1)

# -- Font to bundle ------------------------------------------------
arial_path = None
for candidate in [
    r'C:\Windows\Fonts\arial.ttf',
    r'C:\Windows\Fonts\calibri.ttf',
    r'C:\Windows\Fonts\verdana.ttf',
]:
    if os.path.isfile(candidate):
        arial_path = candidate
        break
print(f'[*] font           : {arial_path}')

# -- Collect all sqlalchemy submodules -----------------------------
hidden = []
site_pkg = os.path.dirname(sq_path)
for root, dirs, files in os.walk(sq_path):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    rel = os.path.relpath(root, site_pkg)
    mod = rel.replace(os.sep, '.')
    hidden.append(mod)
    for f in files:
        if f.endswith('.py') and f != '__init__.py':
            hidden.append(f'{mod}.{f[:-3]}')

hidden += [
    'sqlalchemy', 'sqlalchemy.orm', 'sqlalchemy.orm.decl_api',
    'sqlalchemy.orm.relationships', 'sqlalchemy.orm.mapper',
    'sqlalchemy.orm.session', 'sqlalchemy.orm.attributes',
    'sqlalchemy.ext.declarative',
    'sqlalchemy.dialects', 'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.sqlite.pysqlite',
    'sqlalchemy.sql', 'sqlalchemy.sql.default_comparator',
    'sqlalchemy.sql.visitors', 'sqlalchemy.sql.elements',
    'sqlalchemy.sql.sqltypes', 'sqlalchemy.sql.expression',
    'sqlalchemy.pool', 'sqlalchemy.pool.impl',
    'sqlalchemy.engine', 'sqlalchemy.engine.default',
    'sqlalchemy.engine.reflection',
    'sqlalchemy.event', 'sqlalchemy.event.legacy',
    'greenlet',
    'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui',
    'PyQt6.QtPrintSupport', 'PyQt6.sip',
    'models', 'db_manager', 'calories',
    'main_window', 'add_recipe_dialog', 'cuisines',
]
hidden = list(set(hidden))
print(f'[*] hidden imports : {len(hidden)}')

# -- Path helper ---------------------------------------------------
def p(path): return path.replace('\\', '/') if path else ''

# ALL app paths from dist_pyarmor - obfuscated versions
obfusc_p     = p(OBFUSC)
obf_main_p   = p(obf_main)
obf_db_p     = p(obf_database)     # dist_pyarmor/database/  <- obfuscated
obf_gui_p    = p(obf_gui)          # dist_pyarmor/gui/       <- obfuscated
rt_p         = p(runtime_dir)

# Non-code assets from original project (these are NOT obfuscated, that's correct)
assets_path  = p(os.path.join(ROOT, 'assets'))
icon_path    = p(os.path.join(ROOT, 'icon.ico'))
hook_path    = p(os.path.join(ROOT, 'hook_runtime.py'))
arial_p      = p(arial_path) if arial_path else ''
sq_p         = p(sq_path)
gr_p         = p(gr_path) if gr_path else ''

# -- Build datas ---------------------------------------------------
datas_lines = [
    # SQLAlchemy + greenlet
    f"(r'{sq_p}', 'sqlalchemy'),",
]
if gr_p:
    datas_lines.append(f"(r'{gr_p}', 'greenlet'),")

# pyarmor_runtime - required for obfuscated code to run
datas_lines.append(f"(r'{rt_p}', '{runtime_name}'),")

# Font bundled inside exe
if arial_p:
    datas_lines.append(f"(r'{arial_p}', '.'),")

# Icon
datas_lines.append(f"(r'{icon_path}', '.'),")

# Assets (images) - originals, no obfuscation needed
datas_lines.append(f"(r'{assets_path}', 'assets'),")

# App code - OBFUSCATED versions from dist_pyarmor/
# These override any originals that pathex might find
datas_lines.append(f"(r'{obf_db_p}', 'database'),")
datas_lines.append(f"(r'{obf_gui_p}', 'gui'),")

datas_str = '\n        '.join(datas_lines)

spec_content = f"""\
# -*- mode: python ; coding: utf-8 -*-
# Generated by make_spec.py
# IMPORTANT: app .py files sourced from dist_pyarmor/ (obfuscated)
block_cipher = None

a = Analysis(
    [r'{obf_main_p}'],
    pathex=[r'{obfusc_p}'],
    binaries=[],
    datas=[
        {datas_str}
    ],
    hiddenimports={hidden!r},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[r'{hook_path}'],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CookBook2026',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r'{icon_path}',
)
"""

out = os.path.join(ROOT, 'CookBook2026.spec')
with open(out, 'w', encoding='utf-8') as f:
    f.write(spec_content)

print(f'[OK] CookBook2026.spec written')
print(f'')
print(f'[!!] Verify these paths in spec use dist_pyarmor/:')
print(f'     main    : {obf_main_p}')
print(f'     database: {obf_db_p}')
print(f'     gui     : {obf_gui_p}')
