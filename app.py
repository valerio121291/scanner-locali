from flask import Flask, render_template_string, request, jsonify
from datetime import datetime
import json
import os
import re

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
    <title>Madre Document Context v15</title>
    <script src="https://unpkg.com/tesseract.js@5.1.0/dist/tesseract.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #020202; color: white; margin: 0; padding: 15px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 400px; width: 100%; text-align: center; }
        
        .video-container { position: relative; width: 100%; max-width: 340px; height: 220px; margin: 0 auto; border-radius: 24px; overflow: hidden; border: 3px solid #333; background: #000; }
        video { width: 100%; height: 100%; object-fit: cover; }
        
        /* Box di mira totale: basta infilare il documento qui dentro, fronte visibile */
        .mirino { position: absolute; top: 10%; left: 5%; width: 90%; height: 80%; border: 3px solid #00ffcc; border-radius: 16px; pointer-events: none; box-shadow: 0 0 30px rgba(0,255,204,0.25); box-sizing: border-box; z-index: 10; }
        .oscuratore-top { position: absolute; top: 0; left: 0; width: 100%; height: 10%; background: rgba(0,0,0,0.5); pointer-events: none; z-index: 5; }
        .oscuratore-bottom { position: absolute; top: 90%; left: 0; width: 100%; height: 10%; background: rgba(0,0,0,0.5); pointer-events: none; z-index: 5; }
        
        .status-box { width: 100%; padding: 22px 0; border-radius: 18px; margin-top: 25px; font-size: 2.2rem; font-weight: bold; background-color: #0f0f14; border: 2px solid #1e1e24; transition: all 0.05s ease; letter-spacing: 1px; }
        .maggiorenne { background-color: #10b981 !important; border-color: #059669; box-shadow: 0 0 40px rgba(16,185,129,0.9); }
        .minorenne { background-color: #ef4444 !important; border-color: #dc2626; box-shadow: 0 0 40px rgba(239,68,68,0.9); }
        #sub-text { color: #a1a1aa; font-size: 1.05rem; margin-top: 15px; min-height: 45px; font-weight: 500; }
    </style>
</head>
<body>

<div class="container">
    <h2 style="margin: 0 0 5px 0; font-weight: 900; color: #fff; letter-spacing: -0.5px;">MADRE CONTEXT v15</h2>
    <p style="color: #4b5563; margin: 0 0 15px 0; font-size: 0.85rem; font-weight: 700; text-transform: uppercase;">Analisi Strutturale Standard UE</p>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="oscuratore-top"></div>
        <div class="mirino"></div>
        <div class="oscuratore-bottom"></div>
    </div>

    <div id="status-block" class="status-box">LOG-IN...</div>
    <div id="sub-text">Inquadra il FRONTE del documento nel box</div>
</div>

<canvas id="processingCanvas" style="display:none;" width="640" height="480"></canvas>

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
        worker = await Tesseract.createWorker('eng');
        // Riapriamo il whitelist anche alle lettere per intercettare i punti chiave del documento (es. '3.', 'birth')
        await worker.setParameters({
            tessedit_char_whitelist: '0123456789/.- abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.',
            tessedit_pageseg_mode: '11', 
        });
        
        pronto = true;
        statusBlock.innerText = "PRONTO";
        subText.innerText = "Mostra il fronte del documento";
        loopScansione();
    }

    async function startCamera() {
        try {
            // Ottimizzazione hardware: Forziamo la messa a fuoco continua Macro
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

    // Filtro bilanciato per far risaltare il testo rispetto ai pattern grafici dello sfondo dei documenti
    function applicaFiltroDocumenti(imageData) {
        let d = imageData.data;
        for (let i = 0; i < d.length; i += 4) {
            // Estrazione luminanza bilanciata per abbattere lo sfondo rosa/azzurro delle tessere
            let gray = (0.299 * d[i] + 0.587 * d[i+1] + 0.114 * d[i+2]);
            let b = (gray > 125) ? 255 : 0;
            d[i] = d[i+1] = d[i+2] = b;
        }
        return imageData;
    }

    async function loopScansione() {
        if (!pronto || bloccato || video.readyState !== video.HAVE_ENOUGH_DATA) {
            setTimeout(loopScansione, 30);
            return;
        }

        let videoW = video.videoWidth;
        let videoH = video.videoHeight;
        
        let cropX = videoW * 0.05;
        let cropY = videoH * 0.10;
        let cropW = videoW * 0.90;
        let cropH = videoH * 0.80;

        pCtx.drawImage(video, cropX, cropY, cropW, cropH, 0, 0, processingCanvas.width, processingCanvas.height);
        
        let imgData = pCtx.getImageData(0, 0, processingCanvas.width, processingCanvas.height);
        pCtx.putImageData(applicaFiltroDocumenti(imgData), 0, 0);
        
        try {
            const { data: { text } } = await worker.recognize(processingCanvas);
            
            // Dividiamo il testo estratto in righe per applicare l'algoritmo di analisi contestuale
            let righe = text.toLowerCase().split('\\n');
            
            for (let riga of righe) {
                // 🔎 STRATEGIA DI ANCORAGGIO CONTESTUALE:
                // Se la riga contiene i punti chiave della data di nascita ('3.', 'birth', 'nasc', 'dat')
                // MA non contiene i punti di scadenza/emissione ('4a', '4b', 'scad')
                if ((riga.includes('3.') || riga.includes('birth') || riga.includes('nasc') || riga.includes('dat')) && 
                    !riga.includes('4a') && !riga.includes('4b')) {
                    
                    // Cerchiamo una data in questa riga specifica
                    let match = riga.match(/(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{2,4})/);
                    
                    if (match) {
                        let giorno = parseInt(match[1]);
                        let mese = parseInt(match[2]);
                        let annoStr = match[3];
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
                                        osc.start(); osc.stop(audioCtx.currentTime + 0.1);
                                    } catch(e) {}

                                    setTimeout(() => {
                                        statusBlock.className = 'status-box';
                                        statusBlock.innerText = 'PRONTO';
                                        subText.innerText = 'Mostra il fronte del documento';
                                        bloccato = false;
                                        loopScansione();
                                    }, 1400);
                                }).catch(() => { bloccato = false; loopScansione(); });
                                return;
                            }
                        }
                    }
                }
            }
            
            // FALLBACK IMMEDIATO: Se l'ancora contestuale è sbiadita, cerca comunque una data logica ovunque
            let pulito = text.replace(/[^0-9\/\-\.]/g, '');
            let fallbackMatch = pulito.match(/(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{2,4})/);
            if (fallbackMatch && !bloccato) {
                let giorno = parseInt(fallbackMatch[1]);
                let mese = parseInt(fallbackMatch[2]);
                let annoStr = fallbackMatch[3];
                let anno = parseInt(annoStr);
                
                if (annoStr.length === 2) { anno = (anno <= (new Date().getFullYear() % 100)) ? (2000 + anno) : (1900 + anno); }
                if (giorno >= 1 && giorno <= 31 && mese >= 1 && mese <= 12) {
                    let oggi = new Date();
                    let eta = oggi.getFullYear() - anno;
                    if (oggi.getMonth() + 1 < mese || (oggi.getMonth() + 1 === mese && oggi.getDate() < giorno)) { eta--; }
                    
                    if (eta >= 18 && eta <= 60) { // Finestra di sicurezza per evitare scadenze
                        bloccato = true;
                        let dataValida = `${giorno.toString().padStart(2,'0')}/${mese.toString().padStart(2,'0')}/${anno}`;
                        fetch('/salva_scansione', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ data: dataValida })
                        })
                        .then(res => res.json())
                        .then(data => {
                            statusBlock.className = 'status-box maggiorenne';
                            statusBlock.innerText = '✔️ PASSA';
                            subText.innerHTML = `Data: <b>${dataValida}</b> — Età: <b>${data.eta} anni</b>`;
                            setTimeout(() => {
                                statusBlock.className = 'status-box'; statusBlock.innerText = 'PRONTO'; bloccato = false; loopScansione();
                            }, 1400);
                        }).catch(() => { bloccato = false; loopScansione(); });
                        return;
                    }
                }
            }
            
        } catch (e) {
            console.error(e);
        }

        setTimeout(loopScansione, 25);
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
