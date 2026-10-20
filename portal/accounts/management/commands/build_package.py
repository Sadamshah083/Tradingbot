"""Build dist/axealgo_package.zip - the download customers receive after buying the bot ($20 package).

    python manage.py build_package
Includes: strategies, webhook bot, research toolkit, data, READMEs. Excludes secrets, logs, venvs, databases.
"""
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

EXCLUDE_DIRS = {".venv", "node_modules", "logs", "__pycache__", "tools", "dist", "staticfiles", ".git"}
EXCLUDE_FILES = {".env", ".secret_key", "db.sqlite3", "package-lock.json"}
# Customers get the tools they run themselves (MT5 bridge for Exness) and the historical data, not the strategy source:
# the strategy is delivered as an invite-only TradingView script and the bot runs on our server.
INCLUDE_TOP = ["webhook_bot/mt5_bridge/README.md"]
INCLUDE_DIRS = ["webhook_bot/mt5_bridge", "data"]


class Command(BaseCommand):
    help = "Zip the sellable package (strategies, bot, research, data) into dist/axealgo_package.zip"

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR).parent
        out = Path(settings.PACKAGE_ZIP)
        out.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in INCLUDE_TOP:
                p = root / name
                if p.exists():
                    zf.write(p, f"sambot/{Path(name).name}")
                    count += 1
            for d in INCLUDE_DIRS:
                base = root / d
                if not base.exists():
                    continue
                for p in base.rglob("*"):
                    rel = p.relative_to(root)
                    if p.is_dir() or any(part in EXCLUDE_DIRS for part in rel.parts) or p.name in EXCLUDE_FILES or p.suffix in (".pyc", ".log", ".pid"):
                        continue
                    zf.write(p, "sambot/" + rel.as_posix().replace("webhook_bot/", ""))
                    count += 1
        self.stdout.write(self.style.SUCCESS(f"built {out} with {count} files ({out.stat().st_size / 1e6:.1f} MB)"))
