# -*- coding: utf-8 -*-
"""
Created on Tue Jan 14 15:25:18 2025

@author: rspaeth1
"""

import backtrader as bt

#custom indicator for VWAP
class VWAP(bt.Indicator):
    lines = ('vwap',)
    params = (('period', 9),)
    
    def __init__(self):
        volume_price = self.data.close * self.data.volume
        cumulative_vp = bt.indicators.SumN(volume_price, period = self.params.period)
        cumulative_vol = bt.indicators.SumN(self.data.volume, period = self.params.period)
        self.lines.vwap = cumulative_vp / cumulative_vol

#set params to handle data feed
class CustomPandasData(bt.feeds.PandasData):
    # Add lines for 52-week high and low
    lines = ('high_52_week', 'low_52_week', 'market_cap')

    # Define the default parameters for all lines
    params = (
        ('date', 'datetime'),
        ('open', 'open'),
        ('close', 'close'),
        ('high', 'high'),
        ('low', 'low'),
        ('volume', 'volume'),
        ('high_52_week', '52_Week_High'),  # Map to '52_Week_High' column
        ('low_52_week', '52_Week_Low'),   # Map to '52_Week_Low' column
        ('market_cap', 'market_cap'), #Map 'market_cap' column
    )
    