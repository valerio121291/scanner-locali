from flask import Flask, render_template_string, request, jsonify
from datetime import datetime
import json
import os

app = Flask(__name__)

MEMORIA_FILE = "/tmp/memoria_madre.json"

def inizializza_memoria():
    if not os.path.exists(MEMORIA_FILE):
        with open(MEMORIA_FILE, 'w') as f:
            json.dump({
                "totale_entrati": 0,
                "cronologia": []
            }, f, indent=4)

def salva_in_memoria(esito, eta, data_nascita, sesso_selezionato):
    try:
        inizializza_memoria()
        with open(MEMORIA_FILE, 'r+') as f:
            data = json.load(f)
            
            if esito == "PASSA":
                data["totale_entrati"] += 1
            
            data["cronologia"].append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "esito": esito,
                "eta": eta,
                "data_nascita": data_nascita,
                "sesso_serata": sesso_selezionato
            })
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
        return data
    except Exception as e:
        print(f"Errore scrittura memoria: {e}")
        return None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Madre Matrix v19</title>
    <script src="https://unpkg.com/tesseract.js@5.1.0/dist/tesseract.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #050505; color: white; margin: 0; padding: 10px; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 420px; width: 100%; text-align: center; }
        
        /* Contatore superiore semplificato */
        .dashboard { background: #111; padding: 15px; border-radius: 16px; margin-bottom: 12px; border: 1px solid #222; }
        .counter-val { font-size: 2rem; font-weight: bold; color: #00ffcc; }
        .counter-lbl { font-size: 0.8rem; color: #71717a; text-transform: uppercase; margin-top: 2px; font-weight: bold; }
        
        /* Pannello Regia Selezione Sessi Indipendenti */
        .config-panel { background: #14141b; padding: 12px 15px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #1e1e2d; text-align: left; }
        .config-title { font-size: 0.8rem; color: #00ffcc; font-weight: bold; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.5px; }
        .row-select { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .row-select:last-child { margin-bottom: 0; }
        .row-select label { font-size: 0.95rem; font-weight: 600; color: #e4e4e7; }
        .row-select select { background: #09090b; color: #fff; border: 1px solid #3f3f46; padding: 6px 10px; border-radius: 8px; font-weight: bold; font-size: 0.95rem; outline: none; }
        .select-m { color: #3b82f6 !important; border-color: #1d4ed8 !important; }
        .select-f { color: #ec4899 !important; border-color: #be185d !important; }

        .video-container { position: relative; width: 100%; height: 210px; margin: 0 auto; border-radius: 20px; overflow: hidden; border: 2px solid #333; background: #000; }
        video { width: 100%; height: 100%; object-fit: cover; }
        .mirino { position: absolute; top: 10%; left: 5%; width: 90%; height: 80%; border: 3px solid #00ffcc; border-radius: 14px; pointer-events: none; box-shadow: 0 0 20px rgba(0,255,204,0.15); box-sizing: border-box; z-index: 10; }
        
        .status-box { width: 100%; padding: 20px 0; border-radius: 16px; margin-top: 15px; font-size: 2rem; font-weight: bold; background-color: #0f0f14; border: 2px solid #1e1e24; letter-spacing: 1px; }
        .maggiorenne { background-color: #10b981 !important; border-color: #059669; box-shadow: 0 0 30px rgba(16,185,129,0.6); }
        .minorenne { background-color: #ef4444 !important; border-color: #dc2626; box-shadow: 0 0 30px rgba(239,68,68,0.6); }
        #sub-text { color: #a1a1aa; font-size: 1rem; margin-top: 12px; min-height: 40px; font-weight: 500; }
    </style>
</head>
<body>

<div class="container">
    <div class="dashboard">
        <div id="count-totale" class="counter-val">0</div>
        <div class="counter-lbl">Persone Entrate Stasera</div>
    </div>

    <div class="config-panel">
        <div class="config-title">Configurazione Limiti Serata</div>
        <div class="row-select">
            <label>♂️ Limite Età Uomini:</label>
            <select id="limite-m" class="select-m">
                <option value="16">Over 16</option>
                <option value="18" selected>Over 18</option>
                <option value="20">Over 20</option>
                <option value="21">Over 21</option>
                <option value="23">Over 23</option>
                <option value="25">Over 25</option>
            </select>
        </div>
        <div class="row-select">
            <label>♀️ Limite Età Donne:</label>
            <select id="limite-f" class="select-f">
                <option value="16">Over 16</option>
                <option value="18" selected>Over 18</option>
                <option value="20">Over 20</option>
                <option value="21">Over 21</option>
                <option value="23">Over 23</option>
            </select>
        </div>
    </div>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="mirino"></div>
    </div>

    <div id="status-block" class="status-box">AVVIO...</div>
    <div id="sub-text">Configurazione filtri geometrici...</div>
</div>

<canvas id="processingCanvas" style="display:none;" width="640" height="480"></canvas>

<script>
    const video = document.getElementById('video');
    const processingCanvas = document.getElementById('processingCanvas');
    const statusBlock = document.getElementById('status-block');
    const subText = document.getElementById('sub-text');
    const limiteMSelect = document.getElementById('limite-m');
    const limiteFSelect = document.getElementById('limite-f');
    const pCtx = processingCanvas.getContext('2d', { alpha: false });
    
    let worker = null;
    let bloccato = false;
    let pronto = false;

    async function inizializzaOCR() {
        worker = await Tesseract.createWorker('eng');
        // Filtriamo alla fonte tenendo solo cifre e separatori per una velocità stratosferica
        await worker.setParameters({
            tessedit_char_whitelist: '0123456789/.- ',
            tessedit_pageseg_mode: '11', 
        });
        
        pronto = true;
        statusBlock.innerText = "PRONTO AL VARCO";
        subText.innerText = "Inquadra la data di nascita";
        loopScansione();
    }

    async function startCamera() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "environment", width: { ideal: 640 }, height: { ideal: 480 }, focusMode: { ideal: "continuous" } },
                audio: false
            });
            video.srcObject = stream;
        } catch (err) {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            video.srcObject = stream;
        }
    }

    function applicaFiltroUniversale(imageData) {
        let d = imageData.data;
        for (let i = 0; i < d.length; i += 4) {
            let gray = (0.3 * d[i] + 0.59 * d[i+1] + 0.11 * d[i+2]);
            // Soglia netta per sbiancare lo sfondo e isolare i blocchi numerici neri della data
            let b = (gray > 125) ? 255 : 0;
            d[i] = d[i+1] = d[i+2] = b;
        }
        return imageData;
    }

    async function loopScansione() {
        if (!pronto || bloccato || video.readyState !== video.HAVE_ENOUGH_DATA) {
            setTimeout(loopScansione, 25);
            return;
        }

        let videoW = video.videoWidth;
        let videoH = video.videoHeight;
        
        pCtx.drawImage(video, videoW*0.05, videoH*0.10, videoW*0.90, videoH*0.80, 0, 0, processingCanvas.width, processingCanvas.height);
        let imgData = pCtx.getImageData(0, 0, processingCanvas.width, processingCanvas.height);
        pCtx.putImageData(applicaFiltroUniversale(imgData), 0, 0);
        
        try {
            const { data: { text } } = await worker.recognize(processingCanvas);
            
            // 🔥 NUOVA LOGICA: Pulizia Radicale Isolata
            // Rimuoviamo ogni residuo alfabetico spurio o spazio eccessivo prima di dare in pasto i dati alla matrice
            let stringaNumericaPura = text.replace(/[^0-9\/\-\.]/g, ' ');
            
            // Intercettiamo solo strutture a lunghezza fissa coerenti (2 cifre, separatore, 2 cifre, separatore, 2-4 cifre)
            let dataMatches = stringaNumericaPura.match(/(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{2,4})/g);
            
            if (dataMatches) {
                for (let bloccoData of dataMatches) {
                    let parti = bloccoData.split(/[\/\-\.]/);
                    let giornoGrezzo = parseInt(parti[0]);
                    let mese = parseInt(parti[1]);
                    let annoStr = parti[2];
                    let anno = parseInt(annoStr);
                    
                    let giorno = giornoGrezzo;
                    // Se il giorno è maggiore di 40, applichiamo la decodifica implicita per sapere se la data apparteneva a una donna (Codice Fiscale)
                    let sessoRilevato = "M";
                    if (giornoGrezzo > 40 && giornoGrezzo <= 71) {
                        sessoRilevato = "F";
                        giorno = giornoGrezzo - 40;
                    }

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
                        
                        // Finestra di tolleranza anagrafica biologica
                        if (eta >= 14 && eta <= 75) {
                            bloccato = true;
                            let dataValida = `${giorno.toString().padStart(2,'0')}/${mese.toString().padStart(2,'0')}/${anno}`;
                            
                            // Recupera le soglie separate impostate dalla regia per Maschi e Donne
                            let sogliaM = parseInt(limiteMSelect.value);
                            let sogliaF = parseInt(limiteFSelect.value);
                            
                            // Applica il filtro incrociato a seconda del sesso calcolato dalla data
                            let limiteSelezionato = (sessoRilevato === "M") ? sogliaM : sogliaF;
                            let esitoFinale = (eta >= limiteSelezionato) ? "PASSA" : "RESPINTO";

                            fetch('/salva_scansione', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ data: dataValida, esito: esitoFinale, eta: eta, sesso: sessoRilevato })
                            })
                            .then(res => res.json())
                            .then(data => {
                                document.getElementById('count-totale').innerText = data.totale;

                                if (esitoFinale === 'PASSA') {
                                    statusBlock.className = 'status-box maggiorenne';
                                    statusBlock.innerText = `✔️ ENTRA (${sessoRilevato})`;
                                } else {
                                    statusBlock.className = 'status-box minorenne';
                                    statusBlock.innerText = `❌ BLOCCO (${sessoRilevato})`;
                                }
                                subText.innerHTML = `Data: <b>${dataValida}</b> — Età: <b>${eta} anni</b> (Soglia: Over ${limiteSelezionato})`;
                                
                                try {
                                    let audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                                    let osc = audioCtx.createOscillator();
                                    osc.frequency.setValueAtTime(esitoFinale === 'PASSA' ? 880 : 220, audioCtx.currentTime);
                                    osc.connect(audioCtx.destination);
                                    osc.start(); osc.stop(audioCtx.currentTime + 0.12);
                                } catch(e) {}

                                setTimeout(() => {
                                    statusBlock.className = 'status-box';
                                    statusBlock.innerText = 'PRONTO AL VARCO';
                                    subText.innerText = 'Inquadra la data di nascita';
                                    bloccato = false;
                                    loopScansione();
                                }, 1500);
                            }).catch(() => { bloccato = false; loopScansione(); });
                            return;
                        }
                    }
                }
            }
        } catch (e) { console.error(e); }
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
    req_data = request.get_json()
    if not req_data or 'data' not in req_data:
        return jsonify({'status': 'error'})

    data_str = req_data['data']
    esito = req_data['esito']
    eta = req_data['eta']
    sesso = req_data['sesso']
    
    stato_memoria = salva_in_memoria(esito, eta, data_str, sesso)
    
    return jsonify({
        'status': 'success', 
        'totale': stato_memoria.get("totale_entrati", 0)
    })

if __name__ == '__main__':
    inizializza_memoria()
    app.run(host='0.0.0.0', port=5000, debug=False)
