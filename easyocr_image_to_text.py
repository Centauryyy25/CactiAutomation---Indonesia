import easyocr
import cv2
import csv
import numpy as np
import argparse
from progress_tracker import progress
import os
import re
from pprint import pprint
from datetime import datetime
import time
import json

def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def fix_common_ocr_errors(text):
    # Perbaiki angka desimal yang terpisah spasi: 79. 00 => 79.00
    text = re.sub(r'(\d+)\.\s+(\d+)', r'\1.\2', text)
    text = re.sub(r'(\d+)\s+\.\s+(\d+)', r'\1.\2', text)
    text = re.sub(r'(\d+)\s+(\.\d+)', r'\1\2', text)

    text = re.sub(r'(?<=\d)\s(?=\d{2}\b)', '.', text)
    # Perbaiki karakter OCR yang salah baca di waktu/tanggal
    text = text.replace('OO', '00').replace('CO', '00').replace('O@', '00')

    return text

def clean_ocr_text(raw_text):
    raw_text = fix_common_ocr_errors(raw_text)
    raw_text = ' '.join(raw_text.split())

    corrections = {
    # ❗ Koreksi kata penting yang sering salah terbaca
    r'\bCutbound\b': 'Outbound',
    r'\bCur\s*ent\b': 'Current',
    r'\bFron\b': 'From',
    r'\bTo\b\s*(\d{4})\s*-\s*(\d{2})\s*-\s*(\d{2})': r'To \1-\2-\3',  # Format tanggal
    r'\bNeek\b': 'Week',
    r'\bWeek\s+1[45]\b': lambda m: m.group(0).replace(" ", ""),  # Week 14 jadi Week14

    # 🔢 Koreksi angka yang dipisahkan spasi/titik/koma
    r'(\d)\s*\.\s*(\d)': r'\1.\2',  # Pisah desimal (ex: 223 . 50)
    r'(\d)\s*,\s*(\d)': r'\1.\2',  # Pisah koma
    r'(\d{2,4})\s*\.\s*(\d{3,5})': r'\1.\2',  # Bentuk seperti 223 . 500 => 223.500

    # 🧠 Koreksi karakter acak/salah tafsir
    r'\bPo2o\b': '020',  # Vlan ID yang sering salah
    r'\bO0\b': '00',     # 00 sering salah jadi O0
    r'\bk\b': '',        # Huruf acak 'k'
    r'\bM\b': '',        # Huruf acak 'M'

    # 🔧 Format teks: colon yang hilang
    r'Maximum\s*;': 'Maximum:',
    r'Maximum(\d)': r'Maximum: \1',
    r'Maximum\s*(\d+\.\d+)': r'Maximum: \1',
    r'Average(\d)': r'Average: \1',
    r'Current(\d)': r'Current: \1',
    r'Average:\s*(\d+)\s+(\d+)': r'Average: \1.\2',  # Gabung 869 58 jadi 869.58
    r'Maximum\s+(\d+)\s+(\d+)': r'Maximum: \1.\2',

    # 🔎 Pembersih umum
    r'\s*;\s*': '',  # hapus tanda titik koma acak
    r'~Pre\b': '',   # hilangkan dekorasi tidak perlu

    # 🔍 Koreksi karakter salah baca dalam waktu & angka
    r'Od&': '00:00',
    r'(?<=Maximum\s)(\d{1,2})\b': lambda m: f"{int(m.group(1)) / 100:.2f}",  # ex: 09 → 0.09
    r"'(\d{1,2})": lambda m: f"{int(m.group(1)) / 100:.2f}",  # ex: '84 → 0.84
    r'H\s*Maximum': 'Maximum',
    r'Average:\s+1\.19\s+H': 'Average: 1.19 Maximum:',
    r'Maximum\s*\'?(\d{1,2})': lambda m: f"Maximum: {int(m.group(1)) / 100:.2f}",
    r':\s*O0': ': 00',
    r'Week\s+(\d{2})': r'Week\1',  # Week 14 jadi Week14
    r'\bPozo\b': 'Vlan',
}

    
    for pattern, repl in corrections.items():
        raw_text = re.sub(pattern, repl, raw_text)

    patterns = {
        'inbound': r'Inbound Current (\d+(?:\.\d+)?).*?Average: (\d+(?:\.\d+)?).*?Maximum[:]?\s*(\d+(?:\.\d+)?)',
        'outbound': r'Outbound Current (\d+(?:\.\d+)?).*?Average: (\d+(?:\.\d+)?).*?Maximum[:]?\s*(\d+(?:\.\d+)?)',
        'isp': r'isp-cust (.*?)\/',
        'period': r'From\s*(.*?)\s*To\s*(.*?)\s*Inbound',
        'vlan_id': r'(\d{3,4})\s*\.\s*(\d{3,4})'
    }

    result = {}
    for key, pattern in patterns.items():
        matches = re.findall(pattern, raw_text, re.IGNORECASE)
        if matches:
            if key in ['inbound', 'outbound']:
                # Ambil hasil pertama untuk inbound, terakhir untuk outbound
                data = matches[0] if key == 'inbound' else matches[-1]
                result[key] = {
                    'current': float(data[0]),
                    'average': float(data[1]),
                    'max': float(data[2])
                }
            elif key == 'period':
                from_date = matches[0][0].strip().replace(';', '').replace('O0', '00')
                to_date = matches[0][1].strip().replace(';', '').replace('O0', '00')
                result[key] = {'from': from_date, 'to': to_date}
            elif key == 'vlan_id':
                result['vlan_id'] = matches[0][1]  # Ambil bagian kedua sebagai ID
            else:
                result[key] = matches[0][0].strip()



    print(raw_text)
    return result or {'error': 'No patterns matched', 'raw_text': raw_text}

def save_processed_data(data, output_dir="processed_output"):
    ensure_dir(output_dir)
    filename = f"{output_dir}/processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✅ Data bersih disimpan di: {filename}")
    return filename

def preprocess_image(image_path, target_width=800):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Gambar tidak ditemukan!")
    h, w = img.shape[:2]
    ratio = target_width / float(w)
    dim = (target_width, int(h * ratio))
    img = cv2.resize(img, dim, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    # Denoising
    img = cv2.fastNlMeansDenoising(img, h=10)

    # Atau sharpening:
    kernel = np.array([[0, -1, 0],
                    [-1, 5,-1],
                    [0, -1, 0]])
    img = cv2.filter2D(img, -1, kernel)

    return img

def image_to_text(image_path, languages=['en'], use_gpu=False):
    progress.ocr['current_file'] = os.path.basename(image_path)
    progress.ocr['message'] = f'Memproses {progress.ocr["current_file"]}'
    
    if not hasattr(image_to_text, 'reader'):
        progress.ocr['message'] = 'Menyiapkan model OCR...'
        image_to_text.reader = easyocr.Reader(
            languages,
            gpu=use_gpu,
            model_storage_directory='./models',
            download_enabled=True
        )
    processed_img = preprocess_image(image_path)
    start_time = time.time()
    results = image_to_text.reader.readtext(
        processed_img,
        decoder='greedy',
        batch_size=4,
        paragraph=False,
        detail=0
    )
    progress.ocr['message'] = f'Selesai memproses {progress.ocr["current_file"]}'
    return " ".join(results)

def process_images_in_folder(folder, output_dir, lang, use_gpu):    
    supported_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')
    files = [f for f in os.listdir(folder) if f.lower().endswith(supported_exts)]
    
    progress.ocr.update({
    'current': 0,
    'total': len(files),
    'status': 'running',
    'message': 'Menyiapkan proses OCR...',
    'current_file': ''
    })
    
    all_results = {}
    for i, filename in enumerate(files, 1):
        progress.ocr.update({
            'current': i,
            'total': len(files),
            'status': 'running',
            'message': 'Menyiapkan proses OCR...',
            'current_file': ''
        })
        
        img_path = os.path.join(folder, filename)
        try:
            extracted_text = image_to_text(img_path, lang.split(','), use_gpu)
            cleaned_data = clean_ocr_text(extracted_text)
            all_results[os.path.splitext(filename)[0]] = cleaned_data
        except Exception as e:
            progress.ocr['message'] = f'Error memproses {filename}: {str(e)}'
            continue
    
    progress.ocr['status'] = 'complete'
    return all_results

def convert_json_to_csv(json_file_path, csv_file_path):
    # Baca file JSON
    with open(json_file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    # Buka file CSV dan tulis header
    with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'ID', 'ISP', 'VLAN ID',
            'Inbound Current', 'Inbound Average', 'Inbound Max',
            'Outbound Current', 'Outbound Average', 'Outbound Max',
            'Period From', 'Period To'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # Tulis baris per item
        for key, value in data.items():
            writer.writerow({
                'ID': key,
                'ISP': value.get('isp', ''),
                'VLAN ID': value.get('vlan_id', ''),
                'Inbound Current': value.get('inbound', {}).get('current', ''),
                'Inbound Average': value.get('inbound', {}).get('average', ''),
                'Inbound Max': value.get('inbound', {}).get('max', ''),
                'Outbound Current': value.get('outbound', {}).get('current', ''),
                'Outbound Average': value.get('outbound', {}).get('average', ''),
                'Outbound Max': value.get('outbound', {}).get('max', ''),
                'Period From': value.get('period', {}).get('from', ''),
                'Period To': value.get('period', {}).get('to', ''),
            })

    print(f"Sukses! File CSV tersimpan di: {os.path.abspath(csv_file_path)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, help="Path ke gambar tunggal (contoh: 'data/input/gambar.jpg')")
    parser.add_argument("--folder", type=str, help="Path ke folder berisi gambar")
    parser.add_argument("--output-dir", type=str, default="output", help="Folder penyimpanan hasil")
    parser.add_argument("--lang", type=str, default="en", help="Bahasa OCR (contoh: 'en,id')")
    parser.add_argument("--gpu", action="store_true", help="Gunakan GPU jika tersedia")
    args = parser.parse_args()

    all_results = {}

    # Proses OCR (sama seperti sebelumnya)
    if args.folder:
        supported_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')
        for filename in os.listdir(args.folder):
            if filename.lower().endswith(supported_exts):
                img_path = os.path.join(args.folder, filename)
                print(f"\n🔍 Memproses: {filename}")
                try:
                    extracted_text = image_to_text(img_path, args.lang.split(','), args.gpu)
                    cleaned_data = clean_ocr_text(extracted_text)
                    all_results[os.path.splitext(filename)[0]] = cleaned_data
                except Exception as e:
                    print(f"❌ Gagal memproses {filename}: {e}")
    elif args.image:
        print(f"\n🔍 Memproses: {args.image}")
        extracted_text = image_to_text(args.image, args.lang.split(','), args.gpu)
        cleaned_data = clean_ocr_text(extracted_text)
        all_results[os.path.splitext(os.path.basename(args.image))[0]] = cleaned_data
    else:
        print("❗ Harap masukkan --image atau --folder")
        exit(1)

    # 1. Simpan JSON dan dapatkan path-nya
    json_path = save_processed_data(all_results, args.output_dir)

    # 2. Generate nama CSV otomatis
    csv_filename = f"converted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    csv_path = os.path.join(args.output_dir, csv_filename)

    # 3. Konversi langsung JSON -> CSV
    print("\n🔄 Mulai konversi JSON ke CSV...")
    try:
        convert_json_to_csv(json_path, csv_path)
        print(f"✅ CSV tersimpan di: {csv_path}")
    except Exception as e:
        print(f"❌ Gagal konversi: {e}")