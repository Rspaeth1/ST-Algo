# -*- coding: utf-8 -*-
"""
Created on Sun Dec 22 21:41:39 2024

@author: rspaeth1
"""

import main
import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta

class stockframe:
    def __init__(self, tickerlist, timeframes, interval):
        self.stocks = {}
        self.interval = interval
        self.timeframes = timeframes  # Save timeframes for reference
        self.intraday_data = None
        
        # Process tickers
        self.setTickers(tickerlist)

    def setTickers(self, tickerlist):
        for ticker in tickerlist:
            self.intraday_data = None
            try:
                self.load_from_file(ticker)
            except:
                #if training dont download
                if main.training:
                    continue
                
                try: 
                    if not self.download_data(ticker): continue
                except Exception as e:
                    print(f"Error processing data for {ticker}: {e}")

    def add_market_cap(self, ticker):
        """Add market capitalization as a column to the DataFrame."""
        try:
            # Fetch shares outstanding
            shares_outstanding = yf.Ticker(ticker).info.get('sharesOutstanding', None)
            if shares_outstanding is None:
                print(f"Shares outstanding data not available for {ticker}")
                self.intraday_data['market_cap'] = 0
                return False

            # Calculate market cap as a new column in millions
            self.intraday_data['market_cap'] = self.intraday_data['close'] * shares_outstanding / 1000000
            return True
        except Exception as e:
            print(f"Error calculating market cap for {ticker}: {e}")
            
    def get_year(self):
        end_date = datetime.today()
        start_date = end_date - timedelta(days=365*2)
        return [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')]
    
    def load_from_file(self, ticker):
        # Read the data and parse datetime
        #dataname = str(self.timeframes[0]).replace( + "_" + str(self.timeframes[1])
        data = pd.read_csv(
           f"TickerData/{ticker}_{self.interval}_{self.timeframes[0]}_{self.timeframes[1]}.csv",
           parse_dates=['datetime'],  # Ensure 'datetime' is parsed
           index_col='datetime'  # Set 'datetime' as index
        )
        self.stocks[ticker] = data
        #print(f"{ticker} Loaded from file")
    
    def download_data(self, ticker):
        if not check_equity(ticker): return False
        
        start = self.timeframes[0]
        end = self.timeframes[1]
       
        # Download intraday data
        self.intraday_data = yf.download(ticker, start=start, end=end, interval=self.interval)
     
        if self.intraday_data.empty:
            print(f"Error: No data found for ticker: {ticker}")
            return False

        # Flatten MultiIndex if present
        if isinstance(self.intraday_data.columns, pd.MultiIndex):
            self.intraday_data.columns = [col[0].lower() for col in self.intraday_data.columns]
        
        # Rename columns for Backtrader compatibility
        self.intraday_data.rename(
            columns={
                'Date': 'datetime',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            },
            inplace=True
        )

        self.intraday_data.index.name = 'datetime'

                
        
        if not self.add_custom_components(ticker): return False

        # Save the final dataframe
        try:
            self.intraday_data.to_csv(f"TickerData/{ticker}_{self.interval}_{self.timeframes[0]}_{self.timeframes[1]}.csv", index=True)
        except:
            print(f'Couldn\'t save file for: {ticker}')
        self.stocks[ticker] = self.intraday_data #, yf.Ticker("ticker").info.get("industry")]
    
        return True
        
    def add_custom_components(self, ticker):
        # Validate column names
        expected_columns = {'open', 'high', 'low', 'close', 'volume'}
        if not expected_columns.issubset(self.intraday_data.columns): return False
            
        # Download daily data for 52-week high/low
        day_frame = self.get_year()
        daily_data = yf.download(ticker, start=day_frame[0], end=day_frame[1], interval='1d')

        if daily_data.empty:
            print(f"Warning: No daily data found for ticker: {ticker}")
            return False

        # Flatten MultiIndex for daily data if necessary
        if isinstance(daily_data.columns, pd.MultiIndex):
            daily_data.columns = [col[0].lower() for col in daily_data.columns]
        
        # Rename columns for Backtrader compatibility
        daily_data.rename(
            columns={
                'Date': 'datetime',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            },
            inplace=True
        )

        daily_data.index.name = 'datetime'
        
        # Calculate 52-week high and low using daily data
        rolling_window = min(252, len(daily_data))
        daily_data['52_Week_High'] = daily_data['high'].rolling(window=rolling_window).max()
        daily_data['52_Week_Low'] = daily_data['low'].rolling(window=rolling_window).min()

        # Reset index for merging
        self.intraday_data.reset_index(inplace=True)
        daily_data.reset_index(inplace=True)
       
        # Extract the date portion for merging
        self.intraday_data['date'] = self.intraday_data['datetime'].dt.date
        daily_data['date'] = pd.to_datetime(daily_data['datetime']).dt.date  # Ensure alignment


        # Merge intraday data with daily 52-week high/low
        self.intraday_data = pd.merge(
            self.intraday_data,
            daily_data[['date', '52_Week_High', '52_Week_Low']],
            on='date',
            how='left'
        )

        # Drop the 'date' column and restore the original index
        self.intraday_data.drop(columns=['date'], inplace=True)
        self.intraday_data.set_index('datetime', inplace=True)


        # Add market cap
        if not self.add_market_cap(ticker): return False
        
        return True
        
def check_equity(ticker):
    try: #check if stock is equity (not ETF, etc)
        security_type = None
        
        #get type and save to file if not already
        if not os.path.isfile(f"TickerData/{ticker}_security_type.txt"):
            fh = open(f"TickerData/{ticker}_security_type.txt", "w")
            security_type = yf.Ticker(ticker).info.get("quoteType")
            fh.write(security_type)
            fh.close()
        else:
            fh = open(f"TickerData/{ticker}_security_type.txt", "r")
            security_type = fh.readline()
            fh.close()
            
            #if file is blank, make sure we get it again
            if (security_type == ""):
                fh.close()
                fh = open(f"TickerData/{ticker}_security_type.txt", "w")
                security_type = yf.Ticker(ticker).info.get("quoteType")
                fh.write(security_type)
                fh.close()
        
        #debug
        #print(f"Equity check - {ticker}: {security_type}")
        
        #check type and return
        if security_type == "EQUITY":
            return True
    except:
        print(f"Couldn't get quote type for ticker: {ticker}")
    return False

def get_outstanding_shares(ticker):
    shares_outstanding= 0
    try:
        shares_outstanding = yf.Ticker(ticker).info.get('sharesOutstanding', None)
        if shares_outstanding is None:
            print(f"Shares outstanding data not available for {ticker}")
    except Exception as e:
        print(f"Exception when fetching shares outstanding for {ticker}: {e}")
        
    return shares_outstanding

def get_earnings(ticker):
    try:
        if not os.path.isfile(f"EarningsData/{ticker}.txt"):
            #if no file with data: grab yfin data
            
            #if training, dont download
            if main.training:
                return
            
            stock = yf.Ticker(ticker)
            
            # Get historical and upcoming earnings dates
            earnings_dates = stock.earnings_dates.index.tolist()

            # Convert to string format
            earnings_dates = [date.strftime('%Y-%m-%d') for date in earnings_dates]
            
            fh = open(f"EarningsData/{ticker}.txt", 'w')
            for date in earnings_dates:
                fh.write(date + "\n")
        else:
            #otherwise read from file
            
            fh = open(f"EarningsData/{ticker}.txt", 'r')
            earnings_dates = [line.strip() for line in fh]

        return earnings_dates
    except Exception as e:
        print(f"Failed to retrieve earnings dates for {ticker}: {e}")
        
def get_industry_sector(ticker):
    try:
        stock = yf.Ticker(ticker)
       
        return {
            "industry": stock.info.get("industry", "not found"),
            "sector": stock.info.get("sector", "not found")
            }
    except Exception as e:
        print(f"Error getting industry for {ticker}: {e}")