import time
import pyupbit
import datetime
import schedule
import requests
# from fbprophet import Prophet
import numpy as np

access = ""
secret = ""
myToken = ""

def get_ror(df, k=0.5): 
    # df = pyupbit.get_ohlcv("KRW-ADA", count=7)
    df['range'] = (df['high'] - df['low']) * k
    df['target'] = df['open'] + df['range'].shift(1)

    df['ror'] = np.where(df['high'] > df['target'],
                         df['close'] / df['target'],
                         1)

    ror = df['ror'].cumprod()[-2]
    return ror

def get_best_k(df):
  max_ror = 1
  best_k = 0.5
  for k in np.arange(0.1, 1.0, 0.05):
      ror = get_ror(df, k)
      # print("%.2f %f" % (k, ror))
      if ror > max_ror:
        max_ror = ror
        best_k = k
  # print(max_ror, best_k)
  return best_k

# k = get_best_k(df)
# print(k)

def get_target_price(ticker, k):
    """변동성 돌파 전략으로 매수 목표가 조회"""
    df = pyupbit.get_ohlcv(ticker, interval="minute60", count=2)
    target_price = df.iloc[0]['close'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * k
    return target_price

def get_start_time(ticker):
    """시작 시간 조회"""
    df = pyupbit.get_ohlcv(ticker, interval="day", count=1)
    start_time = df.index[0]
    return start_time

def get_balance(ticker):
    """잔고 조회"""
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker:
            if b['balance'] is not None:
                return float(b['balance'])
            else:
                return 0
    return 0

def get_current_price(ticker):
    """현재가 조회"""
    return pyupbit.get_orderbook(ticker=ticker)["orderbook_units"][0]["ask_price"]


# predicted_close_price = 0

# def predict_price(ticker):
#     """Prophet으로 당일 종가 가격 예측"""
#     global predicted_close_price
#     df = pyupbit.get_ohlcv(ticker, interval="minute60")
#     df = df.reset_index()
#     df['ds'] = df['index']
#     df['y'] = df['close']
#     data = df[['ds','y']]
#     model = Prophet(yearly_seasonality=True, weekly_seasonality=True)
#     model.fit(data)
#     future = model.make_future_dataframe(periods=24, freq='H')
#     forecast = model.predict(future)
#     closeDf = forecast[forecast['ds'] == forecast.iloc[-1]['ds'].replace(hour=9)]
#     if len(closeDf) == 0:
#         closeDf = forecast[forecast['ds'] == data.iloc[-1]['ds'].replace(hour=9)]
#     closeValue = closeDf['yhat'].values[0]
#     predicted_close_price = closeValue

# predict_price("KRW-ADA")
# schedule.every().hour.do(lambda: predict_price("KRW-ADA"))

def get_ma15(ticker):
    """15일 이동 평균선 조회"""
    df = pyupbit.get_ohlcv(ticker, interval="minute60")
    ma15 = df['close'].rolling(15).mean().iloc[-1]
    return ma15

def post_message(token, channel, text):
    """슬랙 메시지 전송"""
    response = requests.post("https://slack.com/api/chat.postMessage",
        headers={"Authorization": "Bearer "+token},
        data={"channel": channel,"text": text})

# 로그인
upbit = pyupbit.Upbit(access, secret)
print("autotrade start")
post_message(myToken,"#upbit-notice", "autotrade start")


#예측 기준
df = pyupbit.get_ohlcv("KRW-ADA", interval="minute60", count=200)

budget = 1000000

# 자동매매 시작
while True:
    try:
        now = datetime.datetime.now()
        start_time = get_start_time("KRW-ADA") + datetime.timedelta(seconds=50000)
        end_time = start_time + datetime.timedelta(days=1)
        schedule.run_pending()

        k = get_best_k(df)
        target_price = get_target_price("KRW-ADA", k)
        current_price = get_current_price("KRW-ADA")
        ma15 = get_ma15("KRW-ADA")
        if upbit.get_avg_buy_price(ticker="KRW-ADA") != None:
          avg_buy_price = upbit.get_avg_buy_price(ticker="KRW-ADA") 

        if start_time < now < end_time - datetime.timedelta(seconds=1800):
            ada = get_balance("ADA")
            if (target_price < current_price) and (ma15 < current_price):
                # krw = get_balance("KRW")
                if budget > 5000:
                  buy_result = upbit.buy_market_order("KRW-ADA", budget*0.90)
                  post_message(myToken,"#upbit-notice", "ADA buy : " +str(buy_result))
                  budget = budget*90
            elif (ada != 0) and (avg_buy_price*1.055 < current_price):
              ada = get_balance("ADA")
              if ada > 10:
                sell_result = upbit.sell_market_order("KRW-ADA", ada)
                post_message(myToken,"#upbit-notice", "1.05 profit \n\
                  ADA sell : " +str(sell_result))              
                budget += (ada*current_price)
            elif (ada != 0) and (avg_buy_price*0.75 > current_price):
              ada = get_balance("ADA")
              if ada > 10:
                sell_result = upbit.sell_market_order("KRW-ADA", ada)
                budget += (ada*current_price)
                profit = (current_price - avg_buy_price)*ada
                post_message(myToken,"#upbit-notice", "0.75 loss \n\
                  ADA sell : " +str(sell_result) + "\nLoss" + str(profit))              
                
        else:
            ada = get_balance("ADA")
            if ada > 10:
              sell_result = upbit.sell_market_order("KRW-ADA", ada)
              budget += ada*current_price
              profit = (current_price - avg_buy_price)*ada
              post_message(myToken,"#upbit-notice", "0.75 loss \n\
                ADA sell : " +str(sell_result) + "\nLoss" + str(profit))  
        time.sleep(1)

    except Exception as e:
        print(e)
        post_message(myToken,"#upbit-notice", e)
        time.sleep(1)
