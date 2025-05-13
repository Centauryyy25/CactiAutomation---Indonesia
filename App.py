from flask import Flask, render_template, request, redirect, send_file, jsonify, Response
import os
from flask_cors import CORS
from datetime import datetime, timedelta
import json
import time
from threading import Thread, Lock
from progress_tracker import progress

app = Flask(__name__)
CORS(app)
worker_thread = None
pipeline_lock = Lock()


def execute_pipeline(date1, date2, target_url, userLogin, userpass, usernames):
    try:
        from main_pipeline import step1_scrape_images, step2_ocr_images, step3_clean_csv

        step1_scrape_images(date1, date2, target_url, userLogin, userpass, usernames)
        step2_ocr_images()
        step3_clean_csv()

        with pipeline_lock:
            progress.scraping.update({
                'status': 'complete',
                'message': 'Proses selesai!'
            })

    except Exception as e:
        with pipeline_lock:
            progress.scraping.update({
                'status': 'error',
                'message': f"Error: {str(e)}"
            })


@app.route('/')
def index():
    today = datetime.now()
    one_month_ago = today - timedelta(days=30)

    default_date1 = one_month_ago.strftime("%Y-%m-%dT%H:%M")
    default_date2 = today.strftime("%Y-%m-%dT%H:%M")

    return render_template('index.html',
                           default_date1=default_date1,
                           default_date2=default_date2,
                           default_url="https://nms.cbn.id/")


@app.route('/progress')
def progress_stream():
    def generate():
        last_id = 0
        while True:
            try:
                with pipeline_lock:
                    data = {
                        'scraping': progress.scraping,
                        'ocr': progress.ocr
                    }
                yield f"id: {last_id}\ndata: {json.dumps(data)}\n\n"
                last_id += 1
                time.sleep(0.5)
            except GeneratorExit:
                print("Client disconnected")
                break
            except Exception as e:
                print(f"SSE Error: {str(e)}")
                time.sleep(1)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache'}
    )


@app.route('/run_pipeline', methods=['POST'])
def run_pipeline():
    global worker_thread
    try:
        with pipeline_lock:
            progress.scraping.update({
                'current': 0,
                'total': 4,
                'message': 'Memulai proses...',
                'status': 'running',
                'current_file': ''
            })
            progress.ocr.update({
                'current': 0,
                'total': 1,
                'message': 'Menunggu...',
                'status': 'idle',
                'current_file': ''
            })

        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        usernames_input = data['usernames'].strip()
        if not usernames_input:
            return jsonify({"status": "error", "message": "Usernames cannot be empty"}), 400
        # Split dan bersihkan usernames
        usernames = [u.strip() for u in usernames_input.split(",") if u.strip()]
        
        # Pastikan ada usernames valid
        if not usernames:
            return jsonify({"status": "error", "message": "No valid usernames provided"}), 400
        
        date1 = data.get('date1')
        date2 = data.get('date2')
        target_url = data.get('target_url')
        userLogin = data.get('userLogin')
        userpass = data.get('userPass')

        worker_thread = Thread(
            target=execute_pipeline,
            args=(date1, date2, target_url, userLogin, userpass, usernames),
            daemon=True
        )
        worker_thread.start()

        return jsonify({"status": "started"}), 202

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/download')
def download_csv():
    path = "hasil_mbps.csv"
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "File tidak ditemukan"


if __name__ == '__main__':
    app.run(debug=True)