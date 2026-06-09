# run.py — Point d'entrée VS Code
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from main import main
main()
