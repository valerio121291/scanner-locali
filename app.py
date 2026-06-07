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
    <title>Madre Laser Zone Scanner</title>
    <script src="https://unpkg.com/tesseract.js@5.1.0/dist/tesseract.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #050505; color: white; margin: 0; padding: 15px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 400px; width: 100%; text-align: center; }
        
        /* Contenitore video */
        .video-container { position: relative; width: 100%; max-width: 340px; height: 220px; margin: 0 auto; border-radius: 20px; overflow: hidden; border: 3px solid #1a1a1a; background: #000; }
        video { width: 100%; height: 100%; object-fit: cover; }
        
        /* Il mirino ora rappresenta l'UNICA zona che l'IA leggerà davvero */
        .mirino { position: absolute; top: 35%; left: 5%; width: 90%; height: 30%; border: 3px solid #00ffcc; border-radius: 8px; pointer-events: none; box-shadow: 0 0 20px rgba(0,255,204,0.4); box-sizing: border-box; }
        .oscuratore-top { position: absolute; top: 0; left: 0; width: 100%; height: 35%; background: rgba(0,0,0,0.6); pointer-events: none; }
        .oscuratore-bottom { position: absolute; top: 65%; left: 0; width: 100%; height: 35%; background: rgba(0,0,0,0.6); pointer-events: none; }
        
        .status-box { width: 100%; padding: 20px 0; border-radius: 16px; margin-top: 20px; font-size: 2rem; font-weight: bold; background-color: #121212; border: 2px solid #222; transition: all 0.1s ease; letter-spacing: 0.5px; }
        .maggiorenne { background-color: #2eb85c !important; color: white; border-color: #1f7a3e; box-shadow: 0 0 30px rgba(46,184,92,0.7); }
        .minorenne { background-color: #e55353 !important; color: white; border-color: #a33939; box-shadow: 0 0 30px rgba(229,83,83,0.7); }
        #sub-text { color: #aaa; font-size: 0.95rem; margin-top: 12px; min-height: 40px; line-height: 1.4; }
        
        /* Canvas di debug visibile solo per regolazione ottimale dello zoom */
        #debugCanvas { width: 100%; max-width: 340px; height: auto; border: 1px solid #333; margin-top: 10px; border-radius: 8px; background: #000; display: none; }
    </style>
</head>
<body>

<div class="container">
    <h2 style="margin: 0 0 5px 0; font-weight: 800; color: #fff;">MADRE TARGET v10</h2>
    <p style="color: #666; margin: 0 0 15px 0; font-size: 0.85rem;">Metti la data di nascita REALE dentro il rettangolo chiaro</p>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="oscuratore-top"></div>
        <div class="mirino"></div>
        <div class="oscuratore-bottom"></div>
    </div>

    <div id="status-block" class="status-box">ACCENSIONE...</div>
    <div id="sub-text">Inizializzazione lenti digitali...</div>
    
    <canvas id="debugCanvas"></canvas>
</div>

<canvas id="processingCanvas" style="display:none;" width="400" height="120"></canvas>

<script>
    const video = document.getElementById('video');
    const processingCanvas = document.getElementById('processingCanvas');
    const debugCanvas = document.getElementById('debugCanvas');
    const statusBlock = document.getElementById('status-block');
    const subText = document.getElementById('sub-text');
    const pCtx = processingCanvas.getContext('2d');
    const dCtx = debugCanvas.getContext('2d');
    
    let worker = null;
    let bloccato = false;
    let pronto = false;

    async function inizializzaOCR() {
        statusBlock.innerText = "AVVIO MOTORE...";
        worker = await Tesseract.createWorker('eng'); // Carichiamo solo numeri inglesi, fulmineo
        
        await worker.setParameters({
            tessedit_char_whitelist: '0123456789/.- ',
        });
        
        pronto = true;
        statusBlock.innerText = "PRONTO AL VARCO";
        subText.innerText = "Inquadra SOLO la riga con la data di nascita";
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

    // Filtro di binarizzazione estrema per distruggere ombre e sfondi colorati dei documenti
    function applicaFiltroOCR(imageData) {
        let d = imageData.data;
        for (let i = 0; i < d.length; i += 4) {
            // Estraiamo la luminanza dando priorità al verde e rosso per eliminare le patine bluastre delle tessere
            let v = (0.3 * d[i] + 0.59 * d[i+1] + 0.11 * d[i+2]);
            // Soglia aggressiva: se il pixel è scuro diventa nero pesto, se è chiaro diventa bianco candido
            v = (v > 110) ? 255 : 0;
            d[i] = d[i+1] = d[i+2] = v;
        }
        return imageData;
    }

    async function loopScansione() {
        if (!pronto || bloccato || video.readyState !== video.HAVE_ENOUGH_DATA) {
            setTimeout(loopScansione, 50);
            return;
        }

        // 🎯 RITAGLIO GEOMETRICO (ROI): Prendiamo solo la porzione centrale del video (corrispondente al mirino)
        // Evitiamo di scansionare il 70% del frame inutile.
        let videoW = video.videoWidth;
        let videoH = video.videoHeight;
        
        let cropX = videoW * 0.05;
        let cropY = videoH * 0.35;
        let cropW = videoW * 0.90;
        let cropH = videoH * 0.30;

        // Disegniamo il ritaglio sul piccolo canvas di elaborazione
        pCtx.drawImage(video, cropX, cropY, cropW, cropH, 0, 0, processingCanvas.width, processingCanvas.height);
        
        // Applichiamo il filtro binarizzante ad alto stacco
        let imgData = pCtx.getImageData(0, 0, processingCanvas.width, processingCanvas.height);
        pCtx.putImageData(applicaFiltroOCR(imgData), 0, 0);
        
        try {
            // L'OCR analizza pochissimi pixel puliti in bianco e nero: calcolo immediato
            const { data: { text } } = await worker.recognize(processingCanvas);
            
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
                        
                        // Accettiamo solo età sensate da locale per scartare scadenze ed emissioni arbitrarie
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
                                    statusBlock.innerText = 'PRONTO AL VARCO';
                                    subText.innerText = 'Inquadra SOLO la riga con la data di nascita';
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

        setTimeout(loopScansione, 40);
    }

    startCamera();
    inizializzaOCR();
</script>

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
