# File: checker.py (Versi Baru dengan Logika Ganda)

import os
import pymongo
from datetime import datetime, timedelta
from dotenv import load_dotenv
import smtplib

# --- KONFIGURASI ---
load_dotenv()
MONGO_URI = os.getenv("MONGO_CONNECTION_STRING")
DB_NAME = "db_sentimen"
COLLECTION_NAME = "netizen_comments"

EMAIL_SENDER = "ilhamrgn22@gmail.com" # Ganti dengan email Anda
EMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
EMAIL_RECEIVER = "ilhamfadlimuzaki@gmail.com" # Ganti dengan email penerima

# --- KONFIGURASI PEMICU (TRIGGER) ---
# Logika 1: Lonjakan Persentase
SPIKE_THRESHOLD_INCREASE = 80.0  # Ambang batas kenaikan dalam persen (%)

# Logika 2: Batas Ambang Absolut (BARU)
ABSOLUTE_THRESHOLD_PERCENT = 70.0 # Batas ambang jika sentimen negatif > 70%

TIME_WINDOW_HOURS = 1
BASELINE_HOURS = 24

def send_email_alert(subject, body):
    if not EMAIL_PASSWORD:
        print("WARNING: GMAIL_APP_PASSWORD tidak diatur. Tidak bisa mengirim email.")
        return False
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        message = f"Subject: {subject}\n\n{body}"
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, message.encode('utf-8'))
        server.quit()
        print(f"✅ Notifikasi email berhasil dikirim ke {EMAIL_RECEIVER}")
        return True
    except Exception as e:
        print(f"❌ Gagal mengirim notifikasi email: {e}")
        return False

def check_sentiment_spike():
    print("🚀 Memulai pengecekan sentimen...")
    client = pymongo.MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    now = datetime.utcnow()
    current_window_start = now - timedelta(hours=TIME_WINDOW_HOURS)
    baseline_window_start = now - timedelta(hours=BASELINE_HOURS)

    # 1. Hitung metrik di jendela waktu saat ini (1 jam terakhir)
    pipeline_current = [
        {"$match": {"published_at": {"$gte": current_window_start}}},
        {"$group": {"_id": "$sentiment", "count": {"$sum": 1}}}
    ]
    results_current = list(collection.aggregate(pipeline_current))
    counts_current = {res['_id']: res['count'] for res in results_current}
    total_current = sum(counts_current.values())
    neg_percent_current = (counts_current.get('Negatif', 0) / total_current * 100) if total_current > 0 else 0

    # 2. Hitung metrik di jendela waktu pembanding (24 jam sebelumnya)
    pipeline_baseline = [
        {"$match": {"published_at": {"$gte": baseline_window_start, "$lt": current_window_start}}},
        {"$group": {"_id": "$sentiment", "count": {"$sum": 1}}}
    ]
    results_baseline = list(collection.aggregate(pipeline_baseline))
    counts_baseline = {res['_id']: res['count'] for res in results_baseline}
    total_baseline = sum(counts_baseline.values())
    neg_percent_baseline = (counts_baseline.get('Negatif', 0) / total_baseline * 100) if total_baseline > 0 else 0

    print(f"   - Sentimen Negatif (1 jam terakhir): {neg_percent_current:.2f}%")
    print(f"   - Rata-rata Sentimen Negatif (24 jam sebelumnya): {neg_percent_baseline:.2f}%")

    # 3. Cek kedua kondisi pemicu
    alert_reason = None

    # Kondisi 1: Batas Ambang Absolut
    if neg_percent_current >= ABSOLUTE_THRESHOLD_PERCENT:
        alert_reason = (
            f"Sentimen negatif telah melampaui batas ambang {ABSOLUTE_THRESHOLD_PERCENT}%.\n\n"
            f"- Persentase Negatif (1 Jam Terakhir): {neg_percent_current:.2f}%"
        )

    # Kondisi 2: Lonjakan Persentase
    elif neg_percent_baseline > 0:
        increase = ((neg_percent_current - neg_percent_baseline) / neg_percent_baseline) * 100
        print(f"   - Kenaikan terhitung: {increase:.2f}%")
        if increase >= SPIKE_THRESHOLD_INCREASE:
            alert_reason = (
                f"Terdeteksi lonjakan sentimen negatif sebesar {increase:.2f}%.\n\n"
                f"- Persentase Negatif (1 Jam Terakhir): {neg_percent_current:.2f}%\n"
                f"- Rata-rata Negatif (24 Jam Sebelumnya): {neg_percent_baseline:.2f}%"
            )

    # 4. Kirim notifikasi jika salah satu kondisi terpenuhi
    if alert_reason:
        print(f"🚨 PERINGATAN! {alert_reason.splitlines()[0]}")
        subject = "Peringatan Dini: Sentimen Negatif Tinggi Terdeteksi"
        body = (
            f"Sistem mendeteksi aktivitas sentimen negatif yang signifikan.\n\n"
            f"Penyebab Peringatan:\n{alert_reason}\n\n"
            f"Disarankan untuk segera memeriksa dashboard untuk analisis lebih lanjut."
        )
        send_email_alert(subject, body)
    else:
        print("   - Kondisi normal, tidak ada pemicu peringatan yang aktif.")
        
    client.close()
    print("🏁 Pengecekan selesai.")

if __name__ == "__main__":
    check_sentiment_spike()