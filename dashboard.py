# File: dashboard.py

import streamlit as st
import pandas as pd
import requests
import pymongo
import os
from dotenv import load_dotenv

# --- 1. KONFIGURASI & SETUP ---
st.set_page_config(
    page_title="Dashboard Pantau Isu",
    page_icon="📊",
    layout="wide"
)

# Muat environment variables dari file .env
load_dotenv()
MONGO_URI = os.getenv("MONGO_CONNECTION_STRING")
DB_NAME = "db_sentimen"
COLLECTION_NAME = "netizen_comments"

# URL ke backend Flask API Anda
API_URL = "http://127.0.0.1:5000/analyze"

# Fungsi untuk mengambil data dari MongoDB
@st.cache_data(ttl=600) # Cache data selama 10 menit
def load_data_from_mongo():
    """Mengambil data komentar dari MongoDB."""
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        # Ambil data, urutkan dari yang terbaru, batasi 1000
        data = list(collection.find().sort("published_at", pymongo.DESCENDING).limit(1000))
        client.close()
        if data:
            df = pd.DataFrame(data)
            # Konversi kolom tanggal
            df['published_at'] = pd.to_datetime(df['published_at'])
            return df
    except Exception as e:
        st.error(f"Gagal terhubung ke MongoDB: {e}")
    return pd.DataFrame()


# --- 2. TAMPILAN DASHBOARD ---
st.title("📊 Dashboard Pemantauan Isu Publik")
st.markdown("Dashboard ini menganalisis sentimen dari komentar netizen di YouTube secara real-time.")

# Tombol untuk refresh data
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()

# Muat data
df = load_data_from_mongo()

if not df.empty:
    # --- 3. VISUALISASI DATA ---
    st.markdown("---")
    
    # KPI (Key Performance Indicators)
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Komentar Dianalisis", len(df))
    
    # Hitung sentimen negatif
    negatif_count = df[df['sentiment'] == 'Negatif'].shape[0]
    col2.metric("Sentimen Negatif", f"{negatif_count}")
    
    # Hitung sentimen positif
    positif_count = df[df['sentiment'] == 'Positif'].shape[0]
    col3.metric("Sentimen Positif", f"{positif_count}")

    # Buat 2 kolom untuk menata letak chart
    fig_col1, fig_col2 = st.columns(2)

    with fig_col1:
        st.subheader("Distribusi Sentimen")
        # Pie chart untuk distribusi sentimen
        sentiment_counts = df['sentiment'].value_counts()
        st.pyplot(sentiment_counts.plot.pie(autopct='%1.1f%%', startangle=90, colors=['#d9534f', '#5cb85c', '#f0ad4e']).figure)

    with fig_col2:
        st.subheader("Sentimen per Hari")
        # Line chart untuk tren sentimen harian
        df['tanggal'] = df['published_at'].dt.date
        sentiment_over_time = df.groupby(['tanggal', 'sentiment']).size().unstack(fill_value=0)
        st.line_chart(sentiment_over_time)

    # Menampilkan data mentah dalam tabel
    st.subheader("Data Komentar Terbaru")
    st.dataframe(df[['published_at', 'author', 'comment', 'sentiment', 'like_count']].head(20))

else:
    st.warning("Tidak ada data untuk ditampilkan. Jalankan crawler terlebih dahulu.")

# --- 4. FITUR ANALISIS TEKS MANUAL ---
st.markdown("---")
st.subheader("🔍 Analisis Teks Baru")
user_text = st.text_area("Masukkan teks atau kalimat untuk dianalisis sentimennya:")

if st.button("Analisis"):
    if user_text:
        with st.spinner("Menganalisis..."):
            try:
                # Kirim request ke API Flask
                response = requests.post(API_URL, json={"text": user_text})
                if response.status_code == 200:
                    result = response.json()
                    sentiment = result['sentiment']
                    if sentiment == "Positif":
                        st.success(f"Sentimen: **{sentiment}**")
                    elif sentiment == "Negatif":
                        st.error(f"Sentimen: **{sentiment}**")
                    else:
                        st.warning(f"Sentimen: **{sentiment}**")
                else:
                    st.error(f"Error dari server: {response.text}")
            except requests.exceptions.ConnectionError:
                st.error("Gagal terhubung ke server backend. Pastikan app.py sudah berjalan.")
    else:
        st.warning("Mohon masukkan teks untuk dianalisis.")