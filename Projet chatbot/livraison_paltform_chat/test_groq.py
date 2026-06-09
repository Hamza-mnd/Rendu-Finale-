"""Test complet de la connexion à Groq API."""

import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

print("=" * 50)
print("🔍 TEST COMPLET GROQ API")
print("=" * 50)

try:
    import openai
    
    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )
    
    print("✓ Client OpenAI initialisé")
    
    # Test simple
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "user", "content": "Dis simplement 'OK'"}
        ],
        max_tokens=10
    )
    
    print(f"✓ Réponse reçue: {response.choices[0].message.content}")
    print("\n✅ Connexion à Groq API réussie !")
    
except Exception as e:
    print(f"❌ Erreur: {e}")
    import traceback
    traceback.print_exc()