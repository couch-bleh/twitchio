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
TWITCH_TOKEN = os.environ.get("TWITCH_TOKEN")

mensajes_enviados = 0

def enviar_a_discord(mensaje_texto):
    if not DISCORD_WEBHOOK_URL or "http" not in DISCORD_WEBHOOK_URL: 
        return
    payload = json.dumps({"content": mensaje_texto}).encode('utf-8')
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL, data=payload, 
        headers={'content-type': 'application/json', 'user-agent': 'Mozilla/5.0'}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r: pass
    except: pass

def ejecutar_bot():
    global mensajes_enviados
    print("[PASO 2] Verificando credenciales...")
    if not TWITCH_TOKEN:
        print("[ERROR CRÍTICO] Falta la variable TWITCH_TOKEN en Render.")
        return
    if not USUARIO:
        print("[ERROR CRÍTICO] Falta la variable TWITCH_USER en Render.")
        return

    print("[PASO 3] Conectando directamente al chat IRC de Twitch...")
    s = socket.socket()
    try:
        s.connect(("irc.chat.twitch.tv", 6667))
        s.send(f"PASS oauth:{TWITCH_TOKEN}\r\n".encode('utf-8'))
        s.send(f"NICK {USUARIO}\r\n".encode('utf-8'))
        s.send(f"JOIN {CANAL}\r\n".encode('utf-8'))
    except Exception as e:
        print(f"[ERROR] Conexión fallida al chat: {e}")
        return
    
    print(f"🎉 ¡ÉXITO TOTAL! Bot conectado al chat de {CANAL}.")
    enviar_a_discord(f"🤖 **Bot Activo y Conectado:** Empezando farmeo en {CANAL}.")
    
    usar_mayusculas = True
    ult_reporte = time.time()
    
    while True:
        try:
            comando = "!LOOT" if usar_mayusculas else "!loot"
            
            s.send(f"PRIVMSG {CANAL} :{comando}\r\n".encode('utf-8'))
            
            print(f"[Chat] Enviado con éxito: {comando}", flush=True)
            
            mensajes_enviados += 1
            usar_mayusculas = not usar_mayusculas
            
            time.sleep(300 + random.uniform(-1.0, 3.0))
        except Exception as e:
            print(f"Conexión caída: {e}. Reintentando en 10s...", flush=True)
            time.sleep(10)

# SERVIDOR WEB REQUISITO DE RENDER
class ServidorRapido(http.server.SimpleHTTPRequestHandler):
    def do_HEAD(self): self.send_response(200); self.end_headers()
    def do_GET(self):
        self.send_response(200)
        self.send_header("content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"OK")

if __name__ == "__main__":
    print("[PASO 1] Abriendo puerto web para Render...")
    threading.Thread(target=lambda: socketserver.TCPServer(("", int(os.environ.get("PORT", 8080))), ServidorRapido).serve_forever(), daemon=True).start()
    ejecutar_bot()
