"""Sesli kitap üretim sisteminin giriş noktası. Ayrıntı: araclar/sesli/MIMARI.md

  .venv-ses/bin/python araclar/sesli_kitap.py --help
  caffeinate -is .venv-ses/bin/python -u araclar/sesli_kitap.py oku >> .tmp/fola-sirayla.log 2>&1
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sesli.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
