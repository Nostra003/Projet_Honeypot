import socket
import threading
import paramiko
import logging
import json
import os
import google.genai as genai
from datetime import datetime

# --- CONFIGURATION ---
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')
HOST_KEY_FILE = 'host.key'
LOG_FILE = 'logs/access.json'

# Configuration de l'IA avec Gemini 2.5 Flash (meilleur modèle disponible)
if not GOOGLE_API_KEY:
    print("[!] ERREUR: Variable d'environnement GOOGLE_API_KEY non définie!")
    client = None
else:
    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
        MODEL_NAME = 'gemini-2.5-flash'
        print(f"[*] IA connectée avec succès (Modèle: {MODEL_NAME}).")
    except Exception as e:
        client = None
        print(f"[!] Erreur de configuration IA : {e}")

# Configuration des Logs
logging.basicConfig(level=logging.INFO)

def log_event(event_type, ip, user, command, response_len):
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type,
        "src_ip": ip,
        "user": user,
        "command": command,
        "response_len": response_len
    }
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[+] {event_type} | {ip} | {user} | {command}")

# --- AI LOGIC ---
def ask_ai_terminal(command, current_path, user):
    if not client:
        return "bash: command not found (AI Error)\r\n"
    
    prompt = f"""
    Agis comme un terminal Linux Ubuntu standard.
    L'utilisateur '{user}' est dans le dossier '{current_path}'.
    Il tape la commande : '{command}'.
    Donne MOI UNIQUEMENT la sortie de cette commande. Pas de blabla, pas de markdown.
    Si la commande est 'ls', invente des fichiers réalistes.
    """
    try:
        # Appel API avec la nouvelle SDK google.genai
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        
        if not response or not response.text:
            return "bash: no output from terminal\r\n"

        # Nettoyage et formatage pour SSH
        clean_text = response.text.strip().replace('```', '').replace('`', '')
        return clean_text.replace('\n', '\r\n') + "\r\n"
    except Exception as e:
        return f"bash: error processing command (API Error): {str(e)}\r\n"

# --- SSH SERVER INTERFACE ---
class ChameleonServer(paramiko.ServerInterface):
    def __init__(self, client_ip):
        self.event = threading.Event()
        self.client_ip = client_ip
        self.username = None

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED if kind == 'session' else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username, password):
        self.username = username
        log_event("login_success", self.client_ip, username, f"PWD:{password}", 0)
        return paramiko.AUTH_SUCCESSFUL

    def get_allowed_auths(self, username):
        return 'password'

    def check_channel_pty_request(self, channel, term, width, height, pwidth, pheight, modes):
        return True

    def check_channel_shell_request(self, channel):
        self.event.set()
        return True

# --- CONNECTION HANDLER ---
def handle_connection(client, addr):
    client_ip = addr[0]
    log_event("connection_new", client_ip, "unknown", "", 0)
    try:
        transport = paramiko.Transport(client)
        transport.add_server_key(paramiko.RSAKey(filename=HOST_KEY_FILE))
        server = ChameleonServer(client_ip)
        transport.start_server(server=server)

        chan = transport.accept(20)
        if chan is None: return
        server.event.wait(10)

        chan.send("Welcome to Ubuntu 22.04.3 LTS (GNU/Linux 5.15.0-91-generic x86_64)\r\n\r\n")
        current_path = f"/home/{server.username or 'user'}"

        while True:
            chan.send(f"{server.username}@ubuntu:{current_path}$ ")
            command = ""
            while not command.endswith("\r"):
                data = chan.recv(1024)
                if not data: break
                chan.send(data) 
                command += data.decode("utf-8", errors="ignore")
            
            command = command.strip()
            if command == "exit": break
            if not command: 
                chan.send("\r\n")
                continue
            
            if command.startswith("cd "):
                parts = command.split(" ")
                if len(parts) > 1: current_path = parts[1]
                chan.send("\r\n")
                log_event("command", client_ip, server.username, command, 0)
            else:
                output = ask_ai_terminal(command, current_path, server.username)
                chan.send("\r\n" + output)
                log_event("command", client_ip, server.username, command, len(output))
        chan.close()
    except: pass

def main():
    # Créer les répertoires nécessaires
    if not os.path.exists(HOST_KEY_FILE):
        paramiko.RSAKey.generate(2048).write_private_key_file(HOST_KEY_FILE)
    os.makedirs(os.path.dirname(LOG_FILE) or 'logs', exist_ok=True)
    
    # Vérifier la configuration IA
    if not client:
        print("[!] ATTENTION: L'IA n'est pas disponible. Vérifiez votre clé API.")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(('0.0.0.0', 2222))
        sock.listen(100)
        print("[*] Chameleon Honeypot listening on port 2222...")
        while True:
            conn, addr = sock.accept()
            threading.Thread(target=handle_connection, args=(conn, addr)).start()
    except Exception as e:
        print(f"[!] Erreur du serveur: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    main()