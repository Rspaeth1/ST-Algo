# ST Algo

This was my first attempt at making an algorithmic trading bot. The live trading implementation was not finished.  
At the time of creation, I was not using jupyter notebook, leading to slow and messy development.  
I will revisit this idea later on after the CME futures competition, where I am implementing better market research.  
With the foundation I have on that, I think development of this project will be significantly more rigorous.  

## Methodology

- Trade momentum on trending tickers based on sentiment from stock messaging boards (StockTwits)
- Download historical data and backtest strategies (I started taking note of trending tickers that had exceptional growth for a little while)
- Use machine learning to optimize trading strategy weights
- Connect to live brokerage for paper trading
- Potential to implement GPT-API for news sentiment analysis

## Libraries Used

- Pandas, Numpy
- Backtester (although admittedly not implemented very well)
- PyTorch
