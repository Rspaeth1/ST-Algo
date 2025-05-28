# -*- coding: utf-8 -*-
"""
Created on Sun Mar 30 14:34:46 2025

@author: rspaeth1
"""

from pathlib import Path



def get_data():
    try:
        
        folder_path = Path('StockTwitsTrending/')
        data = {}
        first = True
        
        for file in folder_path.iterdir():
            if file.is_file():
                date = file.name.split('.txt', 1)[0]
                if first:
                    start_date = date
                    first = False
                
                tickers = []
                with file.open('r') as f:
                    for line in f:
                        tickers.append(line.strip())
                    data[date] = tickers
            end_date = date
            
        ticker_focus = {} #return a dictionary with dates per ticker, not dates with tickers
        
        for date in data.keys():
            for ticker in data[date]:
                ticker_focus.setdefault(ticker, [])
                ticker_focus[ticker].append(date)
                
    except Exception as e:
        print(f"Error getting stocktwits data from file: {e}")
            
    return ticker_focus, start_date, end_date