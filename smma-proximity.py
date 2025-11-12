"""
SMMA Proximity Alert System for Nifty50 and Sensex
Monitors 9-period and 20-period SMMA indicators and sends email alerts when price approaches SMMA.
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



class ProximityDetector:
    """Detect when price is approximately near SMMA"""
    
    def __init__(self, proximity_threshold_percent=0.5):
        """
        proximity_threshold_percent: Alert when price is within this % of SMMA
        Default is 0.5% - meaning alert when price is within 0.5% of SMMA value
        """
        self.proximity_threshold = proximity_threshold_percent / 100.0
        self.previous_state = defaultdict(dict)  # Track previous proximity state
    
    def detect_proximity(self, index_name, smma_period, current_price, smma_value):
        """
        Detect if price is approximately near SMMA
        Returns: 'near_above', 'near_below', or None
        """
        state_key = f"{index_name}_SMMA{smma_period}"
        
        # Calculate percentage difference
        price_diff_percent = abs(current_price - smma_value) / smma_value
        
        # Check if price is within threshold
        is_near = price_diff_percent <= self.proximity_threshold
        
        if not is_near:
            # Reset state if not near
            if state_key in self.previous_state:
                self.previous_state[state_key]['alerted'] = False
            return None
        
        # Initialize tracking if first time
        if state_key not in self.previous_state:
            self.previous_state[state_key] = {'alerted': False}
        
        # Check if we already alerted for this proximity event
        if self.previous_state[state_key]['alerted']:
            return None
        
        # Mark as alerted
        self.previous_state[state_key]['alerted'] = True
        
        # Determine if price is above or below SMMA
        if current_price > smma_value:
            return 'near_above'
        else:
            return 'near_below'



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
    
    def __init__(self, index_name, ticker_symbol, alerter, proximity_threshold=0.5):
        self.index_name = index_name
        self.ticker_symbol = ticker_symbol
        self.alerter = alerter
        self.smma_9 = SMMAIndicator(9)
        self.smma_20 = SMMAIndicator(20)
        self.proximity_detector = ProximityDetector(proximity_threshold)
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
        """Analyze latest candle and detect proximity to SMMA"""
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
        current_smma_20 = smma_20_values[-1]
        
        # Check for proximity to SMMA
        proximity_9 = self.proximity_detector.detect_proximity(
            self.index_name, 9, current_price, current_smma_9
        )
        
        proximity_20 = self.proximity_detector.detect_proximity(
            self.index_name, 20, current_price, current_smma_20
        )
        
        # Send alerts with rate limiting (max once per 5 minutes per signal)
        alert_cooldown = timedelta(minutes=5)
        
        if proximity_9:
            alert_key_9 = f"{self.index_name}_SMMA9_{proximity_9}"
            if datetime.now() - self.last_alert_time[alert_key_9] > alert_cooldown:
                self._send_proximity_alert(9, proximity_9, current_price, current_smma_9)
                self.last_alert_time[alert_key_9] = datetime.now()
        
        if proximity_20:
            alert_key_20 = f"{self.index_name}_SMMA20_{proximity_20}"
            if datetime.now() - self.last_alert_time[alert_key_20] > alert_cooldown:
                self._send_proximity_alert(20, proximity_20, current_price, current_smma_20)
                self.last_alert_time[alert_key_20] = datetime.now()
        
        # Log current state
        diff_9_percent = ((current_price - current_smma_9) / current_smma_9) * 100
        diff_20_percent = ((current_price - current_smma_20) / current_smma_20) * 100
        
        logger.info(
            f"{self.index_name} | Price: {current_price:.2f} | "
            f"SMMA9: {current_smma_9:.2f} ({diff_9_percent:+.2f}%) | "
            f"SMMA20: {current_smma_20:.2f} ({diff_20_percent:+.2f}%)"
        )
    
    def _send_proximity_alert(self, period, proximity_type, price, smma_value):
        """Send proximity alert email"""
        position_text = "ABOVE ↑" if proximity_type == 'near_above' else "BELOW ↓"
        diff_percent = abs((price - smma_value) / smma_value) * 100
        
        subject = f"⚠️ {self.index_name} Price Near SMMA{period} {position_text}"
        
        body = f"""
SMMA Proximity Alert - {self.index_name}


Alert: Price is approximately near SMMA{period}
Position: Price is {position_text} SMMA
Current Price: {price:.2f}
SMMA{period} Value: {smma_value:.2f}
Difference: {diff_percent:.2f}%


Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}


This is an automated alert from SMMA Proximity Monitor.
The price is within the proximity threshold of SMMA{period}.
        """
        
        self.alerter.send_alert(subject, body)



class SMMAMonitoringSystem:
    """Main monitoring system orchestrating all indices"""
    
    def __init__(self):
        self.alerter = EmailAlerter()
        # Proximity threshold can be adjusted via environment variable (default 0.5%)
        proximity_threshold = float(os.getenv('PROXIMITY_THRESHOLD', 0.5))
        
        self.monitors = {
            'Nifty50': IndexMonitor('Nifty50', '^NSEI', self.alerter, proximity_threshold),
            'Sensex': IndexMonitor('Sensex', '^BSESN', self.alerter, proximity_threshold),
            'Reliance': IndexMonitor('Reliance', 'RELIANCE.NS', self.alerter, proximity_threshold),
            'IndusInd Bank': IndexMonitor('IndusInd Bank', 'INDUSINDBK.NS', self.alerter, proximity_threshold),
            'NTPC': IndexMonitor('NTPC', 'NTPC.NS', self.alerter, proximity_threshold),
            'Sun Pharma': IndexMonitor('Sun Pharma', 'SUNPHARMA.NS', self.alerter, proximity_threshold),
            'Tata Motors': IndexMonitor('Tata Motors', 'TATAMOTORS.NS', self.alerter, proximity_threshold),
            'Wipro': IndexMonitor('Wipro', 'WIPRO.NS', self.alerter, proximity_threshold),
            'ONGC': IndexMonitor('ONGC', 'ONGC.NS', self.alerter, proximity_threshold)
        }
        self.check_interval = int(os.getenv('CHECK_INTERVAL', 10))  # seconds
        
        logger.info(f"Proximity threshold set to: {proximity_threshold}%")
    
    def run(self):
        """Main monitoring loop"""
        logger.info("Starting SMMA Proximity Monitoring System...")
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
