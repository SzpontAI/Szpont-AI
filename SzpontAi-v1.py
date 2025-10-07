
import subprocess
import threading
import time
import webbrowser
from flask import Flask, request, jsonify
import requests
import os
import shutil
import platform
import signal

OLLAMA_PORT = 11434  # domyślny port Ollama
MODEL_NAME = "gemma3:1b"
OLLAMA_URL = "https://ollama.com/download/OllamaSetup.exe"

app = Flask(__name__)

# -----------------------
# Funkcje pomocnicze
# -----------------------

def is_ollama_in_path():
    """Sprawdza, czy Ollama jest dostępna w PATH"""
    try:
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def kill_ollama_gui():
    """Zamyka GUI Ollamy, jeśli jest uruchomione"""
    os.system("taskkill /IM Ollama.exe /F >nul 2>&1")

def install_ollama():
    """Pobiera i instaluje Ollamę, jeśli jej nie ma"""
    print("Ollama nieznaleziona — pobieram instalator...")
    setup_path = os.path.join(os.getcwd(), "OllamaSetup.exe")

    try:
        import requests
        with requests.get(OLLAMA_URL, stream=True) as r:
            r.raise_for_status()
            with open(setup_path, "wb") as f:
                shutil.copyfileobj(r.raw, f)
        print("Pobieranie zakończone. Instaluję Ollamę (tryb cichy)...")

        # Instalacja bez GUI
        subprocess.run([setup_path, "/SILENT", "/NORESTART", "/SUPPRESSMSGBOXES"], check=True)

        # GUI może się uruchomić po instalacji — zamykamy je
        time.sleep(3)
        kill_ollama_gui()

        print("Ollama zainstalowana. Usuwam instalator...")
        os.remove(setup_path)
    except Exception as e:
        print(f"Błąd podczas instalacji Ollamy: {e}")
        exit(1)

def start_ollama_server():
    """Uruchamia Ollama w trybie serve w osobnym procesie"""
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def wait_for_server(port, timeout=10):
    """Czeka aż serwer Ollama zacznie działać"""
    import socket
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False

def ensure_model_installed():
    """Sprawdza, czy model jest dostępny i pobiera go, jeśli trzeba"""
    print("Sprawdzam obecność modelu...")
    try:
        models = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if MODEL_NAME not in models.stdout:
            print(f"Pobieram model {MODEL_NAME} (to może potrwać kilka minut)...")
            subprocess.run(["ollama", "pull", MODEL_NAME], check=True)
            print("Model pobrany.")
        else:
            print("Model już zainstalowany.")
    except Exception as e:
        print(f"Błąd przy pobieraniu modelu: {e}")

def query_ollama(prompt):
    """Wysyła zapytanie do serwera Ollama przez HTTP"""
    url = f"http://127.0.0.1:{OLLAMA_PORT}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return f"(Błąd Ollama: {response.status_code})"
    except Exception as e:
        return f"(Błąd połączenia z Ollama: {e})"

# -----------------------
# Flask endpoints
# -----------------------

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    prompt = data.get("prompt", "")
    reply = query_ollama(prompt)
    return jsonify({"reply": reply})

@app.route("/")
def index():
    return """
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<title>Szpont AI</title>
<style>
body { font-family: sans-serif; max-width: 600px; margin: 20px auto; }
#chat { border: 1px solid #ccc; padding: 10px; height: 400px; overflow-y: auto; }
.msg { margin: 5px 0; }
.user { color: blue; }
.ai { color: green; }
</style>
</head>
<body>
<h1>Szpont AI</h1>
<div id="chat"></div>
<input type="text" id="input" placeholder="Napisz wiadomość..." style="width:80%">
<button id="send">Wyślij</button>

<script>
const chatEl = document.getElementById("chat");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");

function appendMessage(role, text) {
    const div = document.createElement("div");
    div.className = "msg " + role;
    div.textContent = text;
    chatEl.appendChild(div);
    chatEl.scrollTop = chatEl.scrollHeight;
}

sendBtn.onclick = async () => {
    const text = inputEl.value.trim();
    if (!text) return;
    appendMessage("user", text);
    inputEl.value = "";

    try {
        const res = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt: text })
        });
        const data = await res.json();
        appendMessage("ai", data.reply);
    } catch (err) {
        appendMessage("ai", "Błąd połączenia z backendem");
    }
};
</script>
</body>
</html>
"""

# -----------------------
# Start aplikacji
# -----------------------

if __name__ == "__main__":
    system = platform.system().lower()
    if "windows" not in system:
        print("⚠️  Automatyczna instalacja działa tylko na Windows. Zainstaluj Ollamę ręcznie.")
    else:
        if not is_ollama_in_path():
            install_ollama()
        else:
            kill_ollama_gui()  # na wszelki wypadek — zamyka GUI, jeśli się otworzyło

    print("Uruchamiam serwer Ollama...")
    start_ollama_server()

    if wait_for_server(OLLAMA_PORT):
        print("✅ Serwer Ollama działa.")
        ensure_model_installed()
        print("✅ Model gotowy. Uruchamiam Flask...")
    else:
        print("❌ Nie udało się uruchomić serwera Ollama. Sprawdź instalację.")
        exit(1)

    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=False)

