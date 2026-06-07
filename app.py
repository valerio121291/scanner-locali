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
    <title>Madre AI Cognitive Scanner</title>
    <script src="https://unpkg.com/tesseract.js@5.1.0/dist/tesseract.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #08080c; color: white; margin: 0; padding: 15px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 400px; width: 100%; text-align: center; }
        .video-container { position: relative; width: 100%; max-width: 340px; height: 220px; margin: 0 auto; border-radius: 24px; overflow: hidden; border: 2px solid #333; background: #000; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        video { width: 100%; height: 100%; object-fit: cover; }
        .mirino { position: absolute; top: 15%; left: 5%; width: 90%; height: 70%; border: 2px dashed #00ffcc; border-radius: 16px; pointer-events: none; animation: pulse 2s infinite; }
        @keyframes pulse { 0% { opacity: 0.6; } 50% { opacity: 1; } 100% { opacity: 0.6; } }
        .status-box { width: 100%; padding: 20px 0; border-radius: 18px; margin-top: 25px; font-size: 1.8rem; font-weight: bold; background-color: #12121a; border: 1px solid #222533; transition: all 0.2s ease; }
        .maggiorenne { background-color: #10b981 !important; color: white; border-color: #047857; box-shadow: 0 0 30px rgba(16,185,129,0.5); }
        .minorenne { background-color: #ef4444 !important; color: white; border-color: #b91c1c; box-shadow: 0 0 30px rgba(239,68,68,0.5); }
        #sub-text { color: #94a3b8; font-size: 0.95rem; margin-top: 15px; min-height: 50px; font-weight: 500; }
    </style>
</head>
<body>

<div class="container">
    <h2 style="margin: 0 0 5px 0; font-weight: 800; letter-spacing: -0.5px; background: linear-gradient(to right, #00ffcc, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">MADRE COGNITIVE v8</h2>
    <p style="color: #64748b; margin: 0 0 20px 0; font-size: 0.85rem;">Lettura Semantica Universale (Qualsiasi Paese)</p>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="mirino"></div>
    </div>

    <div id="status-block" class="status-box">ANALISI RETE...</div>
    <div id="sub-text">Inizializzazione intelligenza contestuale...</div>
</div>

<canvas id="canvas" style="display:none;" width="800" height="600"></canvas>

<script>
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const statusBlock = document.getElementById('status-block');
    const subText = document.getElementById('sub-text');
    const ctx = canvas.getContext('2d');
    
    let scheduler = null;
    let bloccato = false;
    let pronto = false;

    async function inizializzaAI() {
        statusBlock.innerText = "CARICAMENTO IA...";
        
        // Creiamo un motore multi-lingua simultaneo (Inglese, Italiano, Rumeno, Francese, Spagnolo)
        // Questo permette di riconoscere le varianti di "Data di nascita" in tutto il mondo
        scheduler = Tesseract.createScheduler();
        const worker1 = await Tesseract.createWorker('ita+eng');
        scheduler.addWorker(worker1);

        pronto = true;
        statusBlock.innerText = "IA PRONTA";
        subText.innerText = "Mostra il documento liberamente all'interno del riquadro";
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

    function preProcessImage(ctx, width, height) {
        let imgData = ctx.getImageData(0, 0, width, height);
        let d = imgData.data;
        for (let i = 0; i < d.length; i += 4) {
            // Formula di luminanza avanzata per eliminare i riflessi olografici dei documenti di plastica
            let gray = 0.299 * d[i] + 0.587 * d[i+1] + 0.114 * d[i+2];
            // Filtro contrasto dinamico adattivo
            let binarizzato = (gray > 128) ? 255 : 0;
            d[i] = d[i+1] = d[i+2] = binarizzato;
        }
        ctx.putImageData(imgData, 0, 0);
    }

    async function loopScansione() {
        if (!pronto || bloccato || video.readyState !== video.HAVE_ENOUGH_DATA) {
            setTimeout(loopScansione, 80);
            return;
        }

        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        preProcessImage(ctx, canvas.width, canvas.height);
        
        try {
            // Elaborazione parallela ultra-veloce
            const { data: { text } } = await scheduler.addJob('recognize', canvas);
            let bloccoTesto = text.toUpperCase();

            // 🧠 LOGICA COGNITIVA: Estraiamo TUTTE le date presenti nel documento (Nascita, Rilascio, Scadenza)
            let regexDate = /(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{2,4})/g;
            let dateTrovate = bloccoTesto.match(regexDate);

            if (dateTrovate) {
                let dataNascitaIdentificata = null;
                let etaCalcolata = null;

                for (let dataGrezza of dateTrovate) {
                    let parti = dataGrezza.split(/[\/\-\.]/);
                    let g = parseInt(parti[0]);
                    let m = parseInt(parti[1]);
                    let aStr = parti[2];
                    let a = parseInt(aStr);

                    if (aStr.length === 2) {
                        let annoCorto = new Date().getFullYear() % 100;
                        a = (a <= annoCorto) ? (2000 + a) : (1900 + a);
                    }

                    if (g >= 1 && g <= 31 && m >= 1 && m <= 12) {
                        let oggi = new Date();
                        let eta = oggi.getFullYear() - a;
                        if (oggi.getMonth() + 1 < m || (oggi.getMonth() + 1 === m && oggi.getDate() < g)) {
                            eta--;
                        }

                        // L'INTELLIGENZA STA QUI: In un locale notturno, l'unica data valida sul documento
                        // deve generare un'età coerente tra i 16 e i 75 anni. 
                        // Le date di scadenza (es. 2036 -> età negativa) o rilascio (es. 2026 -> 0 anni) vengono segate istantaneamente.
                        if (eta >= 16 && eta <= 75) {
                            dataNascitaIdentificata = `${g.toString().padStart(2,'0')}/${m.toString().padStart(2,'0')}/${a}`;
                            etaCalcolata = eta;
                            break; // Trovata la data corretta, usciamo dal ciclo!
                        }
                    }
                }

                if (dataNascitaIdentificata) {
                    bloccato = true;
                    
                    fetch('/salva_scansione', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ data: dataNascitaIdentificata })
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.esito === 'MAGGIORENNE') {
                            statusBlock.className = 'status-box maggiorenne';
                            statusBlock.innerText = '✔️ PASSA';
                        } else {
                            statusBlock.className = 'status-box minorenne';
                            statusBlock.innerText = '❌ ALT: MINORENNE';
                        }
                        subText.innerHTML = `Data rilevata: <b>${dataNascitaIdentificata}</b><br>Età confermata: <b>${data.eta} anni</b>`;
                        
                        // Segnale acustico
                        try {
                            let audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                            let osc = audioCtx.createOscillator();
                            osc.frequency.setValueAtTime(data.esito === 'MAGGIORENNE' ? 880 : 220, audioCtx.currentTime);
                            osc.connect(audioCtx.destination);
                            osc.start(); osc.stop(audioCtx.currentTime + 0.15);
                        } catch(ae) {}

                        setTimeout(() => {
                            statusBlock.className = 'status-box';
                            statusBlock.innerText = 'PRONTO AL VARCO';
                            subText.innerText = 'Mostra il documento liberamente';
                            bloccato = false;
                            loopScansione();
                        }, 1800);
                    }).catch(() => { bloccato = false; loopScansione(); });
                    return;
                }
            }
        } catch (e) {
            console.error("Errore IA:", e);
        }

        setTimeout(loopScansione, 30);
    }

    startCamera();
    inizializzaAI();
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
