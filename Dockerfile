FROM python:3.11-slim

WORKDIR /app

#Installation des bibliothèques à jour sans caractères d'échappement inutiles

RUN pip install --no-cache-dir paramiko google-genai

COPY honeypot.py .

RUN mkdir -p /app/logs

#Utilisation de Python 3.11 en mode sans tampon (unbuffered) pour les logs

CMD ["python", "-u", "honeypot.py"]