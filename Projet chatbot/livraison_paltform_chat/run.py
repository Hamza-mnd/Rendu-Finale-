import os
import sys

# Ajouter le répertoire courant au PATH Python
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

# Lancer l'application
from main import main

if __name__ == "__main__":
    main()