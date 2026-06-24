# Runtime hook - executed by PyInstaller before any app code
# Fixes sys.path so all modules are importable from _MEIPASS
import sys, os

base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

for sub in ('', 'database', 'gui', 'PyQt6', 'sqlalchemy'):
    p = os.path.join(base, sub)
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

# Also add base itself first
if base not in sys.path:
    sys.path.insert(0, base)
