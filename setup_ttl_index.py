# File: setup_ttl_index.py

import os
import pymongo
from dotenv import load_dotenv

# --- KONFIGURASI ---
load_dotenv()
MONGO_URI = os.getenv("MONGO_CONNECTION_STRING")
DB_NAME = "db_sentimen"
COLLECTION_NAME = "netizen_comments"
EXPIRE_AFTER_SECONDS = 172800  # 2 hari = 2 * 24 * 60 * 60 detik

def create_ttl_index():
    """
    Fungsi untuk membuat TTL Index pada koleksi MongoDB.
    Hanya perlu dijalankan sekali.
    """
    print("🚀 Mencoba membuat TTL Index...")
    client = None
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        # Membuat TTL Index pada field 'published_at'
        # Dokumen akan dihapus setelah 'expireAfterSeconds' dari nilai 'published_at'
        collection.create_index(
            "published_at", 
            expireAfterSeconds=EXPIRE_AFTER_SECONDS
        )

        print(f"✅ Berhasil membuat atau mengonfirmasi TTL Index pada '{COLLECTION_NAME}'.")
        print(f"   Dokumen sekarang akan otomatis terhapus setelah {EXPIRE_AFTER_SECONDS / 3600 / 24:.0f} hari.")

    except Exception as e:
        print(f"❌ Gagal membuat TTL Index: {e}")
    finally:
        if client:
            client.close()

if __name__ == "__main__":
    create_ttl_index()