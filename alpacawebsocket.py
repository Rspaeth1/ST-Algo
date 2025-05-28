# -*- coding: utf-8 -*-
"""
Created on Wed Feb 12 15:55:22 2025

@author: Ryan
"""

import websocket
import asyncio
import json
import threading
import time
import os
from colorama import Fore, Style, init

import live_trading as lt
from websocket_constants import exchange_codes, trade_conditions_cts, trade_conditions_utdf, cqs_quote_conditions, uqdf_quote_conditions

#Alpaca API credentials
ALPACA_API_KEY = ''
ALPACA_SECRET_KEY = ''

ALPACA_PAPER_KEY = 'PK0DGC1RTGBVCT160OY9'
ALPACA_PAPER_SECRET = 'cOdhLakEXgS6N0FG2CQbSGoMCC32e45A95jfwmd0'
ALPACA_PAPER = True #Set to false for live trading

alpaca = None

#call from main to start:
def live_trade(params):
    #source: sip or iex
    source = 'iex'
    
    #create a connection to the websocket
    try:
        ws = create_ws_connection(source=source)
    except Exception as e:
        print(f"Error creating connection to websocket: {e}")
        
    #start the websocket connection in a new thread
    try:
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.start()
        time.sleep(5)
        print("Websocket connection established")
    except Exception as e:
        print(f"Error starting websocket in new thread: {e}")
        
    global alpaca
    alpaca = lt.alpaca_trader(params, ws)

# Function to handle incoming messages
def on_message(ws, message):
    # print("Message received: " + message)
    messages = json.loads(message)
    for msg in messages:
        process_message(msg)
    
#function to authenticate
def authenticate(ws):
    key = None
    secret = None
    
    if ALPACA_PAPER:
        key = ALPACA_PAPER_KEY
        secret = ALPACA_PAPER_SECRET
    else:
        key = ALPACA_API_KEY
        secret = ALPACA_SECRET_KEY

    if key == None:
        print("Failed to initialize keys.")
        return
    
    auth_data = {
        "action": "auth",
        "key": key,
        "secret": secret
    }
    ws.send(json.dumps(auth_data))
    
#establish connection
def create_ws_connection(source='sip'):
    base_url = f"wss://stream.data.alpaca.markets/v2/{source}"

    ws = websocket.WebSocketApp(
        base_url,
        on_message=on_message
    )
    
    #authenticate and subscribe when the connection is open
    ws.on_open = lambda ws: authenticate(ws)
    
    return ws

#function to subscribe to trades
def subscribe_to_trades(ws, symbols):
    sub_data = {
        "action": "subscribe",
        "trades": symbols
    }
    ws.send(json.dumps(sub_data))

# Function to subscribe to quotes
def subscribe_to_quotes(ws, symbols):
    sub_data = {
        "action": "subscribe",
        "quotes": symbols
    }
    ws.send(json.dumps(sub_data))

# Function to subscribe to bars
def subscribe_bars(ws, symbols):
    sub_data = {
        "action": "subscribe",
        "bars": symbols
    }
    ws.send(json.dumps(sub_data))


def unsubscribe_trade_updates(ws, symbols):
    sub_data = {
        "action": "unsubscribe",
        "trades": symbols
    }
    ws.send(json.dumps(sub_data))


def unsubscribe_quote_updates(ws, symbols):
    sub_data = {
        "action": "unsubscribe",
        "quotes": symbols
    }
    ws.send(json.dumps(sub_data))


def unsubscribe_bars(ws, symbols):
    sub_data = {
        "action": "unsubscribe",
        "bars": symbols
    }
    ws.send(json.dumps(sub_data))
    
def process_message(msg):
    msg_type = msg['T']
    
    if msg_type == 't':  # Trade
        print("Message type:", msg_type)
    
        symbol = msg['S']
        trade_id = msg['i']
        exchange_code = msg['x']
        exchange_desc = exchange_codes.get(exchange_code, "Unknown")
        trade_price = msg['p']
        trade_size = msg['s']
        trade_condition = msg['c']
        conditions_desc = [trade_conditions_cts.get(c, "Unknown") for c in trade_condition]
        timestamp = msg['t']
        tape = msg['z']
        if exchange_code in ["A", "N", "P"]:
            plan = "CTA"
            trade_conditions_desc = [trade_conditions_cts.get(cond, "Unknown") for cond in trade_condition]
        elif exchange_code in ["B", "Q", "S", "T", "X"]:
            plan = "UTP"
            trade_conditions_desc = [trade_conditions_utdf.get(cond, "Unknown") for cond in trade_condition]
        elif exchange_code in ["C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "O", "R", "U", "V", "W", "Y"]:
            plan = "Unknown"
            trade_conditions_desc = [trade_conditions_cts.get(cond, "Unknown") for cond in trade_condition]
        else:
            plan = "Unknown"
            trade_conditions_desc = [trade_conditions_cts.get(cond, "Unknown") for cond in trade_condition]
    
        
        print("Trade:")
        print(f"Symbol: {symbol}")
        print(f"Trade ID: {trade_id}")
        print(f"Exchange Code: {exchange_code} ({exchange_desc})")
        print(f"Trade Price: {trade_price}")
        print(f"Trade Size: {trade_size}")
        print(f"Trade Condition: {trade_condition} ({', '.join(conditions_desc)})")
        print(f"Timestamp: {timestamp}")
        print(f"Tape: {tape}")
        print("-------")
    
    elif msg_type == 'q':  # Quote
        symbol = msg['S']
        ask_exchange_code = msg['ax']
        ask_exchange_desc = exchange_codes.get(ask_exchange_code, "Unknown")
        ask_price = msg['ap']
        ask_size = msg['as']
        bid_exchange_code = msg['bx']
        bid_exchange_desc = exchange_codes.get(bid_exchange_code, "Unknown")
        bid_price = msg['bp']
        bid_size = msg['bs']
        quote_condition = msg['c']
        timestamp = msg['t']
        tape = msg['z']
    
        conditions = msg.get("c", [])
        decoded_conditions = []
        for condition_code in conditions:
            if condition_code in cqs_quote_conditions:
                decoded_conditions.append(cqs_quote_conditions[condition_code])
            elif condition_code in uqdf_quote_conditions:
                decoded_conditions.append(uqdf_quote_conditions[condition_code])
            else:
                decoded_conditions.append(f"Unknown Condition: {condition_code}")
    
    
    
        print("Quote:")
        print(f"Symbol: {symbol}")
        print(f"Ask Exchange Code: {ask_exchange_code} ({ask_exchange_desc})")
        print(f"Ask Price: {ask_price}")
        print(f"Ask Size: {ask_size}")
        print(f"Bid Exchange Code: {bid_exchange_code} ({bid_exchange_desc})")
        print(f"Bid Price: {bid_price}")
        print(f"Bid Size: {bid_size}")
        print(f"Quote Condition: {quote_condition}")
        print(f"Quote Condition: {decoded_conditions}")
        print(f"Timestamp: {timestamp}")
        print(f"Tape: {tape}")
        print("-------")
    
    elif msg_type in ['b', 'd', 'u']:  # Bar
        symbol = msg['S']
        open_price = msg['o']
        high_price = msg['h']
        low_price = msg['l']
        close_price = msg['c']
        volume = msg['v']
        timestamp = msg['t']
        
        """
        print("Bar:")
        print(f"Symbol: {symbol}")
        print(f"Open Price: {open_price}")
        print(f"High Price: {high_price}")
        print(f"Low Price: {low_price}")
        print(f"Close Price: {close_price}")
        print(f"Volume: {volume}")
        print(f"Timestamp: {timestamp}")
        print("-------")"""
        
        #send bar to alpaca trader
        #print("sending bar")
        bar = {'symbol': symbol, 'timestamp': timestamp, 'open': open_price, 'high': high_price, 'low': low_price, 'close': close_price, 'volume': volume}
        try:
            
            #just in case this tries to get called before it's finished...
            while alpaca.receiving_bar:
                    time.sleep(1)
                    print("Waiting...")
                    
            alpaca.receiving_bar = True
            alpaca.bar_callback(bar=bar)
            alpaca.receiving_bar = False
        except Exception as e:
            print(f"Error sending bar for {bar['symbol']}: {e}")
    
    elif msg_type == 'error':  # Error
        code = msg['code']
        error_msg = msg['msg']
        print(Fore.RED + f"Error Code: {code}")
        print(f"Error Message: {error_msg}")
        print(Style.RESET_ALL + "-------")
    
    elif msg['T'] == 'success':
        code = msg['code']
        error_msg = msg['msg']
        print(Fore.GREEN + f"Error Code: {code}")
        print(f"Error Message: {error_msg}")
        print(Style.RESET_ALL + "-------")
    
    
    elif msg_type == "subscription":
        print("Subscription:")
        for item, symbols in msg.items():
            if item != 'T' and symbols:
                print(f"{item}: {', '.join(symbols)}")
        print("-------")
    
    else:
        print(f"Unknown message type: {msg_type}")

#testing
if __name__ == "__main__":
    #list to subscribe to
    symbols = ['AAPL', 'NVDA', 'MSFT']
    
    #source: sip or iex
    source = 'iex'
    
    #create a connection to the websocket
    try:
        ws = create_ws_connection(source=source)
    except Exception as e:
        print(f"Error creating connection to websocket: {e}")
        
    #start the websocket connection in a new thread
    try:
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.start()
        time.sleep(5)
    except Exception as e:
        print(f"Error starting websocket in new thread: {e}")
        
    #let it run for a while to receive updates
    
    #subscribe to trades
    #print("Subscribing to trades")
    #subscribe_to_trades(ws, symbols)
    #unsubscribe_trade_updates(ws, symbols)
    
    #subscribe to quotes
    print('Subscribing to quotes')
    subscribe_to_quotes(ws, symbols)
    #unsubscribe_quote_updates(ws, symbols)
    
    #subscribe to bars
    #print('Subscribing to bars')
    #subscribe_to_bars(ws, symbols)
    #time.sleep(5)
    #unsubscribe_bars(ws, symbols)
    