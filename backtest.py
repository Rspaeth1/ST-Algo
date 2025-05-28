# -*- coding: utf-8 -*-
"""
Created on Sun Dec 22 21:44:00 2024

@author: rspaeth1
"""

import backtrader as bt

import EquityStrategy, OptionsStrategy
from custom_components import CustomPandasData


class tradeframe:
    
    def __init__(self,stockdata,startcash,interval,training=False,simulate=False):
        self.startcash = startcash
        self.cerebro = bt.Cerebro()
        self.cerebro.broker.setcash(startcash)
        self.stocks = {}
        self.training = training
        self.simulate = simulate
        
        for stock,data in stockdata.items():
            self.addData(stock,data,interval)
        
    def addData(self,ticker,stockdata,interval):
        self.stocks[ticker] = CustomPandasData(dataname=stockdata, name=ticker, timeframe=bt.TimeFrame.Minutes, compression=interval)
        self.cerebro.adddata(self.stocks[ticker])
        
        
    def run(self, params, period, commission = 0.0, allow_short = False, tradeable_dates={}):
        #Determine if optimizing, training, running
        run_strat = True

        #set strategy
        equity = True
        if equity:
            if run_strat: #add strategy to run
                self.cerebro.addstrategy(EquityStrategy.strategy, **params, allow_short=allow_short, startcash=self.startcash,run_strat=True,training=self.training,simulate=self.simulate, wait_period=period, tradeable_dates=tradeable_dates)
            else: #or optimize strategy with variables
                self.cerebro.optstrategy(EquityStrategy.strategy, exitbars=range(5,15),allow_short=allow_short,run_strat=False,startcash=self.startcash)
        else:
            if run_strat: #add strategy to run
                self.cerebro.addstrategy(OptionsStrategy.strategy, **params, startcash=self.startcash,run_strat=True,training=self.training,simulate=self.simulate, wait_period=period)
            else: #or optimize strategy with variables
                self.cerebro.optstrategy(OptionsStrategy.strategy, exitbars=range(5,15),allow_short=allow_short,run_strat=False,startcash=self.startcash,simulate=self.simulate)
       
        #add necessary components
        self.cerebro.optreturn = False #disable multiprocessing to prevent error when optimizing
        self.cerebro.broker.setcommission(commission=commission)
        
        if not self.training: self.stats()
        results = self.cerebro.run()
            
        return results
        
    def stats(self):
        print('\nCurrent portfolio value is: %.2f' % self.cerebro.broker.getvalue())
        print(f'Profit: {(self.cerebro.broker.getvalue() - self.startcash):.2f}')
        print(f"Return: {((self.cerebro.broker.getvalue()-self.startcash)/self.startcash*100):.2f}%")