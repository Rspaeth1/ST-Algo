# -*- coding: utf-8 -*-
"""
Created on Wed Jan 15 12:05:53 2025

@author: rspaeth1
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

url = "https://stocktwits.com/sentiment/trending"

change_threshold = 0
crypto_enabled = False

def get_trending_stocks():
    try:
        #use headers to mimic browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Send a request to the trending page
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error for failed requests
        
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
    
        # Extract the portion of the text between "Trending" and "MoreSentimentTrending"
        match = re.search(r"Advertise(.*?)Trending(.*?)MoreSentimentTrending", soup.get_text(), re.DOTALL)
        if not match:
            return []  # Return an empty list if no match is found
    
        # Extracted substring containing symbols
        trending_text = match.group(1) + match.group(2)
    
        #split and find symbols
        symbols = trending_text.split("%")
        clean_symbols = []
        for symbol in symbols:
            if symbol.count(".") > 1:
                if crypto_enabled:
                    index = symbol.find(".X")
                    clean_symbols.append(symbol[:index + 2])
            else:
                symbol = ''.join([char for char in symbol if char.isalpha()])
                if symbol != '': clean_symbols.append(symbol)
        
        # only grab symbols <= 4 characters excluding crypto tickers
        for symbol in clean_symbols:
            if len(symbol) > 4 and not symbol.endswith('.X'):
                clean_symbols.remove(symbol)

        #try to save symbols to file
        try:
            fh = open(f"StockTwitsTrending/{datetime.today().strftime('%Y-%m-%d')}.txt", "x")
            for ticker in clean_symbols:
                fh.write(ticker+"\n")
            fh.close()
        except:
            print("\nStockTwits symbols already saved.\n")
            
        return clean_symbols
    
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

def get_news(ticker):
    url = "https://stocktwits.com/symbol/" + ticker + "/news"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Send a request to the trending page
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error for failed requests
        
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        fh = open("news.txt", "w")
        fh.write(soup.get_text())
        fh.close()
        
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")