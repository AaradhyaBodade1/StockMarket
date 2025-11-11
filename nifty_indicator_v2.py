"""
Real-Time Nifty Indicator Application
Monitors Nifty 50 index and sends trading alerts via email
MODIFIED: 10-second fetch interval for 5-minute candle data during market hours
"""

import os
import sys
import logging
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from time import sleep
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings('ignore')

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('nifty_indicator.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Configuration
NIFTY_SYMBOL = "^NSEI"
GIFT_NIFTY_SYMBOL = "^NSEI"
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')
RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL')

# Trading parameters
SMA_9_PERIOD = 9
SMA_20_PERIOD = 20
RISK_REWARD_RATIO = 3
SUPPORT_RESISTANCE_LOOKBACK = 20

# MODIFIED: Fetch interval changed to 10 seconds for more frequent monitoring
LIVE_FETCH_INTERVAL = 10  # seconds (was 300 seconds = 5 minutes)

class NiftyIndicatorApp:
    """Main application class for Nifty indicator monitoring"""
    
    def __init__(self):
        logger.info("=== Initializing Nifty Indicator Application ===")
        self.support_level = None
        self.resistance_level = None
        self.last_signal_time = None
        self.in_position = False
        self.current_trend = "NEUTRAL"
        self.last_processed_candle = None  # Track last processed candle to avoid duplicate signals
        logger.info("Application initialized successfully")
        logger.info(f"Live market fetch interval: {LIVE_FETCH_INTERVAL} seconds")
    
    def fetch_nifty_data(self, interval='5m', period='5d'):
        """Fetch Nifty chart data from Yahoo Finance"""
        try:
            logger.debug(f"Fetching Nifty data - Interval: {interval}, Period: {period}")
            ticker = yf.Ticker(NIFTY_SYMBOL)
            data = ticker.history(interval=interval, period=period)
            
            if data.empty:
                logger.error("No data returned from Yahoo Finance")
                return None
            
            logger.debug(f"Successfully fetched {len(data)} candles")
            return data
        except Exception as e:
            logger.error(f"Error fetching Nifty data: {str(e)}")
            return None
    
    def fetch_gift_nifty(self):
        """Fetch GIFT Nifty current value"""
        try:
            logger.info("Fetching GIFT Nifty data")
            ticker = yf.Ticker(GIFT_NIFTY_SYMBOL)
            data = ticker.history(period='1d')
            
            if data.empty:
                logger.warning("Unable to fetch GIFT Nifty data")
                return None, None
            
            current_price = data['Close'].iloc[-1]
            prev_close = data['Open'].iloc[0]
            pct_change = ((current_price - prev_close) / prev_close) * 100
            
            logger.info(f"GIFT Nifty: {current_price:.2f}, Change: {pct_change:.2f}%")
            return current_price, pct_change
        except Exception as e:
            logger.error(f"Error fetching GIFT Nifty: {str(e)}")
            return None, None
    
    def fetch_fii_dii_data(self):
        """Fetch FII/DII data (simulated for demonstration)"""
        try:
            logger.info("Fetching FII/DII data")
            fii_net = np.random.uniform(-5000, 5000)
            dii_net = np.random.uniform(-3000, 8000)
            
            logger.info(f"FII Net: ₹{fii_net:.2f} Cr, DII Net: ₹{dii_net:.2f} Cr")
            return {
                'fii_net': fii_net,
                'dii_net': dii_net,
                'date': datetime.now().strftime('%Y-%m-%d')
            }
        except Exception as e:
            logger.error(f"Error fetching FII/DII data: {str(e)}")
            return None
    
    def calculate_sma(self, data, period):
        """Calculate Simple Moving Average"""
        try:
            sma = data['Close'].rolling(window=period).mean()
            logger.debug(f"Calculated SMA-{period}")
            return sma
        except Exception as e:
            logger.error(f"Error calculating SMA: {str(e)}")
            return None
    
    def detect_support_resistance(self, data):
        """Detect support and resistance levels using swing highs/lows"""
        try:
            logger.info("Detecting support and resistance levels")
            
            # Find local minima (support)
            local_min = data['Low'].rolling(window=SUPPORT_RESISTANCE_LOOKBACK, center=True).min()
            support_points = data[data['Low'] == local_min]['Low'].values
            
            # Find local maxima (resistance)
            local_max = data['High'].rolling(window=SUPPORT_RESISTANCE_LOOKBACK, center=True).max()
            resistance_points = data[data['High'] == local_max]['High'].values
            
            if len(support_points) > 0:
                self.support_level = np.mean(support_points[-3:]) if len(support_points) >= 3 else support_points[-1]
            else:
                self.support_level = data['Low'].min()
            
            if len(resistance_points) > 0:
                self.resistance_level = np.mean(resistance_points[-3:]) if len(resistance_points) >= 3 else resistance_points[-1]
            else:
                self.resistance_level = data['High'].max()
            
            logger.info(f"Support: {self.support_level:.2f}, Resistance: {self.resistance_level:.2f}")
            return self.support_level, self.resistance_level
        except Exception as e:
            logger.error(f"Error detecting support/resistance: {str(e)}")
            return None, None
    
    def check_sma_crossover(self, data, sma_period):
        """Check for SMA crossover signals"""
        try:
            if len(data) < sma_period + 2:
                return None
            
            sma = self.calculate_sma(data, sma_period)
            if sma is None:
                return None
            
            current_price = data['Close'].iloc[-1]
            prev_price = data['Close'].iloc[-2]
            current_sma = sma.iloc[-1]
            prev_sma = sma.iloc[-2]
            
            # Bullish crossover: Price crosses above SMA
            if prev_price <= prev_sma and current_price > current_sma:
                logger.info(f"Bullish crossover detected - SMA-{sma_period}")
                return "BULLISH"
            
            # Bearish crossover: Price crosses below SMA
            elif prev_price >= prev_sma and current_price < current_sma:
                logger.info(f"Bearish crossover detected - SMA-{sma_period}")
                return "BEARISH"
            
            return None
        except Exception as e:
            logger.error(f"Error checking SMA crossover: {str(e)}")
            return None
    
    def generate_trade_signal(self, data):
        """Generate trade signals based on SMA crossover near support/resistance"""
        try:
            logger.debug("Analyzing for trade signals")
            
            if self.support_level is None or self.resistance_level is None:
                self.detect_support_resistance(data)
            
            current_price = data['Close'].iloc[-1]
            current_candle_time = data.index[-1]
            prev_candle_high = data['High'].iloc[-2]
            prev_candle_low = data['Low'].iloc[-2]
            
            # MODIFIED: Prevent duplicate signals from same candle
            if self.last_processed_candle == current_candle_time:
                logger.debug(f"Candle {current_candle_time} already processed, skipping")
                return None
            
            # Check 9-SMA crossover
            signal_9 = self.check_sma_crossover(data, SMA_9_PERIOD)
            
            signal = None
            
            # Buy signal: Near support + bullish crossover
            support_range = self.support_level * 1.01  # 1% range
            if current_price <= support_range and signal_9 == "BULLISH":
                stop_loss = prev_candle_low
                sl_distance = current_price - stop_loss
                target = current_price + (sl_distance * RISK_REWARD_RATIO)
                
                signal = {
                    'type': 'CALL',
                    'entry': current_price,
                    'stop_loss': stop_loss,
                    'target': target,
                    'level': self.support_level,
                    'timestamp': datetime.now()
                }
                logger.info(f"CALL signal generated - Entry: {current_price:.2f}")
                self.last_processed_candle = current_candle_time
            
            # Sell signal: Near resistance + bearish crossover
            resistance_range = self.resistance_level * 0.99  # 1% range
            if current_price >= resistance_range and signal_9 == "BEARISH":
                stop_loss = prev_candle_high
                sl_distance = stop_loss - current_price
                target = current_price - (sl_distance * RISK_REWARD_RATIO)
                
                signal = {
                    'type': 'PUT',
                    'entry': current_price,
                    'stop_loss': stop_loss,
                    'target': target,
                    'level': self.resistance_level,
                    'timestamp': datetime.now()
                }
                logger.info(f"PUT signal generated - Entry: {current_price:.2f}")
                self.last_processed_candle = current_candle_time
            
            return signal
        except Exception as e:
            logger.error(f"Error generating trade signal: {str(e)}")
            return None
    
    def send_email(self, subject, html_content):
        """Send HTML email via SMTP"""
        try:
            logger.info(f"Sending email: {subject}")
            
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = SENDER_EMAIL
            message['To'] = RECEIVER_EMAIL
            
            html_part = MIMEText(html_content, 'html')
            message.attach(html_part)
            
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())
            
            logger.info("Email sent successfully")
            return True
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False
    
    def create_premarket_html(self, gift_nifty, fii_dii):
        """Create HTML email for pre-market summary"""
        gift_price, gift_change = gift_nifty if gift_nifty else (0, 0)
        fii_net = fii_dii['fii_net'] if fii_dii else 0
        dii_net = fii_dii['dii_net'] if fii_dii else 0
        
        bias_color = "#28a745" if gift_change > 0 else "#dc3545"
        bias_text = "Bullish" if gift_change > 0 else "Bearish" if gift_change < 0 else "Neutral"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px 10px 0 0; margin: -30px -30px 20px -30px; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .section {{ margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-radius: 8px; }}
                .section-title {{ font-weight: bold; color: #333; margin-bottom: 10px; font-size: 16px; border-bottom: 2px solid #667eea; padding-bottom: 5px; }}
                .data-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e0e0e0; }}
                .data-label {{ color: #666; font-weight: 500; }}
                .data-value {{ color: #333; font-weight: bold; }}
                .positive {{ color: #28a745; }}
                .negative {{ color: #dc3545; }}
                .bias {{ padding: 10px 20px; border-radius: 5px; text-align: center; font-weight: bold; font-size: 18px; }}
                .footer {{ margin-top: 20px; text-align: center; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Nifty Pre-Market Summary</h1>
                    <p style="margin: 5px 0 0 0;">{datetime.now().strftime('%B %d, %Y - %I:%M %p')}</p>
                </div>
                
                <div class="section">
                    <div class="section-title">Support & Resistance Levels</div>
                    <div class="data-row">
                        <span class="data-label">Support Level</span>
                        <span class="data-value positive">{self.support_level:.2f}</span>
                    </div>
                    <div class="data-row">
                        <span class="data-label">Resistance Level</span>
                        <span class="data-value negative">{self.resistance_level:.2f}</span>
                    </div>
                </div>
                
                <div class="section">
                    <div class="section-title">GIFT Nifty (Pre-Market Indicator)</div>
                    <div class="data-row">
                        <span class="data-label">Current Value</span>
                        <span class="data-value">{gift_price:.2f}</span>
                    </div>
                    <div class="data-row">
                        <span class="data-label">Change</span>
                        <span class="data-value {'positive' if gift_change > 0 else 'negative'}">{gift_change:+.2f}%</span>
                    </div>
                </div>
                
                <div class="section">
                    <div class="section-title">FII/DII Activity (Previous Day)</div>
                    <div class="data-row">
                        <span class="data-label">FII Net Buy/Sell</span>
                        <span class="data-value {'positive' if fii_net > 0 else 'negative'}">₹ {fii_net:+.2f} Cr</span>
                    </div>
                    <div class="data-row">
                        <span class="data-label">DII Net Buy/Sell</span>
                        <span class="data-value {'positive' if dii_net > 0 else 'negative'}">₹ {dii_net:+.2f} Cr</span>
                    </div>
                </div>
                
                <div class="section">
                    <div class="bias" style="background-color: {bias_color}; color: white;">
                        Technical Bias: {bias_text}
                    </div>
                </div>
                
                <div class="footer">
                    <p>Automated alert from Nifty Indicator Application</p>
                    <p>This is for informational purposes only. Trade at your own risk.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    def create_trade_alert_html(self, signal):
        """Create HTML email for trade signal"""
        signal_color = "#28a745" if signal['type'] == "CALL" else "#dc3545"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .header {{ background: {signal_color}; color: white; padding: 20px; border-radius: 10px 10px 0 0; margin: -30px -30px 20px -30px; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .signal-type {{ background-color: white; color: {signal_color}; display: inline-block; padding: 10px 30px; border-radius: 25px; font-weight: bold; font-size: 20px; margin-top: 10px; }}
                .section {{ margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-radius: 8px; }}
                .section-title {{ font-weight: bold; color: #333; margin-bottom: 10px; font-size: 16px; border-bottom: 2px solid {signal_color}; padding-bottom: 5px; }}
                .data-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e0e0e0; }}
                .data-label {{ color: #666; font-weight: 500; font-size: 14px; }}
                .data-value {{ color: #333; font-weight: bold; font-size: 16px; }}
                .highlight {{ background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; border-radius: 5px; margin: 15px 0; }}
                .footer {{ margin-top: 20px; text-align: center; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Trade Trigger Alert</h1>
                    <div class="signal-type">{signal['type']} SIGNAL</div>
                </div>
                
                <div class="section">
                    <div class="section-title">Trade Parameters</div>
                    <div class="data-row">
                        <span class="data-label">Entry Price</span>
                        <span class="data-value">{signal['entry']:.2f}</span>
                    </div>
                    <div class="data-row">
                        <span class="data-label">Stop Loss</span>
                        <span class="data-value">{signal['stop_loss']:.2f}</span>
                    </div>
                    <div class="data-row">
                        <span class="data-label">Target (1:3 R:R)</span>
                        <span class="data-value">{signal['target']:.2f}</span>
                    </div>
                    <div class="data-row">
                        <span class="data-label">Key Level</span>
                        <span class="data-value">{signal['level']:.2f}</span>
                    </div>
                </div>
                
                <div class="highlight">
                    <strong>Suggested Option:</strong> NIFTY {int(signal['entry'])} {'CE' if signal['type'] == 'CALL' else 'PE'} (Weekly Expiry)
                    <br><small>Verify volume and liquidity before trading</small>
                </div>
                
                <div class="section">
                    <div class="section-title">Risk Management</div>
                    <p style="margin: 5px 0;">Risk per trade: {abs(signal['entry'] - signal['stop_loss']):.2f} points</p>
                    <p style="margin: 5px 0;">Potential reward: {abs(signal['target'] - signal['entry']):.2f} points</p>
                    <p style="margin: 5px 0;">Risk-Reward Ratio: 1:{RISK_REWARD_RATIO}</p>
                </div>
                
                <div class="footer">
                    <p>Alert generated at {signal['timestamp'].strftime('%I:%M:%S %p')}</p>
                    <p>This is an automated alert. Always verify signals before trading.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    def create_momentum_confirmation_html(self, signal):
        """Create HTML email for momentum confirmation"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 20px; border-radius: 10px 10px 0 0; margin: -30px -30px 20px -30px; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .alert-box {{ background-color: #d4edda; border: 2px solid #28a745; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center; }}
                .alert-box h2 {{ color: #155724; margin: 0 0 10px 0; }}
                .section {{ margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-radius: 8px; }}
                .data-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e0e0e0; }}
                .data-label {{ color: #666; font-weight: 500; }}
                .data-value {{ color: #333; font-weight: bold; }}
                .recommendation {{ background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .footer {{ margin-top: 20px; text-align: center; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Momentum Confirmation Alert</h1>
                    <p style="margin: 5px 0 0 0;">{datetime.now().strftime('%I:%M %p')}</p>
                </div>
                
                <div class="alert-box">
                    <h2>20-SMA Crossover Confirmed</h2>
                    <p style="margin: 0; font-size: 16px;">Strong momentum continuation detected</p>
                </div>
                
                <div class="section">
                    <div class="data-row">
                        <span class="data-label">Signal Type</span>
                        <span class="data-value">Strong {'Buy' if signal['type'] == 'CALL' else 'Sell'}</span>
                    </div>
                    <div class="data-row">
                        <span class="data-label">Entry Price</span>
                        <span class="data-value">{signal['entry']:.2f}</span>
                    </div>
                    <div class="data-row">
                        <span class="data-label">Stop Loss</span>
                        <span class="data-value">{signal['stop_loss']:.2f}</span>
                    </div>
                    <div class="data-row">
                        <span class="data-label">Target</span>
                        <span class="data-value">{signal['target']:.2f}</span>
                    </div>
                </div>
                
                <div class="recommendation">
                    <strong>Recommendation:</strong><br>
                    Market shows strong {'bullish' if signal['type'] == 'CALL' else 'bearish'} momentum - likely to surpass Target 1.<br>
                    Consider holding position or booking partial profit.
                </div>
                
                <div class="footer">
                    <p>Automated momentum alert from Nifty Indicator Application</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    def create_market_close_html(self, data):
        """Create HTML email for market close summary"""
        day_open = data['Open'].iloc[0]
        day_close = data['Close'].iloc[-1]
        day_high = data['High'].max()
        day_low = data['Low'].min()
        day_change = ((day_close - day_open) / day_open) * 100
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px 10px 0 0; margin: -30px -30px 20px -30px; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .section {{ margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-radius: 8px; }}
                .section-title {{ font-weight: bold; color: #333; margin-bottom: 10px; font-size: 16px; border-bottom: 2px solid #667eea; padding-bottom: 5px; }}
                .data-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e0e0e0; }}
                .data-label {{ color: #666; font-weight: 500; }}
                .data-value {{ color: #333; font-weight: bold; }}
                .positive {{ color: #28a745; }}
                .negative {{ color: #dc3545; }}
                .footer {{ margin-top: 20px; text-align: center; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Market Close Summary</h1>
                    <p style="margin: 5px 0 0 0;">{datetime.now().strftime('%B %d, %Y')}</p>
                </div>
                
                <div class="section">
                    <div class="section-title">Nifty 50 Performance</div>
                    <div class="data-row">
                        <span class="data-label">Open</span>
                        <span class="data-value">{day_open:.2f}</span>
                    </div>
                    <div class="data-row">
                        <span class="data-label">Close</span>
                        <span class="data-value">{day_close:.2f}</span>
                    </div>
                    <div class="data-row">
                        <span class="data-label">High</span>
                        <span class="data-value">{day_high:.2f}</span>
                    </div>
                    <div class="data-row">
                        <span class="data-label">Low</span>
                        <span class="data-value">{day_low:.2f}</span>
                    </div>
                    <div class="data-row">
                        <span class="data-label">Change</span>
                        <span class="data-value {'positive' if day_change > 0 else 'negative'}">{day_change:+.2f}%</span>
                    </div>
                </div>
                
                <div class="section">
                    <div class="section-title">Key Levels for Next Session</div>
                    <div class="data-row">
                        <span class="data-label">Support</span>
                        <span class="data-value">{self.support_level:.2f}</span>
                    </div>
                    <div class="data-row">
                        <span class="data-label">Resistance</span>
                        <span class="data-value">{self.resistance_level:.2f}</span>
                    </div>
                </div>
                
                <div class="footer">
                    <p>End of day summary from Nifty Indicator Application</p>
                    <p>See you tomorrow for pre-market analysis</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    def premarket_analysis(self):
        """Case 1: Pre-market analysis at 9:00 AM"""
        logger.info("=== Starting Pre-Market Analysis ===")
        
        # Fetch 4-hour data for support/resistance
        data_4h = self.fetch_nifty_data(interval='60m', period='30d')
        if data_4h is None:
            logger.error("Failed to fetch 4-hour data")
            return
        
        # Detect support and resistance
        self.detect_support_resistance(data_4h)
        
        # Fetch GIFT Nifty
        gift_nifty = self.fetch_gift_nifty()
        
        # Fetch FII/DII data
        fii_dii = self.fetch_fii_dii_data()
        
        # Create and send email
        html = self.create_premarket_html(gift_nifty, fii_dii)
        self.send_email("Nifty Pre-Market Summary", html)
        
        logger.info("=== Pre-Market Analysis Complete ===")
    
    def live_market_monitoring(self):
        """
        Case 2: Live market signal monitoring - MODIFIED for 10-second interval
        
        Approximate API calls during market hours:
        - Market duration: 9:15 AM to 3:30 PM = 6 hours 15 minutes = 22,500 seconds
        - Fetch interval: 10 seconds
        - Total calls: ~2,250 per day during market hours
        """
        logger.info("=== Starting Live Market Monitoring ===")
        logger.info(f"Fetch interval: {LIVE_FETCH_INTERVAL} seconds")
        logger.info("Estimated API calls per market day: ~2,250")
        
        while True:
            now = datetime.now().time()
            
            # Market hours: 9:15 AM to 3:30 PM
            market_open = time(9, 15)
            market_close = time(15, 30)
            
            if market_open <= now <= market_close:
                try:
                    # MODIFIED: Fetch 5-minute data every 10 seconds
                    data_5m = self.fetch_nifty_data(interval='5m', period='5d')
                    
                    if data_5m is not None and len(data_5m) >= SMA_20_PERIOD:
                        # Generate trade signal
                        signal = self.generate_trade_signal(data_5m)
                        
                        if signal:
                            # Send trade alert
                            html = self.create_trade_alert_html(signal)
                            self.send_email(f"Trade Alert: {signal['type']} Signal", html)
                            
                            # Check for 20-SMA confirmation after a short delay
                            logger.info("Waiting for 20-SMA confirmation check (60 seconds)...")
                            sleep(60)
                            
                            data_5m = self.fetch_nifty_data(interval='5m', period='5d')
                            signal_20 = self.check_sma_crossover(data_5m, SMA_20_PERIOD)
                            
                            if signal_20 and signal_20 == ("BULLISH" if signal['type'] == "CALL" else "BEARISH"):
                                html_confirm = self.create_momentum_confirmation_html(signal)
                                self.send_email("Momentum Confirmation Alert", html_confirm)
                    
                    # MODIFIED: Sleep for 10 seconds instead of 300 seconds (5 minutes)
                    logger.debug(f"Next fetch in {LIVE_FETCH_INTERVAL} seconds...")
                    sleep(LIVE_FETCH_INTERVAL)
                    
                except Exception as e:
                    logger.error(f"Error in live monitoring: {str(e)}")
                    logger.info(f"Retrying in {LIVE_FETCH_INTERVAL} seconds...")
                    sleep(LIVE_FETCH_INTERVAL)
            else:
                logger.info("Outside market hours. Waiting...")
                sleep(600)  # Check every 10 minutes outside market hours
    
    def market_close_summary(self):
        """Send market close summary"""
        logger.info("=== Generating Market Close Summary ===")
        
        data = self.fetch_nifty_data(interval='5m', period='1d')
        if data is not None:
            html = self.create_market_close_html(data)
            self.send_email("Market Close Summary", html)
        
        logger.info("=== Market Close Summary Sent ===")
    
    def run(self):
        """Main run method"""
        logger.info("=== Application Started ===")
        
        # Check if it's pre-market time (9:00 AM)
        now = datetime.now()
        if now.time() >= time(9, 0) and now.time() < time(9, 15):
            self.premarket_analysis()
        
        # Start live monitoring
        try:
            self.live_market_monitoring()
        except KeyboardInterrupt:
            logger.info("Application stopped by user")
        except Exception as e:
            logger.error(f"Fatal error: {str(e)}")
        finally:
            logger.info("=== Application Shutdown ===")

if __name__ == "__main__":
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        logger.error("SMTP credentials not configured. Please set up .env file")
        sys.exit(1)
    
    app = NiftyIndicatorApp()
    app.run()
