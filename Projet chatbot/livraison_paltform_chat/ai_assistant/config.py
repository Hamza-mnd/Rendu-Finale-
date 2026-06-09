import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def load_api_key() -> str | None:
    """Charge la clé API Groq depuis l'environnement."""
    key = os.getenv("GROQ_API_KEY", "").strip()

    if not key or key == "votre_cle_api_ici":
        print(
            "❌ GROQ_API_KEY non trouvée ou non configurée!\n"
            "   1. Allez sur https://console.groq.com et créez un compte (gratuit)\n"
            "   2. Créez une clé API\n"
            "   3. Ajoutez-la dans votre fichier .env:\n"
            "      GROQ_API_KEY=gsk_votre_cle_ici"
        )
        return None

    return key