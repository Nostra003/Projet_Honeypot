#!/usr/bin/env python3
import google.generativeai as genai
import os

# Charger la clé API depuis .env
api_key = os.getenv('GOOGLE_API_KEY', '').strip()

if not api_key:
    print("[!] ERREUR: GOOGLE_API_KEY non trouvée!")
    print("Mettez à jour votre fichier .env")
    exit(1)

print(f"[*] Clé API détectée: {api_key[:20]}...")

try:
    genai.configure(api_key=api_key)
    print("[✓] Connexion API réussie!")
    
    # Lister les modèles disponibles
    print("\n[*] Modèles disponibles:")
    for model in genai.list_models():
        if 'generateContent' in model.supported_generation_methods:
            print(f"  - {model.name}")
    
    # Tester avec le premier modèle
    print("\n[*] Test d'une requête simple...")
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content("Dis bonjour")
    print(f"[✓] Réponse: {response.text[:100]}")
    
except Exception as e:
    print(f"[!] ERREUR: {e}")
    print("\nVérifiez que:")
    print("1. Votre .env contient GOOGLE_API_KEY=......")
    print("2. La clé vient de Google AI Studio (https://makersuite.google.com)")
    print("3. Elle est valide et activée")
