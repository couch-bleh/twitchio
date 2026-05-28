import socket
import time
import random
import threading
import http.server
import socketserver
import json
import urllib.request
import urllib.parse
import os

# ========================================================
# CONFIGURACIÓN DESDE LAS VARIABLES DE ENTORNO DE RENDER
# ========================================================
CANAL = os.environ.get("TWITCH_CANAL", "#spreen")
USUARIO = os.environ.get("TWITCH_USER")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")

# LEEMOS TUS LLAVES DESDE LAS VARIABLES DE ENTORNO
CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET")

TOKEN_FILE = "twitch_tokens.json"
mensajes_enviados = 0

def enviar_a_discord(mensaje_texto):
    if not DISCORD_WEBHOOK_URL or "http" not in DISCORD_WEBHOOK_URL: 
        return
    payload = json.dumps({"content": mensaje_texto}).encode('utf-8')
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL, 
        data=payload, 
        headers={'content-type': 'application/json', 'user-agent': 'Mozilla/5.0'}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r: pass
    except: pass

def obtener_token_tv():
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                datos = json.load(f)
                return datos.get("access_token")
        except: pass

    print("[PASO 3] Solicitando enlace y código con tus credenciales privadas...")
    url_code = "https://id.twitch.tv/oauth2/device"
    
    # Parámetros exactos que exige Twitch
    cuerpo_codigo = {
        "client_id": CLIENT_ID,
        "scopes": "chat:edit chat:read"
    }
    data_code = urllib.parse.urlencode(cuerpo_codigo).encode('utf-8')
    
    req = urllib.request.Request(
        url_code, data=data_code, method="POST",
        headers={
            'content-type': 'application/x-www-form-urlencoded',
            'user-agent': 'Mozilla/5.0'
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"[CRÍTICO] Error. Twitch dice: {e.read().decode('utf-8')}")
        raise e
    
    device_code = res["device_code"]
    user_code = res["user_code"]
    verification_url = res["verification_url"]
    interval = res["interval"]

    aviso = f"🔑 **VINCULACIÓN REQUERIDA:**\n1. Entra a: {verification_url}\n2. Pon este código en tu celular: **{user_code}**"
    print(f"\n{aviso}\n")
    enviar_a_discord(aviso)

    url_token = "https://id.twitch.tv/oauth2/token"
    cuerpo_token = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
    }
    data_token = urllib.parse.urlencode(cuerpo_token).encode('utf-8')
    
    print("[PASO 4] Esperando código de autorización de tu celular...")
    while True:
        time.sleep(interval)
        try:
            req_t = urllib.request.Request(
                url_token, data=data_token, method="POST",
                headers={'content-type': 'application/x-www-form-urlencoded', 'user-agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req_t, timeout=10) as r_t:
                res_t = json.loads(r_t.read().decode('utf-8'))
                
            with open(TOKEN_FILE, 'w') as f:
                json.dump(res_t, f)
                
            print("[TV Método] ¡Autorizado con éxito!")
            enviar_a_discord("✅ **Autorización exitosa:** Bot conectado.")
            return res_t["access_token"]
        except urllib.error.HTTPError as e:
            res_err = json.loads(e.read().decode('utf-8'))
            if res_err.get("status") == 400 or "pending" in res_err.get("message", "").lower():
                continue
            else: raise e
        except: continue

def ejecutar_bot_secuencial():
    global mensajes_enviados
    print("[PASO 2] Iniciando verificaciones de usuario...")
    if not CLIENT_ID or not CLIENT_SECRET:
        print("[ERROR CRÍTICO] Falta configurar TWITCH_CLIENT_ID o TWITCH_CLIENT_SECRET en Render.")
        return
    if not USUARIO:
        print("[ERROR CRÍTICO] Falta la variable TWITCH_USER.")
        return

    token_oauth = obtener_token_tv()

    print("[PASO 5] Conectando al chat IRC...")
    s = socket.socket()
    try:
        s.connect(("irc.chat.twitch.tv", 6667))
        s.send(f"PASS oauth:{token_oauth}\r\n".encode('utf-8'))
        s.send(f"NICK {USUARIO}\r\n".encode('utf-8'))
        s.send(f"JOIN {CANAL}\r\n".encode('utf-8'))
    except Exception as e:
        print(f"[ERROR] Conexión fallida: {e}")
        return
    
    print(f"🎉 ¡Conectado a {CANAL}!")
    enviar_a_discord(f"🤖 **Bot Activo** en {CANAL}.")
    
    usar_mayusculas = False
    ult_reporte = time.time()
    
    while True:
        try:
            comando = "!LOOT" if usar_mayusculas else "!loot"
            s.send(f"PRIVMSG {CANAL} :{comando}\r\n".encode('utf-8'))
            print(f"[Chat] Enviado: {comando}")
            mensajes_enviados += 1
            usar_mayusculas = not usar_mayusculas
            
            if time.time() - ult_reporte > 1200:
                enviar_a_discord(f"📈 **Reporte (20 min):** Enviados `{mensajes_enviados}` comandos.")
                mensajes_enviados = 0
                ult_reporte = time.time()
                
            time.sleep(12 + random.uniform(-0.1, 0.3))
        except Exception as e:
            print(f"Caída: {e}. Reintentando...")
            time.sleep(10)

class ServidorRapido(http.server.SimpleHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def do_GET(self):
        self.send_response(200)
        self.send_header("content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"OK")

if __name__ == "__main__":
    print("[PASO 1] Abriendo puerto web para Render...")
    threading.Thread(target=lambda: socketserver.TCPServer(("", int(os.environ.get("PORT", 8080))), ServidorRapido).serve_forever(), daemon=True).start()
    ejecutar_bot_secuencial()
