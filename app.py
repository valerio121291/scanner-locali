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
    <title>Madre Flash Scanner v12</title>
    <script src="https://unpkg.com/tesseract.js@5.1.0/dist/tesseract.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #020202; color: white; margin: 0; padding: 15px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 400px; width: 100%; text-align: center; }
        
        .video-container { position: relative; width: 100%; max-width: 340px; height: 220px; margin: 0 auto; border-radius: 24px; overflow: hidden; border: 3px solid #333; background: #000; }
        video { width: 100%; height: 100%; object-fit: cover; }
        
        /* Box laser mirato strettissimo per agganciare al volo */
        .mirino { position: absolute; top: 40%; left: 10%; width: 80%; height: 20%; border: 3px solid #00ffcc; border-radius: 8px; pointer-events: none; box-shadow: 0 0 30px rgba(0,255,204,0.6); box-sizing: border-box; z-index: 10; }
        .oscuratore-top { position: absolute; top: 0; left: 0; width: 100%; height: 40%; background: rgba(0,0,0,0.75); pointer-events: none; z-index: 5; }
        .oscuratore-bottom { position: absolute; top: 60%; left: 0; width: 100%; height: 40%; background: rgba(0,0,0,0.75); pointer-events: none; z-index: 5; }
        
        .status-box { width: 100%; padding: 22px 0; border-radius: 18px; margin-top: 25px; font-size: 2.2rem; font-weight: bold; background-color: #0f0f14; border: 2px solid #1e1e24; transition: all 0.05s ease; letter-spacing: 1px; }
        .maggiorenne { background-color: #10b981 !important; border-color: #059669; box-shadow: 0 0 40px rgba(16,185,129,0.9); }
        .minorenne { background-color: #ef4444 !important; border-color: #dc2626; box-shadow: 0 0 40px rgba(239,68,68,0.9); }
        #sub-text { color: #a1a1aa; font-size: 1.05rem; margin-top: 15px; min-height: 45px; font-weight: 500; }
    </style>
</head>
<body>

<div class="container">
    <h2 style="margin: 0 0 5px 0; font-weight: 900; color: #fff; letter-spacing: -0.5px;">MADRE FLASH v12</h2>
    <p style="color: #52525b; margin: 0 0 15px 0; font-size: 0.85rem; font-weight: 700; text-transform: uppercase;">Aggancio Istantaneo HD</p>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="oscuratore-top"></div>
        <div class="mirino"></div>
        <div class="oscuratore-bottom"></div>
    </div>

    <div id="status-block" class="status-box">AVVIO...</div>
    <div id="sub-text">Caricamento scanner istantaneo...</div>
</div>

<canvas id="processingCanvas" style="display:none;" width="550" height="130"></canvas>

<script>
    const video = document.getElementById('video');
    const processingCanvas = document.getElementById('processingCanvas');
    const statusBlock = document.getElementById('status-block');
    const subText = document.getElementById('sub-text');
    const pCtx = processingCanvas.getContext('2d', { alpha: false }); // Disabilitiamo l'alpha per velocizzare il rendering della GPU
    
    let worker = null;
    let bloccato = false;
    let pronto = false;

    async function inizializzaOCR() {
        worker = await Tesseract.createWorker('eng');
        await worker.setParameters({
            tessedit_char_whitelist: '0123456789/.- ',
            tessedit_pageseg_mode: '7', // Forza Tesseract a trattare il box come una singola riga di testo (velocità moltiplicata x3)
        });
        
        pronto = true;
        statusBlock.innerText = "PRONTO";
        subText.innerText = "Piazza la data di nascita nel rettangolo verde";
        loopScansione();
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

    // Convertitore di contrasto istantaneo ad alto frame-rate
    function applicaFiltroFlash(imageData) {
        let d = imageData.data;
        for (let i = 0; i < d.length; i += 4) {
            let gray = (d[i] + d[i+1] + d[i+2]) / 3;
            // Soglia spinta per separare nettamente l'inchiostro dalla plastica riflettente
            let b = (gray > 115) ? 255 : 0;
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
        
        // Calcolo millimetrico dell'area utile (Box centrale 80% larghezza, 20% altezza)
        let cropX = videoW * 0.10;
        let cropY = videoH * 0.40;
        let cropW = videoW * 0.80;
        let cropH = videoH * 0.20;

        pCtx.drawImage(video, cropX, cropY, cropW, cropH, 0, 0, processingCanvas.width, processingCanvas.height);
        
        let imgData = pCtx.getImageData(0, 0, processingCanvas.width, processingCanvas.height);
        pCtx.putImageData(applicaFiltroFlash(imgData), 0, 0);
        
        try {
            const { data: { text } } = await worker.recognize(processingCanvas);
            
            // Estrazione numerica pulita immediata
            let pulito = text.replace(/[^0-9\/\-\.]/g, '');
            let matches = pulito.match(/(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{2,4})/);
            
            if (matches) {
                let giorno = parseInt(matches[1]);
                let mese = parseInt(matches[2]);
                let annoStr = matches[3];
                let anno = parseInt(annoStr);
                
                if (annoStr.length === 2) {
                    anno = (anno <= (new Date().getFullYear() % 100)) ? (2000 + anno) : (1900 + anno);
                }
                
                if (giorno >= 1 && giorno <= 31 && mese >= 1 && mese <= 12) {
                    let oggi = new Date();
                    let eta = oggi.getFullYear() - anno;
                    if (oggi.getMonth() + 1 < mese || (oggi.getMonth() + 1 === mese && oggi.getDate() < giorno)) {
                        eta--;
                    }
                    
                    // Discriminazione immediata di scadenze/emissioni
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
                                subText.innerText = "Piazza la data di nascita nel rettangolo verde";
                                bloccato = false;
                                loopScansione();
                            }, 1300); // Reset rapido a 1.3 secondi per smaltire la fila fuori
                        }).catch(() => { bloccato = false; loopScansione(); });
                        return;
                    }
                }
            }
        } catch (e) {
            console.error(e);
        }

        setTimeout(loopScansione, 25); // Frequenza di campionamento schiacciata al minimo ritardo fisico
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
