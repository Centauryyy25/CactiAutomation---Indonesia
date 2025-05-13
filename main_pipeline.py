
from ScrapingImageCacti import login_and_scrape
from progress_tracker import progress
from easyocr_image_to_text import image_to_text, process_images_in_folder, clean_ocr_text, save_processed_data, convert_json_to_csv
from testingClean import process_csv
import os
import time
from datetime import datetime

def step1_scrape_images(date1="2025-03-01 00:00", date2="2025-04-01 00:00", target_url="", userLogin="", userPass="", usernames=""):
    print("\n📥 STEP 1: Scraping data dan gambar...")
    login_and_scrape(date1, date2, target_url, userLogin, userPass, usernames)

def step2_ocr_images(folder="downloaded_graphs", csv_output="hasil.csv"):
    print("\n🔎 STEP 2: OCR semua gambar di folder:", folder)

    images = [f for f in os.listdir(folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    # Update progress OCR
    progress.ocr.update({
        'current': 0,
        'total': len(images),
        'status': 'running',
        'message': 'Memulai proses OCR...'
    })
    
    all_results = process_images_in_folder(
        folder=folder,
        output_dir="processed_output",
        lang="en",
        use_gpu=False
    )
    
    progress.ocr.update({
        'status': 'complete',
        'message': 'Proses OCR selesai!'
    })
    
    json_path = save_processed_data(all_results, output_dir="processed_output")
    convert_json_to_csv(json_path, csv_output)


def step3_clean_csv(csv_input="hasil.csv", csv_output="hasil_mbps.csv"):
    print("\n📊 STEP 3: Konversi Kbps → Mbps pada file:", csv_input)
    process_csv(csv_input, csv_output)

if __name__ == "__main__":
    start = time.time()

    step1_scrape_images()
    step2_ocr_images()
    step3_clean_csv()

    print(f"\n✅ Pipeline selesai dalam {time.time() - start:.2f} detik.")
