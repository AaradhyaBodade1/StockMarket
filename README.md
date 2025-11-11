# Real-Time Nifty Indicator Application

**Automated Trading Signal Generator for Nifty 50 Index with Email Alerts**

A production-ready Python application that monitors the Nifty 50 index in real-time, detects technical trading signals using SMA crossovers, and sends professional HTML email alerts with trade recommendations.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [File Structure](#file-structure)
- [How It Works](#how-it-works)
- [Trading Logic](#trading-logic)
- [Email Templates](#email-templates)
- [Logs & Monitoring](#logs--monitoring)
- [API Usage](#api-usage)
- [Customization](#customization)
- [Troubleshooting](#troubleshooting)
- [Safety & Disclaimer](#safety--disclaimer)

---

## Overview

This application automates Nifty 50 trading analysis by:

1. **Pre-Market Analysis (9:00 AM)** - Identifies key support/resistance levels and market sentiment
2. **Live Signal Detection (9:15 AM - 3:30 PM)** - Monitors 5-minute candles every 10 seconds for trade setups
3. **Momentum Confirmation** - Validates signals with 20-SMA crossover
4. **Market Close Summary (3:30 PM)** - Daily performance recap

All findings are sent via **professional HTML emails** with no emojis and impressive color-coded designs.

---

## Features

### ✅ Case 1: Pre-Market Analysis
- **Time**: 9:00 AM daily (before market open)
- **Data**: 4-hour (60-minute) candle analysis for past 30 days
- **Detects**: Support levels (swing lows) and Resistance levels (swing highs)
- **Includes**: 
  - GIFT Nifty pre-market value & % change
  - FII/DII institutional buying/selling activity
  - Technical bias (Bullish/Bearish/Neutral)
- **Output**: HTML email with purple gradient design

### ✅ Case 2: Live Market Signals
- **Duration**: 9:15 AM to 3:30 PM (market hours)
- **Frequency**: Every 10 seconds (configurable)
- **Data**: 5-minute candle data
- **Indicators**:
  - 9-period Simple Moving Average (9-SMA)
  - Support/Resistance zones
- **Signal Types**:
  - **CALL (Buy)**: Price near support + 9-SMA bullish crossover
  - **PUT (Sell)**: Price near resistance + 9-SMA bearish crossover
- **Trade Calculations**:
  - Entry: Current price
  - Stop Loss: Previous candle high/low
  - Target: 1:3 Risk-Reward ratio
  - Option Suggestion: Nearest strike with volume confirmation
- **Output**: HTML email with green (CALL) or red (PUT) header

### ✅ Case 3: Momentum Confirmation
- **Trigger**: After initial trade signal
- **Condition**: 20-SMA crossover in same direction as 9-SMA
- **Meaning**: Strong momentum continuation
- **Recommendation**: Hold for target or book partial profits
- **Output**: HTML email with pink-red gradient header

### ✅ Case 4: Market Close Summary
- **Time**: 3:30 PM (market close)
- **Includes**: 
  - Day's OHLC (Open, High, Low, Close)
  - Performance percentage
  - Key levels for next trading session
- **Output**: HTML email with purple gradient design

---

## System Requirements

### Software
- **Python**: 3.8 or higher
- **Operating System**: Linux, macOS, or Windows
- **Internet**: Required for API calls and email sending

### Python Libraries (see requirements.txt)
```
yfinance==0.2.38          # Fetch Nifty data from Yahoo Finance
pandas==2.2.1             # Data manipulation
numpy==1.26.4             # Numerical operations
python-dotenv==1.0.1      # Load environment variables
beautifulsoup4==4.12.3    # Web scraping FII/DII
requests==2.31.0          # HTTP requests
lxml==5.1.0               # HTML parsing
```

---

## Installation

### Step 1: Clone/Download Files

Download these 6 files into a single directory:

```
your-project-folder/
├── nifty_indicator.py      # Main application
├── requirements.txt         # Dependencies
├── .env.example            # Configuration template
├── .env                    # Your SMTP credentials (create this)
├── setup.sh                # Setup script
└── README.md               # This file
```

### Step 2: Run Setup Script

```bash
chmod +x setup.sh
./setup.sh
```

This script will:
- Create a Python virtual environment (venv/)
- Install all required packages
- Display next steps

### Step 3: Configure Email Credentials

```bash
cp .env.example .env
nano .env  # or use any text editor
```

Edit the `.env` file with your Gmail credentials:

```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password_here
RECEIVER_EMAIL=where_alerts_go@gmail.com
```

### Step 4: Get Gmail App Password

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** (if not already enabled)
3. Search for **"App passwords"**
4. Select **"Mail"** and **"Windows Computer"** (or your device)
5. Copy the **16-character password**
6. Paste it in `.env` as `SENDER_PASSWORD`

### Step 5: Run the Application

```bash
source venv/bin/activate
python nifty_indicator.py
```

---

## Configuration

### Core Parameters (edit in nifty_indicator.py)

```python
# Line 35-39: Trading Configuration
SMA_9_PERIOD = 9                    # Short-term trend (9 candles)
SMA_20_PERIOD = 20                  # Momentum confirmation (20 candles)
RISK_REWARD_RATIO = 3               # Target = Entry + (SL_Distance × 3)
SUPPORT_RESISTANCE_LOOKBACK = 20    # Swing detection window (20 candles)

# Line 42: Fetch Interval
LIVE_FETCH_INTERVAL = 10            # Seconds between data fetches (10 = very fast)
```

### Environment Variables (.env file)

```env
SMTP_SERVER=smtp.gmail.com          # Gmail SMTP server
SMTP_PORT=587                       # TLS encryption port
SENDER_EMAIL=your_email@gmail.com   # Email sending from
SENDER_PASSWORD=xxxx xxxx xxxx xxxx # 16-char Gmail app password
RECEIVER_EMAIL=alerts@example.com   # Email receiving to
```

### Market Hours

Hardcoded in `live_market_monitoring()`:

```python
market_open = time(9, 15)           # 9:15 AM IST
market_close = time(15, 30)         # 3:30 PM IST
```

To change: Edit lines in the function (adjust for your timezone if needed).

---

## File Structure

### Main Application: `nifty_indicator.py`

```
NiftyIndicatorApp Class
│
├── Data Fetching Methods
│   ├── fetch_nifty_data()              # Get 5-min or 1-hour candles from Yahoo
│   ├── fetch_gift_nifty()              # Get GIFT Nifty pre-market indicator
│   └── fetch_fii_dii_data()            # Get FII/DII institutional data
│
├── Technical Analysis Methods
│   ├── calculate_sma()                 # Calculate Simple Moving Averages
│   ├── detect_support_resistance()     # Find swing highs/lows
│   └── check_sma_crossover()           # Detect 9-SMA & 20-SMA crosses
│
├── Signal Generation
│   └── generate_trade_signal()         # Create CALL/PUT signals
│
├── Email Generation Methods
│   ├── create_premarket_html()         # Pre-market template
│   ├── create_trade_alert_html()       # Trade alert template
│   ├── create_momentum_confirmation_html() # Momentum template
│   ├── create_market_close_html()      # Close summary template
│   └── send_email()                    # Send via SMTP
│
├── Main Workflow Methods
│   ├── premarket_analysis()            # Case 1 (9:00 AM)
│   ├── live_market_monitoring()        # Case 2 (9:15 AM - 3:30 PM)
│   ├── market_close_summary()          # Case 4 (3:30 PM)
│   └── run()                           # Main execution
│
└── Application Start
    └── if __name__ == "__main__"
```

### Configuration Files

**requirements.txt**
```
yfinance==0.2.38
pandas==2.2.1
numpy==1.26.4
python-dotenv==1.0.1
beautifulsoup4==4.12.3
requests==2.31.0
lxml==5.1.0
```

**.env (yours, keep secret!)**
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
RECEIVER_EMAIL=recipient_email@gmail.com
```

**.env.example (template)**
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
RECEIVER_EMAIL=recipient_email@gmail.com
# Don't commit .env file to repositories
```

---

## How It Works

### Initialization

```python
app = NiftyIndicatorApp()
# Sets:
# - support_level = None
# - resistance_level = None
# - last_processed_candle = None (prevents duplicate signals)
# - Logging to both file and console
```

### Pre-Market Analysis Workflow (9:00 AM)

```
1. Fetch 4-hour candle data (past 30 days)
   ↓
2. Detect support levels (rolling minimum of lows)
   ↓
3. Detect resistance levels (rolling maximum of highs)
   ↓
4. Fetch GIFT Nifty price & % change
   ↓
5. Fetch FII/DII net buy/sell data
   ↓
6. Generate HTML email with purple header
   ↓
7. Send via SMTP to RECEIVER_EMAIL
   ↓
8. Log: "Pre-Market Analysis Complete"
```

### Live Market Monitoring Workflow (9:15 AM - 3:30 PM)

```
Loop every 10 seconds:
│
├─ Check current time
│  ├─ IF outside 9:15 AM - 3:30 PM → Sleep 10 minutes, retry
│  └─ IF inside market hours → Continue
│
├─ Fetch latest 5-minute candle data
│
├─ Check if 20+ candles available (for SMA calculations)
│
├─ Generate trade signal:
│   ├─ Calculate 9-SMA
│   ├─ Check for 9-SMA crossover
│   ├─ Compare price to support/resistance
│   ├─ If CALL/PUT conditions met → Create signal
│   └─ Prevent duplicate from same candle
│
├─ IF signal generated:
│   ├─ Create HTML email (green for CALL, red for PUT)
│   ├─ Send trade alert email
│   ├─ Wait 60 seconds
│   ├─ Fetch fresh 5-minute data
│   ├─ Check for 20-SMA crossover confirmation
│   ├─ IF 20-SMA confirms → Send momentum alert email
│   └─ Continue monitoring
│
└─ Sleep 10 seconds before next fetch
```

### Market Close Workflow (3:30 PM)

```
1. Fetch today's 5-minute candles
   ↓
2. Extract Open, High, Low, Close
   ↓
3. Calculate day's % change
   ↓
4. Include support/resistance for next session
   ↓
5. Generate HTML email with summary
   ↓
6. Send via SMTP
```

---

## Trading Logic

### Support Detection Algorithm

```python
# Find the lowest low price in each 20-candle rolling window
local_min = data['Low'].rolling(window=20, center=True).min()

# Find rows where actual low = rolling minimum (swing lows)
support_points = data[data['Low'] == local_min]['Low'].values

# Average last 3 support points for final level
support_level = np.mean(support_points[-3:])
```

**Example**: If swing lows are 24,480, 24,490, 24,485
- Support = (24,480 + 24,490 + 24,485) / 3 = **24,485**

### Resistance Detection Algorithm

```python
# Find the highest high price in each 20-candle rolling window
local_max = data['High'].rolling(window=20, center=True).max()

# Find rows where actual high = rolling maximum (swing highs)
resistance_points = data[data['High'] == local_max]['High'].values

# Average last 3 resistance points for final level
resistance_level = np.mean(resistance_points[-3:])
```

### SMA Crossover Detection

**Bullish Crossover** (Price crosses ABOVE SMA):
```python
if previous_price <= previous_sma AND current_price > current_sma:
    signal = "BULLISH"
```

**Bearish Crossover** (Price crosses BELOW SMA):
```python
if previous_price >= previous_sma AND current_price < current_sma:
    signal = "BEARISH"
```

### Trade Signal Generation

#### CALL Signal (Buy) Requirements:
```python
# Condition 1: Price near support (within 1%)
current_price <= support_level * 1.01

# Condition 2: 9-SMA bullish crossover
signal_9 == "BULLISH"

# If both TRUE → Generate CALL signal
entry = current_price
stop_loss = previous_candle_low
risk_distance = entry - stop_loss
target = entry + (risk_distance × RISK_REWARD_RATIO)
```

**Example**:
```
Support Level: 24,500
Current Price: 24,508 (within 1% = 24,705)  ✓ Near support
9-SMA: Just crossed above price  ✓ Bullish
Previous Candle Low: 24,480

Entry: 24,508
Stop Loss: 24,480
Risk: 24,508 - 24,480 = 28 points
Target: 24,508 + (28 × 3) = 24,592
```

#### PUT Signal (Sell) Requirements:
```python
# Condition 1: Price near resistance (within 1%)
current_price >= resistance_level * 0.99

# Condition 2: 9-SMA bearish crossover
signal_9 == "BEARISH"

# If both TRUE → Generate PUT signal
entry = current_price
stop_loss = previous_candle_high
risk_distance = stop_loss - entry
target = entry - (risk_distance × RISK_REWARD_RATIO)
```

**Example**:
```
Resistance Level: 24,800
Current Price: 24,792 (within 1% = 24,705)  ✓ Near resistance
9-SMA: Just crossed below price  ✓ Bearish
Previous Candle High: 24,820

Entry: 24,792
Stop Loss: 24,820
Risk: 24,820 - 24,792 = 28 points
Target: 24,792 - (28 × 3) = 24,708
```

### Momentum Confirmation

After a trade signal is sent, the app waits 60 seconds then checks:

```python
# Does 20-SMA cross in same direction as 9-SMA?
# For CALL: Did price cross ABOVE 20-SMA?
# For PUT: Did price cross BELOW 20-SMA?

if confirmed:
    send_momentum_alert("Strong Buy/Sell - Hold for target")
else:
    continue_monitoring()
```

---

## Email Templates

### 1. Pre-Market Summary Email

**Header**: Purple gradient (#667eea → #764ba2)

**Content**:
```
Nifty Pre-Market Summary
November 12, 2025 - 09:00 AM

Support & Resistance Levels
├─ Support Level: 24,485.50
└─ Resistance Level: 24,815.75

GIFT Nifty (Pre-Market Indicator)
├─ Current Value: 24,550.25
└─ Change: +0.35%

FII/DII Activity (Previous Day)
├─ FII Net Buy/Sell: ₹ -2,450.00 Cr
└─ DII Net Buy/Sell: ₹ +3,200.00 Cr

Technical Bias: Bullish
```

**Color Coding**:
- Green (#28a745): Positive values, support
- Red (#dc3545): Negative values, resistance
- Purple: Bias background

---

### 2. Trade Alert Email

**Header**: Green (#28a745) for CALL, Red (#dc3545) for PUT

**Content**:
```
Trade Trigger Alert
CALL SIGNAL

Trade Parameters
├─ Entry Price: 24,508.00
├─ Stop Loss: 24,480.00
├─ Target (1:3 R:R): 24,592.00
└─ Key Level: 24,485.50

Suggested Option: NIFTY 24508 CE (Weekly Expiry)
Verify volume and liquidity before trading

Risk Management
├─ Risk per trade: 28.00 points
├─ Potential reward: 84.00 points
└─ Risk-Reward Ratio: 1:3

Alert generated at 09:45:30 AM
```

**Interactive Features**:
- Color-coded headers make signal type instantly recognizable
- Risk metrics help with position sizing
- Option suggestion ready to copy-paste

---

### 3. Momentum Confirmation Email

**Header**: Pink-red gradient (#f093fb → #f5576c)

**Content**:
```
Momentum Confirmation Alert
09:46 AM

20-SMA Crossover Confirmed
Strong momentum continuation detected

Signal Details
├─ Signal Type: Strong Buy
├─ Entry Price: 24,508.00
├─ Stop Loss: 24,480.00
└─ Target: 24,592.00

Recommendation:
Market shows strong bullish momentum - likely to surpass Target 1.
Consider holding position or booking partial profit.
```

**Purpose**: Validates the initial signal, increases confidence

---

### 4. Market Close Summary Email

**Header**: Purple gradient (#667eea → #764ba2)

**Content**:
```
Market Close Summary
November 12, 2025

Nifty 50 Performance
├─ Open: 24,500.50
├─ Close: 24,650.75
├─ High: 24,750.00
├─ Low: 24,450.25
└─ Change: +0.61%

Key Levels for Next Session
├─ Support: 24,485.50
└─ Resistance: 24,815.75

End of day summary from Nifty Indicator Application
See you tomorrow for pre-market analysis
```

**Purpose**: Daily recap + preparation for next session

---

## Logs & Monitoring

### Log File: `nifty_indicator.log`

**Created automatically** in your project directory. Contains all operations.

**Example Log Output**:

```
2025-11-12 09:00:15 - INFO - === Initializing Nifty Indicator Application ===
2025-11-12 09:00:16 - INFO - Application initialized successfully
2025-11-12 09:00:16 - INFO - Live market fetch interval: 10 seconds
2025-11-12 09:00:30 - INFO - === Starting Pre-Market Analysis ===
2025-11-12 09:00:31 - INFO - Fetching Nifty data - Interval: 60m, Period: 30d
2025-11-12 09:00:35 - INFO - Successfully fetched 130 candles
2025-11-12 09:00:35 - INFO - Detecting support and resistance levels
2025-11-12 09:00:36 - INFO - Support: 24485.50, Resistance: 24815.75
2025-11-12 09:00:37 - INFO - Fetching GIFT Nifty data
2025-11-12 09:00:38 - INFO - GIFT Nifty: 24550.25, Change: 0.35%
2025-11-12 09:00:39 - INFO - Fetching FII/DII data
2025-11-12 09:00:40 - INFO - FII Net: ₹-2450.00 Cr, DII Net: ₹3200.00 Cr
2025-11-12 09:00:41 - INFO - Sending email: Nifty Pre-Market Summary
2025-11-12 09:00:45 - INFO - Email sent successfully
2025-11-12 09:00:45 - INFO - === Pre-Market Analysis Complete ===
2025-11-12 09:00:46 - INFO - === Starting Live Market Monitoring ===
2025-11-12 09:00:46 - INFO - Fetch interval: 10 seconds
2025-11-12 09:00:46 - INFO - Estimated API calls per market day: ~2,250
2025-11-12 09:15:05 - INFO - Outside market hours. Waiting...
2025-11-12 09:15:56 - DEBUG - Fetching Nifty data - Interval: 5m, Period: 5d
2025-11-12 09:16:02 - DEBUG - Successfully fetched 65 candles
2025-11-12 09:16:03 - DEBUG - Analyzing for trade signals
2025-11-12 09:16:04 - DEBUG - Calculating SMA-9
2025-11-12 09:16:05 - INFO - Bullish crossover detected - SMA-9
2025-11-12 09:16:06 - INFO - CALL signal generated - Entry: 24508.00
2025-11-12 09:16:07 - INFO - Sending email: Trade Alert: CALL Signal
2025-11-12 09:16:12 - INFO - Email sent successfully
2025-11-12 09:16:13 - INFO - Waiting for 20-SMA confirmation check (60 seconds)...
2025-11-12 09:17:13 - DEBUG - Fetching Nifty data - Interval: 5m, Period: 5d
2025-11-12 09:17:19 - INFO - Bullish crossover detected - SMA-20
2025-11-12 09:17:20 - INFO - Sending email: Momentum Confirmation Alert
2025-11-12 09:17:25 - INFO - Email sent successfully
2025-11-12 09:17:26 - DEBUG - Next fetch in 10 seconds...
2025-11-12 09:17:36 - DEBUG - Fetching Nifty data - Interval: 5m, Period: 5d
```

### Log Levels

| Level | Usage | Example |
|-------|-------|---------|
| **INFO** | Important operations | "Email sent successfully" |
| **DEBUG** | Detailed diagnostics | "Calculated SMA-9" |
| **WARNING** | Potential issues | "Unable to fetch GIFT Nifty" |
| **ERROR** | Failures | "SMTP Authentication Failed" |

### Monitoring Commands

```bash
# View live logs as they happen
tail -f nifty_indicator.log

# Search for specific signal type
grep "CALL signal" nifty_indicator.log
grep "PUT signal" nifty_indicator.log

# Count total signals generated
grep "signal generated" nifty_indicator.log | wc -l

# View only errors
grep "ERROR" nifty_indicator.log

# View last 100 lines
tail -100 nifty_indicator.log
```

---

## API Usage

### Yahoo Finance (yfinance)

**Nifty Data Fetching**:

```python
ticker = yf.Ticker("^NSEI")
data = ticker.history(interval='5m', period='5d')
```

| Parameter | Value | Purpose |
|-----------|-------|---------|
| Symbol | `^NSEI` | Nifty 50 Index ticker |
| Interval | `5m` | 5-minute candles |
| Interval | `60m` | 1-hour candles |
| Period | `5d` | Last 5 trading days |
| Period | `30d` | Last 30 trading days |

**API Rate Limits**:
- Yahoo Finance has no official rate limit
- Recommended: 1-2 requests per second
- This app: ~2,250 calls/day during market hours = ~0.09 calls/sec ✓

**Estimated Monthly API Calls** (assuming 20 trading days):
```
2,250 calls/day × 20 days = 45,000 calls/month (Well within limits)
```

### SMTP Email (Gmail)

**Configuration Used**:
```
Server: smtp.gmail.com
Port: 587
Security: TLS (STARTTLS)
Auth: Gmail App Password
```

**Email Sending Limits**:
- Gmail Free: Up to 500 emails/day
- This app: 4-5 emails/day (well within limits)

---

## Customization

### Change SMA Periods

For **faster** signal detection (more signals, more false positives):
```python
SMA_9_PERIOD = 5           # Faster 9-SMA → More sensitive
SMA_20_PERIOD = 10         # Faster 20-SMA → Quicker confirmation
```

For **slower** signal detection (fewer signals, more reliable):
```python
SMA_9_PERIOD = 15          # Slower 9-SMA → Less noise
SMA_20_PERIOD = 30         # Slower 20-SMA → Confirms strong trends
```

### Change Risk-Reward Ratio

For **conservative** trading (closer targets, higher win rate):
```python
RISK_REWARD_RATIO = 1.5    # Target closer (higher hit rate)
```

For **aggressive** trading (distant targets, higher profits):
```python
RISK_REWARD_RATIO = 5      # Target farther (higher reward)
```

### Change Fetch Interval

For **ultra-fast** signal detection:
```python
LIVE_FETCH_INTERVAL = 5    # Fetch every 5 seconds
# ~4,500 API calls/day
```

For **balanced** approach (current):
```python
LIVE_FETCH_INTERVAL = 10   # Fetch every 10 seconds
# ~2,250 API calls/day
```

For **conservative** API usage:
```python
LIVE_FETCH_INTERVAL = 30   # Fetch every 30 seconds
# ~750 API calls/day
```

### Change Market Hours

For **extended** monitoring (e.g., including pre-market):
```python
market_open = time(8, 0)   # Start at 8:00 AM
market_close = time(16, 0) # End at 4:00 PM
```

For **tight** monitoring (last hour only):
```python
market_open = time(14, 30) # Start at 2:30 PM
market_close = time(15, 30) # End at 3:30 PM (last hour)
```

### Change Support/Resistance Lookback

For **recent** levels (shorter window):
```python
SUPPORT_RESISTANCE_LOOKBACK = 10  # Last 10 candles only
```

For **major** levels (longer window):
```python
SUPPORT_RESISTANCE_LOOKBACK = 40  # Last 40 candles
```

### Change Recipient Email

For **multiple** recipients:
```python
# In send_email() method, modify:
recipients = [
    'trader@email.com',
    'backup@email.com',
    'analytics@email.com'
]
```

---

## Troubleshooting

### Common Issues & Solutions

#### ❌ Error: "SMTP Authentication Failed"

**Cause**: Wrong password or 2FA not configured

**Solution**:
1. Verify 2-Step Verification is **enabled** in Google Account
2. Generate a new App Password:
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Click "App passwords"
   - Select "Mail" and "Windows Computer"
   - Copy the **16-character password**
3. Paste into `.env` file
4. **Do not use** your regular Gmail password

---

#### ❌ Error: "No data returned from Yahoo Finance"

**Cause**: Yahoo Finance API unreachable or market data not available

**Solution**:
- Check internet connection
- Verify market is open (9:15 AM - 3:30 PM IST)
- Try again in a few minutes
- Check if Yahoo Finance website works

**Technical**: The `fetch_nifty_data()` function returns `None` on error, app continues operation

---

#### ❌ Error: "Unable to fetch GIFT Nifty data"

**Cause**: GIFT Nifty ticker temporarily unavailable

**Solution**:
- Check if [Yahoo Finance GIFT Nifty page](https://finance.yahoo.com/quote/%5ENSEI) loads
- Wait a few minutes and retry
- This is non-critical; pre-market email still sends

---

#### ⚠️ Logs getting too large

**Cause**: Long-running application creates large log files

**Solution**:
```bash
# Archive old log
mv nifty_indicator.log nifty_indicator.log.backup

# Or rotate logs (Linux/Mac)
# Add to crontab for daily rotation:
0 0 * * * gzip nifty_indicator.log && mv nifty_indicator.log.gz nifty_indicator.log.$(date +\%Y\%m\%d).gz
```

---

#### 📧 Emails not received

**Causes & Solutions**:

1. **Check spam folder**
   - Gmail moves alerts to spam sometimes
   - Add sender to contacts

2. **Verify recipient email**
   ```bash
   grep "RECEIVER_EMAIL" .env
   ```
   - Make sure it's spelled correctly in `.env`

3. **Check SMTP credentials**
   - Test manually:
   ```python
   import smtplib
   server = smtplib.SMTP('smtp.gmail.com', 587)
   server.starttls()
   server.login('your_email@gmail.com', 'app_password')
   print("Login successful!")
   server.quit()
   ```

4. **Check logs for errors**
   ```bash
   grep "Error sending email" nifty_indicator.log
   ```

---

#### 🔄 Signal alerts too frequent/rare

**Cause**: Signal parameters too sensitive/insensitive

**Solution**: Adjust parameters:

```python
# For fewer signals (too many alerts)
SMA_9_PERIOD = 15          # Slower 9-SMA
RISK_REWARD_RATIO = 4      # Stricter targets
SUPPORT_RESISTANCE_LOOKBACK = 30  # Major levels only

# For more signals (too few alerts)
SMA_9_PERIOD = 5           # Faster 9-SMA
RISK_REWARD_RATIO = 2      # Easier targets
SUPPORT_RESISTANCE_LOOKBACK = 10  # More recent levels
```

---

#### ❓ Application runs but no signals

**Checklist**:

1. **Is market open?**
   ```bash
   # Check system time
   date
   # Should be between 9:15 AM and 3:30 PM IST on weekdays
   ```

2. **Check logs**
   ```bash
   tail -50 nifty_indicator.log
   # Look for "Analyzing for trade signals"
   ```

3. **Check support/resistance levels**
   - If support = resistance (very narrow), levels may be off
   - Increase `SUPPORT_RESISTANCE_LOOKBACK` to 30-40 candles

4. **Verify data fetching**
   - Logs should show "Successfully fetched X candles"
   - If 0 candles, Yahoo Finance may be down

---

### Advanced Debugging

Enable **DEBUG** logging (more verbose):

Edit line 15-18:
```python
logging.basicConfig(
    level=logging.DEBUG  # Changed from INFO
    ...
)
```

Then run:
```bash
python nifty_indicator.py 2>&1 | grep -v "^DEBUG" > app.log
# Shows INFO and ERROR only
```

---

## Safety & Disclaimer

### ⚠️ IMPORTANT LEGAL NOTICE

**This application is provided for EDUCATIONAL and INFORMATIONAL purposes ONLY.**

### Risk Disclosure

1. **No Financial Advice**: This is NOT financial advice. Consult a licensed financial advisor before trading.

2. **Risk of Total Loss**: Trading/options involves substantial risk of loss. Past performance ≠ future results.

3. **Market Risk**: Markets can move against your position rapidly, causing losses exceeding your investment.

4. **System Risk**: 
   - API failures may cause missed signals
   - Email delays may result in late alerts
   - Internet outages may disconnect monitoring

5. **Technical Risk**:
   - Indicators are probabilistic, not deterministic
   - No system predicts market movements with certainty
   - False signals are inevitable

### Best Practices

✅ **DO**:
- Test signals in **paper trading mode** first
- Use **proper position sizing** (risk only 1-2% per trade)
- Set **hard stop losses** (mechanical exits)
- **Verify signals manually** before trading
- Keep **adequate capital reserves**
- **Diversify** across multiple strategies
- **Monitor logs** regularly for issues

❌ **DON'T**:
- Trade **real money** without paper testing
- Use **leverage** without understanding risks
- **Override stop losses** emotionally
- Trade **all your capital** in one signal
- **Rely solely** on automated systems
- Trade during **highly volatile periods** if inexperienced
- Use **borrowed money** (margin) if untested

### Regulatory Compliance

- Verify trading is legal in your jurisdiction
- Comply with local tax reporting requirements
- Consult compliance officer for institutional use
- Keep records of all trades for tax purposes

---

## Quick Reference

### Running Commands

```bash
# First time setup
chmod +x setup.sh
./setup.sh

# Activate environment
source venv/bin/activate

# Run application
python nifty_indicator.py

# Run in background (Linux/Mac)
nohup python nifty_indicator.py > nifty.log 2>&1 &

# Kill background process
pkill -f nifty_indicator.py

# View live logs
tail -f nifty_indicator.log

# Deactivate environment
deactivate
```

### Important Files

| File | Purpose | Edit? |
|------|---------|-------|
| `nifty_indicator.py` | Main code | ✓ Yes (params only) |
| `requirements.txt` | Dependencies | ✗ No |
| `.env` | Your credentials | ✓ Yes (setup only) |
| `.env.example` | Template | ✗ No |
| `nifty_indicator.log` | Application logs | ✗ No (auto-generated) |
| `README.md` | This file | ✗ No |

### Automation Setup

**Add to Crontab** (for automatic daily runs):

```bash
crontab -e
```

Add these lines:

```cron
# Pre-market analysis at 9:00 AM on weekdays
0 9 * * 1-5 cd /path/to/app && source venv/bin/activate && python nifty_indicator.py >> logs/premarket.log 2>&1

# Live monitoring starting at 9:15 AM
15 9 * * 1-5 cd /path/to/app && source venv/bin/activate && python nifty_indicator.py >> logs/live.log 2>&1

# Kill the process at 3:35 PM (after market close)
35 15 * * 1-5 pkill -f nifty_indicator.py
```

Replace `/path/to/app` with your actual directory (get it via `pwd` command).

---

## Support & Resources

### Useful Links

- [Yahoo Finance](https://finance.yahoo.com) - Data source
- [NSE India](https://www.nseindia.com) - Official market data
- [Python yfinance](https://github.com/ranaroussi/yfinance) - Documentation
- [Gmail App Passwords](https://support.google.com/accounts/answer/185833) - Setup guide
- [Python Logging](https://docs.python.org/3/library/logging.html) - Logging docs

### Getting Help

1. **Check logs first**: `tail -f nifty_indicator.log`
2. **Search error message** in this README
3. **Review configuration** in `.env` file
4. **Test SMTP manually** (see troubleshooting section)
5. **Verify market hours** (9:15 AM - 3:30 PM IST, weekdays only)

---

## Version History

### v1.0.0 (November 12, 2025)

Initial Release:
- ✅ Pre-market analysis (Case 1)
- ✅ Live market signals (Case 2)
- ✅ Momentum confirmation (Case 3)
- ✅ Market close summary (Case 4)
- ✅ 10-second fetch interval
- ✅ ~2,250 API calls per day
- ✅ Professional HTML emails
- ✅ Comprehensive logging
- ✅ Full documentation

---

## License & Attribution

This application is provided as-is for educational purposes. Use at your own risk.

---

**Happy Trading! 📈**

*Last Updated: November 12, 2025*  
*Questions? Check the logs and troubleshooting section above.*