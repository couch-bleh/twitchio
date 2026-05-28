import socket
import time
import random
import threading
import http.server
import socketserver
import json
import urllib.request
import os

# ========================================================
# CONFIGURACIÓN DESDE LAS VARIABLES DE ENTORNO DE RENDER
# ========================================================
CANAL = os.environ.get("TWITCH_CANAL", "#spreen")
USUARIO = os.environ.get("TWITCH_USER")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")

# ID de cliente público oficial para autenticación (No es secreto)
CLIENT_ID = "kd1unb4b3q4t581w3w8409as30b96q" 
TOKEN_FILE = "twitch_tokens.json"

mensajes_enviados = 0
bloqueo_contador = threading.Lock()

def enviar_a_discord(mensaje_texto):
    if not DISCORD_WEBHOOK_URL or "http" not in DISCORD_WEBHOOK_URL: 
        return
    payload = json.dumps({"content": mensaje_texto}).encode('utf-8')
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL, 
        data=payload, 
        headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
    )
    try:
        with urllib.request.urlopen(req) as r: pass
    except Exception as e:
        print(f"[Discord Error] No se pudo enviar el webhook: {e}")

# --- Sistema de Autenticación de TV Seguro ---
def obtener_token_tv():
    # Si ya existe un token guardado en esta sesión, lo usamos
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                datos = json.load(f)
                return datos.get("access_token")
        except: pass

    # Si no hay token, le pedimos un código de vinculación limpio a Twitch
    print("[TV Método] Solicitando código de vinculación a Twitch...")
    url_code = "https://id.twitch.tv/oauth2/device"
    data_code = f"client_id={CLIENT_ID}&scopes=chat:edit%20chat:read".encode('utf-8')
    
    req = urllib.request.Request(url_code, data=data_code, method="POST")
    with urllib.request.urlopen(req) as r:
        res = json.loads(r.read().decode('utf-8'))
    
    device_code = res["device_code"]
    user_code = res["user_code"]
    verification_url = res["verification_url"]
    interval = res["interval"]

    # Alerta en Discord para que vincules tu cuenta sin usar contraseñas
    aviso = f"🔑 **VINCULACIÓN REQUERIDA:**\n1. Entra a: {verification_url}\n2. Pon este código en tu celular: **{user_code}**"
    print(f"\n{aviso}\n")
    enviar_a_discord(aviso)

    # El bot se queda esperando pacientemente a que pongas el código
    url_token = "https://id.twitch.tv/oauth2/token"
    data_token = f"client_id={CLIENT_ID}&device_code={device_code}&grant_type=urn:ietf:params:oauth:grant-type:device_code".encode('utf-8')
    
    while True:
        time.sleep(interval)
        try:
            req_t = urllib.request.Request(url_token, data=data_token, method="POST")
            with urllib.request.urlopen(req_t) as r_t:
                res_t = json.loads(r_t.read().decode('utf-8'))
                
            # Guardamos el token de forma local
            with open(TOKEN_FILE, 'w') as f:
                json.dump(res_t, f)
                
            print("[TV Método] ¡Autorizado con éxito!")
            enviar_a_discord("✅ **Autorización exitosa:** El bot ya tiene acceso seguro al chat.")
            return res_t["access_token"]
        except urllib.error.HTTPError as e:
            res_err = json.loads(e.read().decode('utf-8'))
            if res_err.get("message") == "authorization_pending":
                continue  # Sigue esperando el código
            else:
                raise e

# --- Bucle Principal del Bot de Twitch ---
def bot_twitch():
    global mensajes_enviados
    if not USUARIO:
        print("[ERROR] Falta la variable de entorno TWITCH_USER.")
        return

    # Carga el token (o te pide vincular por TV si es la primera vez)
    token_oauth = obtener_token_tv()

    s = socket.socket()
    try:
        s.connect(("irc.chat.twitch.tv", 6667))
        s.send(f"PASS oauth:{token_oauth}\r\n".encode('utf-8'))
        s.send(f"NICK {USUARIO}\r\n".encode('utf-8'))
        s.send(f"JOIN {CANAL}\r\n".encode('utf-8'))
    except Exception as e:
        print(f"[ERROR] Conexión fallida: {e}")
        return
    
    print(f"Bot conectado exitosamente a {CANAL}.")
    enviar_a_discord(f"🤖 **Bot Activo:** Empezando farmeo intercalado en el chat de {CANAL}.")
    
    usar_mayusculas = False
    while True:
        try:
            comando = "!LOOT" if usar_mayusculas else "!loot"
            s.send(f"PRIVMSG {CANAL} :{comando}\r\n".encode('utf-8'))
            print(f"[Twitch] Enviado: {comando}")
            
            with bloqueo_contador:
                mensajes_enviados += 1
            
            usar_mayusculas = not usar_mayusculas
            # Espera segura de 12 segundos con variación milimétrica anti-detección
            time.sleep(12 + random.uniform(-0.15, 0.4))
            
        except Exception as e:
            print(f"⚠️ Conexión perdida: {e}. Intentando reconectar en 15s...")
            time.sleep(15)
            try:
                token_oauth = obtener_token_tv()  # Lee el token del archivo
                s = socket.socket()
                s.connect(("irc.chat.twitch.tv", 6667))
                s.send(f"PASS oauth:{token_oauth}\r\n".encode('utf-8'))
                s.send(f"NICK {USUARIO}\r\n".encode('utf-8'))
                s.send(f"JOIN {CANAL}\r\n".encode('utf-8'))
            except: pass

# --- Temporizador de Reportes (Cada 20 minutos) ---
def temporizador_discord():
    global mensajes_enviados
    while True:
        time.sleep(1200)  # 1200 segundos = 20 minutos
        with bloqueo_contador:
            total = mensajes_enviados
            mensajes_enviados = 0
        enviar_a_discord(f"📈 **Reporte de Estado (Últimos 20 min):** El bot sigue activo de fondo en Twitch. Se han enviado exitosamente `{total}` comandos en {CANAL}.")

# --- Servidor Falso para mantener vivo Render ---
def servidor_web():
    PORT = int(os.environ.get("PORT", 8080))
    with socketserver.TCPServer(("", PORT), http.server.SimpleHTTPRequestHandler) as h:
        h.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=bot_twitch, daemon=True).start()
    threading.Thread(target=temporizador_discord, daemon=True).start()
    servidor_web()
