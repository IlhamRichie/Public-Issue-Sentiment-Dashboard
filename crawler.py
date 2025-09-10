# File: crawler.py (Versi Optimasi Memori)

import os
import sys
import traceback
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pymongo
import transformers
import gc # Garbage Collector

# =======================================================================
# KONFIGURASI & SETUP
# =======================================================================
print("🚀 Memulai Crawler...")
load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")
MONGO_URI = os.getenv("MONGO_CONNECTION_STRING")
if not API_KEY or not MONGO_URI:
    print("❌ FATAL: Pastikan YOUTUBE_API_KEY dan MONGO_CONNECTION_STRING ada di file .env")
    sys.exit(1)

SEARCH_QUERY = '"tunjangan dpr" | "demo dpr" | "demo rusuh indonesia" | "bubarkan dpr" | "perampasan aset"'
MAX_SEARCH_RESULTS = 50
SEARCH_PERIOD_DAYS = 30
TARGET_TOTAL_COMMENTS = 10000
DB_NAME = "db_sentimen"
COLLECTION_NAME = "netizen_comments"
BATCH_SIZE = 500 # Ukuran batch untuk diproses, sesuaikan jika perlu

# ... Fungsi search_videos dan scrape_youtube_comments tetap sama ...
def search_videos(youtube, query, max_results, period_days):
    print(f"🔎 Mencari video dengan kata kunci: '{query}'...")
    search_after_date = (datetime.now() - timedelta(days=period_days)).isoformat("T") + "Z"
    try:
        request = youtube.search().list(part="snippet", q=query, type="video", order="relevance", maxResults=max_results, regionCode="ID", relevanceLanguage="id", publishedAfter=search_after_date)
        response = request.execute()
        video_ids = [item['id']['videoId'] for item in response.get('items', [])]
        if video_ids: print(f"✅ Ditemukan {len(video_ids)} ID video relevan.")
        else: print("⚠️ Tidak ada video yang ditemukan.")
        return video_ids
    except HttpError as e:
        if "quotaExceeded" in str(e): print("❌ FATAL: Kuota YouTube API harian telah habis.")
        else: print(f"❌ ERROR HttpError saat mencari video: {e}")
        return []

def scrape_youtube_comments(youtube, video_ids, target_count):
    print(f"💬 Mengambil komentar dari {len(video_ids)} video (target: {target_count} komentar)...")
    comments_list = []
    for video_id in video_ids:
        if len(comments_list) >= target_count: break
        try:
            request = youtube.commentThreads().list(part='snippet', videoId=video_id, maxResults=100, textFormat='plainText', order='relevance')
            while request:
                response = request.execute()
                for item in response['items']:
                    comment_snippet = item['snippet']['topLevelComment']['snippet']
                    comments_list.append({'comment_id': item['id'], 'author': comment_snippet.get('authorDisplayName'), 'comment': comment_snippet.get('textDisplay'), 'published_at': comment_snippet.get('publishedAt'), 'like_count': comment_snippet.get('likeCount', 0), 'video_id': video_id})
                if 'nextPageToken' in response and len(comments_list) < target_count:
                    request = youtube.commentThreads().list_next(request, response)
                else: request = None
        except Exception as e:
            print(f"   [Peringatan] Gagal mengambil komentar dari video {video_id}: {e}")
            continue
    print(f"✅ Berhasil mengumpulkan {len(comments_list)} komentar.")
    return pd.DataFrame(comments_list)

# --- FUNGSI YANG DIUBAH ---

def process_and_save_in_batches(df, client):
    """
    Fungsi baru untuk memproses analisis sentimen dan menyimpan ke MongoDB
    secara batch untuk menghemat memori.
    """
    if df.empty:
        print("ℹ️ Tidak ada data baru untuk diproses.")
        return

    print("🧠 Memulai pemrosesan data dalam batch...")
    
    # 1. Muat model AI sekali saja
    try:
        sentiment_analyzer = transformers.pipeline(
            "sentiment-analysis",
            model="mdhugol/indonesia-bert-sentiment-classification",
            device=-1
        )
        print("   Model AI berhasil dimuat.")
    except Exception as e:
        print(f"❌ ERROR: Gagal memuat model AI. Proses dibatalkan. {e}")
        return

    # 2. Ambil semua ID yang ada di DB sekali saja (jika DB besar, ini juga bisa dioptimalkan)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    print("   Mengambil ID komentar yang sudah ada dari database...")
    existing_ids = {doc.get('comment_id') for doc in collection.find({}, {'comment_id': 1}) if 'comment_id' in doc}
    print(f"   Ditemukan {len(existing_ids)} ID yang sudah ada.")

    # 3. Filter data yang belum ada di database
    df_new = df[~df['comment_id'].isin(existing_ids)]
    if df_new.empty:
        print("ℹ️ Semua data yang di-crawl sudah ada di database.")
        return
        
    print(f"   Ditemukan {len(df_new)} komentar baru untuk diproses.")
    
    # 4. Proses dalam batch
    total_saved = 0
    for start in range(0, len(df_new), BATCH_SIZE):
        end = start + BATCH_SIZE
        df_batch = df_new.iloc[start:end]
        
        print(f"\n--- Memproses batch {start+1}-{min(end, len(df_new))} dari {len(df_new)} ---")
        
        # Analisis sentimen untuk batch ini
        texts = df_batch['comment'].dropna().astype(str).tolist()
        if not texts:
            continue
            
        results = sentiment_analyzer(texts, truncation=True, max_length=512)
        
        def map_label(label):
            if label == 'LABEL_2': return "Negatif"
            if label == 'LABEL_0': return "Positif"
            return "Netral"
        
        sentiments = [map_label(result['label']) for result in results]
        df_batch['sentiment'] = sentiments

        # Simpan batch ini ke MongoDB
        records_to_insert = df_batch.to_dict('records')
        if records_to_insert:
            collection.insert_many(records_to_insert, ordered=False)
            total_saved += len(records_to_insert)
            print(f"   ✅ Berhasil menyimpan {len(records_to_insert)} dokumen.")
            
        # Hapus variabel dan jalankan garbage collector untuk membersihkan memori
        del df_batch, texts, results, sentiments
        gc.collect()

    print(f"\n✅ Pemrosesan batch selesai. Total {total_saved} dokumen baru disimpan.")

def main():
    """Fungsi utama untuk mengorkestrasi seluruh proses."""
    mongo_client = None
    try:
        youtube = build('youtube', 'v3', developerKey=API_KEY)
        mongo_client = pymongo.MongoClient(MONGO_URI)
        
        video_ids = search_videos(youtube, SEARCH_QUERY, MAX_SEARCH_RESULTS, SEARCH_PERIOD_DAYS)
        
        if video_ids:
            df_comments = scrape_youtube_comments(youtube, video_ids, TARGET_TOTAL_COMMENTS)
            # Panggil fungsi pemrosesan batch yang baru
            process_and_save_in_batches(df_comments, mongo_client)

    except Exception as e:
        print(f"❌ Terjadi kesalahan fatal di proses utama: {e}")
        traceback.print_exc()
    finally:
        if mongo_client:
            mongo_client.close()
        print("🏁 Proses crawler selesai.")

if __name__ == "__main__":
    main()