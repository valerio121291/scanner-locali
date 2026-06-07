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
        print(f"Errore salvataggio memoria: {e}")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Scanner Madre AI</title>
    <script src="https://unpkg.com/tesseract.js@v5.1.0/dist/tesseract.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #121212; color: white; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 450px; width: 100%; text-align: center; }
        .upload-btn { background-color: #007aff; color: white; border: none; padding: 15px 30px; font-size: 1.2rem; font-weight: bold; border-radius: 12px; cursor: pointer; width: 100%; margin-top: 20px; box-shadow: 0 4px 15px rgba(0,122,255,0.4); }
        .status-circle { width: 140px; height: 140px; border-radius: 50%; margin: 30px auto; display: flex; align-items: center; justify-content: center; font-size: 3.5rem; font-weight: bold; transition: all 0.4s ease; background-color: #222; border: 4px solid #333; }
        .maggiorenne { background-color: #2eb85c; border-color: #1f7a3e; box-shadow: 0 0 35px #2eb85c; }
        .minorenne { background-color: #e55353; border-color: #a33939; box-shadow: 0 0 35px #e55353; }
        #info { font-size: 1.3rem; font-weight: bold; margin-top: 10px; min-height: 60px; color: #e0e0e0; }
        #preview { width: 100%; max-width: 300px; max-height: 180px; object-fit: contain; margin-top: 15px; border-radius: 10px; border: 2px solid #444; display: none; }
        .loading-bar { width: 100%; background-color: #222; border-radius: 10px; display: none; margin-top: 10px; overflow: hidden; }
        .loading-progress { width: 0%; height: 8px; background-color: #00ffcc; transition: width 0.2s; }
    </style>
</head>
<body>

<div class="container">
    <h2 style="margin-bottom: 5px; color: #fff;">Scanner Intelletto Madre</h2>
    <p style="color: #aaa; margin-top: 0; font-size: 0.95rem;">Fotografa il FRONTE o il RETRO di qualsiasi documento</p>

    <input type="file" id="file-input" accept="image/*" capture="environment" style="display: none;">
    <button class="upload-btn" onclick="document.getElementById('file-input').click()">📸 SCATTA FOTO DOCUMENTO</button>

    <img id="preview" alt="Anteprima">
    
    <div class="loading-bar" id="loading-bar">
        <div class="loading-progress" id="loading-progress"></div>
    </div>

    <div id="circle" class="status-circle">🤖</div>
    <div id="info">In attesa del documento...</div>
</div>

<script>
    const fileInput = document.getElementById('file-input');
    const preview = document.getElementById('preview');
    const circle = document.getElementById('circle');
    const info = document.getElementById('info');
    const loadingBar = document.getElementById('loading-bar');
    const loadingProgress = document.getElementById('loading-progress');

    function playSuono(tipo) {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        let osc = audioCtx.createOscillator();
        let gain = audioCtx.createGain();
        if (tipo === 'ok') {
            osc.type = 'sine'; osc.frequency.setValueAtTime(880, audioCtx.currentTime);
            gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
            osc.connect(gain); gain.connect(audioCtx.destination);
            osc.start(); osc.stop(audioCtx.currentTime + 0.15);
        } else {
            osc.type = 'sawtooth'; osc.frequency.setValueAtTime(220, audioCtx.currentTime);
            gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
            osc.connect(gain); gain.connect(audioCtx.destination);
            osc.start(); osc.stop(audioCtx.currentTime + 0.25);
        }
    }

    function analizzaDataDaTesto(testo) {
        console.log("Testo estratto completo:", testo);
        
        // 1. Cerca formato standard italiano GG/MM/AAAA o GG-MM-AAAA o GG.MM.AAAA
        let dateTrovate = testo.match(/\\d{2}[\\/\\-\\.]\\d{2}[\\/\\-\\.]\\d{4}/g);
        if (dateTrovate) return dateTrovate[0];

        // 2. Controllo specifico per la zona MRZ (Retro Carta d'Identità / Passaporto)
        // Nella zona MRZ la data di nascita è scritta nel formato AAMMGG (6 numeri) seguita da un numero di controllo e dal sesso (M/F)
        // Esempio: 0208154M... -> 15 Agosto 2002
        let mrzMatch = testo.match(/(\\d{6})\\d[MF]/i);
        if (mrzMatch) {
            let mrzData = mrzMatch[1];
            let aa = parseInt(mrzData.substring(0,2));
            let mm = parseInt(mrzData.substring(2,4));
            let gg = parseInt(mrzData.substring(4,6));
            
            let annoCorrenteCorto = new Date().getFullYear() % 100;
            let annoQuattroCifre = (aa <= annoCorrenteCorto) ? (2000 + aa) : (1900 + aa);
            if (mm >= 1 && mm <= 12 && gg >= 1 && gg <= 31) {
                return gg.toString().padStart(2, '0') + '/' + mm.toString().padStart(2, '0') + '/' + annoQuattroCifre;
            }
        }

        // 3. Controllo Codice Fiscale inserito nel testo
        let cfMatch = testo.match(/[A-Z]{6}(\\d{2})([A-EHLMPR-T])(\\d{2})/i);
        if (cfMatch) {
            let aa = cfMatch[1];
            let meseLettera = cfMatch[2].toUpperCase();
            let gg = parseInt(cfMatch[3]);
            if (gg > 40) gg = gg - 40;
            
            const mappaMesi = { 'A':1, 'B':2, 'C':3, 'D':4, 'E':5, 'H':6, 'L':7, 'M':8, 'P':9, 'R':10, 'S':11, 'T':12 };
            let mm = mappaMesi[meseLettera];
            
            let annoCorrenteCorto = new Date().getFullYear() % 100;
            let aaInt = parseInt(aa);
            let annoQuattroCifre = (aaInt <= annoCorrenteCorto) ? (2000 + aaInt) : (1900 + aaInt);
            
            if (mm && gg >= 1 && gg <= 31) {
                return gg.toString().padStart(2, '0') + '/' + mm.toString().padStart(2, '0') + '/' + annoQuattroCifre;
            }
        }
        return null;
    }

    fileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (!file) return;

        // Mostra l'anteprima della foto
        preview.src = URL.createObjectURL(file);
        preview.style.display = 'inline-block';
        
        info.innerText = "Analisi del documento in corso...";
        circle.className = 'status-circle';
        circle.innerText = '⏳';
        loadingBar.style.display = 'block';
        loadingProgress.style.style = 'width: 10%;';

        // Avvia Tesseract OCR direttamente nel browser dello smartphone
        Tesseract.recognize(
            file,
            'ita+eng',
            { logger: m => {
                if(m.status === 'recognizing text') {
                    loadingProgress.style.width = Math.floor(m.progress * 100) + '%';
                }
            }}
        ).then(({ data: { text } }) => {
            loadingBar.style.display = 'none';
            
            // Cerca la data di nascita analizzando il testo letto
            let dataNascita = analizzaDataDaTesto(text);
            
            if (dataNascita) {
                // Invia la data trovata al server per calcolare l'età e salvarla stabilmente
                fetch('/elabora_scansione', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ data_nascita: dataNascita })
                })
                .then(res => res.json())
                .then(data => {
                    if (data.esito === 'MAGGIORENNE') {
                        circle.className = 'status-circle maggiorenne'; circle.innerText = '✔️';
                        info.innerHTML = `<span style="color:#2eb85c">MAGGIORENNE</span><br><span style="font-size:1.1rem">${data.eta} anni (${dataNascita})</span>`;
                        playSuono('ok');
                    } else {
                        circle.className = 'status-circle minorenne'; circle.innerText = '❌';
                        info.innerHTML = `<span style="color:#e55353">MINORENNE</span><br><span style="font-size:1.1rem">${data.eta} anni (${dataNascita})</span>`;
                        playSuono('no');
                    }
                });
            } else {
                circle.innerText = '❓';
                info.innerHTML = `<span style="color:#ffa500">Data non trovata</span><br><span style="font-size:0.85rem; color:#666;">Riprova facendo una foto più nitida ed evita riflessi.</span>`;
            }
        }).catch(err => {
            console.error(err);
            loadingBar.style.display = 'none';
            info.innerText = "Errore durante la lettura digitale.";
            circle.innerText = '❌';
        });
    });
</script>

</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/elabora_scansione', methods=['POST'])
def elabora_scansione():
    data = request.get_json()
    if not data or 'data_nascita' not in data:
        return jsonify({'status': 'error'})

    data_str = data['data_nascita']
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
