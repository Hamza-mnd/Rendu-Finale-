"""Test de la connexion à Groq API."""

import os
from dotenv import load_dotenv

# Charger le fichier .env
load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

print("=" * 50)
print("🔍 TEST DE CONNEXION GROQ API")
print("=" * 50)

if not api_key:
    print("❌ Aucune clé API trouvée dans .env")
    print("   Vérifiez que le fichier .env existe et contient:")
    print("   GROQ_API_KEY=gsk_votre_cle_ici")
else:
    print(f"✓ Clé API trouvée: {api_key[:10]}...{api_key[-5:]}")
    
    # Tester la connexion
    try:
        import openai
        
        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": "Dis 'OK'"}],
            max_tokens=10
        )
        
        print("✓ Connexion à Groq API réussie !")
        print(f"  Réponse: {response.choices[0].message.content}")
        
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")