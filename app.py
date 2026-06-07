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
        print(f"Errore scrittura memoria: {e}")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Madre Scanner Ultra-Light</title>
    <script src="https://unpkg.com/tesseract.js@5.1.0/dist/tesseract.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #050505; color: white; margin: 0; padding: 15px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 400px; width: 100%; text-align: center; }
        .video-container { position: relative; width: 100%; max-width: 340px; height: 220px; margin: 0 auto; border-radius: 20px; overflow: hidden; border: 3px solid #1a1a1a; background: #000; }
        video { width: 100%; height: 100%; object-fit: cover; }
        .mirino { position: absolute; top: 25%; left: 5%; width: 90%; height: 50%; border: 3px solid #00ffcc; border-radius: 12px; pointer-events: none; box-shadow: 0 0 20px rgba(0,255,204,0.4); }
        .status-box { width: 100%; padding: 20px 0; border-radius: 16px; margin-top: 20px; font-size: 2rem; font-weight: bold; background-color: #121212; border: 2px solid #222; transition: all 0.1s ease; letter-spacing: 0.5px; }
        .maggiorenne { background-color: #2eb85c !important; color: white; border-color: #1f7a3e; box-shadow: 0 0 30px rgba(46,184,92,0.7); }
        .minorenne { background-color: #e55353 !important; color: white; border-color: #a33939; box-shadow: 0 0 30px rgba(229,83,83,0.7); }
        #sub-text { color: #888; font-size: 0.95rem; margin-top: 12px; min-height: 40px; }
    </style>
</head>
<body>

<div class="container">
    <h2 style="margin: 0 0 5px 0; font-weight: 800; color: #fff;">MADRE LIGHT v9</h2>
    <p style="color: #555; margin: 0 0 15px 0; font-size: 0.85rem;">Analisi Temporale Intelligente - CIE ed Estere</p>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="mirino"></div>
    </div>

    <div id="status-block" class="status-box">ACCENSIONE...</div>
    <div id="sub-text">Inizializzazione fotocamera...</div>
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
        statusBlock.innerText = "AVVIO MOTORE...";
        // Usiamo un worker singolo (leggerissimo per la memoria del telefono) caricando eng+ita
        worker = await Tesseract.createWorker('eng+ita');
        
        await worker.setParameters({
            tessedit_char_whitelist: '0123456789/.- ',
        });
        
        pronto = true;
        statusBlock.innerText = "PRONTO AL VARCO";
        subText.innerText = "Centra la zona della data nel riquadro";
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
                osc.start(); osc.stop(audioCtx.currentTime + 0.1);
            } else {
                osc.type = 'sawtooth'; osc.frequency.setValueAtTime(220, audioCtx.currentTime);
                gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.start(); osc.stop(audioCtx.currentTime + 0.2);
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

    function applicaFiltroNitidezza(imageData) {
        let d = imageData.data;
        for (let i = 0; i < d.length; i += 4) {
            let v = (0.2126 * d[i] + 0.7152 * d[i+1] + 0.0722 * d[i+2]);
            v = (v > 120) ? 255 : 0;
            d[i] = d[i+1] = d[i+2] = v;
        }
        return imageData;
    }

    async function loopScansione() {
        if (!pronto || bloccato || video.readyState !== video.HAVE_ENOUGH_DATA) {
            setTimeout(loopScansione, 80);
            return;
        }

        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        let imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        ctx.putImageData(applicaFiltroNitidezza(imgData), 0, 0);
        
        try {
            const { data: { text } } = await worker.recognize(canvas);
            
            // Estrae qualsiasi blocco numerico formato data (punti, barre o trattini)
            let matches = text.match(/(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{2,4})/g);
            
            if (matches) {
                for (let matchStr of matches) {
                    let parti = matchStr.split(/[\/\-\.]/);
                    let giorno = parseInt(parti[0]);
                    let mese = parseInt(parti[1]);
                    let annoStr = parti[2];
                    let anno = parseInt(annoStr);
                    
                    if (annoStr.length === 2) {
                        let annoCorrenteCorto = new Date().getFullYear() % 100;
                        anno = (anno <= annoCorrenteCorto) ? (2000 + anno) : (1900 + anno);
                    }
                    
                    if (giorno >= 1 && giorno <= 31 && mese >= 1 && mese <= 12) {
                        let oggi = new Date();
                        let eta = oggi.getFullYear() - anno;
                        if (oggi.getMonth() + 1 < mese || (oggi.getMonth() + 1 === mese && oggi.getDate() < giorno)) {
                            eta--;
                        }
                        
                        // FILTRO SEMANTICO: Accetta solo date che generano un'età coerente da locale (16-75 anni)
                        // Taglia fuori in automatico le date di scadenza (es: 2036) o emissione (es: 2026)
                        if (eta >= 16 && eta <= 75) {
                            bloccato = true;
                            let dataValida = `${giorno.toString().padStart(2,'0')}/${mese.toString().padStart(2,'0')}/${anno}`;
                            
                            fetch('/salva_scansione', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ data: dataValida })
                            })
                            .then(res => res.json())
                            .then(data => {
                                if (data.esito === 'MAGGIORENNE') {
                                    statusBlock.className = 'status-box maggiorenne';
                                    statusBlock.innerText = '✔️ PASSA';
                                } else {
                                    statusBlock.className = 'status-box minorenne';
                                    statusBlock.innerText = '❌ MINORENNE';
                                }
                                subText.innerHTML = `Data: <b>${dataValida}</b> — Età: <b>${data.eta} anni</b>`;
                                playSuono(data.esito === 'MAGGIORENNE' ? 'ok' : 'no');

                                setTimeout(() => {
                                    statusBlock.className = 'status-box';
                                    statusBlock.innerText = 'PRONTO AL VARCO';
                                    subText.innerText = 'Centra la zona della data nel riquadro';
                                    bloccato = false;
                                    loopScansione();
                                }, 1800);
                            }).catch(() => { bloccato = false; loopScansione(); });
                            return;
                        }
                    }
                }
            }
        } catch (e) {
            console.error(e);
        }

        setTimeout(loopScansione, 80);
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
