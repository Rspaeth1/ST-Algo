# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 22:53:56 2025

@author: Ryan
"""

from yahooquery import Ticker
import pandas as pd

def get_earnings(ticker):
    ticker = ticker
    stock = Ticker(ticker)
    
    #get historical earnings dates
    income_statement = stock.income_statement(frequency='q')  # Get quarterly reports
    earnings_history = sorted(list(income_statement.index.get_level_values(1).unique()))
    
    #get upcoming earnings date
    upcoming_earnings = stock.calendar_events[ticker]
    upcoming_date = None
    if 'earnings' in upcoming_earnings:
        upcoming_date = upcoming_earnings['earnings'].get('earningsDate', {}).get('raw')
    
    #convert upcoming date to string format
    if upcoming_date:
        upcoming_date = pd.to_dateframe(upcoming_date).strftime('%Y-%m-%d')
    
    #combine
    earnings_dates = sorted(earnings_history + ([upcoming_date] if upcoming_date else []))
    
    return earnings_dates