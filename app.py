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
    <title>Madre Instant v14</title>
    <script src="https://unpkg.com/tesseract.js@5.1.0/dist/tesseract.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #030303; color: white; margin: 0; padding: 15px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 400px; width: 100%; text-align: center; }
        
        .video-container { position: relative; width: 100%; max-width: 340px; height: 220px; margin: 0 auto; border-radius: 24px; overflow: hidden; border: 3px solid #222; background: #000; box-shadow: 0 12px 40px rgba(0,0,0,0.8); }
        video { width: 100%; height: 100%; object-fit: cover; }
        
        /* Mirino GRANDE: basta inserire il documento nel riquadro, senza allineamenti precisi */
        .mirino { position: absolute; top: 15%; left: 8%; width: 84%; height: 70%; border: 3px solid #00ffcc; border-radius: 14px; pointer-events: none; box-shadow: 0 0 25px rgba(0,255,204,0.3); box-sizing: border-box; z-index: 10; }
        .oscuratore-top { position: absolute; top: 0; left: 0; width: 100%; height: 15%; background: rgba(0,0,0,0.4); pointer-events: none; z-index: 5; }
        .oscuratore-bottom { position: absolute; top: 85%; left: 0; width: 100%; height: 15%; background: rgba(0,0,0,0.4); pointer-events: none; z-index: 5; }
        
        .status-box { width: 100%; padding: 22px 0; border-radius: 18px; margin-top: 25px; font-size: 2.1rem; font-weight: bold; background-color: #111; border: 2px solid #222; transition: all 0.1s cubic-bezier(0.175, 0.885, 0.32, 1.275); letter-spacing: 1px; }
        .maggiorenne { background-color: #10b981 !important; color: white; border-color: #059669; box-shadow: 0 0 35px rgba(16,185,129,0.8); }
        .minorenne { background-color: #ef4444 !important; color: white; border-color: #dc2626; box-shadow: 0 0 35px rgba(239,68,68,0.8); }
        #sub-text { color: #94a3b8; font-size: 1rem; margin-top: 15px; min-height: 45px; line-height: 1.4; font-weight: 500; }
    </style>
</head>
<body>

<div class="container">
    <h2 style="margin: 0 0 5px 0; font-weight: 800; color: #fff; letter-spacing: -0.5px;">MADRE INSTANT v14</h2>
    <p style="color: #00ffcc; margin: 0 0 15px 0; font-size: 0.85rem; font-weight: 600; text-transform: uppercase;">Scansione Libera Omnidirezionale</p>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="oscuratore-top"></div>
        <div class="mirino"></div>
        <div class="oscuratore-bottom"></div>
    </div>

    <div id="status-block" class="status-box">CALIBRAZIONE...</div>
    <div id="sub-text">Inizializzazione lenti rapide...</div>
</div>

<canvas id="processingCanvas" style="display:none;" width="480" height="320"></canvas>

<script>
    const video = document.getElementById('video');
    const processingCanvas = document.getElementById('processingCanvas');
    const statusBlock = document.getElementById('status-block');
    const subText = document.getElementById('sub-text');
    const pCtx = processingCanvas.getContext('2d', { alpha: false });
    
    let worker = null;
    let bloccato = false;
    let pronto = false;

    async function inizializzaOCR() {
        statusBlock.innerText = "AVVIO MOTORE...";
        worker = await Tesseract.createWorker('eng');
        
        await worker.setParameters({
            tessedit_char_whitelist: '0123456789/.- ',
            tessedit_pageseg_mode: '11', // MODO 11: Cerca stringhe sparse ovunque nel foglio/tessera. Zero vincoli di riga!
        });
        
        pronto = true;
        statusBlock.innerText = "PRONTO";
        subText.innerText = "Mostra il documento nel riquadro";
        loopScansione();
    }

    async function startCamera() {
        try {
            // Chiediamo una risoluzione bilanciata per permettere una messa a fuoco fulminea e macro nativa
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { 
                    facingMode: "environment", 
                    width: { ideal: 640 }, 
                    height: { ideal: 480 },
                    focusMode: { ideal: "continuous" }
                },
                audio: false
            });
            video.srcObject = stream;
        } catch (err) {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            video.srcObject = stream;
        }
    }

    // Filtro istantaneo binarizzante ad alta velocità
    function applicaFiltroRapido(imageData) {
        let d = imageData.data;
        for (let i = 0; i < d.length; i += 4) {
            let v = (d[i] + d[i+1] + d[i+2]) / 3;
            // Taglio netto: toglie le sfumature della plastica e lascia solo testo puro
            v = (v > 120) ? 255 : 0;
            d[i] = d[i+1] = d[i+2] = v;
        }
        return imageData;
    }

    async function loopScansione() {
        if (!pronto || bloccato || video.readyState !== video.HAVE_ENOUGH_DATA) {
            setTimeout(loopScansione, 20);
            return;
        }

        let videoW = video.videoWidth;
        let videoH = video.videoHeight;
        
        // Cattura ad ampio spettro (prende quasi tutto il mirino grande)
        let cropX = videoW * 0.08;
        let cropY = videoH * 0.15;
        let cropW = videoW * 0.84;
        let cropH = videoH * 0.70;

        pCtx.drawImage(video, cropX, cropY, cropW, cropH, 0, 0, processingCanvas.width, processingCanvas.height);
        
        let imgData = pCtx.getImageData(0, 0, processingCanvas.width, processingCanvas.height);
        pCtx.putImageData(applicaFiltroRapido(imgData), 0, 0);
        
        try {
            // Esegue il riconoscimento sull'intero blocco in pochissimi millisecondi
            const { data: { text } } = await worker.recognize(processingCanvas);
            
            // Trova qualsiasi pattern di data ovunque nella pagina scansionata
            let matches = text.match(/(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{2,4})/g);
            
            if (matches) {
                for (let matchStr of matches) {
                    let separators = matchStr.match(/[\/\-\.]/g);
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
                        
                        // Accetta la data solo se genera un'età compresa nel range logico di un locale
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
                                
                                try {
                                    let audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                                    let osc = audioCtx.createOscillator();
                                    osc.frequency.setValueAtTime(data.esito === 'MAGGIORENNE' ? 880 : 220, audioCtx.currentTime);
                                    osc.connect(audioCtx.destination);
                                    osc.start(); osc.stop(audioCtx.currentTime + 0.12);
                                } catch(e) {}

                                setTimeout(() => {
                                    statusBlock.className = 'status-box';
                                    statusBlock.innerText = 'PRONTO';
                                    subText.innerText = 'Mostra il documento nel riquadro';
                                    bloccato = false;
                                    loopScansione();
                                }, 1400);
                            }).catch(() => { bloccato = false; loopScansione(); });
                            return;
                        }
                    }
                }
            }
        } catch (e) {
            console.error(e);
        }

        setTimeout(loopScansione, 15); // Loop a raffica continua senza tempi morti
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
