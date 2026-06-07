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
    <title>Scanner Madre Diagnostics</title>
    <script src="https://unpkg.com/@zxing/library@latest"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #121212; color: white; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; box-sizing: border-box; }
        .container { max-width: 450px; width: 100%; text-align: center; }
        .video-container { position: relative; width: 100%; max-width: 360px; height: 240px; margin: 0 auto; border-radius: 20px; overflow: hidden; border: 3px solid #333; background: #000; }
        video { width: 100%; height: 100%; object-fit: cover; }
        .mirino { position: absolute; top: 25%; left: 5%; width: 90%; height: 50%; border: 3px dashed rgba(255,255,255,0.7); border-radius: 12px; pointer-events: none; }
        .laser { position: absolute; top: 50%; left: 10%; width: 80%; height: 2px; background-color: #00ffcc; box-shadow: 0 0 8px #00ffcc; animation: scan 2s infinite linear; pointer-events: none; }
        @keyframes scan { 0% { top: 25%; } 50% { top: 75%; } 100% { top: 25%; } }
        .status-circle { width: 130px; height: 130px; border-radius: 50%; margin: 25px auto; display: flex; align-items: center; justify-content: center; font-size: 3.5rem; font-weight: bold; transition: all 0.4s ease; background-color: #222; border: 4px solid #333; }
        .maggiorenne { background-color: #2eb85c; border-color: #1f7a3e; box-shadow: 0 0 35px #2eb85c; }
        .minorenne { background-color: #e55353; border-color: #a33939; box-shadow: 0 0 35px #e55353; }
        #info { font-size: 1.2rem; font-weight: bold; margin-top: 10px; min-height: 50px; color: #e0e0e0; }
        #debug-panel { margin-top: 15px; padding: 10px; background: #1a1a1a; border: 1px solid #333; border-radius: 8px; font-family: monospace; font-size: 0.8rem; color: #00ff00; text-align: left; max-height: 100px; overflow-y: auto; white-space: pre-wrap; }
    </style>
</head>
<body>

<div class="container">
    <h2 style="margin-bottom: 5px; color: #fff;">Scanner Madre PRO</h2>
    <p style="color: #aaa; margin-top: 0; font-size: 0.95rem;">Inquadra il codice a barre sul retro</p>

    <div class="video-container">
        <video id="video"></video>
        <div class="mirino"></div>
        <div class="laser"></div>
    </div>

    <div id="circle" class="status-circle">📸</div>
    <div id="info">Punta il codice a barre...</div>
    
    <div style="color: #666; font-size: 0.8rem; margin-top: 15px; text-align: left;">Testo rilevato nel Barcode:</div>
    <div id="debug-panel">In attesa di lettura codice...</div>
</div>

<script>
    const video = document.getElementById('video');
    const circle = document.getElementById('circle');
    const info = document.getElementById('info');
    const debugPanel = document.getElementById('debug-panel');
    
    const codeReader = new ZXing.BrowserMultiFormatReader();
    let bloccato = false;

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

    function analizzaTestoBarcode(testo) {
        // Pulizia spazi iniziali/finali
        testo = testo.trim();
        
        // 1. Cerca formato standard GG/MM/AAAA o GG-MM-AAAA
        let dateTrovate = testo.match(/\\d{2}[\\/\\-\\.]\\d{2}[\\/\\-\\.]\\d{4}/);
        if (dateTrovate) return dateTrovate[0];

        // 2. Cerca sequenza pulita di 8 numeri consecutivi (es. 19950815 o 15081995)
        let numeri8 = testo.match(/\\d{8}/g);
        if (numeri8) {
            for (let seq of numeri8) {
                let anno = parseInt(seq.substring(0,4));
                let mese = parseInt(seq.substring(4,6));
                let giorno = parseInt(seq.substring(6,8));
                if (anno > 1920 && anno <= new Date().getFullYear() && mese >= 1 && mese <= 12 && giorno >= 1 && giorno <= 31) {
                    return giorno.toString().padStart(2, '0') + '/' + mese.toString().padStart(2, '0') + '/' + anno;
                }
                
                giorno = parseInt(seq.substring(0,2));
                mese = parseInt(seq.substring(2,4));
                anno = parseInt(seq.substring(4,8));
                if (anno > 1920 && anno <= new Date().getFullYear() && mese >= 1 && mese <= 12 && giorno >= 1 && giorno <= 31) {
                    return giorno.toString().padStart(2, '0') + '/' + mese.toString().padStart(2, '0') + '/' + anno;
                }
            }
        }

        // 3. Algoritmo specifico per estrarre la data dal CODICE FISCALE italiano se presente nel barcode
        // Esempio CF: RSSMRA95M15H501Z -> Anno: 95, Mese: M (Agosto), Giorno: 15
        let cfMatch = testo.match(/[A-Z]{6}(\\d{2})([A-EHLMPR-T])(\\d{2})[A-Z]\\d{3}[A-Z]/i);
        if (cfMatch) {
            let annoDec = cfMatch[1];
            let meseLettera = cfMatch[2].toUpperCase();
            let giornoDec = parseInt(cfMatch[3]);
            
            // Se il giorno è > 40 significa che si tratta di una donna, quindi sottraiamo 40
            if (giornoDec > 40) giornoDec = giornoDec - 40;
            
            // Mappa mesi codice fiscale
            const mesiMappa = { 'A':1, 'B':2, 'C':3, 'D':4, 'E':5, 'H':6, 'L':7, 'M':8, 'P':9, 'R':10, 'S':11, 'T':12 };
            let meseDec = mesiMappa[meseLettera];
            
            let annoCorrenteCorto = new Date().getFullYear() % 100;
            let annoDecIntero = parseInt(annoDec);
            let annoQuattroCifre = (annoDecIntero <= annoCorrenteCorto) ? (2000 + annoDecIntero) : (1900 + annoDecIntero);
            
            if (meseDec && giornoDec >= 1 && giornoDec <= 31) {
                return giornoDec.toString().padStart(2, '0') + '/' + meseDec.toString().padStart(2, '0') + '/' + annoQuattroCifre;
            }
        }
        return null;
    }

    codeReader.listVideoInputDevices()
        .then((videoInputDevices) => {
            let selectedDeviceId = videoInputDevices[0].deviceId;
            if (videoInputDevices.length > 1) {
                for(let device of videoInputDevices) {
                    if(device.label.toLowerCase().includes('back') || device.label.toLowerCase().includes('posteriore')) {
                        selectedDeviceId = device.deviceId;
                        break;
                    }
                }
            }
            
            codeReader.decodeFromVideoDevice(selectedDeviceId, 'video', (result, err) => {
                if (result && !bloccato) {
                    let testoRilevato = result.text;
                    debugPanel.innerText = testoRilevato; // Mostra subito cosa c'è scritto dentro!
                    
                    let dataNascita = analizzaTestoBarcode(testoRilevato);
                    
                    if (dataNascita) {
                        bloccato = true;
                        
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
                            
                            setTimeout(() => {
                                circle.className = 'status-circle'; circle.innerText = '📸';
                                info.innerText = 'Punta il codice a barre...';
                                bloccato = false;
                            }, 3500);
                        });
                    } else {
                        info.innerText = "Codice letto, ma nessuna data trovata.";
                    }
                }
            });
        })
        .catch((err) => {
            console.error(err);
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
    
    data_nascita = datetime(anno, mese, girono) if 'girono' in locals() else datetime(anno, mese, giorno)
    oggi = datetime.now()
    eta = oggi.year - data_nascita.year - ((oggi.month, oggi.day) < (data_nascita.month, data_nascita.day))
    
    esito = "MAGGIORENNE" if eta >= 18 else "MINORENNE"
    salva_in_memoria(esito, eta, data_str)
    
    return jsonify({'status': 'success', 'esito': esito, 'eta': eta})

if __name__ == '__main__':
    inizializza_memoria()
    app.run(host='0.0.0.0', port=5000, debug=False)
