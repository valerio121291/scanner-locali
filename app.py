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
                "uomini_dentro": 0,
                "donne_dentro": 0,
                "scansioni_totali": 0, 
                "maggiorenni": 0, 
                "minorenni": 0, 
                "cronologia": []
            }, f, indent=4)

def salva_in_memoria(esito, eta, data_nascita, sesso, nome, cognome):
    try:
        inizializza_memoria()
        with open(MEMORIA_FILE, 'r+') as f:
            data = json.load(f)
            data["scansioni_totali"] += 1
            
            if esito == "PASSA":
                if sesso == "M":
                    data["uomini_dentro"] = data.get("uomini_dentro", 0) + 1
                else:
                    data["donne_dentro"] = data.get("donne_dentro", 0) + 1
                data["maggiorenni"] += 1
            else:
                data["minorenni"] += 1
            
            data["cronologia"].append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "esito": esito,
                "eta": eta,
                "data_nascita": data_nascita,
                "sesso": sesso,
                "nome": nome,
                "cognome": cognome
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
    <title>Madre Identity v18</title>
    <script src="https://unpkg.com/tesseract.js@5.1.0/dist/tesseract.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #050505; color: white; margin: 0; padding: 10px; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 420px; width: 100%; text-align: center; }
        
        /* Dashboard superiore */
        .dashboard { display: flex; justify-content: space-between; background: #111; padding: 12px; border-radius: 16px; margin-bottom: 12px; border: 1px solid #222; }
        .stat { flex: 1; text-align: center; }
        .stat-val { font-size: 1.6rem; font-weight: bold; color: #fff; }
        .stat-lbl { font-size: 0.75rem; color: #71717a; text-transform: uppercase; margin-top: 2px; }
        .stat-val.uomini { color: #3b82f6; }
        .stat-val.donne { color: #ec4899; }
        
        /* Box Dati Anagrafici Rilevati */
        .identity-box { background: #0f172a; border: 1px solid #1e293b; padding: 8px 12px; border-radius: 12px; margin-bottom: 12px; text-align: left; font-size: 0.9rem; display: flex; justify-content: space-between; }
        .id-field { color: #94a3b8; }
        .id-val { font-weight: bold; color: #f8fafc; text-transform: uppercase; }

        /* Menu selezione limite serata */
        .config-box { background: #14141b; padding: 10px 15px; border-radius: 14px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; border: 1px solid #1e1e2d; }
        .config-box label { font-size: 0.9rem; font-weight: 600; color: #a1a1aa; }
        .config-box select { background: #09090b; color: #00ffcc; border: 1px solid #3f3f46; padding: 6px 12px; border-radius: 8px; font-weight: bold; font-size: 1rem; outline: none; }

        .video-container { position: relative; width: 100%; height: 200px; margin: 0 auto; border-radius: 20px; overflow: hidden; border: 2px solid #333; background: #000; }
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
        <div class="stat" style="border-right: 1px solid #222;">
            <div id="count-uomini" class="stat-val uomini">0</div>
            <div class="stat-lbl">♂️ Uomini</div>
        </div>
        <div class="stat" style="border-right: 1px solid #222;">
            <div id="count-donne" class="stat-val donne">0</div>
            <div class="stat-lbl">♀️ Donne</div>
        </div>
        <div class="stat">
            <div id="count-totale" class="stat-val">0</div>
            <div class="stat-lbl">Tot Entrati</div>
        </div>
    </div>

    <div class="identity-box">
        <div><span class="id-field">Cognome:</span> <span id="id-cognome" class="id-val">---</span></div>
        <div><span class="id-field">Nome:</span> <span id="id-nome" class="id-val">---</span></div>
    </div>

    <div class="config-box">
        <label for="limite-eta">Soglia Ingresso Serata:</label>
        <select id="limite-eta">
            <option value="16">Filtro Over 16</option>
            <option value="18" selected>Filtro Over 18</option>
            <option value="20">Filtro Over 20</option>
            <option value="21">Filtro Over 21</option>
        </select>
    </div>

    <div class="video-container">
        <video id="video" autoplay playsinline muted></video>
        <div class="mirino"></div>
    </div>

    <div id="status-block" class="status-box">AVVIO...</div>
    <div id="sub-text">Inizializzazione scanner...</div>
</div>

<canvas id="processingCanvas" style="display:none;" width="640" height="480"></canvas>

<script>
    const video = document.getElementById('video');
    const processingCanvas = document.getElementById('processingCanvas');
    const statusBlock = document.getElementById('status-block');
    const subText = document.getElementById('sub-text');
    const limiteSelect = document.getElementById('limite-eta');
    const pCtx = processingCanvas.getContext('2d', { alpha: false });
    
    // Database dei Nomi Italiani per la determinazione del sesso tramite Anagrafica sussidiaria
    const NOMI_MASCHILI = ['MARCO','ALESSANDRO','GIUSEPPE','FRANCESCO','GIOVANNI','ROBERTO','STEFANO','ANDREA','LUCA','MATTEO','DAVIDE','VALERIO','ANTONIO','MICHELE','LORENZO','FEDERICO','EDOARDO','SIMONE','CHRISTIAN','ALBERTO'];
    const NOMI_FEMMINILI = ['MARIA','ANNA','GIULIA','FRANCESCA','CHIARA','SARA','SILVIA','ELENA','GIORGIA','MARTINA','ALICE','FEDERICA','ROBERTA','ELISA','ALESSIA','VALENTINA','EMMA','AURORA','MATILDE','SOFIA'];

    let worker = null;
    let bloccato = false;
    let pronto = false;

    async function inizializzaOCR() {
        worker = await Tesseract.createWorker('eng');
        // Whitelist completa per catturare stringhe alfanumeriche, date e lettere di genere
        await worker.setParameters({
            tessedit_char_whitelist: '0123456789/.- abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
            tessedit_pageseg_mode: '11', 
        });
        
        pronto = true;
        statusBlock.innerText = "PRONTO AL VARCO";
        subText.innerText = "Inquadra il fronte del documento";
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
            let b = (gray > 115) ? 255 : 0;
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
            
            // 1. Isola le date presenti
            let testoPulito = text.replace(/[^0-9\/\-\. ]/g, ' ');
            let matches = testoPulito.match(/(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{2,4})/g);
            
            if (matches) {
                for (let matchStr of matches) {
                    let separators = matchStr.match(/[\/\-\.]/g);
                    if (separators && separators[0] !== separators[1]) continue;

                    let parti = matchStr.split(/[\/\-\.]/);
                    let giornoGrezzo = parseInt(parti[0]);
                    let mese = parseInt(parti[1]);
                    let annoStr = parti[2];
                    let anno = parseInt(annoStr);
                    
                    let sesso = "M"; 
                    let giorno = giornoGrezzo;

                    // A. Riconoscimento Genere da algoritmo matematico Codice Fiscale
                    if (giornoGrezzo > 40 && giornoGrezzo <= 71) {
                        sesso = "F";
                        giorno = giornoGrezzo - 40;
                    }
                    
                    // B. Riconoscimento Genere da lettere esplicite sul documento M / F
                    let paroleDoc = text.toUpperCase().split(/[^A-Z]/);
                    if (paroleDoc.includes('F')) sesso = "F";
                    if (paroleDoc.includes('M')) sesso = "M";

                    // C. Riconoscimento Genere Cross-Check da Nome Proprio (Anagrafica)
                    let nomeRilevato = "---";
                    let cognomeRilevato = "---";
                    
                    for (let parola of paroleDoc) {
                        if (parola.length > 2) {
                            if (NOMI_MASCHILI.includes(parola)) { sesso = "M"; nomeRilevato = parola; break; }
                            if (NOMI_FEMMINILI.includes(parola)) { sesso = "F"; nomeRilevato = parola; break; }
                        }
                    }

                    // Tentativo di estrazione del primo blocco di testo utile per valorizzare il cognome a schermo
                    let righeFiltrate = text.toUpperCase().split('\\n').map(r => r.trim()).filter(r => r.length > 3 && !r.match(/[0-9]/));
                    if (righeFiltrate.length > 0) cognomeRilevato = righeFiltrate[0].split(' ')[0];
                    if (righeFiltrate.length > 1 && nomeRilevato === "---") nomeRilevato = righeFiltrate[1].split(' ')[0];

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
                        
                        // Finestra generazionale anagrafica
                        if (eta >= 14 && eta <= 75) {
                            bloccato = true;
                            let dataValida = `${giorno.toString().padStart(2,'0')}/${mese.toString().padStart(2,'0')}/${anno}`;
                            let limiteImpostato = parseInt(limiteSelect.value);
                            let esitoFinale = (eta >= limiteImpostato) ? "PASSA" : "RESPINTO";

                            // Aggiorna subito i campi d'identità visivi sulla regia
                            document.getElementById('id-nome').innerText = nomeRilevato;
                            document.getElementById('id-cognome').innerText = cognomeRilevato;

                            fetch('/salva_scansione', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ 
                                    data: dataValida, sesso: sesso, esito: esitoFinale, eta: eta,
                                    nome: nomeRilevato, cognome: cognomeRilevato
                                })
                            })
                            .then(res => res.json())
                            .then(data => {
                                document.getElementById('count-uomini').innerText = data.uomini;
                                document.getElementById('count-donne').innerText = data.donne;
                                document.getElementById('count-totale').innerText = data.uomini + data.donne;

                                if (esitoFinale === 'PASSA') {
                                    statusBlock.className = 'status-box maggiorenne';
                                    statusBlock.innerText = `✔️ ENTRA (${sesso})`;
                                } else {
                                    statusBlock.className = 'status-box minorenne';
                                    statusBlock.innerText = `❌ STOP (${sesso})`;
                                }
                                subText.innerHTML = `Nato: <b>${dataValida}</b> — Età: <b>${eta} anni</b>`;
                                
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
                                    subText.innerText = 'Inquadra il fronte del documento';
                                    document.getElementById('id-nome').innerText = "---";
                                    document.getElementById('id-cognome').innerText = "---";
                                    bloccato = false;
                                    loopScansione();
                                }, 1800);
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
    sesso = req_data['sesso']
    esito = req_data['esito']
    eta = req_data['eta']
    nome = req_data.get('nome', '---')
    cognome = req_data.get('cognome', '---')
    
    stato_memoria = salva_in_memoria(esito, eta, data_str, sesso, nome, cognome)
    
    return jsonify({
        'status': 'success', 
        'uomini': stato_memoria.get("uomini_dentro", 0), 
        'donne': stato_memoria.get("donne_dentro", 0)
    })

if __name__ == '__main__':
    inizializza_memoria()
    app.run(host='0.0.0.0', port=5000, debug=False)
