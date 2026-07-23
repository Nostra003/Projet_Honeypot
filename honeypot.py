import socket
import threading
import paramiko
import logging
import json
import os
import google.genai as genai
from collections import defaultdict
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
LOG_LOCK = threading.Lock()

# Limite le nombre de connexions simultanées pour éviter l'épuisement de ressources
MAX_CONNECTIONS = 50
connection_semaphore = threading.BoundedSemaphore(MAX_CONNECTIONS)

def log_event(event_type, ip, user, command, response_len):
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type,
        "src_ip": ip,
        "user": user,
        "command": command,
        "response_len": response_len
    }
    with LOG_LOCK:
        with open(LOG_FILE, 'a') as f:
            f.write(json.dumps(entry) + "\n")
    print(f"[+] {event_type} | {ip} | {user} | {command}")

# --- STATIC RESPONSES (économie de quota API) ---
# Ces commandes sont extrêmement fréquentes chez les attaquants (recon de base) et leur
# sortie ne dépend pas de l'historique de session : autant les servir sans appeler l'IA.
STATIC_LS_OUTPUT = "Desktop  Documents  Downloads  Music  Pictures  Public  Templates  Videos  config.yml  notes.txt"
STATIC_UNAME_A = "Linux ubuntu 5.15.0-91-generic #101-Ubuntu SMP PREEMPT_DYNAMIC x86_64 x86_64 x86_64 GNU/Linux"

def static_response(command, current_path, user, fs_state=None):
    """Renvoie une réponse toute faite pour les commandes de reconnaissance basiques,
    ou None si la commande doit être traitée par l'IA."""
    parts = command.split()
    if not parts:
        return None
    base = parts[0]
    user = user or "user"

    if base == "pwd" and len(parts) == 1:
        return current_path + "\r\n"
    if base == "whoami" and len(parts) == 1:
        return user + "\r\n"
    if base == "hostname" and len(parts) == 1:
        return "ubuntu\r\n"
    if base == "id" and len(parts) == 1:
        uid = 0 if user == "root" else 1000
        return f"uid={uid}({user}) gid={uid}({user}) groups={uid}({user})\r\n"
    if base == "uname":
        if len(parts) == 1:
            return "Linux\r\n"
        if "-a" in parts:
            return STATIC_UNAME_A + "\r\n"
    if base == "ls" and len(parts) == 1:
        state = fs_state[current_path] if fs_state is not None else {"added": set(), "removed": set()}
        files = [f for f in STATIC_LS_OUTPUT.split() if f not in state["removed"]]
        files.extend(sorted(state["added"]))
        return "  ".join(files) + "\r\n"
    return None

# --- ÉTAT DE FICHIERS PAR SESSION (cohérence mkdir/touch/rm) ---
# Un fichier créé/supprimé par l'attaquant doit rester visible/absent pour le reste
# de sa session, sans dépendre de la mémoire de l'IA. Suivi en mémoire, par dossier.
def new_fs_state():
    return defaultdict(lambda: {"added": set(), "removed": set()})

def apply_fs_command(command, current_path, fs_state):
    """Gère localement mkdir/touch/rm/rmdir pour que 'ls' et l'IA restent cohérents
    avec les fichiers créés/supprimés durant la session. Retourne la sortie (souvent
    vide) si la commande est prise en charge ici, ou None sinon."""
    parts = command.split()
    if not parts:
        return None
    base = parts[0]
    names = [p for p in parts[1:] if not p.startswith("-")]
    if not names:
        return None

    state = fs_state[current_path]
    if base in ("mkdir", "touch"):
        for name in names:
            state["added"].add(name)
            state["removed"].discard(name)
        return ""
    if base in ("rm", "rmdir"):
        for name in names:
            state["removed"].add(name)
            state["added"].discard(name)
        return ""
    return None

# --- AI LOGIC ---
def ask_ai_terminal(command, current_path, user, fs_state=None):
    if not client:
        return "bash: command not found (AI Error)\r\n"

    context_note = ""
    if fs_state is not None and current_path in fs_state:
        state = fs_state[current_path]
        if state["added"] or state["removed"]:
            added = ", ".join(sorted(state["added"])) or "aucun"
            removed = ", ".join(sorted(state["removed"])) or "aucun"
            context_note = (
                f"\n    Contexte de session pour ce dossier : fichiers créés depuis le début "
                f"de la session : {added}. Fichiers supprimés depuis le début de la session : "
                f"{removed}. Reste cohérent avec cet historique dans ta réponse."
            )

    prompt = f"""
    Agis comme un terminal Linux Ubuntu standard.
    L'utilisateur '{user}' est dans le dossier '{current_path}'.
    Il tape la commande : '{command}'.
    Donne MOI UNIQUEMENT la sortie de cette commande. Pas de blabla, pas de markdown.
    Si la commande est 'ls', invente des fichiers réalistes.{context_note}
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

# --- LECTURE DE COMMANDE ---
def read_next_command(chan, buffer):
    """Lit la prochaine commande complète (terminée par '\\r') envoyée sur le canal.
    `buffer` contient les octets déjà reçus mais pas encore consommés : si le client
    a tapé plusieurs commandes pendant qu'on traitait la précédente (ex: un appel IA
    qui prend plusieurs secondes), elles restent en file au lieu d'être concaténées
    en une seule commande illisible. Retourne (commande, disconnected, buffer_restant)."""
    while "\r" not in buffer:
        data = chan.recv(1024)
        if not data:
            return None, True, buffer
        chan.send(data)
        buffer += data.decode("utf-8", errors="ignore")
        if len(buffer) > 4096:
            return None, True, buffer
    command, buffer = buffer.split("\r", 1)
    return command, False, buffer

# --- CONNECTION HANDLER ---
def handle_connection(client, addr):
    client_ip = addr[0]
    log_event("connection_new", client_ip, "unknown", "", 0)
    chan = None
    transport = None
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
        fs_state = new_fs_state()
        input_buffer = ""

        while True:
            chan.send(f"{server.username}@ubuntu:{current_path}$ ")
            command, disconnected, input_buffer = read_next_command(chan, input_buffer)

            if disconnected: break

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
                output = apply_fs_command(command, current_path, fs_state)
                if output is None:
                    output = static_response(command, current_path, server.username, fs_state)
                if output is None:
                    output = ask_ai_terminal(command, current_path, server.username, fs_state)
                chan.send("\r\n" + output)
                log_event("command", client_ip, server.username, command, len(output))
    except Exception:
        logging.exception(f"[!] Erreur de connexion avec {client_ip}")
    finally:
        if chan is not None:
            try: chan.close()
            except Exception: pass
        if transport is not None:
            try: transport.close()
            except Exception: pass
        connection_semaphore.release()

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
            if not connection_semaphore.acquire(blocking=False):
                log_event("connection_rejected", addr[0], "unknown", "max_connections_reached", 0)
                conn.close()
                continue
            threading.Thread(target=handle_connection, args=(conn, addr), daemon=True).start()
    except Exception as e:
        print(f"[!] Erreur du serveur: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    main()