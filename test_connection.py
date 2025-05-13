import mysql.connector
from mysql.connector import Error

# Konfigurasi koneksi
db_config = {
    'host': 'localhost',
    'user': 'root',      # ganti dengan user yang kamu buat di phpMyAdmin
    'password': 'ilham123',  # ganti dengan password-nya
    'database': 'cacti_db'  # ganti jika pakai nama lain
}

# Tes koneksi
try:
    connection = mysql.connector.connect(**db_config)
    if connection.is_connected():
        print("✅ Berhasil terkoneksi ke database MySQL!")
        db_info = connection.get_server_info()
        print("Versi MySQL:", db_info)
except Error as e:
    print("❌ Gagal terkoneksi:", e)
finally:
    if 'connection' in locals() and connection.is_connected():
        connection.close()
        print("🔌 Koneksi ditutup.")
