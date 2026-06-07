from flask import Flask, render_template_string, request, jsonify
from datetime import datetime
import pytesseract
import re
from PIL import Image, ImageEnhance, ImageFilter
import io
import base64
import json
import os

app = Flask(__name__)

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
    # Pulisce la stringa tenendo solo numeri e separatori
    data_pulita = re.sub(r'[^0-9\/\-\.]', '', data_nascita_str)
    pattern = r'(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})'
    match = re.search(pattern, data_pulita)
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
        .mirino { position: absolute; top: 25%; left: 5%; width: 90%; height: 50%; border: 3px dashed rgba(255,255,255,0.7); border-radius: 10px; pointer-events: none; }
        .status-circle { width: 140px; height: 140px; border-radius: 50%; margin: 25px auto; display: flex; align-items: center; justify-content: center; font-size: 3.5rem; font-weight: bold; transition: all 0.4s ease; background-color: #222; border: 4px solid #333; }
        .maggiorenne { background-color: #2eb85c; border-color: #1f7a3e; box-shadow: 0 0 35px #2eb85c; }
        .minorenne { background-color: #e55353; border-color: #a33939; box-shadow: 0 0 35px #e55353; }
        #info { font-size: 1.3rem; font-weight: bold; margin-top: 10px; min-height: 60px; color: #e0e0e0; }
    </style>
</head>
<body>

<div class="container">
    <h2 style="margin-bottom: 5px; color: #fff;">Scanner Cloud</h2>
    <p id="sub" style="color: #aaa; margin-top: 0; font-size: 0.95rem;">Avvicina la DATA DI NASCITA dentro il mirino</p>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="mirino"></div>
    </div>

    <div id="circle" class="status-circle">📸</div>
    <div id="info">Inquadra la data...</div>
</div>

<canvas id="canvas" style="display:none;" width="800" height="600"></canvas>

<script>
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const circle = document.getElementById('circle');
    const info = document.getElementById('info');
    const ctx = canvas.getContext('2d');
    
    let bloccato = false;

    function playSuono(tipo) {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        let osc = audioCtx.createOscillator();
        let gain = audioCtx.createGain();
        if (tipo === 'ok') {
            osc.type = 'sine'; osc.frequency.setValueAtTime(880, audioCtx.currentTime);
            gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
            osc.connect(gain); gain.connect(audioCtx.destination);
            osc.start(); osc.stop(audioCtx.currentTime + 0.15);
        } else {
            osc.type = 'sawtooth'; osc.frequency.setValueAtTime(220, audioCtx.currentTime);
            gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
            osc.connect(gain); gain.connect(audioCtx.destination);
            osc.start(); osc.stop(audioCtx.currentTime + 0.25);
        }
    }

    async function startCamera() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
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

        // Cattura ad una risoluzione maggiore per permettere a Tesseract di leggere meglio
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
        
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
                    info.innerHTML = `<span style="color:#2eb85c">MAGGIORENNE</span><br><span style="font-size:1.1rem">${data.eta} anni (${data.data_rilevata})</span>`;
                    playSuono('ok');
                } else {
                    circle.className = 'status-circle minorenne'; circle.innerText = '❌';
                    info.innerHTML = `<span style="color:#e55353">MINORENNE</span><br><span style="font-size:1.1rem">${data.eta} anni (${data.data_rilevata})</span>`;
                    playSuono('no');
                }

                setTimeout(() => {
                    circle.className = 'status-circle'; circle.innerText = '📸';
                    info.innerText = 'Inquadra la data...';
                    bloccato = false;
                }, 3500);
            }
        })
        .catch(err => console.log(err));
    }

    startCamera();
    setInterval(catturaEInvia, 1000); // Invia un frame ogni secondo
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

    # --- PRE-ELABORAZIONE IMMAGINE PER L'OCR ---
    # Convertiamo in scala di grigi e aumentiamo il contrasto per rendere i numeri nettissimi
    image = image.convert('L')
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)
    
    try:
        # Configurazione Tesseract: gli diciamo di cercare solo cifre e caratteri di data
        custom_config = r'--psm 11 -c tessedit_char_whitelist=0123456789/.-'
        testo_estratto = pytesseract.image_to_string(image, config=custom_config)
        
        # Cerca formati data tipo 15/08/2002 o 15-08-2002 o 15.08.2002
        date_trovate = re.findall(r'\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4}', testo_estratto)

        if date_trovate:
            for data_str in date_trovate:
                eta = calcola_eta(data_str)
                if eta is not None and 1 < eta < 120: # Filtro per evitare date assurde lette male
                    esito = "MAGGIORENNE" if eta >= 18 else "MINORENNE"
                    salva_in_memoria(esito, eta, data_str)
                    return jsonify({'status': 'success', 'esito': esito, 'eta': eta, 'data_rilevata': data_str})
    except Exception as e:
        print(f"Errore OCR: {e}")

    return jsonify({'status': 'no_date_found'})

if __name__ == '__main__':
    inizializza_memoria()
    app.run(host='0.0.0.0', port=5000, debug=False)
