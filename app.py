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
    <title>Madre Scanner Blindato</title>
    <script src="https://unpkg.com/tesseract.js@5.1.0/dist/tesseract.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #0b0b0b; color: white; margin: 0; padding: 15px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 400px; width: 100%; text-align: center; }
        .video-container { position: relative; width: 100%; max-width: 340px; height: 240px; margin: 0 auto; border-radius: 20px; overflow: hidden; border: 3px solid #333; background: #000; }
        video { width: 100%; height: 100%; object-fit: cover; }
        .mirino { position: absolute; top: 35%; left: 10%; width: 80%; height: 30%; border: 3px solid #00ffcc; border-radius: 12px; pointer-events: none; box-shadow: 0 0 20px rgba(0,255,204,0.5); }
        .status-box { width: 100%; padding: 22px 0; border-radius: 16px; margin-top: 20px; font-size: 1.9rem; font-weight: bold; background-color: #161616; border: 2px solid #252525; transition: all 0.15s ease; }
        .maggiorenne { background-color: #2eb85c !important; color: white; border-color: #1f7a3e; box-shadow: 0 0 30px rgba(46,184,92,0.6); }
        .minorenne { background-color: #e55353 !important; color: white; border-color: #a33939; box-shadow: 0 0 30px rgba(229,83,83,0.6); }
        #sub-text { color: #aaa; font-size: 0.95rem; margin-top: 12px; min-height: 45px; }
    </style>
</head>
<body>

<div class="container">
    <h2 style="margin: 0 0 5px 0; font-weight: 800; letter-spacing: -0.5px;">MADRE SECURE v7</h2>
    <p style="color: #666; margin: 0 0 20px 0; font-size: 0.9rem;">Filtro anti-scadenza e anti-rilascio attivo</p>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="mirino"></div>
    </div>

    <div id="status-block" class="status-box">CARICAMENTO...</div>
    <div id="sub-text">Inizializzazione barriere di sicurezza...</div>
</div>

<canvas id="canvas" style="display:none;" width="800" height="600"></canvas>

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
        worker = await Tesseract.createWorker('ita+eng');
        await worker.setParameters({
            tessedit_char_whitelist: '0123456789/.-ABCDEFGHIJKLMOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz() ',
        });
        pronto = true;
        statusBlock.innerText = "PRONTO AL VARCO";
        subText.innerText = "Inquadra la sezione Data di Nascita";
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
                video: { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 }, focusMode: "continuous" },
                audio: false
            });
            video.srcObject = stream;
        } catch (err) {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            video.srcObject = stream;
        }
    }

    function applicaFiltroContrasto(imageData) {
        let d = imageData.data;
        for (let i = 0; i < d.length; i += 4) {
            let v = (0.2126 * d[i] + 0.7152 * d[i+1] + 0.0722 * d[i+2]);
            v = (v > 125) ? 255 : 0;
            d[i] = d[i+1] = d[i+2] = v;
        }
        return imageData;
    }

    // Calcola l'età al volo sul telefono per verificare la verosimiglianza della data
    function validaEtaLogica(giorno, mese, anno) {
        if (anno <= 1930 || anno > new Date().getFullYear()) return false;
        let dataNascita = new Date(anno, mese - 1, giorno);
        let oggi = new Date();
        let eta = oggi.getFullYear() - dataNascita.getFullYear();
        let m = oggi.getMonth() - dataNascita.getMonth();
        if (m < 0 || (m === 0 && oggi.getDate() < dataNascita.getDate())) {
            eta--;
        }
        // Una data di nascita valida all'ingresso deve generare un'età coerente (tra 14 e 90 anni)
        // Se genera 4 o 5 anni, è palesemente una data di rilascio!
        return (eta >= 14 && eta <= 90);
    }

    async function loopScansione() {
        if (!pronto || bloccato || video.readyState !== video.HAVE_ENOUGH_DATA) {
            setTimeout(loopScansione, 100);
            return;
        }

        let sorgenteX = video.videoWidth * 0.15;
        let sorgenteY = video.videoHeight * 0.35;
        let sorgenteLarghezza = video.videoWidth * 0.70;
        let sorgenteAltezza = video.videoHeight * 0.30;

        ctx.drawImage(video, sorgenteX, sorgenteY, sorgenteLarghezza, sorgenteAltezza, 0, 0, canvas.width, canvas.height);
        
        let imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        ctx.putImageData(applicaFiltroContrasto(imgData), 0, 0);
        
        try {
            const { data: { text } } = await worker.recognize(canvas);
            let testoPulito = text.toUpperCase().replace(/\s+/g, ' ');

            // Troviamo tutte le possibili date presenti nel riquadro
            let regexData globale = /(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{2,4})/g;
            let match;
            
            while ((match = regexData_globale.exec(testoPulito)) !== null) {
                let giorno = parseInt(match[1]);
                let mese = parseInt(match[2]);
                let annoGrezzo = match[3];
                let anno = parseInt(annoGrezzo);
                
                if (annoGrezzo.length === 2) {
                    let annoCorrenteCorto = new Date().getFullYear() % 100;
                    anno = (anno <= annoCorrenteCorto) ? (2000 + anno) : (1900 + anno);
                }
                
                // 1. Controllo di coerenza temporale sui mesi e giorni
                if (giorno >= 1 && giorno <= 31 && mese >= 1 && mese <= 12) {
                    
                    // 2. FILTRO LOGICO DI VEROSIMIGLIANZA
                    if (validaEtaLogica(giorno, mese, anno)) {
                        
                        // 3. VERIFICA DEL CONTESTO (Evitiamo le parole vietate intorno alla data)
                        let indiceData = match.index;
                        // Prendiamo un pezzetto di testo prima e dopo la data per studiare il contesto
                        let contestoPrecedente = testoPulito.substring(Math.max(0, indiceData - 40), indiceData);
                        let contestoSuccessivo = testoPulito.substring(indiceData, Math.min(testoPulito.length, indiceData + 40));
                        
                        let eScadenzaORilascio = contestoPrecedente.includes("SCADENZA") || contestoPrecedente.includes("EXPIRY") ||
                                                 contestoPrecedente.includes("RILASCIO") || contestoPrecedente.includes("ISSUING") ||
                                                 contestoPrecedente.includes("EMISSIONE") || contestoSuccessivo.includes("SCADENZA") ||
                                                 contestoSuccessivo.includes("EXPIRY");
                        
                        if (!eScadenzaORilascio) {
                            // Se la data ha superato i controlli logici e non è circondata da parole tossiche, è quella giusta!
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
                                    subText.innerHTML = `Data Nascita: <b>${dataRilevata}</b><br>Età: <b>${data.eta} anni</b>`;
                                    playSuono('ok');
                               } else {
                                    statusBlock.className = 'status-box minorenne';
                                    statusBlock.innerText = '❌ MINORENNE';
                                    subText.innerHTML = `Data Nascita: <b>${dataRilevata}</b><br>Età: <b>${data.eta} anni</b>`;
                                    playSuono('no');
                                }

                                setTimeout(() => {
                                    statusBlock.className = 'status-box';
                                    statusBlock.innerText = 'PRONTO AL VARCO';
                                    subText.innerText = 'Inquadra la sezione Data di Nascita';
                                    bloccato = false;
                                    loopScansione();
                                }, 2200);
                            }).catch(() => { bloccato = false; loopScansione(); });
                            return;
                        }
                    }
                }
            }
        } catch (e) {
            console.error(e);
        }

        setTimeout(loopScansione, 100);
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
    eta = oggi.year - data_nascita.year - ((oggi.month, obesity) < (data_nascita.month, data_nascita.day)) if 'obesity' in locals() else oggi.year - data_nascita.year - ((oggi.month, oggi.day) < (data_nascita.month, data_nascita.day))
    
    esito = "MAGGIORENNE" if eta >= 18 else "MINORENNE"
    salva_in_memoria(esito, eta, data_str)
    
    return jsonify({'status': 'success', 'esito': esito, 'eta': eta})

if __name__ == '__main__':
    inizializza_memoria()
    app.run(host='0.0.0.0', port=5000, debug=False)
