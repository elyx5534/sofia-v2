/**
 * Sofia V2 Dashboard JavaScript
 * Handles chart initialization and real-time updates
 */

const Dashboard = {
    charts: {},
    updateInterval: null,

    init() {
        this.initPortfolioChart();
        this.startRealTimeUpdates();
        this.updateLastUpdateTime();
    },

    initPortfolioChart() {
        const ctx = document.getElementById('portfolio-chart');
        if (!ctx) return;

        // Sample data - TODO(real API): Replace with real portfolio data
        const data = {
            labels: ['9:00', '9:30', '10:00', '10:30', '11:00', '11:30', '12:00', '12:30', '13:00', '13:30', '14:00', '14:30', '15:00', '15:30', '16:00'],
            datasets: [{
                label: 'Portfolio Value',
                data: [100000, 101500, 103200, 102800, 105600, 108900, 106700, 109200, 112300, 115600, 118900, 122300, 125400, 123800, 125430],
                borderColor: '#9333ea',
                backgroundColor: 'rgba(147, 51, 234, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: '#9333ea',
                pointHoverBorderColor: '#fff',
                pointHoverBorderWidth: 2
            }]
        };

        this.charts.portfolio = new Chart(ctx, {
            type: 'line',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        display: true,
                        grid: {
                            display: true,
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.6)'
                        }
                    },
                    y: {
                        display: true,
                        grid: {
                            display: true,
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.6)',
                            callback: function(value) {
                                return '$' + (value / 1000).toFixed(0) + 'k';
                            }
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        });
    },

    async startRealTimeUpdates() {
        // TODO(real API): Connect to WebSocket for real-time updates
        this.updateInterval = setInterval(() => {
            this.simulateDataUpdate();
            this.updateLastUpdateTime();
        }, 5000);
    },

    simulateDataUpdate() {
        // TODO(real API): Replace with real data fetching
        try {
            // Simulate balance update
            const balanceEl = document.getElementById('total-balance-value');
            if (balanceEl) {
                const currentBalance = parseFloat(balanceEl.textContent.replace(/[$,]/g, ''));
                const change = (Math.random() - 0.5) * 1000; // Random change ±$500
                const newBalance = currentBalance + change;
                balanceEl.textContent = Sofia.formatCurrency(newBalance);
            }

            // Simulate P&L update
            const pnlEl = document.getElementById('pnl-today-value');
            if (pnlEl) {
                const currentPnL = parseFloat(pnlEl.textContent.replace(/[+$,]/g, ''));
                const change = (Math.random() - 0.5) * 200; // Random change ±$100
                const newPnL = currentPnL + change;
                pnlEl.textContent = (newPnL >= 0 ? '+' : '') + Sofia.formatCurrency(Math.abs(newPnL));
                pnlEl.className = newPnL >= 0 ? 'text-2xl font-bold text-green-400 mb-2' : 'text-2xl font-bold text-red-400 mb-2';
            }

            // Update portfolio chart
            if (this.charts.portfolio) {
                const chart = this.charts.portfolio;
                const newValue = 125000 + (Math.random() - 0.5) * 5000;
                
                // Add new data point
                chart.data.labels.push(new Date().toLocaleTimeString('en-US', { 
                    hour12: false, 
                    hour: '2-digit', 
                    minute: '2-digit' 
                }));
                chart.data.datasets[0].data.push(newValue);

                // Keep only last 15 points
                if (chart.data.labels.length > 15) {
                    chart.data.labels.shift();
                    chart.data.datasets[0].data.shift();
                }

                chart.update('none');
            }

        } catch (error) {
            console.error('Error updating dashboard:', error);
        }
    },

    updateLastUpdateTime() {
        const timeEl = document.getElementById('last-update');
        if (timeEl) {
            timeEl.textContent = 'just now';
            
            // Start countdown
            let seconds = 0;
            const countdown = setInterval(() => {
                seconds++;
                if (seconds < 60) {
                    timeEl.textContent = `${seconds} seconds ago`;
                } else {
                    clearInterval(countdown);
                }
            }, 1000);
        }
    },

    destroy() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
        
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        
        this.charts = {};
    }
};

// Handle page visibility for performance
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        Dashboard.destroy();
    } else {
        Dashboard.init();
    }
});

// Export for global access
window.Dashboard = Dashboard;