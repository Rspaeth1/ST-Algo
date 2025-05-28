# -*- coding: utf-8 -*-

#TODO: add functionality to test if same stock has better buying opportunity with cash available

#TODO: improve real time day to day trading - which tickers to keep trading

#TODO: add logic for industry analsis // figure out industry analysis for alpaca (or just use yfin if necessary -- may be easier)

#TODO: save current position buy times and etc to load later for selling in case close console

#TODO: for earnings data, make sure to check if recent data has been grabbed- daily? weekly? monthly? looks like it grabs the next 4 quarters if available, so maybe quarterly or biannually. Not frequently anyway.

#TODO: add more parameters: time of day, variables for factors

#TODO: update function causes websocket disconnection
#TODO: make sure stock loading updates work from file for live


import yfin as yf
import algotorch as alg
import backtest as bt
import stocktwits as st
import alpacawebsocket
import SimulatorFileReader

import numpy as np
import matplotlib.pyplot as plt
import time
from datetime import datetime, timedelta
from skopt import gp_minimize
from skopt.space import Real

""" Change this bool to run backtest vs connect to websocket """
#set live trading, training
live = True

training = False
optimize = False #optimize during training to find best sigma and alpha

#interval
trading_interval = '60m'

#set tickers
ticker_bank = ['AMD', 'UBER', 'ENPH', 'LUMN', 'QNTM', 'PDD', 'SPOT', 'OKLO', 'SMCI', 'FN', 'PLTR', 'CYCN', 'PYPL', 'ROOT', 'FCCN', 'NNOX', 'XOM', 'ABBV', 'DECK', 'OXY', 'CLS', 'CIFR', 'UPS', 'ACON', 'FOXX', 'JL', 'V', 'TEAM', 'VST', 'AVGO, ''NBIS', 'FSLR', 'TEM', 'CELH', 'BLBX', 'FSLR', 'ARM', 'CRSP', 'ASTS', 'AA', 'SOUN', 'CAPR', 'WULF', 'BTCT', 'MARA', 'META', 'HOLO', 'SLDP', 'QS', 'NVO', 'LLY', 'SMCI', 'CELH', 'QCOM', 'TSLA', 'MRNA', 'LMT', 'BAC', 'JPM', 'QUIK', 'STM', 'MU', 'IBM', 'GM', 'SQM', 'ZBRA', 'HUSA', 'INDO', 'GME', 'AMC', 'PHUN', 'DJT', 'RUM', 'BRLS', 'RIVN', 'VVOS', 'UNG', 'RGEN', 'PTLO', 'ATOM', 'WOLF', 'FNMA', 'TGTX', 'NVDA', 'AAPL', 'RGTI', 'QUBT', 'XXII', 'DKNG', 'IONQ', 'QBTS', 'LAZR', 'HOOD', 'TSM', 'WIMI', 'FTAI', 'KOLD', 'PFE', 'VSAT', 'BOIL']
reserve = ['AMV', 'MOS', 'CANO', 'LVTX', 'MLCO', 'BIIB', 'ABOS', 'ATXI', 'INBX', 'CNTQ', 'LUCY', 'INPX', 'LFG', 'ZYME', 'CMG', 'ZVSA', 'MSGM', 'TOST', 'LUNR', 'OCEA', 'ATLX', 'BAER', 'HHRS', 'RETA', 'KBAL', 'AMBI', 'CDIO', 'CS', 'AXTI', 'PRST', 'EYPT', 'FFIE', 'ALL', 'SEZL', 'DTOC', 'ACIC', 'SLNO', 'PRZO', 'SECO', 'SASI', 'TPST', 'NKTX', 'SPRC', 'TGTX', 'ASPA', 'AIRE', 'LPA', 'KOSS', 'ZAPP', 'AZTR', 'KNSA']
#ticker_bank = ticker_bank + reserve

#set banned tickers
banned_tickers = ['AMC', 'GME', 'ATCH'] #'HOLO', 'AAPL', 'GOOG', 'ACON', 'DXF']

#grab random ticker_bank tickers or stocktwits grabber
rand_tickers = True
simulate = True #try using spaced out timeframes to simulate different trading periods

#variables
timeframes = []
industry_analysis = {}
sector_analysis = {}
history = 240 #how far back to go
period = 3 #how many days to segment each run into

iterations = 1 #how many times to do historical runs


""" These parameters influence the trading strategy """
params = {
    #'logging': False,
    #'stops': True,
    #'short_loss': .05,
    #'long_loss': .25,
    'exitbars': 9,
    'rsi1': 40, # <30
    'rsi2': 40, # > 70
    'rsi3': 50,
    'macd1': 40, # <0
    'macd2': 40, # >0
    'vwap1': 25, #sp > vwap
    'vwap2': 25, #sp < vwap
    'stoch1': 40, # < 20
    'stoch2': 40, # < 80
    'mktcap1': 1.15,
    'mktcap2': 1,
    'mktcap3': .85,
    'mktcap4': .5,
    'pricentile1': .25,
    'swing1': 40,
    'swing2': 40,
    'confidence_threshold': 75,
    'exit_threshold': 0,
}


def main():
    #single_ticker_test()
    #st.get_news('MRNA')
    #return

    if training:
        
        if optimize: # if optimizing for parameters
            optimizer()
        else:
            train(generations=500, sigma=.5, alpha=.01)
        return

    if not live:
        #run backtesting
        backtest()


def get_past_x_days(delta=59):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=delta)
    return [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')]

def get_timeframes(current_period):
    start_date = datetime.today() - timedelta(days=history) + timedelta(days=period*current_period-28)
    end_date = start_date + timedelta(days=period+28)
    timeframe = [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')]
    #print(timeframe)
    return timeframe

def get_tickers(amt=8,exclude=None):
    
    #randomly select tickers from ticker_bank for now until add stocktwits
    tickers = []
    if rand_tickers:
        for i in range(amt):
            tick = np.random.randint(0,len(ticker_bank)-1)
            if exclude != None:
                if ticker_bank[tick] in exclude:
                    continue
                
            tickers.append(ticker_bank[tick])
    else:
        tickers = ['DIA', 'SPY', 'QQQ', 'SMCI', 'FSLR', 'CAVA', 'AMD', 'MSTR', 'TSLA', 'VRT', 'RKLB', 'UCTT']
        tickers = ['DIA', 'SPY', 'QQQ', 'HIMS', 'TEM', 'ATCH', 'MARA', 'XPEV', 'LI', 'SMCI', 'RIOT', 'BTC']
        
        tickers = st.get_trending_stocks()
        #tickers = ticker_bank
        
    #remove banned tickers
    tickers = [ticker for ticker in tickers if ticker not in banned_tickers]
            
    return tickers
    
def create_frames(interval=trading_interval, startcash=10000, exclude=None, timeframe=[], tickerlist=[]):
        #get tickers
        if tickerlist == []:
            tickers = get_tickers(exclude=exclude)
        else:
            tickers = tickerlist
            
        #initialize yfin data 
        stocks = {}

        stockframe = yf.stockframe(tickerlist=tickers, timeframes=timeframe, interval=interval)
        stocks = stockframe.stocks
        
        #remove tickers if there isn't sufficient data available
        tickers_to_remove = []
        for stock, data in stocks.items():
            if len(data) < 28:
                tickers_to_remove.append(stock)
        for ticker in tickers_to_remove:
            stocks.pop(ticker)
        
        #grab current stocks to print
        tickers = list(stocks.keys())
            
        if not training:
            print('\nCurrent Stocks: ', tickers)
        
        return bt.tradeframe(stocks,startcash=startcash,interval=int(interval.replace('m','')),training=training,simulate=simulate)
    
    
def backtest(param_dict=params):
    runs = int(history/period) #how many runs to do
    
    #if training print what params using
    if training:
        print(param_dict)
        
    #if not simulating
    if not simulate:
        runs = 1
    
    #if multiple runs track total value to compute average
    total = 0
    last_end_value = 0
    total_trades = 0
    mean = 0
    std = 0
    runs_traded = 0
    results = []
    final_values = []
    

    try:
        file_read = True
        if simulate and not file_read or not simulate:
            #run numerous times
            for j in range(iterations):
                for i in range(runs):
                    #run
                    try:
                        startcash = 10000
                        if i != 0 and simulate: #if simulate, set end value to start value
                            startcash = last_end_value #for multiruns, set value
                        
                        #set time frames
                        timeframe = None
                        tickerlist = []
                        
                        if simulate: #simulate different trading periods
                            timeframe = get_timeframes(i)
                        else:
                            timeframe = get_past_x_days(history)
                        
                            
                        tradeframe = create_frames(startcash=startcash, timeframe=timeframe, tickerlist=tickerlist)
                        results = tradeframe.run(param_dict, commission=0.0, allow_short=True, period=period)
                        print(f"\nCompleted run {i+1}/{runs}")
                        
                        if runs > 1:
                            total += results[0].cerebro.broker.getvalue() - startcash
                            total_trades += results[0].num_trades
                            final_values.append((results[0].cerebro.broker.getvalue() - startcash)/startcash)
                            last_end_value = results[0].cerebro.broker.getvalue()
                            add_indsect(results[0].industry_analysis, results[0].sector_analysis)
                    except Exception as e:
                        print(f"Error occured during run {i+1}: {e}")
        elif simulate and file_read:
            try:
                data, start_date, end_date = SimulatorFileReader.get_data()
                tickers = data.keys()
                startcash = 10000
                
                date_object = datetime.strptime(start_date, '%Y-%m-%d').date()
                date_object -= timedelta(days=28)
                start_date = date_object.strftime('%Y-%m-%d')
                              
                try:
                    tradeframe = create_frames(startcash=startcash, timeframe=[start_date, end_date], tickerlist=tickers)
                    results = tradeframe.run(param_dict, commission=0.0, allow_short=True, period=1, tradeable_dates=data)
                except Exception as e:
                    print(f"Error with backtest: {e}")
                
                total += results[0].cerebro.broker.getvalue() - startcash
                total_trades += results[0].num_trades
                final_values.append((results[0].cerebro.broker.getvalue() - startcash)/startcash)
                last_end_value = results[0].cerebro.broker.getvalue()
                add_indsect(results[0].industry_analysis, results[0].sector_analysis)
            except Exception as e:
                print(f"Error with simulation: {e}")
    finally:
        #print stats
        if runs == 1: 
            tradeframe.stats()
        else:
            try:
                #calculate statistics
                final_values = np.array(final_values)
                runs_finished = len(final_values)
                print(f"\nAverage Profit: {np.mean(final_values)*100:.4f}%")
                print(f"Standard Deviation: {np.std(final_values):.4f}")
                print(f"Total Profit: {total:.2f}")
                
                #remove zeros
                final_values = final_values[final_values != 0]
                mean = np.mean(final_values)*100
                std = np.std(final_values)
                runs_traded = len(final_values)
                print(f"\nAverage Profit (no zeros): {mean:.4f}%")
                print(f"Standard Deviation (no zeros): {std:.4f}")
                print(f"Runs traded: {runs_traded}/{runs_finished}")
                
                #plot
                plt.bar(range(len(final_values)), final_values)
                plt.xlabel("Runs")
                plt.ylabel("Profit Gain (%)")
                plt.title("Profit by Run")
                plt.show()
                
                analyze = True
                if analyze and not training:
                    analyze_indsect()
            except Exception as e:
                print(f"Error generating graphs or statistics: {e}")
        
        if results != []:
            #save log
            fh = open("log.txt", 'w')
            for order in results[0].orderlog:
                fh.write(f"{order[0]}: {order[1]}\n")
        else:
            print("\nNo trading done.")
        
        #if training, send back stats
        if training:
            return {'mean': mean, 'std': std, 'total': total, 'num_trades': total_trades, 'runs_traded': runs_traded, 'runs_finished': runs_finished}
            
def single_ticker_test():
    timeframes.append(get_past_x_days(100))
    profit = {}
    tickers = ticker_bank
    tickers = [ticker for ticker in tickers if ticker not in banned_tickers]
    startcash = 10000
    for ticker in tickers:
        tradeframe = create_frames(startcash=startcash, timeframe=timeframes[0], tickerlist=[ticker])
        results = tradeframe.run(params, commission=0.0, allow_short=False)
        
        if results != []:
            profit[ticker] = ((results[0].cerebro.broker.getvalue() - startcash)/startcash)
    
    #calculate statistics
    profit_values = list(profit.values())
    profit_values = np.array(profit_values)
    print(f"\nAverage Profit: {np.mean(profit_values)*100:.2f}%")
    print(f"Standard Deviation: {np.std(profit_values):.2f}")
    print(f"Total Profit: {np.sum(profit_values):.2f}")

    #plot
    plt.bar(profit.keys(), profit_values)
    plt.xlabel("Ticker")
    plt.ylabel("Profit Gain (%)")
    plt.title("Profit by Ticker")
    plt.show()
    
def analyze_indsect(): #analyze by sector/industry
    print("\nIndustry/Sector Analysis:")
    print("\nIndustry, Profit")
    for key,value in industry_analysis.items():
        print(f"{key} ...... {value:.2f}")
    print("\nSector, Profit")
    for key,value in sector_analysis.items():
        print(f"{key} ...... {value:.2f}")
        #print(f"{trade[0]} -- Industry: {ind['industry']}, Sector: {ind['sector']}")
           
    #plot
    plt.bar(industry_analysis.keys(), industry_analysis.values())
    plt.xlabel("Industry")
    plt.ylabel("Profit")
    plt.title("Profit by Industry")
    plt.show()
    
    plt.bar(sector_analysis.keys(), sector_analysis.values())
    plt.xlabel("Sector")
    plt.ylabel("Profit")
    plt.title("Profit by Sector")
    plt.show()
    
def add_indsect(industry, sector):
    for key,value in industry.items():
        if key not in industry_analysis:
            industry_analysis[key] = value
        else:
            industry_analysis[key] += value
            
    for key,value in sector.items():
        if key not in sector_analysis:
            sector_analysis[key] = value
        else:
            sector_analysis[key] += value
    

#NN methods
def train(generations, sigma, alpha):
    param_keys=params.keys()
    net = alg.ParamOptimizerNet(param_keys=param_keys, filepath="nn_checkpoint.pth")

    #Train neural net
    net.train_nn(num_generations=generations, sigma=sigma, alpha=alpha)
    
def optimizer():
    space = [Real(0.01, 1, name='sigma'),
             Real(0.001, 0.1, name='alpha')]
    
    #run bayesian optimization
    res = gp_minimize(objective, space, n_calls = 10, random_state = 42)
    
    #best values
    best_sigma, best_alpha = res.x
    best_reward = -res.fun #convert back to positive
    
    result = f"Best sigma: {best_sigma:.4f}, Best alpha: {best_alpha:.4f}, Best Reward: {best_reward:.4f}"
    fh = open("Optimal_Sigma_Alpha.txt", "w")
    fh.write(result)
    print(result)
    
def objective(parameters):
    sigma, alpha = parameters
    print(f"\n Testing sigma={sigma:.4f}, alpha={alpha:.4f}")
    
    #init neural net
    param_keys=params.keys()
    net = alg.ParamOptimizerNet(param_keys=param_keys, filepath="nn_checkpoint.pth")

    #Train neural net
    net.train_nn(num_generations=50, sigma=sigma, alpha=alpha)
    
    final_reward = net.get_reward({key: val.item() for key, val in zip(param_keys, net.get_params())})
        
    print(f"Finished sigma={sigma:.4f}, Reward={final_reward:.4f}")
    
    return -final_reward #minimizing, so negative reward
    
def wait_until_open(seconds): #wait for market to open to retry websocket
    time.sleep(seconds)
    alpacawebsocket.live_trade(params)
    
    
#on run
if __name__ == "__main__":
    #do live trading
    if live:
        alpacawebsocket.live_trade(params)
    else: #otherwise do main stuff
        main()
    