# Nama file: convert_kbps_to_mbps.py
import pandas as pd
from easyocr_image_to_text import save_processed_data


def process_csv(input_file, output_file):
    # 1. Baca file CSV
    df = pd.read_csv(input_file)
    
    # 2. Fungsi konversi untuk nilai 3 digit
    def convert_kbps_to_mbps(value):
        try:
            # Cek jika nilai numerik dan antara 100-999
            if isinstance(value, (int, float)) and 100 <= value <= 999:
                return value / 1000  # Konversi ke Mbps
            else:
                return value  # Pertahankan nilai asli
        except:
            return value  # Jika bukan angka (misal: teks), kembalikan asli
    
    # 3. Proses SEMUA kolom numerik dalam DataFrame
    for column in df.select_dtypes(include=['int64', 'float64']).columns:
        df[column] = df[column].apply(convert_kbps_to_mbps)
    
    # 4. Simpan ke file CSV baru
    df.to_csv(output_file, index=False)
    print(f"Proses selesai! File tersimpan di: {output_file}")

# Contoh penggunaan
if __name__ == "__main__":
    input_csv = "maret_tambah.csv"  # Ganti dengan nama file input Anda
    output_csv = "data_output_maret_tambah.csv"  # Ganti dengan nama file output
    process_csv(input_csv, output_csv)