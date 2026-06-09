"""Chatbot utilisant Groq API."""

import openai

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Modèle actif recommandé par Groq
DEFAULT_MODEL = "llama-3.3-70b-versatile"  # ou "llama-3.1-8b-instant"


class ChatBot:
    """Chatbot avec historique de conversation."""
    
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=GROQ_BASE_URL
        )
        self.model = model
        
        self.chat_history = [
            {
                "role": "system",
                "content": (
                    "Tu es un assistant intelligent pour une plateforme de livraison de commandes. "
                    "Tu aides les utilisateurs à suivre leurs commandes, vérifier les statuts, "
                    "et comprendre les performances de livraison. "
                    "Réponds de manière claire, précise et utile. "
                    "Utilise les données fournies par le système pour répondre aux questions "
                    "sur les commandes, les livreurs, et les statistiques. "
                    "Si tu ne connais pas une information, dis-le honnêtement."
                )
            }
        ]
    
    def send_message(self, user_text: str, context: dict = None) -> str:
        """Envoie un message à l'IA et retourne la réponse."""
        messages = self.chat_history.copy()
        
        if context:
            context_msg = {
                "role": "system",
                "content": f"Voici les données actuelles du système:\n{context}"
            }
            messages.insert(1, context_msg)
        
        messages.append({
            "role": "user",
            "content": user_text
        })
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1000,
                temperature=0.7,
            )
            
            ai_reply = response.choices[0].message.content
            
            self.chat_history.append({"role": "user", "content": user_text})
            self.chat_history.append({"role": "assistant", "content": ai_reply})
            
            return ai_reply
            
        except openai.AuthenticationError:
            return "❌ Erreur: Clé API Groq invalide. Vérifie ton fichier .env"
        except openai.RateLimitError:
            return "⚠️ Erreur: Limite de taux atteinte. Attends quelques secondes."
        except openai.APIConnectionError:
            return "🌐 Erreur: Impossible de se connecter à Groq. Vérifie ta connexion."
        except Exception as e:
            return f"❌ Erreur inattendue: {e}"
    
    def clear_history(self):
        """Réinitialise l'historique de conversation."""
        self.chat_history = [self.chat_history[0]]
    
    def get_history(self) -> list:
        """Retourne l'historique de conversation."""
        return self.chat_history[1:]