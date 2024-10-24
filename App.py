from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
from mysql.connector import Error
import requests
from bs4 import BeautifulSoup
import re
import csv
import pandas as pd
from datetime import datetime

app = Flask(__name__)

# MySQL connection configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'your password',
    'database': 'Cacti_Database'
}

# Function to fetch unique titles from the database
def get_unique_titles():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        cursor.execute("SELECT DISTINCT Title FROM Cacti_Table")
        titles = [row[0] for row in cursor.fetchall()]
        return titles
    except Error as e:
        print(f"Error: {e}")
        return []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Function to fetch data from the database within a specific date range
def fetch_data_by_title_and_date(title, start_datetime, end_datetime):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)  # Get results as a dictionary
        query = """
        SELECT Title, Date, Inbound_Gbps, Outbound_Gbps 
        FROM Cacti_Table 
        WHERE Title = %s AND Date BETWEEN %s AND %s
        """
        cursor.execute(query, (title, start_datetime, end_datetime))
        results = cursor.fetchall()
        return results
    except Error as e:
        print(f"Error: {e}")
        return []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Function to process a new URL and add the title and data to the database
def add_url_to_database(url):
    try:
        session = requests.Session()
        login_url = 'put_your_login_url'

        # Step 1: Log in to the cacti system
        login_page = session.get(login_url)
        soup = BeautifulSoup(login_page.text, 'html.parser')
        csrf_token = soup.find('input', {'name': '__csrf_magic'})['value']

        payload = {
            '__csrf_magic': csrf_token,
            'action': 'login',
            'login_username': 'username',
            'login_password': 'password',
            'remember_me': 'on'
        }

        login_response = session.post(login_url, data=payload)

        if not login_response.ok:
            return "Failed to log in to Cacti."

        # Step 2: Download the CSV file from the provided URL
        csv_response = session.get(url)
        if not csv_response.ok:
            return "Failed to download CSV file."

        # Step 3: Extract the title and data from the CSV file
        try:
            # Read the CSV data from the response content
            data = csv_response.content.decode('utf-8').splitlines()
            reader = csv.reader(data)
            title_row = next(reader)
            title = title_row[1]  # Extract the title from the second column
            safe_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()  # Sanitize the title

            # Find the "Date" row to identify the header
            headers = next(row for row in reader if row[0].startswith('Date'))

            # Create a pandas DataFrame from the remaining rows
            df = pd.DataFrame(reader, columns=headers)
            df['Inbound'] = df['Inbound'].astype(float) / 8_000_000_000  # Convert bits to gigabits
            df['Outbound'] = df['Outbound'].astype(float) / 8_000_000_000

            # Step 4: Insert data into the database
            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor()

            # Insert each row into the database
            for index, row in df.iterrows():
                insert_query = """
                INSERT IGNORE INTO Cacti_Table (Title, Date, Inbound_Gbps, Outbound_Gbps) 
                VALUES (%s, %s, %s, %s)
                """
                cursor.execute(insert_query, (safe_title, row['Date'], row['Inbound'], row['Outbound']))
            connection.commit()

        except Exception as e:
            return f"An error occurred while processing the URL: {e}"

        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

        return "Title and data added successfully!"

    except Exception as e:
        return f"An error occurred: {e}"

# Route to display the index page and titles
@app.route('/', methods=['GET', 'POST'])
def index():
    titles = get_unique_titles()  # Fetch unique titles from the database
    results = None

    if request.method == 'POST':
        title = request.form.get('title')
        start_date = request.form.get('start_date')
        start_time = request.form.get('start_time')
        end_date = request.form.get('end_date')
        end_time = request.form.get('end_time')

        if title and start_date and start_time and end_date and end_time:
            start_datetime = f"{start_date} {start_time}:00"
            end_datetime = f"{end_date} {end_time}:00"

            results = fetch_data_by_title_and_date(title, start_datetime, end_datetime)

    return render_template('index.html', titles=titles, results=results)

# Route to handle adding a new URL
@app.route('/add-url', methods=['POST'])
def add_url():
    new_url = request.form.get('new_url')
    if new_url:
        message = add_url_to_database(new_url)
        print(message)  # You can handle this message appropriately
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
