// Function to show/hide the date and time inputs based on title selection
function showDateTimeInputs() {
    const dateTimeSection = document.getElementById('date-time-section');
    dateTimeSection.style.display = 'block';
}

// Script for rendering the chart using Chart.js
document.addEventListener('DOMContentLoaded', (event) => {
    const resultsJsonElement = document.getElementById('results-json');
    if (resultsJsonElement) {
        const fetchedResults = JSON.parse(resultsJsonElement.textContent);

        const labels = fetchedResults.map(row => row.Date);
        const inboundData = fetchedResults.map(row => row.Inbound_Gbps);
        const outboundData = fetchedResults.map(row => row.Outbound_Gbps);
        const title = fetchedResults[0] ? fetchedResults[0].Title : 'Bandwidth Usage'; 

        const ctx = document.getElementById('bandwidthChart').getContext('2d');
        const bandwidthChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Inbound (Gbps)',
                        data: inboundData,
                        backgroundColor: 'yellow'
                    },
                    {
                        label: 'Outbound (Gbps)',
                        data: outboundData,
                        backgroundColor: 'blue'
                    }
                ]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Bandwidth Usage (Gbps)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    title: {
                        display: true,
                        text: title
                    }
                }
            }
        });
    }
});
