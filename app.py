from flask import Flask, render_template_string, request, jsonify
from datetime import datetime
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
        print(f"Errore memoria: {e}")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Scanner Madre Intelligente</title>
    <script src="https://unpkg.com/tesseract.js@5.1.0/dist/tesseract.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #121212; color: white; margin: 0; padding: 15px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 400px; width: 100%; text-align: center; }
        .video-container { position: relative; width: 100%; max-width: 340px; height: 220px; margin: 0 auto; border-radius: 15px; overflow: hidden; border: 3px solid #333; background: #000; }
        video { width: 100%; height: 100%; object-fit: cover; }
        .mirino { position: absolute; top: 25%; left: 5%; width: 90%; height: 50%; border: 3px solid #00ffcc; border-radius: 8px; pointer-events: none; box-shadow: 0 0 10px rgba(0,255,204,0.4); }
        .status-box { width: 100%; padding: 20px 0; border-radius: 15px; margin-top: 20px; font-size: 1.8rem; font-weight: bold; background-color: #1e1e1e; border: 2px solid #333; transition: all 0.2s ease; }
        .maggiorenne { background-color: #2eb85c !important; color: white; border-color: #1f7a3e; box-shadow: 0 0 25px #2eb85c; }
        .minorenne { background-color: #e55353 !important; color: white; border-color: #a33939; box-shadow: 0 0 25px #e55353; }
        #sub-text { color: #aaa; font-size: 0.9rem; margin-top: 10px; min-height: 40px; }
    </style>
</head>
<body>

<div class="container">
    <h2 style="margin: 0 0 5px 0;">Madre Intelletto v4</h2>
    <p style="color: #888; margin: 0 0 15px 0; font-size: 0.9rem;">Inquadra la sezione "Data di Nascita"</p>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="mirino"></div>
    </div>

    <div id="status-block" class="status-box">CARICAMENTO...</div>
    <div id="sub-text">Inizializzazione motore di lettura...</div>
</div>

<canvas id="canvas" style="display:none;" width="640" height="480"></canvas>

<script>
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const statusBlock = document.getElementById('status-block');
    const subText = document.getElementById('sub-text');
    const ctx = canvas.getContext('2d');
    
    let worker = null;
    let bloccato = false;
    let pronto = false;

    async function inizializzaOCR() {
        statusBlock.innerText = "SISTEMA AVVIATO";
        // Configurazione bilingue leggera per intercettare sia l'italiano che le etichette inglesi dei documenti
        worker = await Tesseract.createWorker('ita+eng');
        
        // Mettiamo in whitelist lettere e numeri chiave per non rallentare l'elaborazione
        await worker.setParameters({
            tessedit_char_whitelist: '0123456789/.-ABCDEFGHIJKLMOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz() ',
        });
        pronto = true;
        statusBlock.innerText = "PRONTO AL VARCO";
        subText.innerText = "Inquadra la data (tieni fermo a 15-20cm)";
        loopScansione();
    }

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

    async function loopScansione() {
        if (!pronto || bloccato || video.readyState !== video.HAVE_ENOUGH_DATA) {
            setTimeout(loopScansione, 250);
            return;
        }

        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        try {
            const { data: { text } } = await worker.recognize(canvas);
            let testoPulito = text.toUpperCase();

            // --- TUA INTUIZIONE: ANCORAGGIO INTELLIGENTE ---
            // Controlliamo se nel testo ci sono le parole magiche del documento
            if (testoPulito.includes("NASCITA") || testoPulito.includes("BIRTH") || testoPulito.includes("DATA") || testoPulito.includes("PLACE")) {
                
                // Estrae la stringa di numeri GG/MM/AAAA vicina alle parole chiave
                let match = testoPulito.match(/(\\d{2})[\\/\\-\\.](\\d{2})[\\/\\-\\.](\\d{4})/);
                
                if (match) {
                    let giorno = parseInt(match[1]);
                    let mese = parseInt(match[2]);
                    let anno = parseInt(match[3]);
                    
                    if (anno > 1930 && anno <= new Date().getFullYear() && mese >= 1 && mese <= 12 && giorno >= 1 && giorno <= 31) {
                        bloccato = true;
                        let dataRilevata = `${giorno.toString().padStart(2,'0')}/${mese.toString().padStart(2,'0')}/${anno}`;
                        
                        fetch('/salva_scansione', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ data: dataRilevata })
                        })
                        .then(res => res.json())
                        .then(data => {
                            if (data.esito === 'MAGGIORENNE') {
                                statusBlock.className = 'status-box maggiorenne';
                                statusBlock.innerText = '✔️ MAGGIORENNE';
                                subText.innerHTML = `Nato il: <b>${dataRilevata}</b> (${data.eta} anni)`;
                                playSuono('ok');
                            } else {
                                statusBlock.className = 'status-box minorenne';
                                statusBlock.innerText = '❌ MINORENNE';
                                subText.innerHTML = `Nato il: <b>${dataRilevata}</b> (${data.eta} anni)`;
                                playSuono('no');
                            }

                            // Reset rapido di 2 secondi, perfetto per la fila
                            setTimeout(() => {
                                statusBlock.className = 'status-box';
                                statusBlock.innerText = 'PRONTO AL VARCO';
                                subText.innerText = 'Inquadra la data (tieni fermo a 15-20cm)';
                                bloccato = false;
                                loopScansione();
                            }, 2000);
                        });
                        return;
                    }
                }
            }
        } catch (e) {
            console.error(e);
        }

        // Continua a scansionare a raffica ogni 150ms finché non aggancia il testo corretto
        setTimeout(loopScansione, 150);
    }

    startCamera();
    inizializzaOCR();
</script>

</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/salva_scansione', methods=['POST'])
def salva_scansione():
    data = request.get_json()
    if not data or 'data' not in data:
        return jsonify({'status': 'error'})

    data_str = data['data']
    giorno, mese, anno = map(int, data_str.split('/'))
    
    data_nascita = datetime(anno, mese, giorno)
    oggi = datetime.now()
    eta = oggi.year - data_nascita.year - ((oggi.month, oggi.day) < (data_nascita.month, data_nascita.day))
    
    esito = "MAGGIORENNE" if eta >= 18 else "MINORENNE"
    salva_in_memoria(esito, eta, data_str)
    
    return jsonify({'status': 'success', 'esito': esito, 'eta': eta})

if __name__ == '__main__':
    inizializza_memoria()
    app.run(host='0.0.0.0', port=5000, debug=False)
