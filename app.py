from flask import Flask, render_template_string, request, jsonify
from datetime import datetime
import json
import os

app = Flask(__name__)

MEMORIA_FILE = "/tmp/memoria_madre.json"

def inizializza_memoria():
    if not os.path.exists(MEMORIA_FILE):
        with open(MEMORIA_FILE, 'w') as f:
            json.dump({"scansioni_totali": 0, "maggiorenni": 0, "minorenni": 0, "uomini": 0, "donne": 0, "cronologia": []}, f, indent=4)

def salva_in_memoria(esito, eta, sesso, data_nascita):
    try:
        inizializza_memoria()
        with open(MEMORIA_FILE, 'r+') as f:
            data = json.load(f)
            data["scansioni_totali"] += 1
            if esito == "APPROVATO":
                if sesso == "M": data["uomini"] = data.get("uomini", 0) + 1
                else: data["donne"] = data.get("donne", 0) + 1
            
            data["cronologia"].append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "esito": esito,
                "sesso": sesso,
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
    <title>Madre Gatekeeper Pro</title>
    <script src="https://unpkg.com/tesseract.js@5.1.0/dist/tesseract.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #0b0b0b; color: white; margin: 0; padding: 10px; display: flex; flex-direction: column; align-items: center; justify-content: start; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 400px; width: 100%; text-align: center; }
        
        /* Pannello di Controllo Limiti Serata */
        .config-panel { background: #161616; padding: 12px; border-radius: 14px; margin-bottom: 15px; border: 1px solid #252525; display: flex; justify-content: space-around; align-items: center; }
        .config-group { display: flex; flex-direction: column; align-items: center; }
        .config-group label { font-size: 0.75rem; color: #888; text-transform: uppercase; margin-bottom: 4px; font-weight: bold; }
        .config-group select { background: #222; color: #00ffcc; border: 1px solid #333; padding: 6px 10px; border-radius: 8px; font-weight: bold; font-size: 1rem; outline: none; }
        
        .video-container { position: relative; width: 100%; max-width: 340px; height: 200px; margin: 0 auto; border-radius: 20px; overflow: hidden; border: 3px solid #333; background: #000; }
        video { width: 100%; height: 100%; object-fit: cover; }
        .mirino { position: absolute; top: 30%; left: 5%; width: 90%; height: 40%; border: 3px solid #00ffcc; border-radius: 12px; pointer-events: none; box-shadow: 0 0 20px rgba(0,255,204,0.4); }
        
        .status-box { width: 100%; padding: 25px 0; border-radius: 18px; margin-top: 15px; font-size: 2rem; font-weight: 900; background-color: #161616; border: 2px solid #252525; transition: all 0.15s ease; letter-spacing: -0.5px; }
        .approvato { background-color: #2eb85c !important; color: white; border-color: #1f7a3e; box-shadow: 0 0 35px rgba(46,184,92,0.7); }
        .respinto { background-color: #e55353 !important; color: white; border-color: #a33939; box-shadow: 0 0 35px rgba(229,83,83,0.7); }
        #sub-text { color: #aaa; font-size: 1rem; margin-top: 12px; min-height: 50px; line-height: 1.4; }
    </style>
</head>
<body>

<div class="container">
    <h3 style="margin: 5px 0 10px 0; font-weight: 800; letter-spacing: -0.5px; color: #fff;">MADRE GATEKEEPER v8</h3>
    
    <div class="config-panel">
        <div class="config-group">
            <label>🚹 Limite Ragazzi</label>
            <select id="limite-uomini">
                <option value="18" selected>18+</option>
                <option value="19">19+</option>
                <option value="20">20+</option>
                <option value="21">21+</option>
                <option value="22">22+</option>
                <option value="23">23+</option>
                <option value="24">24+</option>
                <option value="25">25+</option>
            </select>
        </div>
        <div style="width: 1px; height: 30px; background: #333;"></div>
        <div class="config-group">
            <label>🚺 Limite Ragazze</label>
            <select id="limite-donne">
                <option value="18" selected>18+</option>
                <option value="19">19+</option>
                <option value="20">20+</option>
                <option value="21">21+</option>
                <option value="22">22+</option>
                <option value="23">23+</option>
                <option value="24">24+</option>
                <option value="25">25+</option>
            </select>
        </div>
    </div>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="mirino"></div>
    </div>

    <div id="status-block" class="status-box">AVVIO...</div>
    <div id="sub-text">Configurazione sensori d'ingresso...</div>
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
        statusBlock.innerText = "CARICAMENTO...";
        worker = await Tesseract.createWorker('ita+eng');
        await worker.setParameters({
            tessedit_char_whitelist: '0123456789/.-ABCDEFGHIJKLMOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz() ',
        });
        pronto = true;
        statusBlock.innerText = "PRONTO AL VARCO";
        subText.innerText = "Inquadra la data di nascita";
        loopScansione();
    }

    function playSuono(tipo) {
        try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            let osc = audioCtx.createOscillator();
            let gain = audioCtx.createGain();
            if (tipo === 'ok') {
                osc.type = 'sine'; osc.frequency.setValueAtTime(880, audioCtx.currentTime);
                gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.start(); osc.stop(audioCtx.currentTime + 0.15);
            } else {
                osc.type = 'sawtooth'; osc.frequency.setValueAtTime(180, audioCtx.currentTime);
                gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.start(); osc.stop(audioCtx.currentTime + 0.3);
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
            // Soglia adattiva ottimizzata per aumentare la nitidezza dei caratteri piccoli da lontano
            v = (v > 120) ? 255 : 0;
            d[i] = d[i+1] = d[i+2] = v;
        }
        return imageData;
    }

    function calcolaEta(giorno, mese, anno) {
        let dataNascita = new Date(anno, mese - 1, girono=giorno);
        let oggi = new Date();
        let eta = oggi.getFullYear() - dataNascita.getFullYear();
        let m = oggi.getMonth() - dataNascita.getMonth();
        if (m < 0 || (m === 0 && oggi.getDate() < dataNascita.getDate())) {
            eta--;
        }
        return eta;
    }

    async function loopScansione() {
        if (!pronto || bloccato || video.readyState !== video.HAVE_ENOUGH_DATA) {
            setTimeout(loopScansione, 100);
            return;
        }

        // Ritaglio e zoom digitale migliorati
        let sorgenteX = video.videoWidth * 0.12;
        let sorgenteY = video.videoHeight * 0.32;
        let sorgenteLarghezza = video.videoWidth * 0.76;
        let sorgenteAltezza = video.videoHeight * 0.36;

        ctx.drawImage(video, sorgenteX, sorgenteY, sorgenteLarghezza, sorgenteAltezza, 0, 0, canvas.width, canvas.height);
        
        let imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        ctx.putImageData(applicaFiltroContrasto(imgData), 0, 0);
        
        try {
            const { data: { text } } = await worker.recognize(canvas);
            let testoPulito = text.toUpperCase().replace(/\s+/g, ' ');

            let regexData = /(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{2,4})/g;
            let match;
            
            while ((match = regexData.exec(testoPulito)) !== null) {
                let giorno = parseInt(match[1]);
                let mese = parseInt(match[2]);
                let annoGrezzo = match[3];
                let anno = parseInt(annoGrezzo);
                
                if (annoGrezzo.length === 2) {
                    let annoCorrenteCorto = new Date().getFullYear() % 100;
                    anno = (anno <= annoCorrenteCorto) ? (2000 + anno) : (1900 + anno);
                }
                
                if (giorno >= 1 && giorno <= 31 && mese >= 1 && mese <= 12 && anno > 1930 && anno <= new Date().getFullYear()) {
                    
                    let etaCalcolata = calcolaEta(giorno, mese, anno);
                    
                    // Filtro logico per scartare scadenze/rilasci assurdi
                    if (etaCalcolata >= 14 && etaCalcolata <= 90) {
                        
                        let indiceData = match.index;
                        let contestoPrecedente = testoPulito.substring(Math.max(0, indiceData - 40), indiceData);
                        let contestoSuccessivo = testoPulito.substring(indiceData, Math.min(testoPulito.length, indiceData + 40));
                        
                        let eScadenzaORilascio = contestoPrecedente.includes("SCADENZA") || contestoPrecedente.includes("EXPIRY") ||
                                                 contestoPrecedente.includes("RILASCIO") || contestoPrecedente.includes("ISSUING") ||
                                                 contestoPrecedente.includes("EMISSIONE") || contestoSuccessivo.includes("SCADENZA") ||
                                                 contestoSuccessivo.includes("EXPIRY");
                        
                        if (!eScadenzaORilascio) {
                            bloccato = true;
                            
                            // DETERMINAZIONE INTELLIGENTE DEL SESSO (Analisi stringhe CIE e Codice Fiscale)
                            let sesso = "M"; // Default di sicurezza
                            
                            // Se nel documento trova "F" isolata vicino a SEX/SESS o se rileva la matematica del codice fiscale femminile
                            if (testoPulito.includes("SESS F") || testoPulito.includes("SEX F") || giorno > 40) {
                                sesso = "F";
                            }
                            
                            // Se il giorno estratto è > 40 (Tessera Sanitaria Donna), correggiamo il giorno reale per visualizzarlo bene
                            let giornoMostrato = giorno;
                            if (giorno > 40) {
                                giornoMostrato = giorno - 40;
                                sesso = "F";
                            }

                            let dataRilevata = `${giornoMostrato.toString().padStart(2,'0')}/${mese.toString().padStart(2,'0')}/${anno}`;
                            
                            // Recupera i limiti impostati in tempo reale dai menu a tendina
                            let limiteUomini = parseInt(document.getElementById('limite-uomini').value);
                            let limiteDonne = parseInt(document.getElementById('limite-donne').value);
                            let limiteAttuale = (sesso === "M") ? limiteUomini : limiteDonne;
                            
                            let esitoIngresso = (etaCalcolata >= limiteAttuale) ? "APPROVATO" : "RESPINTO";
                            
                            fetch('/salva_scansione', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ data: dataRilevata, sesso: sesso, eta: etaCalcolata, esito: esitoIngresso })
                            })
                            .then(res => res.json())
                            .then(data => {
                                if (data.esito === 'APPROVATO') {
                                    statusBlock.className = 'status-box approvato';
                                    statusBlock.innerText = '✔️ ENTRA';
                                    subText.innerHTML = `Genere: <b>${sesso === "M" ? "UOMO" : "DONNA"}</b> (Limite: ${limiteAttuale}+)<br>Nato il: <b>${dataRilevata}</b> (${data.eta} anni)`;
                                    playSuono('ok');
                                } else {
                                    statusBlock.className = 'status-box respinto';
                                    statusBlock.innerText = '❌ NO INGRESSO';
                                    subText.innerHTML = `Genere: <b>${sesso === "M" ? "UOMO" : "DONNA"}</b> (Serve: ${limiteAttuale}+)<br>Nato il: <b>${dataRilevata}</b> (${data.eta} anni)`;
                                    playSuono('no');
                                }

                                setTimeout(() => {
                                    statusBlock.className = 'status-box';
                                    statusBlock.innerText = 'PRONTO AL VARCO';
                                    subText.innerText = 'Inquadra la sezione Data di Nascita';
                                    bloccato = false;
                                    loopScansione();
                                }, 2500);
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
    if not data:
        return jsonify({'status': 'error'})

    data_str = data.get('data')
    sesso = data.get('sesso', 'M')
    eta = data.get('eta')
    esito = data.get('esito', 'RESPINTO')
    
    salva_in_memoria(esito, eta, sesso, data_str)
    return jsonify({'status': 'success', 'esito': esito, 'eta': eta})

if __name__ == '__main__':
    inizializza_memoria()
    app.run(host='0.0.0.0', port=5000, debug=False)
