"""
SMMA Trading System - PRODUCTION READY VERSION
Real-time safe with complete data validation and error handling
"""

import yfinance as yf
import pandas as pd
import numpy as np
import smtplib
import time
import logging
from datetime import datetime, timedelta, time as dt_time
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
        logging.FileHandler('smma_trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MarketHoursValidator:
    """Validate if market is open and data is fresh"""
    
    @staticmethod
    def is_market_open():
        """Check if NSE market is currently open"""
        now = datetime.now()
        market_open = dt_time(9, 15)
        market_close = dt_time(15, 30)
        
        # Check if weekday (Mon-Fri)
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check if within market hours
        current_time = now.time()
        return market_open <= current_time <= market_close
    
    @staticmethod
    def get_last_market_close():
        """Get timestamp of last market close"""
        now = datetime.now()
        
        if MarketHoursValidator.is_market_open():
            last_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
            if now.time() < dt_time(9, 15):
                last_close = last_close - timedelta(days=1)
        else:
            if now.weekday() == 0:  # Monday
                last_close = (now - timedelta(days=3)).replace(hour=15, minute=30)
            elif now.weekday() == 6:  # Sunday
                last_close = (now - timedelta(days=2)).replace(hour=15, minute=30)
            else:
                last_close = (now - timedelta(days=1)).replace(hour=15, minute=30)
        
        return last_close


class DataQualityChecker:
    """Check data quality and freshness"""
    
    @staticmethod
    def validate_data(data, min_candles=35):
        """Validate fetched data"""
        if data is None or data.empty:
            logger.warning("❌ Data is empty")
            return False
        
        if len(data) < min_candles:
            logger.warning(f"❌ Insufficient candles: {len(data)} < {min_candles}")
            return False
        
        if data['Close'].isna().sum() > 0:
            logger.warning(f"⚠️  Data contains NaN values: {data['Close'].isna().sum()}")
        
        return True
    
    @staticmethod
    def is_candle_complete(data, interval_minutes=15):
        """Check if latest candle is complete"""
        if data is None or data.empty:
            return False
        
        last_timestamp = data.index[-1]
        now = datetime.now(last_timestamp.tz)
        time_diff = (now - last_timestamp).total_seconds() / 60
        
        if time_diff < interval_minutes:
            logger.warning(f"⚠️  Current candle still forming ({time_diff:.0f} min old)")
            return False
        
        return True


class RetryMechanism:
    """Handle network errors with retry logic"""
    
    def __init__(self, max_retries=3, backoff_factor=2):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
    
    def fetch_with_retry(self, ticker_symbol, func):
        """Fetch data with retry mechanism"""
        for attempt in range(self.max_retries):
            try:
                return func()
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.backoff_factor ** attempt
                    logger.warning(f"⚠️  Attempt {attempt + 1} failed for {ticker_symbol}: {str(e)}")
                    logger.info(f"   Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ Failed to fetch {ticker_symbol} after {self.max_retries} attempts")
                    return None


class SMMAIndicator:
    """Calculate SMMA"""
    def __init__(self, period):
        self.period = period
    
    def calculate(self, prices):
        if len(prices) < self.period:
            return None
        
        smma_values = []
        initial_sma = prices[:self.period].mean()
        smma_values.append(initial_sma)
        
        for i in range(self.period, len(prices)):
            smma = (smma_values[-1] * (self.period - 1) + prices.iloc[i]) / self.period
            smma_values.append(smma)
        
        return np.array(smma_values)


class MACDIndicator:
    """Calculate MACD"""
    def calculate(self, prices, fast=12, slow=26, signal=9):
        if len(prices) < slow + signal:
            return None, None, None
        
        ema_12 = prices.ewm(span=fast, adjust=False).mean()
        ema_26 = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_12 - ema_26
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return macd_line.values, signal_line.values, histogram.values
    
    def get_signal(self, macd_line, signal_line, prev_macd=None, prev_signal=None):
        if prev_macd is None or prev_signal is None:
            if macd_line > signal_line:
                return 'bullish'
            elif macd_line < signal_line:
                return 'bearish'
            else:
                return 'neutral'
        
        prev_histogram = prev_macd - prev_signal
        current_histogram = macd_line - signal_line
        
        if prev_histogram < 0 and current_histogram > 0:
            return 'bullish_crossover'
        elif prev_histogram > 0 and current_histogram < 0:
            return 'bearish_crossover'
        elif macd_line > signal_line:
            return 'bullish'
        else:
            return 'bearish'


class RSIIndicator:
    """Calculate RSI"""
    def calculate(self, prices, period=14):
        if len(prices) < period + 1:
            return None
        
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.values


class VolumeAnalyzer:
    """Analyze volume"""
    def is_volume_high(self, current_volume, avg_volume, threshold=1.2):
        return current_volume > (avg_volume * threshold)


class TradingSignalGenerator:
    """Generate trading signals"""
    def __init__(self):
        self.active_trades = {}
    
    def generate_signal(self, index_name, price, smma_9, smma_20, rsi, volume_high,
                       macd_signal, prev_price, prev_smma_9, prev_smma_20):
        if index_name in self.active_trades:
            return self._check_exit_signal(index_name, price, smma_9, rsi, macd_signal)
        
        return self._check_entry_signal(index_name, price, smma_9, smma_20, rsi,
                                       volume_high, macd_signal, prev_price, 
                                       prev_smma_9, prev_smma_20)
    
    def _check_entry_signal(self, index_name, price, smma_9, smma_20, rsi,
                           volume_high, macd_signal, prev_price, prev_smma_9, prev_smma_20):
        macd_bullish = macd_signal in ['bullish', 'bullish_crossover']
        macd_bearish = macd_signal in ['bearish', 'bearish_crossover']
        
        if (prev_price <= prev_smma_9 and price > smma_9 and
            smma_9 > smma_20 and 40 < rsi < 70 and macd_bullish and volume_high):
            
            stop_loss = smma_20
            risk = price - stop_loss
            trade = {
                'type': 'BUY',
                'entry_price': price,
                'stop_loss': stop_loss,
                'target_1': price + (risk * 1.5),
                'target_2': price + (risk * 2.5),
                'entry_time': datetime.now(),
                'smma_9': smma_9,
                'smma_20': smma_20,
                'rsi': rsi,
                'macd_signal': macd_signal
            }
            self.active_trades[index_name] = trade
            return trade
        
        elif (prev_price >= prev_smma_9 and price < smma_9 and
              smma_9 < smma_20 and 30 < rsi < 60 and macd_bearish and volume_high):
            
            stop_loss = smma_20
            risk = stop_loss - price
            trade = {
                'type': 'SELL',
                'entry_price': price,
                'stop_loss': stop_loss,
                'target_1': price - (risk * 1.5),
                'target_2': price - (risk * 2.5),
                'entry_time': datetime.now(),
                'smma_9': smma_9,
                'smma_20': smma_20,
                'rsi': rsi,
                'macd_signal': macd_signal
            }
            self.active_trades[index_name] = trade
            return trade
        
        return None
    
    def _check_exit_signal(self, index_name, price, smma_9, rsi, macd_signal):
        trade = self.active_trades[index_name]
        exit_reason = None
        
        if trade['type'] == 'BUY':
            if price <= trade['stop_loss']:
                exit_reason = 'STOP_LOSS'
            elif price >= trade['target_2']:
                exit_reason = 'TARGET_2'
            elif price >= trade['target_1']:
                exit_reason = 'TARGET_1'
            elif price < smma_9 and rsi < 40 and macd_signal == 'bearish_crossover':
                exit_reason = 'TREND_REVERSAL'
        else:
            if price >= trade['stop_loss']:
                exit_reason = 'STOP_LOSS'
            elif price <= trade['target_2']:
                exit_reason = 'TARGET_2'
            elif price <= trade['target_1']:
                exit_reason = 'TARGET_1'
            elif price > smma_9 and rsi > 60 and macd_signal == 'bullish_crossover':
                exit_reason = 'TREND_REVERSAL'
        
        if exit_reason:
            exit_trade = {
                'type': 'EXIT',
                'original_trade': trade['type'],
                'entry_price': trade['entry_price'],
                'exit_price': price,
                'exit_reason': exit_reason,
                'profit_loss': self._calc_pnl(trade, price),
                'profit_loss_percent': self._calc_pnl_percent(trade, price),
                'duration': datetime.now() - trade['entry_time']
            }
            del self.active_trades[index_name]
            return exit_trade
        return None
    
    def _calc_pnl(self, trade, exit_price):
        return exit_price - trade['entry_price'] if trade['type'] == 'BUY' else trade['entry_price'] - exit_price
    
    def _calc_pnl_percent(self, trade, exit_price):
        pnl = self._calc_pnl(trade, exit_price)
        return (pnl / trade['entry_price']) * 100


class EmailAlerter:
    """Send email alerts"""
    def __init__(self):
        self.sender_email = os.getenv('SMTP_EMAIL')
        self.sender_password = os.getenv('SMTP_PASSWORD')
        self.recipient_email = os.getenv('RECIPIENT_EMAIL')
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
    
    def send_alert(self, subject, body):
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"✅ Email sent: {subject}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send email: {str(e)}")
            return False


class IndexMonitor:
    """Monitor index with real-time validation"""
    def __init__(self, index_name, ticker_symbol, alerter):
        self.index_name = index_name
        self.ticker_symbol = ticker_symbol
        self.alerter = alerter
        self.smma_9 = SMMAIndicator(9)
        self.smma_20 = SMMAIndicator(20)
        self.macd = MACDIndicator()
        self.rsi = RSIIndicator()
        self.volume_analyzer = VolumeAnalyzer()
        self.signal_generator = TradingSignalGenerator()
        self.data_checker = DataQualityChecker()
        self.retry = RetryMechanism()
        self.previous_data = None
    
    def fetch_latest_data(self, interval='15m'):
        """Fetch data with retry and validation"""
        def _fetch():
            ticker = yf.Ticker(self.ticker_symbol)
            return ticker.history(period='10d', interval=interval)
        
        data = self.retry.fetch_with_retry(self.ticker_symbol, _fetch)
        
        if not self.data_checker.validate_data(data):
            return None
        
        return data
    
    def analyze_and_alert(self, interval='15m'):
        """Analyze with full validation"""
        if not MarketHoursValidator.is_market_open():
            return
        
        data = self.fetch_latest_data(interval)
        if data is None or len(data) < 35:
            return
        
        if not self.data_checker.is_candle_complete(data):
            return
        
        closes = data['Close']
        volumes = data['Volume']
        
        smma_9_values = self.smma_9.calculate(closes)
        smma_20_values = self.smma_20.calculate(closes)
        rsi_values = self.rsi.calculate(closes)
        macd_line, signal_line, histogram = self.macd.calculate(closes)
        
        if (smma_9_values is None or smma_20_values is None or 
            rsi_values is None or macd_line is None):
            return
        
        current_price = closes.iloc[-1]
        current_smma_9 = smma_9_values[-1]
        current_smma_20 = smma_20_values[-1]
        current_rsi = rsi_values[-1]
        current_macd = macd_line[-1]
        current_signal = signal_line[-1]
        current_histogram = histogram[-1]
        current_volume = volumes.iloc[-1]
        avg_volume = volumes.iloc[-20:].mean()
        
        volume_high = self.volume_analyzer.is_volume_high(current_volume, avg_volume)
        
        prev_macd = macd_line[-2] if len(macd_line) > 1 else None
        prev_signal = signal_line[-2] if len(signal_line) > 1 else None
        macd_signal = self.macd.get_signal(current_macd, current_signal, prev_macd, prev_signal)
        
        if self.previous_data is not None:
            signal = self.signal_generator.generate_signal(
                self.index_name, current_price, current_smma_9, current_smma_20,
                current_rsi, volume_high, macd_signal, self.previous_data['price'],
                self.previous_data['smma_9'], self.previous_data['smma_20']
            )
            
            if signal:
                self._send_trade_alert(signal)
        
        self.previous_data = {
            'price': current_price,
            'smma_9': current_smma_9,
            'smma_20': current_smma_20,
            'rsi': current_rsi,
            'macd_signal': macd_signal
        }
        
        macd_status = "📈" if current_histogram > 0 else "📉"
        logger.info(
            f"{self.index_name} | Price: {current_price:.2f} | SMMA9: {current_smma_9:.2f} | "
            f"SMMA20: {current_smma_20:.2f} | RSI: {current_rsi:.1f} | MACD: {macd_status}"
        )
    
    def _send_trade_alert(self, signal):
        if signal['type'] in ['BUY', 'SELL']:
            subject = f"🚀 {signal['type']} SIGNAL - {self.index_name}"
            body = f"""
📊 {signal['type']} SIGNAL - {self.index_name}
Entry: ₹{signal['entry_price']:.2f}
Stop Loss: ₹{signal['stop_loss']:.2f}
Target 1: ₹{signal['target_1']:.2f}
Target 2: ₹{signal['target_2']:.2f}
MACD: {signal['macd_signal'].upper()}
Time: {signal['entry_time'].strftime('%H:%M:%S')}
            """
        else:
            subject = f"🔔 EXIT - {self.index_name}"
            body = f"""
Trade: {signal['original_trade']}
Entry: ₹{signal['entry_price']:.2f}
Exit: ₹{signal['exit_price']:.2f}
P&L: ₹{signal['profit_loss']:.2f} ({signal['profit_loss_percent']:.2f}%)
Reason: {signal['exit_reason']}
            """
        
        self.alerter.send_alert(subject, body)


class SMMAMonitoringSystem:
    """Main trading system"""
    def __init__(self):
        self.alerter = EmailAlerter()
        self.monitors = {
            'Nifty50': IndexMonitor('Nifty50', '^NSEI', self.alerter),
            'Sensex': IndexMonitor('Sensex', '^BSESN', self.alerter),
            'Reliance': IndexMonitor('Reliance', 'RELIANCE.NS', self.alerter),
            'IndusInd Bank': IndexMonitor('IndusInd Bank', 'INDUSINDBK.NS', self.alerter),
            'NTPC': IndexMonitor('NTPC', 'NTPC.NS', self.alerter),
            'Sun Pharma': IndexMonitor('Sun Pharma', 'SUNPHARMA.NS', self.alerter),
            'Tata Motors': IndexMonitor('Tata Motors', 'TATAMOTORS.NS', self.alerter),
            'Wipro': IndexMonitor('Wipro', 'WIPRO.NS', self.alerter),
            'ONGC': IndexMonitor('ONGC', 'ONGC.NS', self.alerter)
        }
        self.check_interval = int(os.getenv('CHECK_INTERVAL', 60))
    
    def run(self):
        logger.info("=" * 70)
        logger.info("SMMA Trading System - PRODUCTION READY")
        logger.info("=" * 70)
        logger.info("Market Hours: 9:15 AM - 3:30 PM IST")
        logger.info("Data Fetch: 10 days (MACD reliable)")
        logger.info("Candle Check: Complete candles only")
        logger.info("Network: Auto-retry 3x with backoff")
        logger.info("=" * 70)
        
        try:
            while True:
                if not MarketHoursValidator.is_market_open():
                    logger.info(f"Market closed. Sleeping...")
                    time.sleep(300)
                    continue
                
                logger.info("--- Scanning for signals ---")
                for index_name, monitor in self.monitors.items():
                    try:
                        monitor.analyze_and_alert(interval='15m')
                    except Exception as e:
                        logger.error(f"❌ Error in {index_name}: {str(e)}")
                
                time.sleep(self.check_interval)
        
        except KeyboardInterrupt:
            logger.info("System stopped")
        except Exception as e:
            logger.critical(f"CRITICAL ERROR: {str(e)}")
            raise


if __name__ == '__main__':
    system = SMMAMonitoringSystem()
    system.run()
