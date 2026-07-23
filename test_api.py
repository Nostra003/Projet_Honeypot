#!/usr/bin/env python3
import google.genai as genai
import os

# Charger la clé API depuis .env
api_key = os.getenv('GOOGLE_API_KEY', '').strip()

if not api_key:
    print("[!] ERREUR: GOOGLE_API_KEY non trouvée!")
    print("Mettez à jour votre fichier .env")
    exit(1)

print(f"[*] Clé API détectée: {api_key[:20]}...")

try:
    client = genai.Client(api_key=api_key)
    print("[OK] Client API initialisé!")

    # Lister les modèles disponibles
    print("\n[*] Modèles disponibles:")
    for model in client.models.list():
        if 'generateContent' in (model.supported_actions or []):
            print(f"  - {model.name}")

    # Tester avec le modèle utilisé par le honeypot
    print("\n[*] Test d'une requête simple...")
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents="Dis bonjour"
    )
    print(f"[OK] Réponse: {response.text[:100]}")

except Exception as e:
    print(f"[!] ERREUR: {e}")
    print("\nVérifiez que:")
    print("1. Votre .env contient GOOGLE_API_KEY=......")
    print("2. La clé vient de Google AI Studio (https://makersuite.google.com)")
    print("3. Elle est valide et activée")
