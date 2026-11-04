#!/usr/bin/env python3
"""Compatibilidade: sitemap só pode ser gerado a partir do catalogo.json V4."""
import subprocess, sys
from pathlib import Path
if __name__ == '__main__':
    sys.exit(subprocess.run([sys.executable,str(Path(__file__).with_name('make-sitemap.py'))]).returncode)
