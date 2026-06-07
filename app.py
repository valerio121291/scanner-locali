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
        print(f"Errore salvataggio memoria: {e}")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Madre Scanner Ultra</title>
    <script src="https://unpkg.com/tesseract.js@5.1.0/dist/tesseract.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #0b0b0b; color: white; margin: 0; padding: 15px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 400px; width: 100%; text-align: center; }
        .video-container { position: relative; width: 100%; max-width: 340px; height: 220px; margin: 0 auto; border-radius: 20px; overflow: hidden; border: 3px solid #222; background: #000; }
        video { width: 100%; height: 100%; object-fit: cover; }
        .mirino { position: absolute; top: 20%; left: 5%; width: 90%; height: 60%; border: 3px solid #00ffcc; border-radius: 12px; pointer-events: none; box-shadow: 0 0 15px rgba(0,255,204,0.3); }
        .status-box { width: 100%; padding: 22px 0; border-radius: 16px; margin-top: 20px; font-size: 1.9rem; font-weight: bold; background-color: #161616; border: 2px solid #252525; transition: all 0.15s ease; }
        .maggiorenne { background-color: #2eb85c !important; color: white; border-color: #1f7a3e; box-shadow: 0 0 30px rgba(46,184,92,0.6); }
        .minorenne { background-color: #e55353 !important; color: white; border-color: #a33939; box-shadow: 0 0 30px rgba(229,83,83,0.6); }
        #sub-text { color: #aaa; font-size: 0.95rem; margin-top: 12px; min-height: 45px; line-height: 1.4; }
    </style>
</head>
<body>

<div class="container">
    <h2 style="margin: 0 0 5px 0; font-weight: 800; letter-spacing: -0.5px;">MADRE SCANNER v5</h2>
    <p style="color: #666; margin: 0 0 20px 0; font-size: 0.9rem;">Ottimizzato per CIE, Patente e Tessera Sanitaria</p>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="mirino"></div>
    </div>

    <div id="status-block" class="status-box">CARICAMENTO...</div>
    <div id="sub-text">Inizializzazione filtri ottici...</div>
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
        worker = await Tesseract.createWorker('ita+eng');
        
        // Whitelist estesa per catturare etichette testuali e numeri di data con punti o barre
        await worker.setParameters({
            tessedit_char_whitelist: '0123456789/.-ABCDEFGHIJKLMOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz() ',
        });
        pronto = true;
        statusBlock.innerText = "PRONTO AL VARCO";
        subText.innerText = "Inquadra il documento fermo a 15-20 cm";
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

    // Filtro di elaborazione grafica per rendere i caratteri super-leggibili all'OCR
    function applicaFiltroContrasto(imageData) {
        let d = imageData.data;
        for (let i = 0; i < d.length; i += 4) {
            // Conversione in scala di grigi ad alta precisione
            let r = d[i], g = d[i+1], b = d[i+2];
            let v = (0.2126 * r + 0.7152 * g + 0.0722 * b);
            
            // Soglia di binarizzazione drastica (effetto bianco e nero puro)
            v = (v > 115) ? 255 : 0;
            d[i] = d[i+1] = d[i+2] = v;
        }
        return imageData;
    }

    async function loopScansione() {
        if (!pronto || bloccato || video.readyState !== video.HAVE_ENOUGH_DATA) {
            setTimeout(loopScansione, 100);
            return;
        }

        // 1. Disegna il fotogramma sul canvas
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // 2. Estrai l'immagine e applica l'aumento di contrasto hardware prima dell'OCR
        let imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        ctx.putImageData(applicaFiltroContrasto(imgData), 0, 0);
        
        try {
            const { data: { text } } = await worker.recognize(canvas);
            let testoPulito = text.toUpperCase().replace(/\s+/g, ' ');

            // Regex flessibile totale che intercetta: GG/MM/AAAA, GG.MM.AAAA, GG/MM/AA e varianti spaziate
            // Copre CIE (punti), TS (barre a 4 cifre) e Patente (barre a 2 cifre dell'item 3.)
            let regexData = /(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{2,4})/;
            let match = testoPulito.match(regexData);
            
            // Verifichiamo se c'è un'ancora di testo dei tuoi documenti per evitare falsi positivi casuali
            let haAncora = testoPulito.includes("NASCITA") || 
                           testoPulito.includes("BIRTH") || 
                           testoPulito.includes("DATA") || 
                           testoPulito.includes("COMM") || // Comune di... (CIE)
                           testoPulito.includes("ROMA") || 
                           testoPulito.includes("PATENTE") ||
                           /3\.\s\d/.test(testoPulito); // Struttura della Patente (3. 12/12/91)

            if (match && haAncora) {
                let giorno = parseInt(match[1]);
                let mese = parseInt(match[2]);
                let annoGrezzo = match[3];
                let anno = parseInt(annoGrezzo);
                
                // Ricostruzione intelligente dell'anno se a 2 cifre (Patente)
                if (annoGrezzo.length === 2) {
                    let annoCorrenteCorto = new Date().getFullYear() % 100;
                    anno = (anno <= annoCorrenteCorto) ? (2000 + anno) : (1900 + anno);
                }
                
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
                            subText.innerHTML = `Data: <b>${dataRilevata}</b><br>Età: <b>${data.eta} anni</b>`;
                            playSuono('ok');
                        } else {
                            statusBlock.className = 'status-box minorenne';
                            statusBlock.innerText = '❌ MINORENNE';
                            subText.innerHTML = `Data: <b>${dataRilevata}</b><br>Età: <b>${data.eta} anni</b>`;
                            playSuono('no');
                        }

                        // Reset rapido di 2 secondi, ottimizzato per la fila all'ingresso
                        setTimeout(() => {
                            statusBlock.className = 'status-box';
                            statusBlock.innerText = 'PRONTO AL VARCO';
                            subText.innerText = 'Inquadra il documento fermo a 15-20 cm';
                            bloccato = false;
                            loopScansione();
                        }, 2000);
                    }).catch(() => { bloccato = false; loopScansione(); });
                    return;
                }
            }
        } catch (e) {
            console.error(e);
        }

        // Frequenza di campionamento tarata per non surriscaldare il telefono ma essere istantanea
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
    
    data_nascita = datetime(anno, mese, girono) if 'girono' in locals() else datetime(anno, mese, giorno)
    oggi = datetime.now()
    eta = oggi.year - data_nascita.year - ((oggi.month, oggi.day) < (data_nascita.month, data_nascita.day))
    
    esito = "MAGGIORENNE" if eta >= 18 else "MINORENNE"
    salva_in_memoria(esito, eta, data_str)
    
    return jsonify({'status': 'success', 'esito': esito, 'eta': eta})

if __name__ == '__main__':
    inizializza_memoria()
    app.run(host='0.0.0.0', port=5000, debug=False)
