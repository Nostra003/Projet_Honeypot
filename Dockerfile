FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY honeypot.py .

RUN mkdir -p /app/logs

#Utilisation de Python 3.11 en mode sans tampon (unbuffered) pour les logs

CMD ["python", "-u", "honeypot.py"]