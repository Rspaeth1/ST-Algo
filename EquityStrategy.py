# -*- coding: utf-8 -*-
"""
Created on Sat Feb  1 11:35:32 2025

@author: Ryan
"""

import backtrader as bt
import numpy as np

import yfin as yf
import determine_weights, backtest
from custom_components import VWAP
from datetime import datetime, timedelta

class strategy(bt.Strategy):
    params = (
        ('exitbars', 24),
        ('allow_short', False),
        ('logging', False),
        ('run_strat', True),
        ('training', False),
        ('simulate', False),
        ('wait_period', 3),
        ('tradeable_dates', {}),
        ('short_loss', .05),
        ('long_loss', .25),
        ('stops', True),
        ('startcash', 10000),
        ('rsi1', 30),
        ('rsi2', 10),
        ('rsi3', 30),
        ('macd1', 20),
        ('macd2', 20),
        ('vwap1', 15),
        ('vwap2', 15),
        ('stoch1', 15),
        ('stoch2', 15),
        ('mktcap1', 1.15),
        ('mktcap2', 1.35),
        ('mktcap3', 2),
        ('mktcap4', 3),
        ('pricentile1', 5),
        ('swing1', 10),
        ('swing2', 10),
        ('confidence_threshold', 50),
        ('exit_threshold', 50),
    )
    
    def __init__(self):     
        try:
            self.params.exitbars = int(self.params.exitbars)
            self.period = max(self.params.exitbars, 14)
            
            #keep track of pending orders and buy price/commission
            self.order = None
            self.buyprice = {data: None for data in self.datas}
            self.buycomm = {data: None for data in self.datas}
            self.buytotal = {data: None for data in self.datas}
            self.bar_executed = {data: None for data in self.datas}
            self.weight_bought = {data: None for data in self.datas}
            
            #get earnings data
            self.earnings = {data: yf.get_earnings(data._name) for data in self.datas}
            
            # for wrap up
            self.last_close = {data: None for data in self.datas}
            
            #track short sells
            self.shorts = {data: False for data in self.datas}
            
            #track orders and trades
            self.orderlog = []
            self.num_trades = 0
            self.numtrades = {}
            self.tradepnl = []
            self.industry_analysis = {}
            self.sector_analysis = {}
            
            #create indicators for each data
            try:
                self.rsi = {data: bt.indicators.RSI(data.close, period=self.period) for data in self.datas}
                self.macd = {data: bt.indicators.MACD(data.close) for data in self.datas}
                self.macd_signal = {data: self.macd[data].signal for data in self.datas}
                self.vwap = {data: VWAP(data, period=self.period) for data in self.datas}
                self.stochastic = {data: bt.indicators.Stochastic(data, period=self.period, period_dfast=3, period_dslow=3) for data in self.datas}
                self.bollinger = {data: bt.indicators.BollingerBands(data.close, period=self.period, devfactor=2) for data in self.datas}
            except Exception as e:
                print(f"Error creating indicators: {e}")
            
            #initalize variable to keep track of weights and avg weights historically
            self.buy_weights = {}
            self.sell_weights = {}
            
            #check if reading from stocktwits file
            if self.params.tradeable_dates == {}:
                self.file_feed = False
            else:
                self.file_feed = True
                
            #create wait time to get up to current timeframe (extra days for indicator init)
            if not self.file_feed:
                self.last_date = self.datas[0].datetime.date(-self.params.wait_period) 
            

        except Exception as e:
            print(f"Error during backtest initialization: {e}")
    
    #log trade profit
    def notify_trade(self, trade):
         if not trade.isclosed:
             return
         ticker = trade.data._name
         self.log(f'OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}',ticker)
         self.num_trades += 1
         
    #log orders and track
    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.order_handle(order)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected', order.data._name)
        else:
            return
        # Reset the order variable
        self.order = None

        
    #log orders, trades, etc
    def log(self, txt, ticker=None, dt=None):
        dt = dt or self.datas[0].datetime.datetime(0)
        if self.params.logging and self.params.run_strat:
            print('%s: %s, %s' % (ticker, dt.isoformat(), txt))
        
    #increment period/place trades
    def next(self):
        try:
            #wait period
            if not self.file_feed:
                if self.datetime.date() != self.last_date and self.params.simulate:
                    return
            
            #If pending order, cancel, can't send another one
            if self.order:
                return
            
            #enter strategy
            self.enter_positions()
            
            # exit strategy
            self.exit_positions()
           
        except Exception as e:
            print(f"Error occured during next operation: {e}")
            
            
    #get highest weight
    def find_best_entry(self):
        for data in self.datas:
            
            #check if stock is currently tradeable if simulating
            if self.file_feed:
                if self.datetime.date().strftime('%Y-%m-%d') not in self.params.tradeable_dates[data._name]:
                    self.buy_weights[data] = 0
                    continue
            
            try:
                self.get_buy_weight(data)
            except Exception as e:
                print(f"Error getting buy weight for {data._name}: {e}")
                self.buy_weights[data] = 0
            
            #set weight to 0 if earnings date
            # Convert serial date to a datetime object
            serial_date = data.datetime[0]
            converted_date = datetime.fromordinal(int(serial_date)) + timedelta(days=serial_date % 1)
            converted_date1 = converted_date - timedelta(days=1)
            converted_date2 = converted_date + timedelta(days=1)
            formatted_date = converted_date.strftime('%Y-%m-%d')
            formatted_date1 = converted_date1.strftime('%Y-%m-%d')
            formatted_date2 = converted_date2.strftime('%Y-%m-%d')
            formatted_dates = [formatted_date, formatted_date1, formatted_date2]
            one_day = False
            if self.earnings[data]:
                if one_day:
                    if formatted_date in self.earnings[data]:
                        self.buy_weights[data] = 0
                else:
                    for date in formatted_dates:
                        if date in self.earnings[data]:
                            self.buy_weights[data] = 0
        
        #testing shorting only high market caps
        test_high_cap = True
        
        abs_test = False #turned it into a toggle for testing purposes
        max_weight = None
        if abs_test:
            max_weight = max(self.buy_weights, key = lambda x: abs(self.buy_weights[x])) 
        else:
            max_weight = max(self.buy_weights, key = lambda x: self.buy_weights[x]) 
        if max_weight == None: 
            print("Error setting max weight.")
            return
        
        
        while test_high_cap and self.params.allow_short:
            if max_weight.market_cap[0] < 10000 and self.buy_weights[max_weight] < 0:
                self.buy_weights[max_weight] = 0
                max_weight = max(self.buy_weights, key = lambda x: abs(self.buy_weights[x]))
            else:
                break
            
        return max_weight
    
    
    #enter strategy
    def enter_positions(self):
        
        #get best buy opportunity
        max_weight = self.find_best_entry()
        
        #place orders
        
        position = self.getposition(max_weight)
        if position.size == 0:
            if self.buy_weights[max_weight] != 0:
                
                #set stake size
                stake = self.setstake(max_weight, self.buy_weights[max_weight]/100)
                
                #check if stake == 0, is there a trade that hasn't closed that is already profitable?
                quick_turnover = True #toggle for testing
                rebuy = True #toggle for testing
                if stake == 0 and quick_turnover:
                    for data in self.datas:
                        
                        #check if given stock is tradeable if simulating
                        if self.file_feed:
                            if self.datetime.date().strftime('%Y-%m-%d') not in self.params.tradeable_dates[data._name]:
                                continue
                        
                        if self.getposition(data).size > 0:
                            #try different conditions
                            greater_weight = self.buy_weights[max_weight] >= self.weight_bought[data]
                            min_gain = 1
                            profitable = data.close[0] >= self.buyprice[data] * min_gain and data != max_weight
                            rebuy_opportunity = self.cerebro.broker.getcash() > 0 and data == max_weight and rebuy
                            if greater_weight and profitable:
                                self.order = self.sell(data=data, size=self.getposition(data).size)
                                self.order = self.buy(data=max_weight, size=self.setstake(max_weight, self.buy_weights[max_weight/100]))
                            if greater_weight and rebuy_opportunity:
                                self.order = self.buy(data=max_weight, size=self.setstake(max_weight, self.buy_weights[max_weight/100]))
                
                if self.buy_weights[max_weight] > 0:
                    self.order = self.buy(data=max_weight, size=stake)
                elif self.params.allow_short and self.cerebro.broker.getvalue() > self.params.startcash*.5:
                    if stake >= self.cerebro.broker.getvalue()*.1:
                        stake = self.cerebro.broker.getvalue()*.1
                    self.order = self.sell(data=max_weight, size=stake)
    
    #exit strategy
    def exit_positions(self):
        for data in self.datas: #check each stock
            
            position = self.getposition(data)
            
            if position.size != 0 and not self.order:
                
                try:
                    self.get_sell_weight(data)
                except Exception as e:
                    print(f"Error getting sell weight for {data._name}: {e}")
                    self.sell_weights[data] = 0
                    
                current_bar = len(self)
                exitbar_constraint = current_bar >= (self.bar_executed[data] + self.params.exitbars) #simple sell after # of bars
                long_profit_constraint = self.buyprice[data] <= data.close[0]
                short_profit_constraint = self.buyprice[data] >= data.close[0] # only sell/cover if profit/breakeven
                
                boll_long_constraint = data.close[0] >= self.bollinger[data].lines.top
                boll_short_constraint = data.close[0] <= self.bollinger[data].lines.bot
                
                simple_enabled = True # for testing, enable simple strategy
                simple_long_strategy = exitbar_constraint and long_profit_constraint and simple_enabled
                simple_short_strategy = exitbar_constraint and short_profit_constraint and simple_enabled
                
                indicator_strategy = True # for testing, enable indicator strategy
                boll_long_strategy = boll_long_constraint and long_profit_constraint and indicator_strategy
                boll_short_strategy = boll_short_constraint and short_profit_constraint and indicator_strategy
                
                weight_strategy = True # for testing, enable weight based strategy
                weight_sell_signal = False
                weight_cover_signal = False
                if self.sell_weights[data] < self.params.exit_threshold and not self.shorts[data] and weight_strategy and long_profit_constraint:
                    weight_sell_signal = True
                elif self.sell_weights[data] > self.params.confidence_threshold and self.shorts[data] and weight_strategy and short_profit_constraint:
                    weight_cover_signal = True
                
                #sell (cover)
                if self.params.stops:
                    if not self.shorts[data]:
                        if data.close[0] <= self.buyprice[data]*(1-self.params.long_loss):
                            self.order = self.sell(data=data, size=position.size)
                    else:
                        if data.close[0] >= self.buyprice[data]*(1+self.params.short_loss):
                            self.order = self.buy(data=data, size=position.size)
                if not self.shorts[data]:
                    if boll_long_strategy or weight_sell_signal or simple_long_strategy:
                        self.order = self.sell(data=data, size=position.size)
                else:
                    if boll_short_strategy or weight_cover_signal or simple_short_strategy:
                        self.order = self.buy(data=data, size=position.size)
    
            
    #set stake sizing
    def setstake(self,data,confidence):
        confidence = determine_weights.get_confidence(confidence, self.params.confidence_threshold, self.params.exit_threshold, self.params.allow_short)
        size = confidence*self.cerebro.broker.getvalue()/data.close[0]
        return size if size <= self.broker.getcash() else self.broker.getcash()/data.close[0] - 1
        
    #clean up at end
    def stop(self):
        #check if running/optimizing
        if self.params.run_strat:
            
            #close positions
            if not self.params.training: print("\nClosing positions...")
            for data in self.datas:
                position = self.getposition(data)
                if position.size != 0:
                    self.log(f'Closing out position, Size: {position.size:.2f}, Price: {data.close[0]:.2f}',data._name)
                    if position.size > 0:
                       self.trade_count({'pnl': position.size*data.close[0] - self.buytotal[data]}, self.sell(data=data, size=position.size))
                    else:
                        self.trade_count({'pnl': self.buytotal[data] - abs(position.size)*data.close[0]}, self.buy(data=data, size=position.size))
                    
            #run another iteration to process close orders
            self.cerebro.runstop()
            #print("All positions closed.")
            
            #print orders for debug or other purposes
            print_orders = False
            if print_orders:
                print("\nOrder Log:")
                for log in self.orderlog:
                    print(f"{log[0]}:{log[1]}")
        else: #otherwise just print ending value
            print(f"Exitbar: {self.params.exitbars} - Ending value: {self.cerebro.broker.getvalue()}")
            
        if self.params.training:
            return
        
        #show portfolio stats by ticker
        print("\nPortfolio breakout:")
        for ticker,value in self.numtrades.items():
            print(f".....{ticker}......")
            print(f"Num Trades: {round(value[0],2)}")
            print(f"Gross PNL: {round(value[1],2)}")
           # print(f"NET: {round(value[2],2)}")
            
        #most profitable trades
        print("\nMost profitable trades:")
        for i in range(1,len(self.tradepnl)+1):
            trade = self.tradepnl[i-1]
            print(f"{i} --- {trade[0]}")
            print(f"GROSS: {round(trade[1],2)}")
           # print(f"NET: {round(trade[2],2)}")
           
        #send pnl array to backtest to analyze results
        self.analyze_trades()

    def get_buy_weight(self, data):
        share_price = data.close[0]
        ticker = data._name  
        
        #init weights, indicators, variables
        self.buy_weights[data] = 0
        current_rsi = self.rsi[data][0]
        last_macd = self.macd[data][-1]
        last_signal = self.macd_signal[data][-1]
        macd = self.macd[data][0]
        signal = self.macd_signal[data][0]
        current_vwap = self.vwap[data][0]
        stoch_k = self.stochastic[data].percK[0]
        stoch_d = self.stochastic[data].percD[0]
        
        mktcap = data.market_cap[0]
        high_52 = data.high_52_week[0]
        low_52 = data.low_52_week[0]
        
        if high_52 - low_52 == 0:
            pricentile = 0
        else: 
            pricentile = (share_price-low_52)/(high_52-low_52)
        
        #initialize dict to send to determine_weights
        params_dict = {
            #set variables
            'ticker': ticker,
            'exitbars': self.params.exitbars,
            'share_price': share_price,
            'current_rsi': current_rsi,
            'current_vwap': current_vwap,
            'mktcap': mktcap,
            'current_macd': macd,
            'current_signal': signal,
            'last_macd': last_macd,
            'last_signal': last_signal,
            'stoch_k': stoch_k,
            'stoch_d': stoch_d,
            'current_pricentile': pricentile,
            'last_per_rsi': self.rsi[data][-self.params.exitbars],
            'last_per_close': self.data.close[-self.params.exitbars],
            'last_per_mktcap': self.data.market_cap[-self.params.exitbars],
            'boll_upper': self.bollinger[data].lines.top,
            'boll_lower': self.bollinger[data].lines.bot,
            'confidence_threshold': self.params.confidence_threshold,
            
            #weights
            'pricentile1': self.params.pricentile1,
            'rsi1': self.params.rsi1,
            'rsi2': self.params.rsi2,
            'rsi3': self.params.rsi3,
            'vwap1': self.params.vwap1,
            'vwap2': self.params.vwap2,
            'stoch1': self.params.stoch1,
            'stoch2': self.params.stoch2,
            'swing1': self.params.swing1,
            'swing2': self.params.swing2,
            'macd1': self.params.macd1,
            'macd2': self.params.macd2,
            'mktcap1': self.params.mktcap1,
            'mktcap2': self.params.mktcap2,
            'mktcap3': self.params.mktcap3,
            'mktcap4': self.params.mktcap4,    
        }
    
        #get weights
        weight = determine_weights.get_buy_weight(params_dict)
        self.buy_weights[data] = weight
        
            
    def get_sell_weight(self, data):
        share_price = data.close[0]
        ticker = data._name  
        
        #init weights, indicators, variables
        self.sell_weights[data] = 0
        current_rsi = self.rsi[data][0]
        last_macd = self.macd[data][-1]
        last_signal = self.macd_signal[data][-1]
        macd = self.macd[data][0]
        signal = self.macd_signal[data][0]
        current_vwap = self.vwap[data][0]
        stoch_k = self.stochastic[data].percK[0]
        stoch_d = self.stochastic[data].percD[0]

        mktcap = data.market_cap[0]
        high_52 = data.high_52_week[0]
        low_52 = data.low_52_week[0]
            
        if high_52 - low_52 == 0:
            pricentile = 0
        else: 
            pricentile = (share_price-low_52)/(high_52-low_52)
    
        #initialize weights to send to determine_weights
        params_dict = {
            #set variables
            'ticker': ticker,
            'exitbars': self.params.exitbars,
            'share_price': share_price,
            'current_rsi': current_rsi,
            'current_vwap': current_vwap,
            'mktcap': mktcap,
            'current_macd': macd,
            'current_signal': signal,
            'last_macd': last_macd,
            'last_signal': last_signal,
            'stoch_k': stoch_k,
            'stoch_d': stoch_d,
            'current_pricentile': pricentile,
            'last_per_rsi': self.rsi[data][-self.params.exitbars],
            'last_per_close': self.data.close[-self.params.exitbars],
            'last_per_mktcap': self.data.market_cap[-self.params.exitbars],
            'boll_upper': self.bollinger[data].lines.top,
            'boll_lower': self.bollinger[data].lines.bot,
            'confidence_threshold': self.params.confidence_threshold,
            
            #weights
            'pricentile1': self.params.pricentile1,
            'rsi1': self.params.rsi1,
            'rsi2': self.params.rsi2,
            'rsi3': self.params.rsi3,
            'vwap1': self.params.vwap1,
            'vwap2': self.params.vwap2,
            'stoch1': self.params.stoch1,
            'stoch2': self.params.stoch2,
            'swing1': self.params.swing1,
            'swing2': self.params.swing2,
            'macd1': self.params.macd1,
            'macd2': self.params.macd2,
            'mktcap1': self.params.mktcap1,
            'mktcap2': self.params.mktcap2,
            'mktcap3': self.params.mktcap3,
            'mktcap4': self.params.mktcap4,    
        }
        
        #get weights
        weight = determine_weights.get_sell_weight(params_dict)
        self.sell_weights[data] = weight
        
        
    def order_handle(self, order):
        data = order.data
        ticker = data._name
        if order.isbuy():
            if not self.shorts[order.data]:  # Long buy
                self.log(
                    f'BUY EXECUTED @ {order.executed.price:.2f}, '
                    f'TOTAL: {order.executed.value:.2f}, '
                    f'COMM: {order.executed.comm:.2f}', order.data._name)
                self.orderlog.append([order.data._name,
                                      f'BUY EXECUTED @ {order.executed.price:.2f}, '
                                      f'TOTAL: {order.executed.value:.2f}'])
                self.buyprice[order.data] = order.executed.price
                self.buycomm[order.data] = order.executed.comm
                self.buytotal[order.data] = order.executed.size*order.executed.price
                self.bar_executed[order.data] = len(self)
                self.weight_bought[data] = self.buy_weights[data]
            elif self.shorts[order.data]:  # Cover (closing a short position)
                total_cover_value = abs(order.executed.size) * order.executed.price
                self.log(
                    f'COVER EXECUTED @ {order.executed.price:.2f}, '
                    f'TOTAL: {total_cover_value:.2f}, '
                    f'COMM: {order.executed.comm:.2f}', order.data._name)
                self.orderlog.append([order.data._name,
                                      f'COVER EXECUTED @ {order.executed.price:.2f}, '
                                      f'TOTAL: {total_cover_value:.2f}'])
                self.buyprice[order.data] = None
                self.buycomm[order.data] = None
                self.bar_executed[order.data] = None
                self.shorts[order.data] = False
                self.trade_count({'pnl': self.buytotal[order.data] - total_cover_value}, order)
                self.buytotal[order.data] = None
                self.shorts[order.data] = False
            self.orderlog.append([ticker, f"RSI: {self.rsi[data][0]:.2f}, MACD: {self.macd[data][0]:.2f}, VWAP: {self.vwap[data][0]:.2f}, stock_k & stoch_d: {self.stochastic[data].percK[0]:.2f} & {self.stochastic[data].percD[0]:.2f}, Pricentile: {(data.close[0]-data.low_52_week[0])/(data.high_52_week[0]-data.low_52_week[0]):.2f}, Mktcap: {data.market_cap[0]:.2f}"])
            self.orderlog.append([ticker, f"Total weight: {self.buy_weights[data]:.2f}, Date: {(datetime.fromordinal(int(data.datetime[0])) + timedelta(days=data.datetime[0] % 1)).strftime('%m/%d/%Y %H:%M:%S')}"])
        elif order.issell():
            if self.getposition(order.data).size < 0:  # Short sell
                self.log(
                    f'SHORT SELL EXECUTED @ {order.executed.price:.2f}, '
                    f'TOTAL: {order.executed.value:.2f}, '
                    f'COMM: {order.executed.comm:.2f}', order.data._name)
                self.orderlog.append([order.data._name,
                                      f'SHORT SELL EXECUTED @ {order.executed.price:.2f}, '
                                      f'TOTAL: {order.executed.value:.2f}'])
                self.buyprice[order.data] = order.executed.price
                self.buycomm[order.data] = order.executed.comm
                self.buytotal[order.data] = abs(order.executed.size*order.executed.price)
                self.bar_executed[order.data] = len(self)
                self.shorts[order.data] = True
            else:  # Sell (closing a long position)
                total_sell_value = abs(order.executed.size) * order.executed.price
                self.log(
                    f'SELL EXECUTED @ {order.executed.price:.2f}, '
                    f'TOTAL: {total_sell_value:.2f}, '
                    f'COMM: {order.executed.comm:.2f}', order.data._name)
                self.orderlog.append([order.data._name,
                                      f'SELL EXECUTED @ {order.executed.price:.2f}, '
                                      f'TOTAL: {total_sell_value:.2f}'])
                self.buyprice[order.data] = None
                self.buycomm[order.data] = None
                self.bar_executed[order.data] = None
                self.trade_count({'pnl': total_sell_value - self.buytotal[order.data]}, order)
                self.buytotal[order.data] = None
                self.weight_bought[data] = None
            self.orderlog.append([ticker, f"RSI: {self.rsi[data][0]:.2f}, MACD: {self.macd[data][0]:.2f}, VWAP: {self.vwap[data][0]:.2f}, stock_k & stoch_d: {self.stochastic[data].percK[0]:.2f} & {self.stochastic[data].percD[0]:.2f}, Pricentile: {(data.close[0]-data.low_52_week[0])/(data.high_52_week[0]-data.low_52_week[0]):.2f}, Mktcap: {data.market_cap[0]:.2f}"])
            self.orderlog.append([ticker, f"Total weight: {self.sell_weights[data]:.2f}, Date: {(datetime.fromordinal(int(data.datetime[0])) + timedelta(days=data.datetime[0] % 1)).strftime('%m/%d/%Y %H:%M:%S')}"])
    
    def trade_count(self, trade, order):
         data = order.data
         ticker = data._name
         #log
         trade_value = f"Profit: {trade['pnl']:.2f}"
         if self.params.logging:
             self.log(ticker, trade_value)
         self.orderlog.append([ticker, trade_value])
         
         #count trades/profit per ticker
         if ticker not in self.numtrades:
             self.numtrades[ticker] = np.array([1,trade['pnl']])
         else:
             self.numtrades[ticker] += np.array([1,trade['pnl']])
    
        #track most profitable trades and sort
         if len(self.tradepnl) < 3:
             self.tradepnl.append([ticker,trade['pnl']])
         else:
             min_trade = min(self.tradepnl, key = lambda x: x[1])
             if trade['pnl'] > min_trade[1]:
                 self.tradepnl.remove(min_trade)
                 self.tradepnl.append([ticker,trade['pnl']])
         self.tradepnl = sorted(self.tradepnl, key = lambda x: x[1], reverse=True)
         
    def analyze_trades(self):
        try:
            industry_analysis = {}
            sector_analysis = {}
            
            #get and calculate industry and sector profits
            for key, value in self.numtrades.items():
                ind = yf.get_industry_sector(key)
                industry = ind['industry']
                sector = ind['sector']
                if industry not in industry_analysis:
                    industry_analysis[industry] = value[1]
                else:
                    industry_analysis[industry] += value[1]
                if sector not in sector_analysis:
                    sector_analysis[sector] = value[1]
                else:
                    sector_analysis[sector] += value[1]
                
            #add to dicts
            for key,value in industry_analysis.items():
                if key not in self.industry_analysis:
                    self.industry_analysis[key] = value
                else:
                    self.industry_analysis[key] += value
                    
            for key,value in sector_analysis.items():
                if key not in self.sector_analysis:
                    self.sector_analysis[key] = value
                else:
                    self.sector_analysis[key] += value
        except Exception as e:
            print(f"Error when analyzing trades: {e}")