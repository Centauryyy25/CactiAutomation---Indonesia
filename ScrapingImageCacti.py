import pymysql
import os
from App import pipeline_lock
import requests
import re

from progress_tracker import progress
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import StaleElementReferenceException
import traceback
import time
from datetime import datetime
import logging
from urllib.parse import urlparse


# Fungsi untuk mengubah nama file agar valid di sistem file
def sanitize_filename(title):
    # Ganti karakter yang tidak valid dengan underscore
    sanitized_title = re.sub(r'[\/:*?"<>|]', '_', title)
    # Potong nama file agar tidak terlalu panjang
    max_length = 255  # Batasi panjang file (tergantung sistem file)
    return sanitized_title[:max_length]


DB_CONFIG = {
    # 'host': 'localhost',
    # 'user': 'root',
    # 'password': 'UrPassword',
    # 'database': 'UrDB'
}

log_folder = "Debug"
os.makedirs(log_folder, exist_ok=True)

# Nama file log berdasarkan tanggal hari ini
log_filename = datetime.now().strftime("%Y-%m-%d") + ".log"
log_path = os.path.join(log_folder, log_filename)

# Atur konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def connect_to_database(retries=3, delay=2):
    """Mencoba koneksi ke database dengan retries."""
    for attempt in range(retries):
        try:
            logger.info(f"Menghubungkan ke database... (Percobaan {attempt + 1})")
            connection = pymysql.connect(**DB_CONFIG)
            logger.info("Berhasil terhubung ke database.")
            return connection
        except pymysql.MySQLError as e:
            logger.error(f"Gagal konek database: {str(e)}")
            time.sleep(delay)
    raise Exception("Gagal konek ke database setelah beberapa percobaan.")

def insert_data(connection, title, graph_url, local_path, keterangan):
    """Menyimpan data ke tabel cacti_graph."""
    sql = "INSERT INTO cacti_graph (title, graph_url, local_path, keterangan) VALUES (%s, %s, %s, %s)"
    with connection.cursor() as cursor:
        logger.info(f"Menyimpan data: {title}, {graph_url}, {local_path}, {keterangan}")
        cursor.execute(sql, (title, graph_url, local_path, keterangan))
        connection.commit()
        logger.info("Data berhasil disimpan.")

def handle_database_error(connection, title, graph_url, local_path, error_message):
    """Menyimpan data error ke database."""
    if not connection or not connection.open:
        logger.error("Koneksi tidak valid untuk menyimpan error")
        return False
    
    try:
        keterangan = f"Gagal: {error_message[:250]}"
        with connection.cursor() as cursor:
            sql = "INSERT INTO cacti_graph (title, graph_url, local_path, keterangan) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (title, graph_url, local_path, keterangan))
            connection.commit()
            logger.info("Data error berhasil disimpan ke database.")
            return True
    except Exception as inner_e:
        connection.rollback()
        logger.error(f"Gagal menyimpan error ke database: {str(inner_e)}")
        return False

def save_to_database(title, graph_url, local_path, keterangan=None):
    connection = None
    try:
        connection = connect_to_database()
        if keterangan is None:
            keterangan = "Sukses"
        insert_data(connection, title, graph_url, local_path, keterangan)
        
    except Exception as ex:
        logger.error(f"Terjadi kesalahan: {str(ex)}")
        try:
            # Coba simpan error dengan koneksi yang sama
            if connection and connection.open:
                handle_database_error(connection, title, graph_url, local_path, str(ex))
            else:
                # Buat koneksi baru hanya jika diperlukan
                new_conn = connect_to_database()
                handle_database_error(new_conn, title, graph_url, local_path, str(ex))
                new_conn.close()
        except Exception as inner_ex:
            logger.critical(f"Gagal total menyimpan data: {str(inner_ex)}")
            return False
    finally:
        if connection and connection.open:
            connection.close()
    return False



# Fungsi untuk mendownload gambar
def save_graph_image(graph_url, title, driver):
    try:
        filename = f"{sanitize_filename(title)}.png"
        local_path = os.path.join("downloaded_graphs", filename)

        if not os.path.exists("downloaded_graphs"):
            os.makedirs("downloaded_graphs")

        # Ambil cookies dari Selenium
        selenium_cookies = driver.get_cookies()
        session = requests.Session()
        for cookie in selenium_cookies:
            session.cookies.set(cookie['name'], cookie['value'])

        logger.info(f"Mendownload gambar dari {graph_url}...")
        response = session.get(graph_url)

        if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
            with open(local_path, 'wb') as f:
                f.write(response.content)
            logger.info(f"Gambar berhasil disimpan ke {local_path}")
            return local_path
        else:
            logger.info(f"[ERROR] Gagal mengunduh gambar. Status Code: {response.status_code}, Content-Type: {response.headers.get('Content-Type')}")
            return None

    except Exception as e:
        logger.info(f"[ERROR] Gagal mendownload gambar: {str(e)}")
        return None

def extract_short_title(full_title):
    try:
        parts = full_title.split(' - ')
        short_title = parts[-1].strip()

        # Hapus tanda kutip tunggal atau ganda kalau ada
        short_title = short_title.replace("'", "").replace('"', '')
        
        return short_title
    except Exception as e:
        logger.info(f"[ERROR] Gagal ekstrak short title: {str(e)}")
        return full_title

def retry_on_stale_element(max_retries=3, delay=1):
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except StaleElementReferenceException:
                    print(f"[WARN] Stale element detected. Retrying {retries + 1}/{max_retries}...")
                    time.sleep(delay)
                    retries += 1
            raise Exception(f"[ERROR] Failed after {max_retries} retries due to stale element.")
        return wrapper
    return decorator

def check_and_click_zoom(driver, username):
    try:
        # 1. Cek apakah ada pesan "no data"
        no_data_markers = [
            "No data sources present",
            "Tidak ada data",
            "No matching records found"
        ]
        
        for marker in no_data_markers:
            if marker in driver.page_source:
                print(f"[WARN] Data tidak tersedia untuk {username}")
                return False, f"Data tidak tersedia (Marker: {marker})"

        debug_dir = "Debug/debug_screenshots"
        os.makedirs(debug_dir, exist_ok=True)
        driver.save_screenshot(f"{debug_dir}/{username}_before_zoom_check.png")

        # 2. Multi-strategy untuk menemukan link Zoom
        zoom_selectors = [
            {"type": "xpath", "value": "//a[contains(@href,'graph.php?action=zoom')]"},
            {"type": "xpath", "value": "//a[img[contains(@src,'graph_image.php')]]"},
            {"type": "css", "value": "a.graph-zoom"},
            {"type": "xpath", "value": "//a[contains(@onclick,'graph_zoom')]"},
            {"type": "xpath", "value": "//a[contains(@class,'zoomLink')]"},
            {"type": "xpath", "value": "//a[contains(text(),'Zoom')]"},
            {"type": "xpath", "value": "//a[normalize-space(.)='Zoom']"},
            # Additional selector for img inside any a element
            {"type": "xpath", "value": "//a[.//img]"}
        ]

        for selector in zoom_selectors:
            try:
                if selector["type"] == "xpath":
                    zoom_link = WebDriverWait(driver, 1).until(
                        EC.presence_of_element_located((By.XPATH, selector["value"]))
                    )
                else:
                    zoom_link = WebDriverWait(driver, 1).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector["value"]))
                    )
                
                logger.info(f"[DEBUG] Link Zoom ditemukan dengan {selector['type']}: {selector['value']}")
                return True, zoom_link
            except Exception as e:
                logger.info(f"[DEBUG] Gagal menemukan Zoom link dengan selector {selector['value']}: {str(e)}")
                continue

        # 3. Fallback: Cek apakah ada grafik tanpa link zoom
        graph_images = driver.find_elements(By.XPATH, "//img[contains(@src,'graph_image.php')]")
        if graph_images:
            print(f"[WARN] Grafik ditemukan tapi tanpa link Zoom untuk {username}")
            return False, "Grafik ada tetapi tidak ada link Zoom"
        
        return False, "Link Zoom tidak ditemukan dengan semua selector"

    except Exception as e:
        print(f"[ERROR] Terjadi error dalam pencarian Zoom untuk {username}: {str(e)}")
        logger.error("Error detail:", exc_info=True)
        # Print full traceback untuk debugging lebih lanjut
        return False, f"Error dalam pencarian Zoom: {str(e)}"

@retry_on_stale_element(max_retries=3, delay=1)
def fill_filter_input(driver, username):
    filter_input = driver.find_element(By.NAME, 'filter')
    filter_input.clear()
    filter_input.send_keys(username)

def setup_logging():
    """Setup comprehensive logging configuration"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Main logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # File handler for debug logs
    file_handler = logging.FileHandler('application.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Fungsi untuk mengotomatiskan login dan scraping untuk setiap username
def login_and_scrape(date1="2025-03-01 00:00", date2="2025-04-01 00:00", target_url="https://nms.cbn.id/", userLogin="", userPass="", usernames=None):
    driver = None
    results = {
        "total_processed": 0,
        "success": 0,
        "failed": 0,
        "processed_usernames": [],
        "errors": []
    }

    progress.scraping['total'] = len(usernames)
    # Tentukan folder untuk menyimpan gambar lokal
    image_folder = "downloaded_graphs"
    os.makedirs(image_folder, exist_ok=True)

    try:
        print("[INFO] Memulai WebDriver...")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        wait = WebDriverWait(driver, 15)

        print(f"[INFO] Membuka halaman login: {target_url}")
        driver.get(target_url)  # Gunakan URL dari parameter

        print("[INFO] Mengisi username dan password...")
        username_input = wait.until(EC.presence_of_element_located((By.NAME, 'login_username')))
        password_input = driver.find_element(By.NAME, 'login_password')
        login_button = driver.find_element(By.CLASS_NAME, 'button--primary')

        username_input.send_keys({userLogin})
        password_input.send_keys({userPass})
        login_button.click()

        print("[INFO] Mengisi tanggal awal...")
        date1_input = wait.until(EC.presence_of_element_located((By.ID, "date1")))
        date1_input.clear()
        date1_input.send_keys(date1)  # Use the passed parameter

        print("[INFO] Mengisi tanggal akhir...")
        date2_input = driver.find_element(By.ID, "date2")
        date2_input.clear()
        date2_input.send_keys(date2)  # Use the passed parameter

        print("[INFO] Menekan tombol Refresh...")
        refresh_button = driver.find_element(By.NAME, "button_refresh_x")
        refresh_button.click()

        # Proses otomatis untuk setiap username
        for i, username in enumerate(usernames, 1):
            results["total_processed"] += 1
            results["processed_usernames"].append(username)
            progress.scraping.update({
            'current': i,
            'total': len(usernames),
            'message': f'Memproses {username} ({i}/{len(usernames)})',
            'current_file': username,
            'status': 'running'
            })
            try:
                fill_filter_input(driver, username)

                logger.info("[DEBUG] Mencari tombol Go...")
                go_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@value='Go' and @title='Set/Refresh Filters']"))
                )
                if not go_button:
                    error_msg = f"Gagal Menemukan btton {username}"
                    print(f"[ERROR] {error_msg}")
                    results["failed"] += 1
                    results["errors"].append({"username": username, "error": error_msg})
                logger.info("[DEBUG] Tombol Go ditemukan, mencoba klik...")
                # driver.save_screenshot(f"debug_{username}_before_go.png")
                go_button.click()
                logger.info("[DEBUG] Tombol Go diklik")
    
                # [Sebelum mencari link Zoom]
                logger.info(f"[DEBUG] Memeriksa ketersediaan data untuk {username}")

                # Gunakan fungsi deteksi zoom yang ditingkatkan
                zoom_found, zoom_result = check_and_click_zoom(driver, username)

                if not zoom_found:
                    error_msg = f"Gagal menemukan Zoom untuk {username}: {zoom_result}"
                    print(f"[ERROR] {error_msg}")
                    
                    # Simpan screenshot dengan annotation
                    # 1. Buat folder khusus jika belum ada
                    no_zoom_dir = "no_zoom_reports"
                    os.makedirs(no_zoom_dir, exist_ok=True)  # exist_ok=True agar tidak error jika folder sudah ada
                    
                    # 2. Simpan screenshot ke folder baru
                    screenshot_path = os.path.join(no_zoom_dir, f"no_zoom_{username}.png")
                    driver.save_screenshot(screenshot_path)
                    
                    # (Opsional) Simpan HTML ke folder yang sama
                    # html_path = os.path.join(no_zoom_dir, f"no_zoom_{username}_page.html")
                    # with open(html_path, "w", encoding="utf-8") as f:
                    #     f.write(driver.page_source)
                    
                    # Simpan detail HTML untuk analisis
                    # with open(f"no_zoom_{username}_page.html", "w", encoding="utf-8") as f:
                    #     f.write(driver.page_source)
                    
                    save_to_database(
                        title=f"NoZoom-{username}",
                        graph_url=driver.current_url,
                        local_path=f"no_zoom_{username}.png",
                        keterangan=error_msg
                    )
                    results["failed"] += 1
                    results["errors"].append({"username": username, "error": error_msg})
                    continue

                # Jika zoom ditemukan
                zoom_link = zoom_result
                print("[DEBUG] Klik link Zoom...")
                try:
                    driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth',block:'center'});", zoom_link)
                    time.sleep(1)  # Beri waktu untuk scroll
                    driver.execute_script("arguments[0].click();", zoom_link)
                except Exception as click_error:
                    error_msg = f"Invalid zoom {username}"
                    print(f"[ERROR] {error_msg}")
                    print(f"[ERROR] Gagal klik Zoom: {str(click_error)}")
                    results["failed"] += 1
                    results["errors"].append({"username": username, "error": error_msg})
                    continue

            except Exception as e:
                error_msg = f"Gagal Menemukan {username}"
                print(f"[ERROR] {error_msg}")
                
                # Simpan error ke database
                short_title = f"Error-{username}"
                save_to_database(
                    title=short_title,
                    graph_url="N/A", 
                    local_path="N/A",
                    keterangan=error_msg
                )
                results["failed"] += 1
                results["errors"].append({"username": username, "error": error_msg})
                continue

            # Coba ambil gambar graph
            try:
                print("[INFO] Menunggu gambar Graph muncul setelah klik Zoom...")
                graph_img = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//img[contains(@src, 'graph_image.php')]"))
                )
                graph_src = graph_img.get_attribute("src")
                print(f"[INFO] Gambar Graph ditemukan: {graph_src}")

                # Lanjutkan dengan penyimpanan gambar dan data lainnya...
            except Exception as e:
                error_msg = f"Gagal Menemukan gambar {username}"
                print(f"[ERROR] {error_msg}")
                print(f"[ERROR] Gambar Graph tidak ditemukan untuk {username}. Error: {str(e)}")
                results["failed"] += 1
                results["errors"].append({"username": username, "error": error_msg})
                continue

            if not graph_src.startswith("http"):
                graph_src = "https://nms.cbn.id/" + graph_src

            print("[INFO] Mengambil judul grafik...")
            try:
                td_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//td[contains(., 'Zooming Graph')]"))
                )
                title_text = td_element.text.strip()
                short_title = extract_short_title(title_text)

                print(f"\n[HASIL] Username: {username}")
                print(f"Judul pendek: {short_title}")
                print(f"Gambar URL: {graph_src}")

                local_path = save_graph_image(graph_src, short_title, driver)

                if local_path:
                    save_to_database(short_title, graph_src, local_path)
                    results["success"] += 1
                    logger.info(f"[SUCCESS] Processed {username} successfully")

            except Exception as e:
                error_msg = f"Gagal mengambil graph untuk {username}. Lanjut username berikutnya..."
                print(f"[ERROR] {error_msg}")
                results["failed"] += 1
                results["errors"].append({"username": username, "error": error_msg})
                continue                    


            # Klik Preview Mode (keluar dari blok try-except atas)
            try:
                print("[INFO] Klik link Preview Mode...")
                preview_link = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.LINK_TEXT, "Preview Mode"))
                )
                preview_link.click()

                print("[INFO] Menunggu halaman Preview Mode terbuka...")
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "filter"))
                )

                print(f"[INFO] Menekan tombol Go lagi untuk username: {username} di Preview Mode")
                go_button = driver.find_element(By.XPATH, "//input[@value='Go' and @title='Set/Refresh Filters']")
                go_button.click()

                time.sleep(2)

            except Exception as e:
                print(f"[ERROR] Gagal klik Preview Mode untuk {username}. Lanjut username berikutnya...\n")
                continue


        # Summary report
        logger.info("\n===== SCRAPING SUMMARY =====")
        logger.info(f"Total usernames: {len(usernames)}")
        logger.info(f"Successful: {results['success']}")
        logger.info(f"Failed: {results['failed']}")
        logger.info(f"Missing: {len(usernames) - results['total_processed']}")

        progress.scraping['message'] = f'Selesai. Sukses: {results["success"]}, Gagal: {results["failed"]}'

        #     Calculate unprocessed usernames
        all_processed = set(results["processed_usernames"])
        all_usernames = set(usernames)
        unprocessed = all_usernames - all_processed

        with open("scraping_report.txt", "w") as report_file:
            report_file.write(f"SCRAPING REPORT\n")
            report_file.write(f"Date range: {date1} to {date2}\n")
            report_file.write(f"Total usernames: {len(usernames)}\n")
            report_file.write(f"Successful: {results['success']}\n")
            report_file.write(f"Failed: {results['failed']}\n\n")
            processed = set(results["success"] + [x.split(":")[0] for x in results["failed"]])
            unprocessed = set(usernames) - processed
            
            if unprocessed:
                report_file.write("UNPROCESSED USERNAMES:\n")
                for u in unprocessed:
                    report_file.write(f"{u}: Tidak diproses sama sekali (missed in loop)\n")
                report_file.write("\n")

            if results["errors"]:
                report_file.write("ERROR DETAILS:\n")
                for error in results["errors"]:
                    report_file.write(f"{error['username']}: {error['error']}\n")
    
    except Exception as e:
        progress.scraping['message'] = f'Error saat memproses {username}: {str(e)}'
        traceback.print_exc()

    # Write report to file

    finally:
        if driver:
            print("[INFO] Menutup browser...")
            with pipeline_lock:
                progress.scraping.update({
                    'status': 'complete',
                    'message': f'Scraping selesai! Sukses: {results["success"]}, Gagal: {results["failed"]}',
                    'current_file': '',
                    'current': len(usernames)
                })
            driver.quit()

if __name__ == '__main__':
    login_and_scrape()
