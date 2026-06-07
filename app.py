from flask import Flask, render_template_string, request, jsonify
from datetime import datetime
import json
import os
import re
import base64
import io
from PIL import Image

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

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Scanner Madre Flash</title>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #121212; color: white; margin: 0; padding: 15px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 400px; width: 100%; text-align: center; }
        .video-container { position: relative; width: 100%; max-width: 340px; height: 200px; margin: 0 auto; border-radius: 15px; overflow: hidden; border: 3px solid #333; background: #000; }
        video { width: 100%; height: 100%; object-fit: cover; }
        .mirino { position: absolute; top: 30%; left: 10%; width: 80%; height: 40%; border: 3px solid #00ffcc; border-radius: 8px; pointer-events: none; box-shadow: 0 0 10px rgba(0,255,204,0.5); }
        .status-box { width: 100%; padding: 20px 0; border-radius: 15px; margin-top: 20px; font-size: 2rem; font-weight: bold; background-color: #1e1e1e; border: 2px solid #333; transition: all 0.2s ease; }
        .maggiorenne { background-color: #2eb85c !important; color: white; border-color: #1f7a3e; box-shadow: 0 0 25px #2eb85c; }
        .minorenne { background-color: #e55353 !important; color: white; border-color: #a33939; box-shadow: 0 0 25px #e55353; }
        #sub-text { color: #888; font-size: 0.9rem; margin-top: 10px; }
    </style>
</head>
<body>

<div class="container">
    <h2 style="margin: 0 0 5px 0;">Madre Flash Scanner</h2>
    <p style="color: #aaa; margin: 0 0 15px 0; font-size: 0.9rem;">Passa la data di nascita dentro il mirino verde</p>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="mirino"></div>
    </div>

    <div id="status-block" class="status-box">CERCANDO DATA...</div>
    <p id="sub-text">Tieni il documento fermo e ben illuminato</p>
</div>

<canvas id="canvas" style="display:none;" width="400" height="300"></canvas>

<script>
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const statusBlock = document.getElementById('status-block');
    const subText = document.getElementById('sub-text');
    const ctx = canvas.getContext('2d');
    
    let bloccato = false;

    function playSuono(tipo) {
        try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            let osc = audioCtx.createOscillator();
            let gain = audioCtx.createGain();
            if (tipo === 'ok') {
                osc.type = 'sine'; osc.frequency.setValueAtTime(880, audioCtx.currentTime);
                gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.start(); osc.stop(audioCtx.currentTime + 0.12);
            } else {
                osc.type = 'sawtooth'; osc.frequency.setValueAtTime(220, audioCtx.currentTime);
                gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.start(); osc.stop(audioCtx.currentTime + 0.22);
            }
        } catch(e) {}
    }

    async function startCamera() {
        const vincolati = {
            video: { facingMode: "environment", width: { ideal: 640 }, height: { ideal: 480 } },
            audio: false
        };
        try {
            const stream = await navigator.mediaDevices.getUserMedia(vincolati);
            video.srcObject = stream;
        } catch (err) {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            video.srcObject = stream;
        }
    }

    function catturaEInvia() {
        if (bloccato || video.readyState !== video.HAVE_ENOUGH_DATA) return;

        // Cattura a risoluzione ridotta ed ottimizzata per una trasmissione immediata
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.4);
        
        fetch('/analizza_immediato', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: dataUrl })
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success' && !bloccato) {
                bloccato = true;
                
                if (data.esito === 'MAGGIORENNE') {
                    statusBlock.className = 'status-box maggiorenne';
                    statusBlock.innerText = '✔️ MAGGIORENNE';
                    subText.innerHTML = `Età: <b>${data.eta} anni</b> (${data.data})`;
                    playSuono('ok');
                } else {
                    statusBlock.className = 'status-box minorenne';
                    statusBlock.innerText = '❌ MINORENNE';
                    subText.innerHTML = `Età: <b>${data.eta} anni</b> (${data.data})`;
                    playSuono('no');
                }

                // Sblocco rapido dopo 2 secondi per essere subito pronti per il cliente successivo
                setTimeout(() => {
                    statusBlock.className = 'status-box';
                    statusBlock.innerText = 'CERCANDO DATA...';
                    subText.innerText = 'Tieni il documento fermo e ben illuminato';
                    bloccato = false;
                }, 2000);
            }
        })
        .catch(err => console.log(err));
    }

    startCamera();
    // Esegue il controllo in background ogni 400 millisecondi (velocissimo!)
    setInterval(catturaEInvia, 400);
</script>

</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/analizza_immediato', methods=['POST'])
def analizza_immediato():
    import pytesseract
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({'status': 'error'})

    header, encoded = data['image'].split(",", 1)
    image_bytes = base64.b64decode(encoded)
    image = Image.open(io.BytesIO(image_bytes))

    # Lettura ultra rapida via Tesseract Cloud su stringa numerica pura
    try:
        config_veloce = r'--psm 11 -c tessedit_char_whitelist=0123456789/.-'
        testo = pytesseract.image_to_string(image, config=config_veloce)
        
        # Estrae le date nel formato classico italiano (GG/MM/AAAA)
        date_trovate = re.findall(r'(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})', testo)
        
        if date_trovate:
            giorno, mese, anno = map(int, date_trovate[0])
            if 1930 < anno <= datetime.now().year and 1 <= mese <= 12 and 1 <= giorno <= 31:
                data_nascita = datetime(anno, mese, giorno)
                oggi = datetime.now()
                eta = oggi.year - data_nascita.year - ((oggi.month, oggi.day) < (data_nascita.month, data_nascita.day))
                
                if 5 < eta < 100:
                    esito = "MAGGIORENNE" if eta >= 18 else "MINORENNE"
                    data_formattata = f"{giorno:02d}/{mese:02d}/{anno}"
                    salva_in_memoria(esito, eta, data_formattata)
                    return jsonify({'status': 'success', 'esito': esito, 'eta': eta, 'data': data_formattata})
    except Exception as e:
        print(f"Errore: {e}")

    return jsonify({'status': 'searching'})

if __name__ == '__main__':
    inizializza_memoria()
    app.run(host='0.0.0.0', port=5000, debug=False)
