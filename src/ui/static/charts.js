// Chart utilities and configurations

// Chart colors
const chartColors = {
    primary: 'rgb(75, 192, 192)',
    success: 'rgb(40, 167, 69)',
    danger: 'rgb(220, 53, 69)',
    warning: 'rgb(255, 193, 7)',
    info: 'rgb(23, 162, 184)',
    dark: 'rgb(52, 58, 64)'
};

// Initialize equity chart
function initEquityChart() {
    const ctx = document.getElementById('equity-chart');
    if (!ctx) return null;
    
    return new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Equity',
                data: [],
                borderColor: chartColors.primary,
                backgroundColor: 'rgba(75, 192, 192, 0.1)',
                borderWidth: 2,
                tension: 0.1,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return 'Equity: $' + context.parsed.y.toFixed(2);
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    grid: {
                        display: false
                    }
                },
                y: {
                    display: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    ticks: {
                        callback: function(value) {
                            return '$' + value;
                        }
                    }
                }
            }
        }
    });
}

// Initialize drawdown chart
function initDrawdownChart() {
    const ctx = document.getElementById('drawdown-chart');
    if (!ctx) return null;
    
    return new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Drawdown',
                data: [],
                borderColor: chartColors.danger,
                backgroundColor: 'rgba(220, 53, 69, 0.1)',
                borderWidth: 2,
                tension: 0.1,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return 'Drawdown: ' + context.parsed.y.toFixed(2) + '%';
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    grid: {
                        display: false
                    }
                },
                y: {
                    display: true,
                    reverse: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                }
            }
        }
    });
}

// Initialize P&L sparkline
function initPnLSparkline() {
    const ctx = document.getElementById('pnl-sparkline');
    if (!ctx) return null;
    
    return new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
            labels: Array(20).fill(''),
            datasets: [{
                data: Array(20).fill(0),
                borderColor: chartColors.success,
                borderWidth: 1,
                pointRadius: 0,
                tension: 0.3,
                fill: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    enabled: false
                }
            },
            scales: {
                x: {
                    display: false
                },
                y: {
                    display: false
                }
            },
            elements: {
                line: {
                    borderWidth: 1
                }
            }
        }
    });
}

// Update chart data
function updateChartData(chart, labels, data) {
    if (!chart) return;
    
    chart.data.labels = labels;
    chart.data.datasets[0].data = data;
    chart.update('none'); // No animation for smooth updates
}

// Add data point to chart
function addChartDataPoint(chart, label, value) {
    if (!chart) return;
    
    const maxPoints = 50;
    
    chart.data.labels.push(label);
    chart.data.datasets[0].data.push(value);
    
    // Keep only last maxPoints
    if (chart.data.labels.length > maxPoints) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }
    
    chart.update('none');
}

// Create candlestick chart (for OHLC data)
function createCandlestickChart(canvasId, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    
    // Convert OHLC data to candlestick format
    const candlestickData = data.map(d => ({
        x: new Date(d[0]),
        o: d[1],
        h: d[2],
        l: d[3],
        c: d[4]
    }));
    
    return new Chart(ctx.getContext('2d'), {
        type: 'candlestick',
        data: {
            datasets: [{
                label: 'Price',
                data: candlestickData
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'day'
                    }
                }
            }
        }
    });
}

// Create volume chart
function createVolumeChart(canvasId, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    
    const volumeData = data.map(d => ({
        x: new Date(d[0]),
        y: d[5]
    }));
    
    return new Chart(ctx.getContext('2d'), {
        type: 'bar',
        data: {
            datasets: [{
                label: 'Volume',
                data: volumeData,
                backgroundColor: 'rgba(75, 192, 192, 0.5)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'day'
                    }
                },
                y: {
                    ticks: {
                        callback: function(value) {
                            return formatNumber(value);
                        }
                    }
                }
            }
        }
    });
}

// Export functions
window.initEquityChart = initEquityChart;
window.initDrawdownChart = initDrawdownChart;
window.initPnLSparkline = initPnLSparkline;
window.updateChartData = updateChartData;
window.addChartDataPoint = addChartDataPoint;
window.createCandlestickChart = createCandlestickChart;
window.createVolumeChart = createVolumeChart;