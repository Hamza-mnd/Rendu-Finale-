import sys
import os
import time

# Ajouter le dossier du projet au sys.path
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)


def main():
    print("=" * 60)
    print("🚀 PLATEFORME DE LIVRAISON AVEC ASSISTANT IA")
    print("=" * 60)

    # Nettoyer les fichiers de lock potentiellement corrompus
    for dir_name in ["broker_data", "offsets", "data"]:
        dir_path = os.path.join(_BASE_DIR, dir_name)
        if os.path.exists(dir_path):
            for f in os.listdir(dir_path):
                if f.endswith('.lock'):
                    try:
                        os.remove(os.path.join(dir_path, f))
                    except Exception:
                        pass

    # Charger le .env AVANT tout (depuis le dossier du projet)
    env_path = os.path.join(_BASE_DIR, ".env")
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        print(f"✓ Fichier .env chargé depuis {env_path}")
    except ImportError:
        # dotenv non installé → lire le .env manuellement
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        os.environ[key.strip()] = value.strip()
            print("✓ .env chargé manuellement (python-dotenv non installé)")

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    has_api_key = bool(api_key and api_key != "votre_cle_api_ici" and len(api_key) > 10)

    if has_api_key:
        print(f"✓ Clé API Groq détectée : {api_key[:12]}...")
    else:
        print("⚠️  Aucune clé API Groq valide trouvée dans .env")

    from platform_app import DeliveryPlatform
    platform = DeliveryPlatform(num_partitions=4)

    try:
        platform.start()
        time.sleep(2)

        # Lancer l'interface graphique (avec ou sans IA)
        print("\n🖥️  Lancement de l'interface graphique...")
        try:
            from gui.app_window import DeliveryPlatformApp
            app = DeliveryPlatformApp(platform)

            def on_closing():
                platform.stop()
                app.destroy()

            app.protocol("WM_DELETE_WINDOW", on_closing)
            app.mainloop()

        except ImportError as e:
            print(f"⚠️  Module GUI manquant : {e}")
            print("📟 Passage en mode console...")
            platform.interactive_mode()
        except Exception as e:
            print(f"⚠️  Erreur interface graphique : {e}")
            import traceback
            traceback.print_exc()
            print("📟 Passage en mode console...")
            platform.interactive_mode()

    except KeyboardInterrupt:
        print("\n\n⚠️  Interruption reçue...")
    except Exception as e:
        print(f"\n❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
    finally:
        platform.stop()
        print("\n👋 Au revoir!")


if __name__ == "__main__":
    main()
