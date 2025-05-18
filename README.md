# Cacti Dashboard

A Flask web application designed to interface with a MySQL database and display Cacti network monitoring data.

## Overview
Aplikasi ini berfungsi sebagai dashboard untuk data monitoring jaringan dari Cacti. Pengguna dapat:
- Memilih judul unik dari database dan mengambil data berdasarkan rentang tanggal tertentu.
- Menambahkan data CSV baru dari sistem Cacti dengan memasukkan URL, yang kemudian akan diproses dan disimpan.
- Menampilkan visualisasi lalu lintas masuk dan keluar (inbound & outbound) dalam satuan Gbps melalui grafik batang yang jelas.

## Features
- **Data Retrieval**: Query network traffic data from the MySQL database using titles and date ranges.
- **Data Processing**: Extract and sanitize titles and traffic data from CSV files.
- **Interactive UI**: Use a responsive, styled HTML/CSS frontend with JavaScript for dynamic updates.
- **Visualization**: Display traffic data using Chart.js for an easy-to-understand visual representation.
- **Database Management**: Automatically insert and ignore duplicate records in the database.

## Usage

- **Home Page**: Displays unique titles fetched from the database.
  - Select a title and specify a date range to fetch and display the data.
  - Results are presented in a table and as bar charts.
- **Add URL**: Enter a new URL to extract data from a Cacti system.
  - The application logs in, downloads the CSV, and adds the data to the database.

## Configuration

- **Database Configuration**: Update the `db_config` dictionary in `APP.py` with your MySQL host, user, password, and database name.
- **Cacti Login Details**: Update the `login_url` and login credentials in the `add_url_to_database` function to match your Cacti setup.

## Technologies Used

- **Backend**: Python, Flask, MySQL
- **Frontend**: HTML, CSS, JavaScript, Chart.js
- **Libraries**:
  - `requests` and `BeautifulSoup` for web scraping
  - `pandas` for data manipulation
  - `mysql-connector-python` for database interactions


