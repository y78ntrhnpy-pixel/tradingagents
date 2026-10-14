
import os
import requests
import yfinance as yf
import pandas as pd

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": message},
        timeout=15
    )
    response.raise_for_status()

def analyse_gold():
    df = yf.Ticker("GC=F").history(
        period="5d", interval="15m"
    )

    if df.empty or len(df) < 60:
        print("Not enough price data.")
        return

    df = df.dropna().copy()
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    df["ema9"] = close.ewm(span=9, adjust=False).mean()
    df["ema21"] = close.ewm(span=21, adjust=False).mean()

    change = close.diff()
    gain = change.clip(lower=0).ewm(
        alpha=1/14, min_periods=14, adjust=False
    ).mean()
    loss = (-change.clip(upper=0)).ewm(
        alpha=1/14, min_periods=14, adjust=False
    ).mean()

    rs = gain / loss.replace(0, float("nan"))
    df["rsi"] = 100 - (100 / (1 + rs))

    previous_close = close.shift(1)
    true_range = pd.concat([
        high - low,
        (high - previous_close).abs(),
        (low - previous_close).abs()
    ], axis=1).max(axis=1)

    df["atr"] = true_range.rolling(14).mean()

    # Use completed candles only
    df = df.iloc[:-1]
    previous = df.iloc[-2]
    current = df.iloc[-1]

    crossed_up = (
        previous["ema9"] <= previous["ema21"]
        and current["ema9"] > current["ema21"]
    )
    crossed_down = (
        previous["ema9"] >= previous["ema21"]
        and current["ema9"] < current["ema21"]
    )

    price = float(current["Close"])
    rsi = float(current["rsi"])
    atr = float(current["atr"])

    if pd.isna(rsi) or pd.isna(atr) or atr <= 0:
        return

    direction = None

    if crossed_up and 50 < rsi < 68:
        direction = "BUY"
        stop = price - 1.5 * atr
        target = price + 2 * atr

    elif crossed_down and 32 < rsi < 50:
        direction = "SELL"
        stop = price + 1.5 * atr
        target = price - 2 * atr

    if direction:
        message = (
            f"XAUUSD WATCHLIST SIGNAL — {direction}\n"
            f"Instrument: GC=F gold futures proxy\n"
            f"15-minute candle close: {price:.2f}\n"
            f"RSI: {rsi:.1f}\n"
            f"Illustrative stop: {stop:.2f}\n"
            f"Illustrative target: {target:.2f}\n"
            f"Risk/reward: approximately 1:1.33\n"
            f"Confirm prices on your Vantage XAUUSD chart.\n"
            f"Signal only — no trade has been placed."
        )
        send_message(message)
        print(message)
    else:
        print("No qualifying setup.")

if __name__ == "__main__":
    analyse_gold()
