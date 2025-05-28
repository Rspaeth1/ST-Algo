# -*- coding: utf-8 -*-
"""
Created on Sat Jan 25 15:38:57 2025

@author: Ryan
"""

import stocktwits as st
import gptapi as gpt

def get_confidence(confidence, confidence_threshold, exit_threshold, allow_short=False):
    if confidence > 1: confidence = 1
    if confidence < 0 and allow_short: 
        confidence = abs(confidence)
        if confidence > 1: confidence = 1
    if not allow_short:
        if confidence < confidence_threshold/100: confidence = 0 #try assigning as probability
    else:
        if confidence < exit_threshold/100: confidence = 0
        
    return confidence

def get_buy_weight(params):
    buy_weight = 0
    
    #set variables
    ticker = params['ticker']
    exit_bars = params['exitbars']
    share_price = params['share_price']
    current_rsi = params['current_rsi']
    current_vwap = params['current_vwap']
    mktcap = params['mktcap']
    macd = params['current_macd']
    signal = params['current_signal']
    last_macd = params['last_macd']
    last_signal = params['last_signal']
    stoch_k = params['stoch_k']
    stoch_d = params['stoch_d']
    current_pricentile = params['current_pricentile']
    last_per_rsi = params['last_per_rsi']
    last_per_close = params['last_per_close']
    last_per_mktcap = params['last_per_mktcap']
    boll_upper = params['boll_upper']
    boll_lower = params['boll_lower']
    boll_mid = (boll_upper + boll_lower)/2
    boll_perc = (share_price - boll_lower)/(boll_upper - boll_lower)
    confidence_threshold = params['confidence_threshold']
    
    #weights
    pricentile1 = params['pricentile1']
    rsi1 = params['rsi1']
    rsi2 = params['rsi2']
    rsi3 = params['rsi3']
    vwap1 = params['vwap1']
    vwap2 = params['vwap2']
    stoch1 = params['stoch1']
    stoch2 = params['stoch2']
    swing1 = params['swing1']
    swing2 = params['swing2']
    macd1 = params['macd1']
    macd2 = params['macd2']
    mktcap1 = params['mktcap1']
    mktcap2 = params['mktcap2']
    mktcap3 = params['mktcap3']
    mktcap4 = params['mktcap4']
    
    #set buy weight
    #rsi
    if current_rsi <= 30:
        buy_weight += rsi1
    elif current_rsi >= 70:
        buy_weight -= rsi2
    else:
        buy_weight += rsi3 - current_rsi
    
    #vwap
    if share_price > current_vwap:
        buy_weight -= vwap1*(share_price/current_vwap)
    else:
        buy_weight += vwap2*(share_price/current_vwap)
    
    #stoch
    if stoch_k < 20 and stoch_d < 20:
        if stoch_k > stoch_d:
            buy_weight += stoch1
    elif stoch_k > 80 and stoch_d > 80:
        if stoch_k < stoch_d:
            buy_weight -= stoch2
        
    #more fine tuning required maybe for experimental indicators
    buy_weight -= (current_pricentile*100)*pricentile1
    
    #swings
    if last_per_close/share_price > 1.3:
        buy_weight -= swing1*(last_per_close/share_price)
    elif last_per_close/share_price < .7:
        buy_weight += swing2/(last_per_close/share_price)
                
    #macd
    if macd < 0:
        factor = 5
        if macd > signal:
            if last_macd < last_signal:
                factor = 10
            buy_weight += macd1*(-macd)/share_price*factor
        else:
            buy_weight -= macd1*(-macd)/share_price*factor
    else: #HAD THIS COMMENTED OUT BEFORE. TESTING WITH IT OPEN.
        buy_weight = 0
        """
        if macd > signal:
            factor = 10
            if last_macd < signal:
                factor = 30
            buy_weight -= macd2*(macd)/share_price*factor
            """
      
    #try downside protection, but reenter later
    #if bad_rsi and bad_macd and bad_stoch:
        #buy_weight = 0
        #watch[ticker] = exit_bars
                    
    #market cap scaling
    micro_protection = False #testing if this affects anything
    micro_cap = 300
    if last_per_mktcap <= micro_cap and micro_protection: # microcap protection
        buy_weight = 0
    
    if mktcap < 2000:
        buy_weight *= mktcap1
    elif mktcap < 4500:
        buy_weight *= mktcap2
    elif mktcap < 10000:
        buy_weight *= mktcap3
    elif mktcap > 100000:
        buy_weight *= .25
    elif mktcap == 0: 
        buy_weight = 0
    else:
        buy_weight *= mktcap4
        
    #try using news to capture weights
    use_news = False
    if use_news:
        response = gpt.get_response(st.get_news(params['ticker']))
        if type(response) != str:
            #init weights
            date_factor = 1
            sentiment_factor = 1
            category_factor = 1
            
            #init responses
            date = response['Date'].lower()
            sentiment = response['Sentiment'].lower()
            category = response['Category'].lower()
            
            #set weights
            if date == "3d" or date == "2d":
                date_factor = 1
            else:
                date_factor = 1.5
                
            if sentiment == "very bearish":
                sentiment_factor = .25
            elif sentiment == "bearish":
                sentiment_factor = .5
            elif sentiment == "neutral":
                sentiment_factor = 1
            elif sentiment == "bullish":
                sentiment_factor = 1.5
            elif sentiment == "very bullish":
                sentiment_factor = 2
                
            if category == "earnings":
                category_factor = 0
            elif category == "offering":
                category_factor = .25
            elif category == "management outlook":
                if sentiment_factor >= 1:
                    category_factor = 1.5
                else:
                    category_factor = .5
            elif category == "new operations deal/market share gain or loss":
                if sentiment_factor >= 1:
                    category_factor = 1.5
                else:
                    category_factor = .5
            elif category == "m&a announcement (acquirer/target)":
                category_factor = 1.25
            elif category == "drug passed trial phase (1/2/3/fda approval)":
                category_factor = 1.5
            elif category == "government funding":
                category_factor = 1.5
            elif category == "top stock movers":
                category_factor = 1
            elif category == "bank target price change":
                if sentiment_factor >= 1:
                    category_factor = 1.25
                else:
                    category_factor = .75
            elif category == "stock split":
                category_factor = 0
            
            total_news_weight = date_factor*sentiment_factor*category_factor/4.5
            if total_news_weight < 1 and total_news_weight != 0: 
                total_news_weight = 1 - total_news_weight
            buy_weight *= total_news_weight
                
    return buy_weight

def get_sell_weight(params):
    sell_weight = 0
    
    #set variables
    ticker = params['ticker']
    share_price = params['share_price']
    current_rsi = params['current_rsi']
    current_vwap = params['current_vwap']
    mktcap = params['mktcap']
    macd = params['current_macd']
    signal = params['current_signal']
    last_macd = params['last_macd']
    last_signal = params['last_signal']
    stoch_k = params['stoch_k']
    stoch_d = params['stoch_d']
    current_pricentile = params['current_pricentile']
    last_per_close = params['last_per_close']
    last_per_mktcap = params['last_per_mktcap']
    
    #weights
    pricentile1 = params['pricentile1']
    rsi1 = params['rsi1']
    rsi2 = params['rsi2']
    rsi3 = params['rsi3']
    vwap1 = params['vwap1']
    vwap2 = params['vwap2']
    stoch1 = params['stoch1']
    stoch2 = params['stoch2']
    swing1 = params['swing1']
    swing2 = params['swing2']
    macd1 = params['macd1']
    macd2 = params['macd2']
    mktcap1 = params['mktcap1']
    mktcap2 = params['mktcap2']
    mktcap3 = params['mktcap3']
    mktcap4 = params['mktcap4']
    
    #set weights
    #rsi
    if current_rsi <= 30:
        sell_weight -= rsi1
    elif current_rsi >= 70:
        sell_weight += rsi2
    else:
        sell_weight -= rsi3 - current_rsi
    
    #vwap
    if share_price > current_vwap:
        sell_weight += vwap1*(share_price/current_vwap)
    else:
        sell_weight -= vwap2*(share_price/current_vwap)
    
    #stoch
    if stoch_k < 20 and stoch_d < 20:
        if stoch_k > stoch_d:
            sell_weight += stoch1
    elif stoch_k > 80 and stoch_d > 80:
        if stoch_k < stoch_d:
            sell_weight -= stoch2
        
    #more fine tuning required maybe for experimental indicators
    sell_weight += (current_pricentile*100)*pricentile1
    
    if last_per_close/share_price > 1.3: #bonus for price target
        sell_weight += swing1*(last_per_close/share_price)
                
    #macd
    if macd < 0:
        sell_weight = 100
    else:
        if macd > signal:
            factor = 10
            if last_macd < signal:
                factor = 30
            sell_weight -= macd2*(macd)/share_price*factor
    
    return sell_weight
                