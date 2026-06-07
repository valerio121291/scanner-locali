from flask import Flask, render_template_string, request, jsonify
from datetime import datetime
import pytesseract
import re
from PIL import Image
import io
import base64
import json
import os

app = Flask(__name__)

# File di memoria per l'IA "Madre" (nella cartella temporanea del server)
MEMORIA_FILE = "/tmp/memoria_madre.json"

def inizializza_memoria():
    if not os.path.exists(MEMORIA_FILE):
        with open(MEMORIA_FILE, 'w') as f:
            json.dump({"scansioni_totali": 0, "maggiorenni": 0, "minorenni": 0, "cronologia": []}, f, indent=4)

def salva_in_memoria(esito, eta, data_nascita):
    try:
        inizializza_memoria()
        with open(MEMORIA_FILE, 'r+') as f:
            data = json.load(f)
            data["scansioni_totali"] += 1
            if esito == "MAGGIORENNE":
                data["maggiorenni"] += 1
            else:
                data["minorenni"] += 1
            
            data["cronologia"].append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "esito": esito,
                "eta": eta,
                "data_nascita": data_nascita
            })
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
    except Exception as e:
        print(f"Errore salvataggio memoria: {e}")

def calcola_eta(data_nascita_str):
    pattern = r'(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})'
    match = re.search(pattern, data_nascita_str)
    if not match:
        return None
    giorno, mese, anno = map(int, match.groups())
    try:
        data_nascita = datetime(anno, mese, giorno)
        oggi = datetime.now()
        eta = oggi.year - data_nascita.year - ((oggi.month, oggi.day) < (data_nascita.month, data_nascita.day))
        return eta
    except ValueError:
        return None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Scanner Madre Cloud</title>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #121212; color: white; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 450px; width: 100%; text-align: center; }
        .video-container { position: relative; width: 100%; max-width: 360px; height: 240px; margin: 0 auto; border-radius: 20px; overflow: hidden; border: 3px solid #333; background: #000; }
        video { width: 100%; height: 100%; object-fit: cover; }
        .mirino { position: absolute; top: 15%; left: 5%; width: 90%; height: 70%; border: 3px dashed rgba(255,255,255,0.6); border-radius: 15px; pointer-events: none; }
        .status-circle { width: 140px; height: 140px; border-radius: 50%; margin: 25px auto; display: flex; align-items: center; justify-content: center; font-size: 3.5rem; font-weight: bold; transition: all 0.4s ease; background-color: #222; border: 4px solid #333; }
        .maggiorenne { background-color: #2eb85c; border-color: #1f7a3e; box-shadow: 0 0 35px #2eb85c; }
        .minorenne { background-color: #e55353; border-color: #a33939; box-shadow: 0 0 35px #e55353; }
        #info { font-size: 1.3rem; font-weight: bold; margin-top: 10px; min-height: 60px; color: #e0e0e0; }
    </style>
</head>
<body>

<div class="container">
    <h2 style="margin-bottom: 5px; color: #fff;">Scanner Cloud</h2>
    <p id="sub" style="color: #666; margin-top: 0; font-size: 0.95rem;">Inquadra nitidamente la data di nascita</p>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="mirino"></div>
    </div>

    <div id="circle" class="status-circle">📸</div>
    <div id="info">Pronto alla scansione...</div>
</div>

<canvas id="canvas" style="display:none;" width="640" height="480"></canvas>

<script>
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const circle = document.getElementById('circle');
    const info = document.getElementById('info');
    const ctx = canvas.getContext('2d');
    
    let bloccato = false;

    function playSuono(tipo) {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        if (tipo === 'ok') {
            let osc = audioCtx.createOscillator();
            let gain = audioCtx.createGain();
            osc.type = 'sine'; osc.frequency.setValueAtTime(880, audioCtx.currentTime);
            gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
            osc.connect(gain); gain.connect(audioCtx.destination);
            osc.start(); osc.stop(audioCtx.currentTime + 0.15);
        } else if (tipo === 'no') {
            [0, 0.2].forEach(delay => {
                let osc = audioCtx.createOscillator();
                let gain = audioCtx.createGain();
                osc.type = 'sawtooth'; osc.frequency.setValueAtTime(220, audioCtx.currentTime + delay);
                gain.gain.setValueAtTime(0.1, audioCtx.currentTime + delay);
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.start(audioCtx.currentTime + delay); osc.stop(audioCtx.currentTime + delay + 0.15);
            });
        }
    }

    async function startCamera() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "environment", width: { ideal: 640 }, height: { ideal: 480 } },
                audio: false
            });
            video.srcObject = stream;
        } catch (err) {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            video.srcObject = stream;
        }
    }

    function catturaEInvia() {
        if (bloccato || video.readyState !== video.HAVE_ENOUGH_DATA) return;

        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.5); // Compressione ottimale per il cloud
        
        fetch('/scan_frame', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: dataUrl })
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                bloccato = true;
                
                if (data.esito === 'MAGGIORENNE') {
                    circle.className = 'status-circle maggiorenne'; circle.innerText = '✔️';
                    info.innerHTML = `<span style="color:#2eb85c">MAGGIORENNE</span><br><span style="font-size:0.9rem">${data.eta} anni</span>`;
                    playSuono('ok');
                } else {
                    circle.className = 'status-circle minorenne'; circle.innerText = '❌';
                    info.innerHTML = `<span style="color:#e55353">MINORENNE</span><br><span style="font-size:0.9rem">${data.eta} anni</span>`;
                    playSuono('no');
                }

                setTimeout(() => {
                    circle.className = 'status-circle'; circle.innerText = '📸';
                    info.innerText = 'Pronto alla scansione...';
                    bloccato = false;
                }, 3000);
            }
        })
        .catch(err => console.log(err));
    }

    startCamera();
    setInterval(catturaEInvia, 1000); // Analisi ogni secondo
</script>

</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/scan_frame', methods=['POST'])
def scan_frame():
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({'status': 'error'})

    header, encoded = data['image'].split(",", 1)
    image_bytes = base64.b64decode(encoded)
    image = Image.open(io.BytesIO(image_bytes))

    # Analisi OCR veloce tramite Tesseract (Nativo del server)
    try:
        testo_estratto = pytesseract.image_to_string(image)
        date_trovate = re.findall(r'\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4}', testo_estratto)

        if date_trovate:
            for data_str in date_trovate:
                eta = calcola_eta(data_str)
                if eta is not None:
                    esito = "MAGGIORENNE" if eta >= 18 else "MINORENNE"
                    salva_in_memoria(esito, eta, data_str)
                    return jsonify({'status': 'success', 'esito': esito, 'eta': eta, 'data_rilevata': data_str})
    except Exception as e:
        print(f"Errore OCR: {e}")

    return jsonify({'status': 'no_date_found'})

if __name__ == '__main__':
    inizializza_memoria()
    app.run(host='0.0.0.0', port=5000, debug=False)