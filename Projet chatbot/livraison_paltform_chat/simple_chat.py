"""Version simple avec interface console pour le chatbot (Windows compatible)."""

import os
from dotenv import load_dotenv
import openai

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print("❌ Clé API non trouvée dans .env")
    print("   Vérifiez que le fichier .env contient: GROQ_API_KEY=votre_cle")
    exit(1)

print(f"✓ Clé API chargée: {api_key[:10]}...")

try:
    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )
    print("✓ Client Groq initialisé")
except Exception as e:
    print(f"❌ Erreur initialisation client: {e}")
    exit(1)

print("=" * 60)
print("🤖 ASSISTANT LIVRAISON - Mode Console")
print("=" * 60)

# Liste des modèles actifs Groq (mis à jour)
MODELS = [
    "llama-3.3-70b-versatile",  # Le plus puissant
    "llama-3.1-8b-instant",     # Rapide et bon
    "mixtral-8x7b-32768",       # Bon contexte
    "gemma2-9b-it",             # Alternative
]

print(f"📌 Modèle utilisé: {MODELS[0]}")
print("\nPosez vos questions sur les commandes !")
print("Exemples:")
print("  • Statistiques globales")
print("  • Statut de la commande ORD-20250604-0001")
print("  • Performance du livreur CRR-01")
print("\nTapez 'quit' ou 'q' pour quitter")
print("-" * 60)

# Contexte système
system_prompt = {
    "role": "system",
    "content": """Tu es un assistant pour une plateforme de livraison.
    Tu réponds aux questions sur:
    - Les commandes (statut, livraison)
    - Les livreurs (performance, taux de succès)
    - Les statistiques globales (commandes créées, livrées, échouées)
    - L'activité par ville
    
    Sois concis et utile. Si tu ne sais pas, dis-le honnêtement."""
}

history = [system_prompt]

while True:
    try:
        user_input = input("\n👤 Vous: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Au revoir!")
            break
        
        if not user_input:
            continue
        
        history.append({"role": "user", "content": user_input})
        
        print("🤖 Assistant: ", end="", flush=True)
        
        try:
            response = client.chat.completions.create(
                model=MODELS[0],  # Utilise le modèle valide
                messages=history,
                max_tokens=500,
                temperature=0.7
            )
            
            reply = response.choices[0].message.content
            print(reply)
            history.append({"role": "assistant", "content": reply})
            
        except Exception as e:
            print(f"\n❌ Erreur API: {e}")
            # En cas d'erreur, réinitialiser l'historique
            history = [system_prompt]
            
    except KeyboardInterrupt:
        print("\n\n👋 Au revoir!")
        break
    except EOFError:
        break