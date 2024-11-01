##Cacti Dashboard
A Flask web application designed to interface with a MySQL database and display Cacti network monitoring data. 

## Overview
This application serves as a dashboard for Cacti network monitoring data. Users can:
- Select unique titles from the database and fetch data within a specified date range.
- Add new CSV data from a Cacti system by providing URLs, which are then processed and stored.
- Visualize inbound and outbound traffic in Gbps with clear bar charts.

## Features
- **Data Retrieval**: Query network traffic data from the MySQL database using titles and date ranges.
- **Data Processing**: Extract and sanitize titles and traffic data from CSV files.
- **Interactive UI**: Use a responsive, styled HTML/CSS frontend with JavaScript for dynamic updates.
- **Visualization**: Display traffic data using Chart.js for an easy-to-understand visual representation.
- **Database Management**: Automatically insert and ignore duplicate records in the database.

