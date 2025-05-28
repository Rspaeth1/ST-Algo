# -*- coding: utf-8 -*-
"""
Created on Fri Jan 24 17:34:09 2025

@author: Ryan
"""

import pandas as pd
import asyncio

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.common.exceptions import APIError
from alpaca.data.live import StockDataStream
from alpaca.data.timeframe import TimeFrame
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest

from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD
from ta.volatility import BollingerBands

from datetime import datetime, timedelta

import stocktwits as st
import yfin as yf
import determine_weights
import main

#Alpaca API credentials
ALPACA_API_KEY = 'AK3GLQI340K3XYAO7PFZ'
ALPACA_SECRET_KEY = 'WXfeMfJWcN1Sw8sgS4nQcwG7IyLM96ntI5zNCOe2'

ALPACA_PAPER_KEY = 'PK0DGC1RTGBVCT160OY9'
ALPACA_PAPER_SECRET = 'cOdhLakEXgS6N0FG2CQbSGoMCC32e45A95jfwmd0'
ALPACA_PAPER = True #Set to false for live trading
        
class alpaca_trader:
    
    def __init__(self, params):
        self.paper = ALPACA_PAPER
        self.stocks = {}
        self.params = params
        
        self.key = None
        self.secret = None

        self.first = True
        
        if self.paper:
            self.key = ALPACA_PAPER_KEY
            self.secret = ALPACA_PAPER_SECRET
        else:
            self.key = ALPACA_API_KEY
            self.secret = ALPACA_SECRET_KEY

        if self.key == None:
            print("Failed to initialize keys.")
            return
        
        #init
        self.historical_client = None
        self.trading_client = None
        self.account = None
        self.stream = None
        
        #initialize clients
        try:
            self.historical_client = StockHistoricalDataClient(self.key, self.secret)
            self.trading_client = TradingClient(api_key=self.key, secret_key=self.secret, paper=self.paper)
            self.account = self.trading_client.get_account()
        except APIError as e:
            print(f"API error during initialization: {e}")
            return
        
        # Initialize the stream
        self.create_stream()
         
        #initialize order log and order trackers
        self.orderlog = []
        self.orders = []
        self.fh = None
        self.log(start=True)
        
        #initialize for run
        self.market_open = False
        self.check_time()
        self.stock_check_hours = 0
        self.stream_task = None
        
        # Initialize the event loop
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
    
        # Schedule the trade coroutine
        self.loop.create_task(self.trade())
        
    def create_stream(self):
        if self.stream is None:
            try:
                self.stream = StockDataStream(self.key, self.secret)
                print("Stream initialized successfully.")
            except Exception as e:
                print(f"Error initializing stream: {e}")
                return
        
    def log(self, start=False, message=None):
        #init log and log orders/messages
        
        if start:
            try:
                self.fh = open(f"LiveTradingLogs/{datetime.now()}.txt", 'x')
            except Exception as e:
                print(f"Error opening trading log file: {e}")
            return
        
        if message:
            try:
                self.fh.write(message)
            except Exception as e:
                print(f"Error trying to write to trading log: {e}")
                
    def check_time(self):
        try:
            clock = self.trading_client.get_clock()
            if clock.is_open:
                self.market_open = True
            else:
                self.market_open = False
        except Exception as e:
            print(f"Error checking if market is open: {e}")
        
    def print_account_details(self):
        mode = "Paper"
        if not self.paper: mode = "Live"
        print(f"\nMode: {mode}")
        print("Account ID:", self.account.id)
        print("Cash Balance:", self.account.cash)
        print("Portfolio Value:", self.account.portfolio_value)
                
    def buy(self, size, ticker):
        try:
            market_order_data = MarketOrderRequest(
                symbol=ticker,
                qty=size,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY
            )
            
            self.orders.append(self.trading_client.submit_order(market_order_data))
            self.stocks[ticker].set_buy(position_size=size)
            order = f"Bought {size:.2f} of {ticker} at {self.stocks[ticker].share_price:.2f}"
            print(order)
            self.log(message=order)
            
        except Exception as e:
            print(f"Error trying to buy {ticker}: {e}")
        
    def sell(self, size, ticker):
        try:
            market_order_data = MarketOrderRequest(
                symbol=ticker,
                qty=size,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY
            )
            
            self.orders.append(self.trading_client.submit_order(market_order_data))
            self.stocks[ticker].reset_order_data() #FOR NOW JUST USING RESET, WHEN ADD SHORT CAPABILITIES WILL NEED TO CHANGE HOW ORDERS ARE TRACKED WITHIN STOCKS
            order = f"Sold {size:.2f} of {ticker} at {self.stocks[ticker].share_price:.2f}"
            print(order)
            self.log(message=order)
            
        except Exception as e:
            print(f"Error trying to sell {ticker}: {e}")
            
    def check_position(self, ticker):
        positions = self.trading_client.get_all_positions()
        for position in positions:
            if position.symbol == ticker:
                return True
        return False
    
    
    
    ### Main Loop ###
    
    async def trade(self):
        try:
            if not self.market_open:
                print("Market is closed. Stream will not initialize properly.")
                
            await self.subscribe_positions()  # Try to get any open positions
            
            # Run stream and update() at the same time
            await asyncio.gather(
                self.run_stream(),  # Keeps the data stream running
                self.update()  # Runs in parallel, updates every hour
            )

        except Exception as e:
            print(f"Trade Error: {e}")     
             
    async def run_stream(self):
        if self.stream is not None:
             await self.stream._run_forever()
        else:
            print("Stream is not initialized; cannot run.")
                
    async def update(self):
       # Periodically update stocks
       
       while True:  
           # Subscribe to live data for tickers
           try:
               #check market hours
               self.check_time()
               
               #create stream if needed
               self.create_stream()
            
               if self.stock_check_hours >= 4: #and self.market_open: #update ticker list every 4 hours
                   self.stock_check_hours = 0
                   
                   #cancel all tasks
                   #tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
                   #for task in tasks:
                   #    task.cancel()
                   #    
                   #break
                   await self.get_new_stocks()
                   
               else:
                   self.stock_check_hours += 1
           except Exception as e:
               print(f"Couldn't get new stocks: {e}")
                
           print(f"\nCurrent stocks: {list(self.stocks.keys())}")
           self.print_account_details()
            
           time_until_next_hour = 60*(60-datetime.now().minute)
           await asyncio.sleep(1)  # Update every hour
       await self.trade()
        
    async def subscribe_positions(self):
        try:
            #try to get any positions at the start
            
            positions = self.trading_client.get_all_positions()
            for position in positions:
                ticker = position.symbol
                self.tickers.append(ticker)
                self.stocks[ticker] = stock_data(ticker, self.params['exitbars'], self.historical_client)
                self.stocks[ticker].position_size = float(position.quantity)
                self.stocks[ticker].buy_price = float(position.avg_entry_price)
                
                # MAY WANT TO REVISIT THIS. CURRENTLY, COULD LEAD TO ISSUES IF STREAM LOSES CONNECTION, WHEN BACK, ANY OPEN POSITIONS ARE IMMEDIATELY IN SELL ZONE
                self.stocks[ticker].bars_since_execution = self.params['exitbars']
                
                self.stream.subscribe_bars(self.bar_callback, ticker)
                print(f"Subscribed to open position {ticker}")
            await self.get_new_stocks()
        except Exception as e:
            print(f"Failed to subscribe to open position {ticker}: {e}")
    
    async def get_new_stocks(self, tickerlist=[]):
        #get trending tickers
        tickers = st.get_trending_stocks()
        
        if not self.first:
            tickers = ['FSLR', 'TEM', 'CELH', 'BLBX', 'FSLR', 'OXLO']
        self.first = False
        
        #check for banned tickers
        tickers = [ticker for ticker in tickers if ticker not in main.banned_tickers]
        
        #remove any duplicates
        tickers = list(set(tickers))
        
        #check if any already open in our portfolio and get rid of others that aren't
        for stock in self.stocks.values():
            ticker = stock.ticker
            try:
                position = self.check_position(ticker)
                if not position and self.stocks[ticker].timer <= 0 and not ticker in tickers:
                    try:
                        await self.stream.unsubscribe_bars(ticker)
                        self.stocks.pop(ticker)
                        print(f"Unsubscribed from {ticker}")
                    except Exception as e:
                        print(f"Unable to unsubscribe from ticker {ticker}: {e}")
                if ticker in tickers:
                    self.stocks[ticker].timer += 4 #add an extra 4 hours to the timer if it's still on the trending list
            except Exception as e:
                print(f"Error checking ticker position for {ticker}: {e}")

        for ticker in tickers:
            try:
                print(ticker)
                if ticker not in self.stocks:
                    if not yf.check_equity(ticker): continue
                    self.stocks[ticker] = stock_data(ticker, self.params['exitbars'], self.historical_client)
                    await self.stream.subscribe_bars(self.bar_callback, ticker)
                    print(f"Subscribed to {ticker}")
            except Exception as e:
                print(f"Error subscribing to ticker {ticker}: {e}")
     
        
     
        
    #update stock data and aggregate minute bars into hourly
    def update_stock_data(self, bar, stock):
        #update stock data based on new bar
        new_row = {
          "symbol": bar.symbol,
          "timestamp": pd.to_datetime(bar.timestamp),
          "open": bar.open,
          "high": bar.high,
          "low": bar.low,
          "close": bar.close,
          "volume": bar.volume,
          "vwap": bar.vwap,
          "trade_count": bar.trade_count,
        }
        new_row = pd.DataFrame.from_dict([new_row])
        stock.add_minute_bar(new_row)
        
        if stock.minute_bar_count >= 60:
            # Convert timestamp column to datetime format and set as index
            stock.minute_bars["timestamp"] = pd.to_datetime(stock.minute_bars["timestamp"])
            stock.minute_bars.set_index("timestamp", inplace=True)
        
            # Calculate typical price
            stock.minute_bars["typical_price"] = (
                stock.minute_bars["close"] + stock.minute_bars["high"] + stock.minute_bars["low"]
            ) / 3
            
            # Aggregate minute bars into hourly bars using .agg()
            hourly_bar = stock.minute_bars.resample("h").agg({
                "open": "first",         # First open price of the hour
                "high": "max",           # Maximum high price of the hour
                "low": "min",            # Minimum low price of the hour
                "close": "last",         # Last close price of the hour
                "volume": "sum",         # Total volume of the hour
                "trade_count": "sum",    # Total trades of the hour
                "typical_price": "mean"  # Average typical price
            })
     
            # Calculate VWAP
            hourly_bar["vwap"] = (stock.minute_bars["typical_price"] * stock.minute_bars["volume"]).resample("h").sum() / stock.minute_bars["volume"].resample("h").sum()
     
            # Reset index so timestamp is a column again
            hourly_bar.reset_index(inplace=True)
            
            hourly_bar = pd.DataFrame().from_dict(hourly_bar)
            stock.update_data(hourly_bar)
            
            #tick stock timer
            stock.timer -= 1
        
        
        
    ### Callbacks ###
    async def stock_data_stream_handler(self, data):
        #print(data)
        #stream.subscribe_quotes(self.stock_data_stream_handler, 'NVDA')
        pass
        
    # callback for live trades
    async def trade_callback(self, trade):
        pass
    
    # callback for live bars
    async def bar_callback(self, bar):
        if self.market_open: #ensure market is open to place trades and analyze bars
            print(f"Bar received for {bar.symbol} at {datetime.now()}")
            ticker = bar.symbol
            stock = self.stocks[ticker]
    
            #update_stock_data based on bar
            self.update_stock_data(bar, self.stocks[bar.symbol])
            
            # get weights based on position: sell / buy weights
            if self.check_position(ticker):
                self.get_weight(stock, 'sell')
            elif stock.minute_bar_count >= 60:
                self.get_weight(stock, 'buy')
            
            #check if we should place orders now
            if self.check_callbacks():
                self.place_buys()
                self.place_sells()
                
            #check sells at every bar
            #ADD FUNCTIONALITY TO SELL IF HIT PRICE TARGET AT MINUTE BAR, SAY 50% ROI, OTHERWISE TRADE AT HOUR
    
    
    
    ### Trade Logic ###
    def place_buys(self):
        #check which trades to place
        
        #CHECK TO SEE IF CURRENT ORDER PENDING, ELSE RETURN
        
        #check stock with max weight to look at an entry
        buy_weights = {}
        for stock in self.stocks.values():
            buy_weights[stock.ticker] = stock.buy_weight
            
        max_weight = max(buy_weights, key = lambda x: buy_weights[x])
        buy_weight = self.stocks[max_weight].buy_weight
        max_stock = self.stocks[max_weight]
        
        if not self.check_position(ticker=max_weight):
            if buy_weight != 0:
                stake = self.setstake(max_stock, buy_weight/100)
                if buy_weight > 0:
                    self.buy(size=stake, ticker=max_weight)
                elif self.params['allow_short']:
                    #short logic
                    pass
        
    def place_sells(self):
        #exit strategy for existing positions
        for stock in self.stocks.values():
            if self.check_position(ticker=stock.ticker): # AND NOT CURRENT ORDER PENDING
                exitbar_constraint = stock.bars_since_execution >= self.params['exitbars'] #simple sell after # of bars
                long_profit_constraint = stock.buy_price <= stock.share_price
                short_profit_constraint = stock.buy_price >= stock.share_price # only sell/cover if profit/breakeven
                
                boll_long_constraint = stock.share_price >= stock.boll_upper
                boll_short_constraint = stock.share_price <= stock.boll_lower
                
                simple_enabled = True # for testing, enable simple strategy
                simple_long_strategy = exitbar_constraint and long_profit_constraint and simple_enabled
                simple_short_strategy = exitbar_constraint and short_profit_constraint and simple_enabled
                
                indicator_strategy = True # for testing, enable indicator strategy
                boll_long_strategy = boll_long_constraint and long_profit_constraint and indicator_strategy
                boll_short_strategy = boll_short_constraint and short_profit_constraint and indicator_strategy
                
                weight_strategy = True # for testing, enable weight based strategy
                weight_sell_signal = False
                weight_cover_signal = False
                if stock.sell_weight < self.params['exit_threshold'] and not stock.is_shorted and weight_strategy and long_profit_constraint:
                    weight_sell_signal = True
                elif stock.sell_weight > self.params['confidence_threshold'] and stock.is_shorted and weight_strategy and short_profit_constraint:
                    weight_cover_signal = True
                
                #sell (cover)
                if self.params['stops']:
                    if not stock.is_shorted:
                        if stock.share_price <= stock.buy_price*(1-self.params['long_loss']):
                            self.sell(size=stock.position_size, ticker=stock.ticker)
                    else:
                        if stock.share_price >= stock.buy_price*(1+self.params['short_loss']):
                            self.buy(size=stock.position_size, ticker=stock.ticker)
                if not stock.is_shorted:
                    if boll_long_strategy or weight_sell_signal or simple_long_strategy:
                        self.sell(size=stock.position_size, ticker=stock.ticker)
                else:
                    if boll_short_strategy or weight_cover_signal or simple_short_strategy:
                        self.buy(size=stock.position_size, ticker=stock.ticker)
        
    def set_stake(self, stock, confidence):
        confidence = determine_weights.get_confidence(confidence, self.params['confidence_threshold'], self.params['exit_threshold'])
        size = confidence*self.account.cash/stock.share_price
        return size if size <= self.account.cash else self.account.cash/stock.share_price - 1
        
    def check_callbacks(self):
        #check if all bar callbacks have been received
        for stock in self.stocks.values():
            if not stock.updated:
                return False
        
        #if yes, reset check variable and give ok (return True) to start placing trades
        for stock in self.stocks.values():
            stock.updated = False
            
        return True
        
    def get_weight(self, stock, weight_type):
        params_dict = {
            #set variables
            'ticker': stock.ticker,
            'exitbars': stock.period,
            'share_price': stock.share_price,
            'current_rsi': stock.rsi,
            'current_vwap': stock.vwap,
            'mktcap': stock.mktcap,
            'current_macd': stock.macd,
            'current_signal': stock.signal,
            'last_macd': stock.last_macd,
            'last_signal': stock.last_signal,
            'stoch_k': stock.stoch_k,
            'stoch_d': stock.stoch_d,
            'current_pricentile': stock.pricentile,
            'last_per_close': stock.last_per_close,
            'last_per_mktcap': stock.last_per_mktcap,
            'last_per_rsi': stock.last_per_rsi,
            'boll_upper': stock.boll_upper,
            'boll_lower': stock.boll_lower,
            'confidence_threshold': self.params['confidence_threshold'],
            
            #weights
            'pricentile1': self.params['pricentile1'],
            'rsi1': self.params['rsi1'],
            'rsi2': self.params['rsi2'],
            'rsi3': self.params['rsi3'],
            'vwap1': self.params['vwap1'],
            'vwap2': self.params['vwap2'],
            'stoch1': self.params['stoch1'],
            'stoch2': self.params['stoch2'],
            'swing1': self.params['swing1'],
            'swing2': self.params['swing2'],
            'macd1': self.params['macd1'],
            'macd2': self.params['macd2'],
            'mktcap1': self.params['mktcap1'],
            'mktcap2': self.params['mktcap2'],
            'mktcap3': self.params['mktcap3'],
            'mktcap4': self.params['mktcap4'],    
        }
        
        if weight_type == 'sell':
            try:
                weight = determine_weights.get_sell_weight(params_dict)
                stock.sell_weight = weight
            except Exception as e:
                print(f"Error getting sell weight for {stock.ticker}: {e}")
        elif weight_type == 'buy':
            try:
                weight = determine_weights.get_buy_weight(params_dict)
                stock.buy_weight = weight
            except Exception as e:
                print(f"Error getting buy weight for {stock.ticker}: {e}")
                stock.buy_weight = 0
                
            try:
                #check if it's earnings date
                today = datetime.now()
                converted_date1 = today - timedelta(days=1)
                converted_date2 = today + timedelta(days=1)
                formatted_date = today.strftime('&Y-%m-%d')
                formatted_date1 = converted_date1.strftime('%Y-%m-%d')
                formatted_date2 = converted_date2.strftime('%Y-%m-%d')
                formatted_dates = [formatted_date, formatted_date1, formatted_date2]
                for date in formatted_dates:
                    if date in stock.earnings:
                        stock.buy_weight = 0
            except Exception as e:
                print(f"Error checking earnings date for ticker {stock.ticker}: {e}")
    
    
    
### Stock Class ###
    
class stock_data:
    def __init__(self, ticker, period, historical_client, pandasdata=None):
        self.ticker = ticker
        self.pandasdata = pandasdata
        self.historical_client = historical_client
        self.period = max(period, 14)
        
                
        #variables related to buying/selling
        self.buy_weight = 0
        self.sell_weight = 0
        self.minute_bar_count = 0
        self.minute_bars = None
        self.minute_bars_fill = True
        self.updated = False
        self.timer = period
        
        #set data if none
        if pandasdata == None:
            self.get_pandas_data()
        
        #get indicators
        self.rsi = None
        self.macd = None
        self.signal = None
        self.last_macd = None
        self.last_signal = None
        self.vwap = None
        self.stoch_k = None
        self.stoch_d = None
        self.boll_upper = None
        self.boll_lower = None
        self.calculate_indicators()
        
        #get stock data
        self.share_price = None
        self.mktcap = None
        self.pricentile = None
        self.week_52_high = None
        self.week_52_low = None
        self.last_per_close = None
        self.last_per_mktcap = None
        self.last_per_rsi = None
        self.shares_outstanding = None
        try:
            self.shares_outstanding = yf.get_outstanding_shares(self.ticker)
        except:
            print("Couldn't get shares outstanding for {self.ticker}")
            return
        self.earnings = yf.get_earnings(self.ticker)
        self.get_stock_data()
        
        self.is_shorted = False
        self.buy_price = None
        self.position_size = None
        self.bars_since_execution = None
        
    def set_buy(self, position_size):
        self.buy_price = self.share_price
        self.position_size = position_size
        self.bars_since_execution = 0
        
    def set_short(self, buy_price, position_size):
        self.buy_price = buy_price
        self.position_size = position_size
        self.bars_since_execution = 0
        self.is_shorted = True
        
    def reset_order_data(self):
        self.buy_price = None
        self.position_size = None
        self.bars_since_execution = None
        
    def update_data(self, new_row):
        #call this when bar callback is triggered, add datalines to update indicators
        
        try:
            #adjust pandas data
            self.pandasdata.drop(self.pandasdata.index[0])
            self.pandasdata = pd.concat([self.pandasdata, new_row])
            
            #recalculate indicators and data points
            self.calculate_indicators()
            self.get_stock_data()
            
            #reset minute bars
            self.minute_bar_count = 0
            self.minute_bars = None
            self.minute_bars_fill = True
            
            #this may need to change when adding order lists for shorts/more buys
            if self.buy_price != None:
                self.bars_since_execution += 1  #increment our counter for bars since we just updated them
                
            #set updated to true
            self.updated = True
            
        except Exception as e:
            print(f"Error when updating data for {self.ticker}: {e}")
            
    def add_minute_bar(self, new_row):
        #add a minute bar to the pandasdata storage to aggregate into hourly
        try:
            if self.minute_bars_fill:
                self.minute_bars = new_row
            else:
                self.minute_bars = pd.concat([self.minute_bars, new_row])
            
            #adjust variables
            self.minute_bar_count += 1
            self.share_price = self.minute_bars['close'].iloc[-1]
            self.mktcap = self.shares_outstanding * self.share_price / 1000000 #in millions
            self.week_52_high = max(self.pandasdata['high'].max(), self.minute_bars['high'].max())
            self.week_52_low = min(self.pandasdata['low'].min(), self.minute_bars['low'].min())
            self.pricentile = (self.share_price - self.week_52_low) / (self.week_52_high - self.week_52_low)
            
        except Exception as e:
            print(f"Error when updating minute bars for {self.ticker}: {e}")
    
    def get_pandas_data(self):
        #on init, get data from alpaca historically ... note to self probably could have just used this from the beginning instead of yfin to save SO much time .....
       
        try:
            #get historical hour data until now
            self.pandasdata = self.historical_client.get_stock_bars(StockBarsRequest(
                symbol_or_symbols=self.ticker,
                timeframe=TimeFrame.Hour,
                start=datetime.now()-timedelta(weeks=52),
                end=datetime.now(),
                adjustment='raw'
            )).df
            
            #get remainder of hour in minute bars
            minutes = datetime.now().minute
            self.minute_bar_count = minutes            
            if self.minute_bar_count != 0:
                self.minute_bar_fill = False
            self.minute_bars = self.historical_client.get_stock_bars(StockBarsRequest(
                symbol_or_symbols=self.ticker,
                timeframe=TimeFrame.Minute,
                start=datetime.now()-timedelta(minutes=minutes),
                end=datetime.now(),
                adjustment='raw'
            )).df

            
        except Exception as e:
            print(f"Error fetching historical data: {e}")
        
    def calculate_indicators(self, pandasdata=None):
        #take data and calculate indicators using ta library and alpaca data feed
        
        if pandasdata != None:
            self.pandasdata = pandasdata
        
        recent_data = self.pandasdata.tail(50)
        recent_prices = recent_data["close"]
        
        #rsi
        rsi = RSIIndicator(close=recent_prices, window=self.period)
        self.rsi = rsi.rsi().iloc[-1]
        self.last_per_rsi = rsi.rsi().iloc[-self.period]
        
        #vwap
        self.vwap = recent_data['vwap'].iloc[-1]
        
        #macd
        macd = MACD(close=recent_prices)
        self.macd = macd.macd().iloc[-1]
        self.last_macd = macd.macd().iloc[-2]
        self.signal = macd.macd_signal().iloc[-1]
        self.last_signal = macd.macd_signal().iloc[-2]
        
        #boll
        boll = BollingerBands(close=recent_prices, window=self.period, window_dev=2)
        self.boll_upper = boll.bollinger_hband().iloc[-1]
        self.boll_lower = boll.bollinger_lband().iloc[-1]
        
        #stoch
        stoch = StochasticOscillator(recent_data['high'], recent_data['low'], recent_prices, window=self.period, smooth_window=3)
        self.stoch_k = stoch.stoch().iloc[-1]
        self.stoch_d = stoch.stoch_signal().iloc[-1]
        
    def get_stock_data(self):
        #get stock data for trading information like current sp, mktcap, etc
        
        self.share_price = self.pandasdata['close'].iloc[-1]
        self.mktcap = self.shares_outstanding * self.share_price / 1000000 #in millions
        self.week_52_high = self.pandasdata['high'].max()
        self.week_52_low = self.pandasdata['low'].min()
        self.pricentile = (self.share_price - self.week_52_low) / (self.week_52_high - self.week_52_low)
        self.last_per_close = self.pandasdata['close'].iloc[-self.period]
        self.last_per_mktcap = self.shares_outstanding * self.pandasdata['close'].iloc[-self.period] / 1000000 #in millions
        
    def print_indicators(self):
        print(f"\nIndicators for {self.ticker}")
        print(self.rsi)
        print(self.macd)
        print(self.signal)
        print(self.last_macd)
        print(self.last_signal)
        print(self.vwap)
        print(self.stoch_k)
        print(self.stoch_d)
        print(self.boll_upper)
        print(self.boll_lower)
        