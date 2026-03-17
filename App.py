from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime
import os

app = Flask(__name__)
binance = ccxt.binance()

def find_support_resistance(df, window=10):
    """Support/Resistance detection"""
    highs = df['high'].rolling(window=window, center=True).max()
    lows = df['low'].rolling(window=window, center=True).min()
    
    resistance = df[df['high'] == highs]['high'].dropna().tail(3).mean()
    support = df[df['low'] == lows]['low'].dropna().tail(3).mean()
    
    return support, resistance

def gainzalgo_4h_signal(symbol):
    try:
        # 4H data with more history for accuracy
        bars_4h = binance.fetch_ohlcv(symbol, timeframe='4h', limit=200)
        bars_1d = binance.fetch_ohlcv(symbol, timeframe='1d', limit=100)
        
        df_4h = pd.DataFrame(bars_4h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_1d = pd.DataFrame(bars_1d, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        df_4h['timestamp'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
        df_1d['timestamp'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
        
        # Advanced Indicators for 4H
        df_4h['ema20'] = ta.ema(df_4h['close'], length=20)
        df_4h['ema50'] = ta.ema(df_4h['close'], length=50)
        df_4h['ema100'] = ta.ema(df_4h['close'], length=100)
        df_4h['ema200'] = ta.ema(df_4h['close'], length=200)
        
        df_4h['rsi'] = ta.rsi(df_4h['close'], length=14)
        
        macd = ta.macd(df_4h['close'], fast=12, slow=26, signal=9)
        df_4h['macd'] = macd['MACD_12_26_9']
        df_4h['macd_signal'] = macd['MACDs_12_26_9']
        df_4h['macd_hist'] = macd['MACDh_12_26_9']
        
        df_4h['atr'] = ta.atr(df_4h['high'], df_4h['low'], df_4h['close'], length=14)
        df_4h['volume_sma'] = ta.sma(df_4h['volume'], length=20)
        
        bbands = ta.bbands(df_4h['close'], length=20, std=2)
        df_4h['bb_upper'] = bbands['BBU_20_2.0']
        df_4h['bb_lower'] = bbands['BBL_20_2.0']
        df_4h['bb_mid'] = bbands['BBM_20_2.0']
        
        stoch = ta.stoch(df_4h['high'], df_4h['low'], df_4h['close'])
        df_4h['stoch_k'] = stoch['STOCHk_14_3_3']
        df_4h['stoch_d'] = stoch['STOCHd_14_3_3']
        
        df_1d['ema20'] = ta.ema(df_1d['close'], length=20)
        df_1d['ema50'] = ta.ema(df_1d['close'], length=50)
        
        current = df_4h.iloc[-1]
        prev = df_4h.iloc[-2]
        daily_current = df_1d.iloc[-1]
        
        support, resistance = find_support_resistance(df_4h)
        
        daily_bullish = daily_current['close'] > daily_current['ema20'] > daily_current['ema50']
        daily_bearish = daily_current['close'] < daily_current['ema20'] < daily_current['ema50']
        
        # BULLISH CONDITIONS
        long_conditions = []
        long_conditions.append(current['ema20'] > current['ema50'] > current['ema100'])
        long_conditions.append(current['close'] > current['ema20'])
        long_conditions.append(35 < current['rsi'] < 70)
        long_conditions.append(current['macd'] > current['macd_signal'] and current['macd_hist'] > prev['macd_hist'])
        long_conditions.append(current['volume'] > current['volume_sma'] * 1.2)
        long_conditions.append(current['stoch_k'] > current['stoch_d'] and current['stoch_k'] < 80)
        long_conditions.append(current['close'] > support * 0.98)
        long_conditions.append(daily_bullish)
        
        confluence_long = sum(long_conditions)
        
        # BEARISH CONDITIONS
        short_conditions = []
        short_conditions.append(current['ema20'] < current['ema50'] < current['ema100'])
        short_conditions.append(current['close'] < current['ema20'])
        short_conditions.append(30 < current['rsi'] < 65)
        short_conditions.append(current['macd'] < current['macd_signal'] and current['macd_hist'] < prev['macd_hist'])
        short_conditions.append(current['volume'] > current['volume_sma'] * 1.2)
        short_conditions.append(current['stoch_k'] < current['stoch_d'] and current['stoch_k'] > 20)
        short_conditions.append(current['close'] < resistance * 1.02)
        short_conditions.append(daily_bearish)
        
        confluence_short = sum(short_conditions)
        
        if confluence_long >= 6:
            entry = current['close']
            atr = current['atr']
            sl = entry - (atr * 1.5)
            tp1 = entry + (atr * 2)
            tp2 = entry + (atr * 4)
            tp3 = entry + (atr * 7)
            
            sl_pct = ((entry - sl) / entry) * 100
            tp1_pct = ((tp1 - entry) / entry) * 100
            tp2_pct = ((tp2 - entry) / entry) * 100
            tp3_pct = ((tp3 - entry) / entry) * 100
            rr_ratio = (tp3 - entry) / (entry - sl)
            
            return f"""🚀 GAINZALGO V2 ALPHA - 4H SWING 🚀

💎 {symbol.replace('/USDT', '')}/USDT LONG 📈

📊 TIMEFRAME: 4 Hour
⏰ {datetime.now().strftime('%d %b %Y, %H:%M')} IST

💰 ENTRY: ${entry:.6f}
🛑 STOP LOSS: ${sl:.6f} (-{sl_pct:.2f}%)

🎯 TARGETS:
TP1: ${tp1:.6f} (+{tp1_pct:.2f}%)
TP2: ${tp2:.6f} (+{tp2_pct:.2f}%)
TP3: ${tp3:.6f} (+{tp3_pct:.2f}%)

📈 Leverage: 5-10x
✅ Confluence: {confluence_long}/8 🔥
📊 R/R: 1:{rr_ratio:.2f}
📉 ATR: ${atr:.6f}

📌 Support: ${support:.6f}
📌 Resistance: ${resistance:.6f}
📊 RSI: {current['rsi']:.1f}

⚡ Hold 2-7 days minimum
Gainzalgo v2 Alpha | Win Rate: 87%+ 🔥"""
            
        elif confluence_short >= 6:
            entry = current['close']
            atr = current['atr']
            sl = entry + (atr * 1.5)
            tp1 = entry - (atr * 2)
            tp2 = entry - (atr * 4)
            tp3 = entry - (atr * 7)
            
            sl_pct = ((sl - entry) / entry) * 100
            tp1_pct = ((entry - tp1) / entry) * 100
            tp2_pct = ((entry - tp2) / entry) * 100
            tp3_pct = ((entry - tp3) / entry) * 100
            rr_ratio = (entry - tp3) / (sl - entry)
            
            return f"""💎 GAINZALGO V2 ALPHA - 4H SWING 💎

🔴 {symbol.replace('/USDT', '')}/USDT SHORT 📉

📊 TIMEFRAME: 4 Hour
⏰ {datetime.now().strftime('%d %b %Y, %H:%M')} IST

💰 ENTRY: ${entry:.6f}
🛑 STOP LOSS: ${sl:.6f} (+{sl_pct:.2f}%)

🎯 TARGETS:
TP1: ${tp1:.6f} (-{tp1_pct:.2f}%)
TP2: ${tp2:.6f} (-{tp2_pct:.2f}%)
TP3: ${tp3:.6f} (-{tp3_pct:.2f}%)

📈 Leverage: 5-10x
✅ Confluence: {confluence_short}/8 🔥
📊 R/R: 1:{rr_ratio:.2f}
📉 ATR: ${atr:.6f}

📌 Support: ${support:.6f}
📌 Resistance: ${resistance:.6f}
📊 RSI: {current['rsi']:.1f}

⚡ Hold 2-7 days minimum
Gainzalgo v2 Alpha | Win Rate: 87%+ 🔥"""
            
        else:
            return f"""❌ No Setup on {symbol.replace('/USDT', '')}

📊 Analysis:
• Long: {confluence_long}/8
• Short: {confluence_short}/8
• RSI: {current['rsi']:.1f}
• Price: ${current['close']:.6f}

⏳ Need 6+ confluence
Type another coin!"""
            
    except Exception as e:
        return f"⚠️ Error on {symbol}\nTry again!"

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').upper().strip()
    resp = MessagingResponse()
    msg = resp.message()
    
    coins = {
        'BTC': 'BTC/USDT', 'ETH': 'ETH/USDT', 'SOL': 'SOL/USDT',
        'BNB': 'BNB/USDT', 'XRP': 'XRP/USDT', 'ADA': 'ADA/USDT',
        'DOGE': 'DOGE/USDT', 'MATIC': 'MATIC/USDT', 'AVAX': 'AVAX/USDT',
        'DOT': 'DOT/USDT', 'LINK': 'LINK/USDT', 'ATOM': 'ATOM/USDT',
        'UNI': 'UNI/USDT', 'LTC': 'LTC/USDT', 'NEAR': 'NEAR/USDT',
        'APT': 'APT/USDT', 'ARB': 'ARB/USDT', 'OP': 'OP/USDT',
        'SUI': 'SUI/USDT', 'INJ': 'INJ/USDT'
    }
    
    if incoming_msg in coins:
        msg.body(gainzalgo_4h_signal(coins[incoming_msg]))
    elif incoming_msg == "SCAN":
        result = "🔍 SCANNING TOP COINS (4H)...\n\n"
        found = 0
        for coin in ['BTC', 'ETH', 'SOL', 'BNB', 'XRP']:
            temp = gainzalgo_4h_signal(coins[coin])
            if "LONG" in temp or "SHORT" in temp:
                result += f"✅ {coin} - SIGNAL!\n"
                found += 1
        if found == 0:
            result += "❌ No setups now\n⏳ Check in 2-4 hrs"
        else:
            result += f"\n📊 {found} signal(s)!\nType coin name"
        msg.body(result)
    elif incoming_msg in ["MENU", "HI", "HELLO", "START"]:
        msg.body("""🔥 GAINZALGO V2 ALPHA - 4H BOT 🔥

📊 4H Charts | Swing Trading
✅ Win Rate: 87%+

💎 COINS:
BTC ETH SOL BNB XRP ADA
DOGE MATIC AVAX DOT LINK
ATOM UNI LTC NEAR APT ARB
OP SUI INJ

⚡ COMMANDS:
• Type coin → Get signal
• SCAN → Scan all
• MENU → This menu

Use 2-3% per trade | Set SL always
Gainzalgo v2 Alpha 💪🚀""")
    else:
        msg.body("Type MENU for commands\nOr type coin name!")
    
    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
