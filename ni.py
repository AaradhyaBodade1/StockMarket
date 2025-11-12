
"""
SMMA Crossover Alert System for Nifty50 and Sensex
Monitors 9-period and 20-period SMMA indicators and sends email alerts on crossovers.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import smtplib
import time
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os
from collections import defaultdict

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('smma_alerts.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SMMAIndicator:
    """Calculate Smoothed Moving Average (SMMA)"""
    
    def __init__(self, period):
        self.period = period
        self.smma = None
        self.count = 0
    
    def calculate(self, prices):
        """
        Calculate SMMA for a series of prices
        Initial SMMA = SMA of first N periods
        Subsequent SMMA = (Previous SMMA * (N-1) + Current Price) / N
        """
        if len(prices) < self.period:
            return None
        
        smma_values = []
        
        # Initial SMMA is SMA of first period
        initial_sma = prices[:self.period].mean()
        smma_values.append(initial_sma)
        
        # Calculate subsequent SMMA values
        for i in range(self.period, len(prices)):
            smma = (smma_values[-1] * (self.period - 1) + prices.iloc[i]) / self.period
            smma_values.append(smma)
        
        return np.array(smma_values)


class CrossoverDetector:
    """Detect SMMA crossovers with price candles"""
    
    def __init__(self):
        self.previous_state = defaultdict(dict)  # Track previous crossover state
    
    def detect_crossover(self, index_name, smma_period, current_price, smma_value, prev_smma_value):
        """
        Detect if SMMA crosses above or below the price candle
        Returns: 'bullish', 'bearish', or None
        """
        state_key = f"{index_name}_SMMA{smma_period}"
        
        if state_key not in self.previous_state:
            # Initialize tracking
            self.previous_state[state_key] = {
                'price': current_price,
                'smma': smma_value
            }
            return None
        
        prev_state = self.previous_state[state_key]
        prev_price = prev_state['price']
        prev_smma = prev_state['smma']
        
        crossover_signal = None
        
        # Check for bullish crossover (SMMA crosses above price)
        if prev_smma <= prev_price and smma_value > current_price:
            crossover_signal = 'bullish'
        
        # Check for bearish crossover (SMMA crosses below price)
        elif prev_smma >= prev_price and smma_value < current_price:
            crossover_signal = 'bearish'
        
        # Update state
        self.previous_state[state_key] = {
            'price': current_price,
            'smma': smma_value
        }
        
        return crossover_signal


class EmailAlerter:
    """Send email alerts via SMTP"""
    
    def __init__(self):
        self.sender_email = os.getenv('SMTP_EMAIL')
        self.sender_password = os.getenv('SMTP_PASSWORD')
        self.recipient_email = os.getenv('RECIPIENT_EMAIL')
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
    
    def send_alert(self, subject, body):
        """Send email alert"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"Email sent: {subject}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False


class IndexMonitor:
    """Monitor individual index with SMMA indicators"""
    
    def __init__(self, index_name, ticker_symbol, alerter):
        self.index_name = index_name
        self.ticker_symbol = ticker_symbol
        self.alerter = alerter
        self.smma_9 = SMMAIndicator(9)
        self.smma_20 = SMMAIndicator(20)
        self.crossover_detector = CrossoverDetector()
        self.last_alert_time = defaultdict(lambda: datetime.min)
    
    def fetch_latest_data(self, interval='1h'):
        """
        Fetch latest candle data
        interval: '1m', '5m', '15m', '1h', '1d'
        """
        try:
            # Fetch last 100 candles to ensure we have enough for SMMA calculation
            ticker = yf.Ticker(self.ticker_symbol)
            data = ticker.history(period='30d', interval=interval)
            
            if data.empty:
                logger.warning(f"No data fetched for {self.index_name}")
                return None
            
            return data
        
        except Exception as e:
            logger.error(f"Error fetching data for {self.index_name}: {str(e)}")
            return None
    
    def analyze_and_alert(self, interval='1h'):
        """Analyze latest candle and detect crossovers"""
        data = self.fetch_latest_data(interval)
        
        if data is None or len(data) < 20:
            return
        
        # Get the latest closing prices
        closes = data['Close']
        
        # Calculate SMMA values
        smma_9_values = self.smma_9.calculate(closes)
        smma_20_values = self.smma_20.calculate(closes)
        
        if smma_9_values is None or smma_20_values is None:
            logger.warning(f"Not enough data for SMMA calculation for {self.index_name}")
            return
        
        # Get latest values
        current_price = closes.iloc[-1]
        current_smma_9 = smma_9_values[-1]
        prev_smma_9 = smma_9_values[-2] if len(smma_9_values) > 1 else smma_9_values[-1]
        
        current_smma_20 = smma_20_values[-1]
        prev_smma_20 = smma_20_values[-2] if len(smma_20_values) > 1 else smma_20_values[-1]
        
        # Check for crossovers
        crossover_9 = self.crossover_detector.detect_crossover(
            self.index_name, 9, current_price, current_smma_9, prev_smma_9
        )
        
        crossover_20 = self.crossover_detector.detect_crossover(
            self.index_name, 20, current_price, current_smma_20, prev_smma_20
        )
        
        # Send alerts with rate limiting (max once per 5 minutes per signal)
        alert_cooldown = timedelta(minutes=5)
        
        if crossover_9:
            alert_key_9 = f"{self.index_name}_SMMA9_{crossover_9}"
            if datetime.now() - self.last_alert_time[alert_key_9] > alert_cooldown:
                self._send_crossover_alert(9, crossover_9, current_price, current_smma_9)
                self.last_alert_time[alert_key_9] = datetime.now()
        
        if crossover_20:
            alert_key_20 = f"{self.index_name}_SMMA20_{crossover_20}"
            if datetime.now() - self.last_alert_time[alert_key_20] > alert_cooldown:
                self._send_crossover_alert(20, crossover_20, current_price, current_smma_20)
                self.last_alert_time[alert_key_20] = datetime.now()
        
        # Log current state
        logger.info(
            f"{self.index_name} | Price: {current_price:.2f} | "
            f"SMMA9: {current_smma_9:.2f} | SMMA20: {current_smma_20:.2f}"
        )
    
    def _send_crossover_alert(self, period, signal_type, price, smma_value):
        """Send crossover alert email"""
        signal_text = "BULLISH ↑" if signal_type == 'bullish' else "BEARISH ↓"
        subject = f"🚀 {self.index_name} SMMA{period} {signal_text} Crossover Alert"
        
        body = f"""
SMMA Crossover Alert - {self.index_name}

Signal Type: {signal_type.upper()}
SMMA Period: {period}
Current Price: {price:.2f}
SMMA Value: {smma_value:.2f}

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This is an automated alert from SMMA Crossover Monitor.
        """
        
        self.alerter.send_alert(subject, body)


class SMMAMonitoringSystem:
    """Main monitoring system orchestrating all indices"""
    
    def __init__(self):
        self.alerter = EmailAlerter()
        self.monitors = {
            'Nifty50': IndexMonitor('Nifty50', '^NSEI', self.alerter),
            'Sensex': IndexMonitor('Sensex', '^BSESN', self.alerter)
        }
        self.check_interval = int(os.getenv('CHECK_INTERVAL', 10))  # seconds
    
    def run(self):
        """Main monitoring loop"""
        logger.info("Starting SMMA Crossover Monitoring System...")
        logger.info(f"Monitoring: {', '.join(self.monitors.keys())}")
        logger.info(f"Check interval: {self.check_interval} seconds")
        
        try:
            while True:
                logger.info("--- Checking indicators ---")
                
                for index_name, monitor in self.monitors.items():
                    try:
                        monitor.analyze_and_alert(interval='1h')
                    except Exception as e:
                        logger.error(f"Error analyzing {index_name}: {str(e)}")
                
                logger.info(f"Waiting {self.check_interval} seconds until next check...")
                time.sleep(self.check_interval)
        
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise


if __name__ == '__main__':
    system = SMMAMonitoringSystem()
    system.run()
