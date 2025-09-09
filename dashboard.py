# File: dashboard.py (Versi Lengkap)

import streamlit as st
import pandas as pd
import requests
import pymongo
import os
from dotenv import load_dotenv
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from sklearn.feature_extraction.text import CountVectorizer
from datetime import datetime, timedelta

# --- 1. KONFIGURASI & SETUP ---
st.set_page_config(page_title="Dashboard Analisis Isu Publik", page_icon="📈", layout="wide")

load_dotenv()
MONGO_URI = os.getenv("MONGO_CONNECTION_STRING")
DB_NAME = "db_sentimen"
COLLECTION_NAME = "netizen_comments"
API_URL = "http://127.0.0.1:5000/analyze"

# --- 2. FUNGSI-FUNGSI BANTUAN ---
@st.cache_data(ttl=600) # Cache data selama 10 menit
def load_data_from_mongo():
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        data = list(collection.find({}, {"_id": 0})) # Ambil semua data tanpa _id
        client.close()
        if data:
            df = pd.DataFrame(data)
            df['published_at'] = pd.to_datetime(df['published_at'])
            return df
    except Exception as e:
        st.error(f"Gagal terhubung ke MongoDB: {e}")
    return pd.DataFrame()

def get_top_ngrams(corpus, n=2, top_k=20):
    vec = CountVectorizer(ngram_range=(n, n), stop_words=['di', 'dan', 'yang', 'ini', 'itu', 'ke', 'dari', 'dengan', 'untuk']).fit(corpus)
    bag_of_words = vec.transform(corpus)
    sum_words = bag_of_words.sum(axis=0)
    words_freq = [(word, sum_words[0, idx]) for word, idx in vec.vocabulary_.items()]
    words_freq = sorted(words_freq, key=lambda x: x[1], reverse=True)
    return words_freq[:top_k]

# --- 3. TAMPILAN DASHBOARD ---
st.title("📈 Dashboard Analisis Sentimen Isu Publik")
st.markdown("Analisis sentimen *real-time* dari komentar netizen di YouTube.")

df_raw = load_data_from_mongo()

if not df_raw.empty:
    # --- SIDEBAR & FILTER GLOBAL ---
    st.sidebar.header("⚙️ Filter Data")
    
    # Filter tanggal
    min_date = df_raw['published_at'].min().date()
    max_date = df_raw['published_at'].max().date()
    
    date_range = st.sidebar.date_input(
        "Pilih Rentang Tanggal:",
        (min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        # Filter dataframe berdasarkan rentang tanggal yang dipilih
        mask = (df_raw['published_at'].dt.date >= start_date) & (df_raw['published_at'].dt.date <= end_date)
        df = df_raw.loc[mask]
    else:
        df = df_raw.copy()

    # Filter sentimen
    sentiment_options = ['Semua'] + df['sentiment'].unique().tolist()
    selected_sentiment = st.sidebar.selectbox("Pilih Sentimen:", sentiment_options)
    
    if selected_sentiment != 'Semua':
        df = df[df['sentiment'] == selected_sentiment]

    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # --- RINGKASAN EKSEKUTIF (KPI) ---
    st.markdown("---")
    st.header("Executive Summary")
    
    total_comments = len(df)
    neg_count = df[df['sentiment'] == 'Negatif'].shape[0]
    pos_count = df[df['sentiment'] == 'Positif'].shape[0]
    net_count = df[df['sentiment'] == 'Netral'].shape[0]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Komentar", f"{total_comments:,}")
    col2.metric("Sentimen Negatif 🔻", f"{neg_count:,}", f"{neg_count/total_comments:.1%}" if total_comments > 0 else "0%")
    col3.metric("Sentimen Positif ▲", f"{pos_count:,}", f"{pos_count/total_comments:.1%}" if total_comments > 0 else "0%")
    col4.metric("Sentimen Netral ➖", f"{net_count:,}", f"{net_count/total_comments:.1%}" if total_comments > 0 else "0%")
    
    # --- ANALISIS SENTIMEN MENDALAM ---
    st.markdown("---")
    st.header("📊 Analisis Sentimen Mendalam")

    col5, col6 = st.columns([1, 2])
    with col5:
        st.subheader("Distribusi Sentimen")
        sentiment_counts = df['sentiment'].value_counts()
        fig, ax = plt.subplots()
        ax.pie(sentiment_counts, labels=sentiment_counts.index, autopct='%1.1f%%', startangle=90, colors=['#d9534f','#5cb85c','#f0ad4e'])
        ax.axis('equal') # Pastikan pie chart berbentuk lingkaran
        st.pyplot(fig)

    with col6:
        st.subheader("Tren Sentimen Harian")
        df['tanggal'] = df['published_at'].dt.date
        sentiment_over_time = df.groupby(['tanggal', 'sentiment']).size().unstack(fill_value=0)
        st.line_chart(sentiment_over_time, color=['#d9534f','#f0ad4e','#5cb85c']) # Sesuaikan warna

    # --- ANALISIS TOPIK & KUALITATIF ---
    st.markdown("---")
    st.header("💬 Analisis Topik & Kualitatif")
    
    neg_comments = df[df['sentiment'] == 'Negatif']['comment'].dropna()
    
    col7, col8 = st.columns(2)
    with col7:
        st.subheader("Topik Utama Komentar Negatif")
        if not neg_comments.empty:
            top_topics = get_top_ngrams(neg_comments, n=2, top_k=15)
            topics_df = pd.DataFrame(top_topics, columns=['Topik', 'Jumlah']).set_index('Topik')
            st.bar_chart(topics_df)
    with col8:
        st.subheader("Word Cloud Komentar Negatif")
        if not neg_comments.empty:
            text = " ".join(comment for comment in neg_comments)
            wordcloud = WordCloud(width=800, height=400, background_color="white", collocations=False).generate(text)
            st.image(wordcloud.to_array())

    # --- KOMENTAR PALING POPULER ---
    st.markdown("---")
    st.header("⭐ Komentar Paling Populer (Berdasarkan Likes)")
    
    st.dataframe(
        df.sort_values("like_count", ascending=False).head(10)[['author', 'comment', 'like_count', 'sentiment']],
        use_container_width=True
    )
    
    # --- DATA LENGKAP ---
    with st.expander("Lihat Data Lengkap (Filtered)"):
        st.dataframe(df[['published_at', 'author', 'comment', 'sentiment', 'like_count']], use_container_width=True)

else:
    st.warning("Tidak ada data untuk ditampilkan. Jalankan crawler sekali secara manual atau tunggu jadwal otomatis berjalan.")

# --- FITUR ANALISIS MANUAL (TETAP SAMA) ---
st.sidebar.markdown("---")
st.sidebar.header("🔍 Analisis Teks Manual")
user_text = st.sidebar.text_area("Masukkan teks untuk dianalisis:")
if st.sidebar.button("Analisis"):
    if user_text:
        try:
            response = requests.post(API_URL, json={"text": user_text})
            if response.status_code == 200:
                result = response.json()
                st.sidebar.success(f"Sentimen Prediksi: **{result['sentiment']}**")
            else: st.sidebar.error(f"Error: {response.text}")
        except requests.exceptions.ConnectionError:
            st.sidebar.error("Gagal terhubung ke backend. Pastikan app.py sudah berjalan.")