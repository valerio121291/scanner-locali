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
    <title>Madre Laser Precision v11</title>
    <script src="https://unpkg.com/tesseract.js@5.1.0/dist/tesseract.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #030303; color: white; margin: 0; padding: 15px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 400px; width: 100%; text-align: center; }
        
        .video-container { position: relative; width: 100%; max-width: 340px; height: 220px; margin: 0 auto; border-radius: 24px; overflow: hidden; border: 3px solid #222; background: #000; box-shadow: 0 12px 40px rgba(0,0,0,0.8); }
        video { width: 100%; height: 100%; object-fit: cover; }
        
        /* Zona di mira ristretta per massima precisione di focus numerico */
        .mirino { position: absolute; top: 38%; left: 8%; width: 84%; height: 24%; border: 3px solid #00ffcc; border-radius: 10px; pointer-events: none; box-shadow: 0 0 25px rgba(0,255,204,0.5); box-sizing: border-box; z-index: 10; }
        .oscuratore-top { position: absolute; top: 0; left: 0; width: 100%; height: 38%; background: rgba(0,0,0,0.7); pointer-events: none; z-index: 5; }
        .oscuratore-bottom { position: absolute; top: 62%; left: 0; width: 100%; height: 38%; background: rgba(0,0,0,0.7); pointer-events: none; z-index: 5; }
        
        .status-box { width: 100%; padding: 22px 0; border-radius: 18px; margin-top: 25px; font-size: 2.1rem; font-weight: bold; background-color: #111; border: 2px solid #222; transition: all 0.1s cubic-bezier(0.175, 0.885, 0.32, 1.275); letter-spacing: 1px; }
        .maggiorenne { background-color: #10b981 !important; color: white; border-color: #059669; box-shadow: 0 0 35px rgba(16,185,129,0.8); }
        .minorenne { background-color: #ef4444 !important; color: white; border-color: #dc2626; box-shadow: 0 0 35px rgba(239,68,68,0.8); }
        #sub-text { color: #94a3b8; font-size: 1rem; margin-top: 15px; min-height: 45px; line-height: 1.4; font-weight: 500; }
    </style>
</head>
<body>

<div class="container">
    <h2 style="margin: 0 0 5px 0; font-weight: 800; color: #fff; letter-spacing: -0.5px;">MADRE PRECISION v11</h2>
    <p style="color: #475569; margin: 0 0 15px 0; font-size: 0.85rem; font-weight: 600;">Isolamento HD e Filtro Ottico Ottimizzato</p>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="oscuratore-top"></div>
        <div class="mirino"></div>
        <div class="oscuratore-bottom"></div>
    </div>

    <div id="status-block" class="status-box">CALIBRAZIONE...</div>
    <div id="sub-text">Allineamento sensori di precisione...</div>
</div>

<canvas id="processingCanvas" style="display:none;" width="600" height="160"></canvas>

<script>
    const video = document.getElementById('video');
    const processingCanvas = document.getElementById('processingCanvas');
    const statusBlock = document.getElementById('status-block');
    const subText = document.getElementById('sub-text');
    const pCtx = processingCanvas.getContext('2d');
    
    let worker = null;
    let bloccato = false;
    let pronto = false;

    async function inizializzaOCR() {
        statusBlock.innerText = "AVVIO MOTORE...";
        worker = await Tesseract.createWorker('eng');
        
        await worker.setParameters({
            tessedit_char_whitelist: '0123456789/.- ',
        });
        
        pronto = true;
        statusBlock.innerText = "PRONTO AL VARCO";
        subText.innerText = "Inquadra stabilmente la riga della data nel box";
        loopScansione();
    }

    async function startCamera() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 } },
                audio: false
            });
            video.srcObject = stream;
        } catch (err) {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            video.srcObject = stream;
        }
    }

    // Filtro adattivo ad alto stacco per distruggere i riflessi lucidi e le patine cromatiche delle tessere plastiche
    function applicaFiltroPrecisione(imageData) {
        let d = imageData.data;
        for (let i = 0; i < d.length; i += 4) {
            // Diamo maggiore enfasi al canale rosso e verde per abbattere i riflessi olografici blu/viola delle discoteche
            let v = (0.35 * d[i] + 0.55 * d[i+1] + 0.10 * d[i+2]);
            // Soglia netta antiriflesso
            v = (v > 115) ? 255 : 0;
            d[i] = d[i+1] = d[i+2] = v;
        }
        return imageData;
    }

    async function loopScansione() {
        if (!pronto || bloccato || video.readyState !== video.HAVE_ENOUGH_DATA) {
            setTimeout(loopScansione, 50);
            return;
        }

        // Recuperiamo le dimensioni reali del flusso video (HD)
        let videoW = video.videoWidth;
        let videoH = video.videoHeight;
        
        // Calcoliamo geometricamente la porzione del mirino centrale sul flusso HD reale
        let cropX = videoW * 0.08;
        let cropY = videoH * 0.38;
        let cropW = videoW * 0.84;
        let cropH = videoH * 0.24;

        // Disegniamo sul canvas aumentando la densità dei pixel per rendere i caratteri ultra-definiti
        pCtx.drawImage(video, cropX, cropY, cropW, cropH, 0, 0, processingCanvas.width, processingCanvas.height);
        
        let imgData = pCtx.getImageData(0, 0, processingCanvas.width, processingCanvas.height);
        pCtx.putImageData(applicaFiltroPrecisione(imgData), 0, 0);
        
        try {
            const { data: { text } } = await worker.recognize(processingCanvas);
            
            // Validazione formati data rigorosa (evita falsi positivi con numeri seriali)
            let matches = text.replace(/\s+/g, '').match(/(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{2,4})/g);
            
            if (matches) {
                for (let matchStr of matches) {
                    let separators = matchStr.match(/[\/\-\.]/g);
                    // Controllo coerenza separatori (evita letture sporche come 12/12.19)
                    if (separators && separators[0] !== separators[1]) continue;

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
                        
                        // Finestra d'età logica per escludere emissioni e scadenze dei documenti
                        if (eta >= 15 && eta <= 75) {
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
                                
                                try {
                                    let audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                                    let osc = audioCtx.createOscillator();
                                    osc.frequency.setValueAtTime(data.esito === 'MAGGIORENNE' ? 880 : 220, audioCtx.currentTime);
                                    osc.connect(audioCtx.destination);
                                    osc.start(); osc.stop(audioCtx.currentTime + 0.12);
                                } catch(e) {}

                                setTimeout(() => {
                                    statusBlock.className = 'status-box';
                                    statusBlock.innerText = 'PRONTO AL VARCO';
                                    subText.innerText = 'Inquadra stabilmente la riga della data nel box';
                                    bloccato = false;
                                    loopScansione();
                                }, 1500);
                            }).catch(() => { bloccato = false; loopScansione(); });
                            return;
                        }
                    }
                }
            }
        } catch (e) {
            console.error(e);
        }

        setTimeout(loopScansione, 45);
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
