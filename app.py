# File: app.py

from flask import Flask, request, jsonify
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

# --- 1. SETUP ---
# Inisialisasi aplikasi Flask
app = Flask(__name__)

# Tentukan path ke model terbaik yang sudah Anda simpan di Google Drive dan unduh
MODEL_PATH = "./model_terbaik" # Pastikan folder model_terbaik ada di sini

# Muat model dan tokenizer hanya sekali saat aplikasi dimulai
print("🧠 Memuat model sentimen...")
try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
    print("✅ Model berhasil dimuat!")
except Exception as e:
    print(f"❌ Gagal memuat model: {e}")
    tokenizer = None
    model = None

# Definisikan label
labels = ["Negatif", "Netral", "Positif"]

# --- 2. BUAT API ENDPOINT ---
@app.route('/analyze', methods=['POST'])
def analyze_sentiment():
    """Endpoint untuk menerima teks dan mengembalikan prediksi sentimen."""
    if not model or not tokenizer:
        return jsonify({"error": "Model tidak tersedia"}), 500

    # Ambil data JSON dari request
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "Input tidak valid, butuh field 'text'"}), 400

    text_to_analyze = data['text']

    # Lakukan prediksi
    try:
        inputs = tokenizer(text_to_analyze, return_tensors="pt", truncation=True, max_length=128)
        with torch.no_grad():
            outputs = model(**inputs)
        
        logits = outputs.logits
        predicted_class_id = torch.argmax(logits, dim=1).item()
        predicted_label = labels[predicted_class_id]
        
        # Kembalikan hasil dalam format JSON
        return jsonify({
            "text": text_to_analyze,
            "sentiment": predicted_label
        })
    except Exception as e:
        return jsonify({"error": f"Terjadi kesalahan saat analisis: {e}"}), 500

# --- 3. JALANKAN APLIKASI ---
if __name__ == '__main__':
    # Jalankan server Flask di port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)