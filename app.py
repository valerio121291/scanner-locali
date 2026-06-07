from flask import Flask, render_template_string, request, jsonify
from datetime import datetime, timedelta
import json
import os

app = Flask(__name__)

MEMORIA_FILE = "/tmp/memoria_madre.json"

def inizializza_memoria():
    if not os.path.exists(MEMORIA_FILE):
        with open(MEMORIA_FILE, 'w') as f:
            json.dump({
                "presenti_uomini": 0,
                "presenti_donne": 0,
                "capienza_massima": 500, # Puoi cambiarla a piacimento
                "scansioni_totali": 0,
                "cronologia": []
            }, f, indent=4)

def leggi_memoria():
    inizializza_memoria()
    try:
        with open(MEMORIA_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"presenti_uomini": 0, "presenti_donne": 0, "capienza_massima": 500, "scansioni_totali": 0, "cronologia": []}

def scrivi_memoria(data):
    try:
        with open(MEMORIA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Errore scrittura memoria: {e}")

@app.route('/')
def home():
    memoria = leggi_memoria()
    return render_template_string(HTML_TEMPLATE, 
                                  uomini=memoria.get("presenti_uomini", 0), 
                                  donne=memoria.get("presenti_donne", 0),
                                  massima=memoria.get("capienza_massima", 500))

@app.route('/azione_varco', methods=['POST'])
def azione_varco():
    req = request.get_json()
    azione = req.get('azione') # 'entra', 'esce_m', 'esce_f'
    data_str = req.get('data', '')
    sesso = req.get('sesso', 'M')
    eta = req.get('eta', 0)
    esito = req.get('esito', 'RESPINTO')
    
    memoria = leggi_memoria()
    ora_attuale = datetime.now()
    
    if azione == 'entra':
        # --- CONTROLLO DOPPIA SCANSIONE (ANTI-FURBI) ---
        for s in reversed(memoria["cronologia"]):
            # Se la scansione è avvenuta meno di 3 minuti fa (180 secondi)
            ora_scansione = datetime.strptime(s["timestamp"], "%Y-%m-%d %H:%M:%S")
            if ora_attuale - ora_scansione < timedelta(seconds=180):
                if s["data_nascita"] == data_str and s["sesso"] == sesso:
                    return jsonify({
                        'status': 'furbetto', 
                        'messaggio': 'ATTENZIONE: Documento già usato negli ultimi 3 min!'
                    })
        
        # --- CONTROLLO CAPIENZA ---
        totale_dentro = memoria["presenti_uomini"] + memoria["presenti_donne"]
        if totale_dentro >= memoria["capienza_massima"]:
            return jsonify({'status': 'pieno', 'messaggio': 'BLOCCATO: LOCALE PIENO!'})
        
        # Se approvato, aggiorna i contatori interni
        if esito == "APPROVATO":
            if sesso == "M":
                memoria["presenti_uomini"] += 1
            else:
                memoria["presenti_donne"] += 1
                
        memoria["scansioni_totali"] += 1
        memoria["cronologia"].append({
            "timestamp": ora_attuale.strftime("%Y-%m-%d %H:%M:%S"),
            "esito": esito,
            "sesso": sesso,
            "eta": eta,
            "data_nascita": data_str
        })
        
    elif azione == 'esce_m':
        if memoria["presenti_uomini"] > 0:
            memoria["presenti_uomini"] -= 1
            
    elif azione == 'esce_f':
        if memoria["presenti_donne"] > 0:
            memoria["presenti_donne"] -= 1

    scrivi_memoria(memoria)
    return jsonify({
        'status': 'success', 
        'uomini': memoria["presenti_uomini"], 
        'donne': memoria["presenti_donne"],
        'totale': memoria["presenti_uomini"] + memoria["presenti_donne"]
    })

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Madre Controllo Accessi</title>
    <script src="https://unpkg.com/tesseract.js@5.1.0/dist/tesseract.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #060606; color: white; margin: 0; padding: 10px; display: flex; flex-direction: column; align-items: center; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 400px; width: 100%; text-align: center; }
        
        .config-panel { background: #121212; padding: 10px; border-radius: 14px; margin-bottom: 10px; border: 1px solid #222; display: flex; justify-content: space-around; align-items: center; }
        .config-group { display: flex; flex-direction: column; align-items: center; }
        .config-group label { font-size: 0.7rem; color: #777; text-transform: uppercase; margin-bottom: 2px; font-weight: bold; }
        .config-group select { background: #1a1a1a; color: #00ffcc; border: 1px solid #333; padding: 5px 8px; border-radius: 6px; font-weight: bold; font-size: 0.95rem; outline: none; }
        
        .video-container { position: relative; width: 100%; max-width: 340px; height: 180px; margin: 0 auto; border-radius: 16px; overflow: hidden; border: 2px solid #222; background: #000; }
        video { width: 100%; height: 100%; object-fit: cover; }
        .mirino { position: absolute; top: 25%; left: 5%; width: 90%; height: 50%; border: 2px solid #00ffcc; border-radius: 10px; pointer-events: none; box-shadow: 0 0 15px rgba(0,255,204,0.3); }
        
        /* Bottone Torcia integrato nel Box Video */
        .btn-torcia { position: absolute; bottom: 8px; right: 8px; background: rgba(0,0,0,0.7); border: 1px solid #00ffcc; color: #00ffcc; padding: 6px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: bold; cursor: pointer; }
        
        .status-box { width: 100%; padding: 20px 0; border-radius: 16px; margin-top: 12px; font-size: 1.8rem; font-weight: 900; background-color: #121212; border: 2px solid #222; transition: all 0.15s ease; }
        .approvato { background-color: #2eb85c !important; color: white; border-color: #1f7a3e; box-shadow: 0 0 25px rgba(46,184,92,0.6); }
        .respinto { background-color: #e55353 !important; color: white; border-color: #a33939; box-shadow: 0 0 25px rgba(229,83,83,0.6); }
        .allarme { background-color: #f9b115 !important; color: black; border-color: #b8820b; box-shadow: 0 0 25px #f9b115; }
        
        #sub-text { color: #aaa; font-size: 0.9rem; margin-top: 8px; min-height: 40px; line-height: 1.3; }
        
        /* SEZIONE CONTATORI E CONTROLLO DEFLUSSO */
        .stats-panel { width: 100%; background: #121212; border: 1px solid #222; border-radius: 16px; margin-top: 10px; padding: 12px; box-sizing: border-box; }
        .counters { display: flex; justify-content: space-around; margin-bottom: 10px; }
        .counter-box { font-size: 0.9rem; color: #aaa; }
        .counter-box span { display: block; font-size: 1.6rem; font-weight: bold; color: #fff; margin-top: 2px; }
        .c-uomini { color: #39f !important; }
        .c-donne { color: #f69 !important; }
        
        .btn-deflusso-container { display: flex; gap: 10px; }
        .btn-out { flex: 1; background: #222; border: 1px solid #444; color: #fff; padding: 10px 0; border-radius: 10px; font-weight: bold; font-size: 0.85rem; cursor: pointer; transition: background 0.1s; }
        .btn-out:active { background: #333; }
    </style>
</head>
<body>

<div class="container">
    <h3 style="margin: 2px 0 8px 0; font-weight: 800; color: #fff; font-size: 1.1rem;">MADRE CONTROL ACCESS v9</h3>
    
    <div class="config-panel">
        <div class="config-group">
            <label>🚹 Limite Uomini</label>
            <select id="limite-uomini">
                <option value="18" selected>18+</option><option value="20">20+</option><option value="23">23+</option><option value="25">25+</option>
            </select>
        </div>
        <div style="width: 1px; height: 25px; background: #222;"></div>
        <div class="config-group">
            <label>🚺 Limite Donne</label>
            <select id="limite-donne">
                <option value="18" selected>18+</option><option value="20">20+</option><option value="23">23+</option><option value="25">25+</option>
            </select>
        </div>
    </div>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="mirino"></div>
        <button id="btn-torcia" class="btn-torcia" onclick="toggleTorcia()">🔦 TORCIA OFF</button>
    </div>

    <div id="status-block" class="status-box">AVVIO...</div>
    <div id="sub-text">Inizializzazione...</div>

    <div class="stats-panel">
        <div class="counters">
            <div class="counter-box">UOMINI DENTRO<span id="count-uomini" class="c-uomini">{{ uomini }}</span></div>
            <div class="counter-box">DONNE DENTRO<span id="count-donne" class="c-donne">{{ donne }}</span></div>
            <div class="counter-box">TOTALE / MAX<span id="count-totale">{{ uomini + donne }} / {{ massima }}</span></div>
        </div>
        <div class="btn-deflusso-container">
            <button class="btn-out" onclick="registraUscita('esce_m')">🚹 ESCE 1 UOMO</button>
            <button class="btn-out" onclick="registraUscita('esce_f')">🚺 ESCE 1 DONNA</button>
        </div>
    </div>
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
    let videoTrack = null;
    let torciaAttiva = false;

    async function inizializzaOCR() {
        statusBlock.innerText = "CARICAMENTO...";
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
            } else if (tipo === 'furbetto') {
                osc.type = 'sawtooth'; osc.frequency.setValueAtTime(350, audioCtx.currentTime);
                gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.start(); osc.stop(audioCtx.currentTime + 0.4);
            } else {
                osc.type = 'sawtooth'; osc.frequency.setValueAtTime(180, audioCtx.currentTime);
                gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.start(); osc.stop(audioCtx.currentTime + 0.25);
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
            videoTrack = stream.getVideoTracks()[0];
        } catch (err) {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            video.srcObject = stream;
            videoTrack = stream.getVideoTracks()[0];
        }
    }

    // --- TORCIA ON/OFF FORZATA ---
    async function toggleTorcia() {
        if (!videoTrack) return;
        try {
            const capabilities = videoTrack.getCapabilities();
            if (capabilities.torch) {
                torciaAttiva = !torciaAttiva;
                await videoTrack.applyConstraints({ advanced: [{ torch: torciaAttiva }] });
                document.getElementById('btn-torcia').innerText = torciaAttiva ? "🔦 TORCIA ON" : "🔦 TORCIA OFF";
            } else {
                alert("Il flash non è supportato su questo browser/dispositivo.");
            }
        } catch (e) { console.error(e); }
    }

    // --- ACCELERAZIONE HARDWARE IMMAGINE PER CARTA IDENTITÀ (CIE) ---
    function applicaFiltroContrasto(imageData) {
        let d = imageData.data;
        for (let i = 0; i < d.length; i += 4) {
            let v = (0.2126 * d[i] + 0.7152 * d[i+1] + 0.0722 * d[i+2]);
            // Soglia più netta per staccare le scritte CIE dallo sfondo azzurro/rosa della plastica
            v = (v > 110) ? 255 : 0;
            d[i] = d[i+1] = d[i+2] = v;
        }
        return imageData;
    }

    function calcolaEta(giorno, mese, anno) {
        let dataNascita = new Date(anno, mese - 1, giorno);
        let oggi = new Date();
        let eta = oggi.getFullYear() - dataNascita.getFullYear();
        let m = oggi.getMonth() - dataNascita.getMonth();
        if (m < 0 || (m === 0 && oggi.getDate() < dataNascita.getDate())) { eta--; }
        return eta;
    }

    function aggiornaInterfacciaContatori(data) {
        document.getElementById('count-uomini').innerText = data.uomini;
        document.getElementById('count-donne').innerText = data.donne;
        document.getElementById('count-totale').innerText = `${data.totale} / 500`;
    }

    function registraUscita(tipoAzione) {
        fetch('/azione_varco', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ azione: tipoAzione })
        })
        .then(res => res.json())
        .then(data => { if(data.status === 'success') aggiornaInterfacciaContatori(data); });
    }

    async function loopScansione() {
        if (!pronto || bloccato || video.readyState !== video.HAVE_ENOUGH_DATA) {
            setTimeout(loopScansione, 100);
            return;
        }

        // Taglio centrato e pulito
        let sorgenteX = video.videoWidth * 0.12;
        let sorgenteY = video.videoHeight * 0.28;
        let sorgenteLarghezza = video.videoWidth * 0.76;
        let sorgenteAltezza = video.videoHeight * 0.40;

        ctx.drawImage(video, sorgenteX, sorgenteY, sorgenteLarghezza, sorgenteAltezza, 0, 0, canvas.width, canvas.height);
        
        let imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        ctx.putImageData(applicaFiltroContrasto(imgData), 0, 0);
        
        try {
            const { data: { text } } = await worker.recognize(canvas);
            let testoPulito = text.toUpperCase().replace(/\s+/g, ' ');

            // Accetta sia punti che barre (Ottimizzato per CIE e Patente simultaneamente)
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
                
                if (giorno >= 1 && giorno <= 31 && mese >= 1 && mese <= 12 && anno > 1930) {
                    let etaCalcolata = calcolaEta(giorno, mese, anno);
                    
                    if (etaCalcolata >= 14 && etaCalcolata <= 90) {
                        let indiceData = match.index;
                        let contestoPrecedente = testoPulito.substring(Math.max(0, indiceData - 40), indiceData);
                        let contestoSuccessivo = testoPulito.substring(indiceData, Math.min(testoPulito.length, indiceData + 40));
                        
                        let eScadenzaORilascio = contestoPrecedente.includes("SCADENZA") || contestoPrecedente.includes("EXPIRY") ||
                                                 contestoPrecedente.includes("RILASCIO") || contestoPrecedente.includes("ISSUING") ||
                                                 contestoPrecedente.includes("EMISSIONE") || contestoSuccessivo.includes("SCADENZA");
                        
                        // Velocizzazione CIE: basta una parola d'aggancio minima per renderlo fulmineo
                        let haAncoraCIE = contestoPrecedente.includes("NASCITA") || contestoPrecedente.includes("BIRTH") || 
                                           contestoPrecedente.includes("DATA") || contestoPrecedente.includes("ROMA") || 
                                           contestoPrecedente.includes("RM") || contestoPrecedente.includes("COMM") ||
                                           /3\.\s\d/.test(testoPulito);

                        if (!eScadenzaORilascio && haAncoraCIE) {
                            bloccato = true;
                            
                            let sesso = "M";
                            if (testoPulito.includes("SESS F") || testoPulito.includes("SEX F") || giorno > 40) { sesso = "F"; }
                            
                            let giornoMostrato = giorno;
                            if (giorno > 40) { giornoMostrato = giorno - 40; sesso = "F"; }

                            let dataRilevata = `${giornoMostrato.toString().padStart(2,'0')}/${mese.toString().padStart(2,'0')}/${anno}`;
                            
                            let limiteUomini = parseInt(document.getElementById('limite-uomini').value);
                            let limiteDonne = parseInt(document.getElementById('limite-donne').value);
                            let limiteAttuale = (sesso === "M") ? limiteUomini : limiteDonne;
                            
                            let esitoIngresso = (etaCalcolata >= limiteAttuale) ? "APPROVATO" : "RESPINTO";
                            
                            fetch('/azione_varco', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ 
                                    azione: 'entra', data: dataRilevata, sesso: sesso, eta: etaCalcolata, esito: esitoIngresso 
                                })
                            })
                            .then(res => res.json())
                            .then(data => {
                                if (data.status === 'furbetto') {
                                    statusBlock.className = 'status-box allarme';
                                    statusBlock.innerText = '⚠️ DOPPIONE';
                                    subText.innerHTML = `<span style="color:#ffcc00;font-weight:bold;">${data.messaggio}</span>`;
                                    playSuono('furbetto');
                                } else if (data.status === 'pieno') {
                                    statusBlock.className = 'status-box respinto';
                                    statusBlock.innerText = '❌ LOCALE PIENO';
                                    subText.innerText = data.messaggio;
                                    playSuono('no');
                                } else {
                                    aggiornaInterfacciaContatori(data);
                                    if (esitoIngresso === 'APPROVATO') {
                                        statusBlock.className = 'status-box approvato';
                                        statusBlock.innerText = '✔️ PASSA';
                                        subText.innerHTML = `Genere: <b>${sesso === "M" ? "UOMO" : "DONNA"}</b> (Limite: ${limiteAttuale}+)<br>Nato il: <b>${dataRilevata}</b> (${etaCalcolata} anni)`;
                                        playSuono('ok');
                                    } else {
                                        statusBlock.className = 'status-box respinto';
                                        statusBlock.innerText = '❌ RESPINT0';
                                        subText.innerHTML = `Genere: <b>${sesso === "M" ? "UOMO" : "DONNA"}</b> (Serve: ${limiteAttuale}+)<br>Nato il: <b>${dataRilevata}</b> (${etaCalcolata} anni)`;
                                        playSuono('no');
                                    }
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
        } catch (e) { console.error(e); }

        setTimeout(loopScansione, 100);
    }

    startCamera();
    inizializzaOCR();
</script>

</body>
</html>
"""

if __name__ == '__main__':
    inizializza_memoria()
    app.run(host='0.0.0.0', port=5000, debug=False)
