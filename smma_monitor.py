# SMMA Crossover Alert System for Nifty50, Sensex, and Individual Stocks
# Monitors 9-period and 20-period SMMA indicators and sends email alerts on crossovers

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
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        self.alert_queue = []
        self.batch_alerts = os.getenv('BATCH_ALERTS', 'false').lower() == 'true'
    
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
    """Monitor individual index/stock with SMMA indicators"""
    
    def __init__(self, index_name, ticker_symbol, alerter, is_index=False):
        self.index_name = index_name
        self.ticker_symbol = ticker_symbol
        self.alerter = alerter
        self.is_index = is_index
        self.smma_9 = SMMAIndicator(9)
        self.smma_20 = SMMAIndicator(20)
        self.crossover_detector = CrossoverDetector()
        self.last_alert_time = defaultdict(lambda: datetime.min)
        self.last_data_fetch = None
        self.fetch_errors = 0
    
    def fetch_latest_data(self, interval='1h'):
        """
        Fetch latest candle data
        interval: '1m', '5m', '15m', '1h', '1d'
        """
        try:
            ticker = yf.Ticker(self.ticker_symbol)
            
            # Use appropriate period based on interval
            if interval == '1m':
                period = '7d'
            elif interval == '5m':
                period = '30d'
            elif interval == '15m':
                period = '60d'
            elif interval == '1h':
                period = '730d'
            else:
                period = '730d'
            
            data = ticker.history(period=period, interval=interval)
            
            if data.empty:
                self.fetch_errors += 1
                if self.fetch_errors > 5:
                    logger.warning(f"Persistent data fetch issues for {self.index_name}")
                return None
            
            self.fetch_errors = 0
            self.last_data_fetch = datetime.now()
            return data
        
        except Exception as e:
            self.fetch_errors += 1
            if self.fetch_errors <= 3:  # Log only first 3 errors
                logger.warning(f"Error fetching data for {self.index_name}: {str(e)}")
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
        logger.debug(
            f"{self.index_name} | Price: {current_price:.2f} | "
            f"SMMA9: {current_smma_9:.2f} | SMMA20: {current_smma_20:.2f}"
        )
    
    def _send_crossover_alert(self, period, signal_type, price, smma_value):
        """Send crossover alert email"""
        signal_text = "BULLISH ↑" if signal_type == 'bullish' else "BEARISH ↓"
        
        if self.is_index:
            subject = f"📈 {self.index_name} SMMA{period} {signal_text} Crossover Alert"
        else:
            subject = f"📊 {self.index_name} SMMA{period} {signal_text} Crossover Alert"
        
        body = f"""
SMMA Crossover Alert - {self.index_name}

Signal Type: {signal_type.upper()}
SMMA Period: {period}
Current Price: ₹{price:.2f}
SMMA Value: ₹{smma_value:.2f}
Ticker: {self.ticker_symbol}

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This is an automated alert from SMMA Crossover Monitor.
        """
        
        self.alerter.send_alert(subject, body)


class SMMAMonitoringSystem:
    """Main monitoring system orchestrating all indices and stocks"""
    
    def __init__(self):
        self.alerter = EmailAlerter()
        
        # Define all monitored assets
        self.indices = {
            'Nifty50': ('^NSEI', True),
            'Sensex': ('^BSESN', True)
        }
        
        self.stocks = {
            'Reliance': ('RELIANCE.NS', False),
            'HDFC Bank': ('HDFCBANK.NS', False),
            'ICICI Bank': ('ICICIBANK.NS', False),
            'Infosys': ('INFY.NS', False),
            'TCS': ('TCS.NS', False),
            'Bajaj Finance': ('BAJAJFINSV.NS', False),
            'Kotak Mahindra': ('KOTAKBANK.NS', False),
            'Axis Bank': ('AXISBANK.NS', False),
            'SBI': ('SBIN.NS', False),
            'L&T': ('LT.NS', False),
            'Maruti Suzuki': ('MARUTI.NS', False),
            'HUL': ('HINDUNILVR.NS', False),
            'Asian Paints': ('ASIANPAINT.NS', False),
            'Adani Enterprises': ('ADANIENTER.NS', False),
            'Indusind Bank': ('INDUSINDBK.NS', False),
            'NTPC': ('NTPC.NS', False),
            'Sun Pharma': ('SUNPHARMA.NS', False),
            'Tata Motors': ('TATAMOTORS.NS', False),
            'Wipro': ('WIPRO.NS', False),
            'ONGC': ('ONGC.NS', False)
        }
        
        # Initialize monitors
        self.monitors = {}
        all_assets = {**self.indices, **self.stocks}
        
        for asset_name, (ticker, is_idx) in all_assets.items():
            self.monitors[asset_name] = IndexMonitor(asset_name, ticker, self.alerter, is_idx)
        
        self.check_interval = int(os.getenv('CHECK_INTERVAL', 300))  # Default 5 minutes
        self.max_workers = int(os.getenv('MAX_WORKERS', 5))
    
    def run(self):
        """Main monitoring loop with parallel processing"""
        logger.info("=" * 70)
        logger.info("Starting SMMA Crossover Monitoring System (Enhanced)")
        logger.info("=" * 70)
        logger.info(f"Monitoring Indices: {', '.join(self.indices.keys())}")
        logger.info(f"Monitoring Stocks: {', '.join(self.stocks.keys())}")
        logger.info(f"Total Assets: {len(self.monitors)}")
        logger.info(f"Check interval: {self.check_interval} seconds")
        logger.info(f"Max parallel workers: {self.max_workers}")
        logger.info("=" * 70)
        
        try:
            iteration = 0
            while True:
                iteration += 1
                logger.info(f"\n--- Iteration #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
                
                # Use ThreadPoolExecutor for parallel monitoring
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {}
                    
                    for asset_name, monitor in self.monitors.items():
                        future = executor.submit(monitor.analyze_and_alert, interval='1h')
                        futures[future] = asset_name
                    
                    # Collect results
                    completed = 0
                    errors = 0
                    for future in as_completed(futures):
                        asset_name = futures[future]
                        try:
                            future.result()
                            completed += 1
                        except Exception as e:
                            logger.error(f"Error analyzing {asset_name}: {str(e)}")
                            errors += 1
                
                logger.info(f"Iteration complete - {completed} successful, {errors} errors")
                logger.info(f"Next check in {self.check_interval} seconds...")
                time.sleep(self.check_interval)
        
        except KeyboardInterrupt:
            logger.info("\n" + "=" * 70)
            logger.info("Monitoring stopped by user")
            logger.info("=" * 70)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise


if __name__ == '__main__':
    system = SMMAMonitoringSystem()
    system.run()
