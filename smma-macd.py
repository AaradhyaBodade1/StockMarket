"""
SMMA Trading System with Entry/Exit Signals + MACD Indicator
Provides exact BUY/SELL signals with MACD confirmation for intraday trading.
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
        logging.FileHandler('smma_trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SMMAIndicator:
    """Calculate Smoothed Moving Average (SMMA)"""
    
    def __init__(self, period):
        self.period = period
    
    def calculate(self, prices):
        """
        Calculate SMMA for a series of prices
        Initial SMMA = SMA of first N periods
        Subsequent SMMA = (Previous SMMA * (N-1) + Current Price) / N
        """
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
    """Calculate MACD (Moving Average Convergence Divergence)"""
    
    def calculate(self, prices, fast=12, slow=26, signal=9):
        """
        Calculate MACD, Signal line, and Histogram
        
        MACD = 12-period EMA - 26-period EMA
        Signal = 9-period EMA of MACD
        Histogram = MACD - Signal
        """
        if len(prices) < slow + signal:
            return None, None, None
        
        # Calculate exponential moving averages
        ema_12 = prices.ewm(span=fast, adjust=False).mean()
        ema_26 = prices.ewm(span=slow, adjust=False).mean()
        
        # Calculate MACD line
        macd_line = ema_12 - ema_26
        
        # Calculate Signal line
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        
        # Calculate Histogram
        histogram = macd_line - signal_line
        
        return macd_line.values, signal_line.values, histogram.values
    
    def get_signal(self, macd_line, signal_line, prev_macd=None, prev_signal=None):
        """
        Determine MACD signal status
        Returns: 'bullish', 'bearish', 'neutral', or 'crossover'
        
        Bullish: MACD > Signal (positive histogram)
        Bearish: MACD < Signal (negative histogram)
        Crossover: MACD crosses above/below Signal
        """
        if prev_macd is None or prev_signal is None:
            # First candle, just check position
            if macd_line > signal_line:
                return 'bullish'
            elif macd_line < signal_line:
                return 'bearish'
            else:
                return 'neutral'
        
        # Check for crossover
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
    """Calculate Relative Strength Index for trend confirmation"""
    
    def calculate(self, prices, period=14):
        """Calculate RSI"""
        if len(prices) < period + 1:
            return None
        
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.values


class VolumeAnalyzer:
    """Analyze volume for trade confirmation"""
    
    def is_volume_high(self, current_volume, avg_volume, threshold=1.2):
        """Check if current volume is higher than average"""
        return current_volume > (avg_volume * threshold)


class TradingSignalGenerator:
    """Generate precise entry and exit signals with MACD"""
    
    def __init__(self):
        self.active_trades = {}  # Track active positions
    
    def generate_signal(self, index_name, price, smma_9, smma_20, rsi, volume_high,
                       macd_signal, prev_price, prev_smma_9, prev_smma_20, prev_macd_signal=None):
        """
        Generate trading signals based on multiple confirmations
        
        BUY Signal Conditions:
        1. Price crosses above SMMA9 from below
        2. SMMA9 > SMMA20 (uptrend confirmation)
        3. RSI > 40 and < 70 (not oversold or overbought)
        4. MACD bullish or bullish crossover (momentum confirmation)
        5. Volume higher than average (confirmation)
        
        SELL Signal Conditions:
        1. Price crosses below SMMA9 from above
        2. SMMA9 < SMMA20 (downtrend confirmation)
        3. RSI < 60 and > 30
        4. MACD bearish or bearish crossover (momentum confirmation)
        5. Volume higher than average
        """
        
        # Check for active trade
        if index_name in self.active_trades:
            return self._check_exit_signal(index_name, price, smma_9, rsi, macd_signal)
        
        # Check for new entry signal
        return self._check_entry_signal(index_name, price, smma_9, smma_20, rsi,
                                       volume_high, macd_signal, prev_price, 
                                       prev_smma_9, prev_smma_20, prev_macd_signal)
    
    def _check_entry_signal(self, index_name, price, smma_9, smma_20, rsi,
                           volume_high, macd_signal, prev_price, prev_smma_9, 
                           prev_smma_20, prev_macd_signal):
        """Check for entry signals with MACD confirmation"""
        
        # Check MACD condition for BUY
        macd_bullish = macd_signal in ['bullish', 'bullish_crossover']
        
        # BUY Signal: Bullish crossover with all confirmations
        if (prev_price <= prev_smma_9 and price > smma_9 and  # Price crosses above SMMA9
            smma_9 > smma_20 and  # SMMA9 above SMMA20 (uptrend)
            40 < rsi < 70 and  # RSI in healthy range
            macd_bullish and  # MACD bullish signal
            volume_high):  # Volume confirmation
            
            # Calculate stop loss and targets
            stop_loss = smma_20
            risk = price - stop_loss
            target_1 = price + (risk * 1.5)
            target_2 = price + (risk * 2.5)
            
            trade = {
                'type': 'BUY',
                'entry_price': price,
                'stop_loss': stop_loss,
                'target_1': target_1,
                'target_2': target_2,
                'entry_time': datetime.now(),
                'smma_9': smma_9,
                'smma_20': smma_20,
                'rsi': rsi,
                'macd_signal': macd_signal
            }
            
            self.active_trades[index_name] = trade
            return trade
        
        # Check MACD condition for SELL
        macd_bearish = macd_signal in ['bearish', 'bearish_crossover']
        
        # SELL Signal: Bearish crossover with all confirmations
        if (prev_price >= prev_smma_9 and price < smma_9 and  # Price crosses below SMMA9
            smma_9 < smma_20 and  # SMMA9 below SMMA20 (downtrend)
            30 < rsi < 60 and  # RSI in healthy range
            macd_bearish and  # MACD bearish signal
            volume_high):  # Volume confirmation
            
            # Calculate stop loss and targets
            stop_loss = smma_20
            risk = stop_loss - price
            target_1 = price - (risk * 1.5)
            target_2 = price - (risk * 2.5)
            
            trade = {
                'type': 'SELL',
                'entry_price': price,
                'stop_loss': stop_loss,
                'target_1': target_1,
                'target_2': target_2,
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
        """Check for exit signals on active trades"""
        
        trade = self.active_trades[index_name]
        exit_reason = None
        
        if trade['type'] == 'BUY':
            # Exit conditions for BUY trade
            if price <= trade['stop_loss']:
                exit_reason = 'STOP_LOSS'
            elif price >= trade['target_2']:
                exit_reason = 'TARGET_2'
            elif price >= trade['target_1']:
                exit_reason = 'TARGET_1'
            elif price < smma_9 and rsi < 40 and macd_signal == 'bearish_crossover':
                exit_reason = 'TREND_REVERSAL'
        
        else:  # SELL trade
            # Exit conditions for SELL trade
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
                'profit_loss': self._calculate_pnl(trade, price),
                'profit_loss_percent': self._calculate_pnl_percent(trade, price),
                'duration': datetime.now() - trade['entry_time']
            }
            
            del self.active_trades[index_name]
            return exit_trade
        
        return None
    
    def _calculate_pnl(self, trade, exit_price):
        """Calculate profit/loss"""
        if trade['type'] == 'BUY':
            return exit_price - trade['entry_price']
        else:
            return trade['entry_price'] - exit_price
    
    def _calculate_pnl_percent(self, trade, exit_price):
        """Calculate profit/loss percentage"""
        pnl = self._calculate_pnl(trade, exit_price)
        return (pnl / trade['entry_price']) * 100


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
    """Monitor individual index with trading signals and MACD"""
    
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
        self.previous_data = None
    
    def fetch_latest_data(self, interval='15m'):
        """Fetch latest candle data"""
        try:
            ticker = yf.Ticker(self.ticker_symbol)
            data = ticker.history(period='5d', interval=interval)
            
            if data.empty:
                logger.warning(f"No data fetched for {self.index_name}")
                return None
            
            return data
        
        except Exception as e:
            logger.error(f"Error fetching data for {self.index_name}: {str(e)}")
            return None
    
    def analyze_and_alert(self, interval='15m'):
        """Analyze and generate trading signals with MACD"""
        data = self.fetch_latest_data(interval)
        
        if data is None or len(data) < 35:  # Need extra data for MACD
            return
        
        closes = data['Close']
        volumes = data['Volume']
        
        # Calculate indicators
        smma_9_values = self.smma_9.calculate(closes)
        smma_20_values = self.smma_20.calculate(closes)
        rsi_values = self.rsi.calculate(closes)
        macd_line, signal_line, histogram = self.macd.calculate(closes)
        
        if (smma_9_values is None or smma_20_values is None or 
            rsi_values is None or macd_line is None):
            return
        
        # Current values
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
        
        # Get MACD signal
        prev_macd = macd_line[-2] if len(macd_line) > 1 else None
        prev_signal = signal_line[-2] if len(signal_line) > 1 else None
        macd_signal = self.macd.get_signal(current_macd, current_signal, prev_macd, prev_signal)
        
        # Previous values for crossover detection
        if self.previous_data is not None:
            prev_price = self.previous_data['price']
            prev_smma_9 = self.previous_data['smma_9']
            prev_smma_20 = self.previous_data['smma_20']
            prev_macd_signal = self.previous_data['macd_signal']
            
            # Generate signal
            signal = self.signal_generator.generate_signal(
                self.index_name, current_price, current_smma_9, current_smma_20,
                current_rsi, volume_high, macd_signal, prev_price, 
                prev_smma_9, prev_smma_20, prev_macd_signal
            )
            
            if signal:
                self._send_trade_alert(signal)
        
        # Store current data for next iteration
        self.previous_data = {
            'price': current_price,
            'smma_9': current_smma_9,
            'smma_20': current_smma_20,
            'rsi': current_rsi,
            'macd_signal': macd_signal,
            'macd': current_macd,
            'signal_line': current_signal,
            'histogram': current_histogram
        }
        
        # Log current state with MACD
        macd_status = "📈" if current_histogram > 0 else "📉"
        logger.info(
            f"{self.index_name} | Price: {current_price:.2f} | "
            f"SMMA9: {current_smma_9:.2f} | SMMA20: {current_smma_20:.2f} | "
            f"RSI: {current_rsi:.1f} | MACD: {macd_status} {current_histogram:.4f} | "
            f"Vol: {'HIGH' if volume_high else 'NORMAL'}"
        )
    
    def _send_trade_alert(self, signal):
        """Send trading signal alert with MACD info"""
        
        if signal['type'] in ['BUY', 'SELL']:
            # Entry signal
            subject = f"🚀 {signal['type']} SIGNAL - {self.index_name}"
            
            risk_reward = (signal['target_1'] - signal['entry_price']) / (signal['entry_price'] - signal['stop_loss']) if signal['type'] == 'BUY' else (signal['entry_price'] - signal['target_1']) / (signal['stop_loss'] - signal['entry_price'])
            
            body = f"""
═══════════════════════════════════════
    {signal['type']} SIGNAL - {self.index_name}
═══════════════════════════════════════

📊 ENTRY DETAILS:
   Entry Price: ₹{signal['entry_price']:.2f}
   
🛡️  RISK MANAGEMENT:
   Stop Loss: ₹{signal['stop_loss']:.2f}
   Risk per trade: ₹{abs(signal['entry_price'] - signal['stop_loss']):.2f}

🎯 TARGETS:
   Target 1: ₹{signal['target_1']:.2f} (Book 50%)
   Target 2: ₹{signal['target_2']:.2f} (Book 50%)
   
📈 TECHNICAL INDICATORS:
   SMMA9: ₹{signal['smma_9']:.2f}
   SMMA20: ₹{signal['smma_20']:.2f}
   RSI: {signal['rsi']:.1f}
   MACD Signal: {signal['macd_signal'].upper()}
   Risk:Reward: 1:{risk_reward:.1f}

⏰ Time: {signal['entry_time'].strftime('%Y-%m-%d %H:%M:%S')}

═══════════════════════════════════════
TRADE EXECUTION PLAN:
1. Enter at market price
2. Place Stop Loss immediately
3. Book 50% at Target 1
4. Trail stop loss to entry for remaining 50%
5. Exit remaining at Target 2 or trailing stop
═══════════════════════════════════════
            """
        
        else:  # EXIT signal
            subject = f"🔔 EXIT SIGNAL - {self.index_name} - {signal['exit_reason']}"
            
            pnl_emoji = "💰" if signal['profit_loss'] > 0 else "📉"
            
            body = f"""
═══════════════════════════════════════
    EXIT SIGNAL - {self.index_name}
═══════════════════════════════════════

📊 TRADE SUMMARY:
   Trade Type: {signal['original_trade']}
   Entry Price: ₹{signal['entry_price']:.2f}
   Exit Price: ₹{signal['exit_price']:.2f}
   
{pnl_emoji} PROFIT/LOSS:
   P&L: ₹{signal['profit_loss']:.2f}
   P&L %: {signal['profit_loss_percent']:.2f}%
   
📍 EXIT REASON: {signal['exit_reason']}
⏱️  Duration: {signal['duration']}
⏰ Exit Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

═══════════════════════════════════════
            """
        
        self.alerter.send_alert(subject, body)
        logger.info(f"Trade alert sent: {subject}")


class SMMAMonitoringSystem:
    """Main trading system with MACD"""
    
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
        """Main trading loop"""
        logger.info("=" * 60)
        logger.info("SMMA Trading System with MACD Indicator Started")
        logger.info("=" * 60)
        logger.info(f"Monitoring: {', '.join(self.monitors.keys())}")
        logger.info(f"Check interval: {self.check_interval} seconds")
        logger.info(f"Timeframe: 15-minute candles")
        logger.info(f"Indicators: SMMA9/20 + RSI + MACD + Volume")
        logger.info("=" * 60)
        
        try:
            while True:
                logger.info("--- Scanning for trade signals ---")
                
                for index_name, monitor in self.monitors.items():
                    try:
                        monitor.analyze_and_alert(interval='15m')
                    except Exception as e:
                        logger.error(f"Error analyzing {index_name}: {str(e)}")
                
                logger.info(f"Next scan in {self.check_interval} seconds...")
                time.sleep(self.check_interval)
        
        except KeyboardInterrupt:
            logger.info("Trading system stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise


if __name__ == '__main__':
    system = SMMAMonitoringSystem()
    system.run()
