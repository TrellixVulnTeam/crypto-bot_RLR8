import data_handling as d
import json
import csv
import datetime as dt
from binance.client import Client 
import os 
import time
import math

with open('config/config.json', 'r') as config:
    configs = json.load(config)
    client = Client(configs["api"], configs["secret"])
    alts = configs["alts"]

starting_amt_btc = 0
next_buytime = 0

def main():
    print(choose_alt_buy())
    print(choose_alt_sell())
    #while True:
    #    trade()
    #    report()
    #    time.sleep(60)

def report():
    init_report()
    time = dt.datetime.now.strftime("%d/%m/%Y %H:%M:%S")
    value_of_portfolio = d.get_account_balance_USD()
    value_of_btc = starting_amt_btc * d.get_current_price("BTCBUSD")
    gain = ((value_of_portfolio - value_of_btc)/value_of_btc)*100
    with open("portfolio_value.csv", 'a') as pv:
        writer =csv.DictWriter(pv, fieldnames = ["time", "portfolio value", "value of initial investment", "percentage gain/loss"])
        row = {'time': time, 'portfolio value': value_of_portfolio, 'value of initial investment': value_of_btc, 'percentage gain/loss': gain}
        writer.writerow(row)
        
def init_report():
    if os.path.exists("portfolio_value.csv"):
        return
    with open('portfolio_value.csv', 'w') as pv:
        writer = csv.DictWriter(pv, fieldnames = ["time", "portfolio value", "value of initial investment", "percentage gain/loss"])
        writer.writeheader()


def trade():
    if buy():
        alt = choose_alt_buy()
        if alt is None:
            return
        else:
            symbol = alt+"BTC"
            qty = d.get_asset_free_balance("BTC")
            #btc_price = d.get_current_price("BTCUSDT")
            #default buy amt is minimum transaction value of 0.0001 btc 
            if qty < 0.0001:
                return
            else:
                btc_qty = 0.0001
            price = d.get_current_price(symbol)
            order_qty=btc_qty/price
            order = client.order_limit_buy(symbol=symbol,quantity=order_qty,price=price)
            d.log_transaction(alt, "buy", price, btc_qty, order_qty)
            next_buytime = dt.datetime.now() + dt.timedelta(minutes=15)
    elif sell():
        alt = choose_alt_sell()
        if alt is None:
            return
        else:
            symbol = alt+"BTC"
            qty = d.get_asset_free_balance(alt)
            order_qty = qty/2
            price = d.get_current_price(symbol)
            if price * order_qty < 0.0001:
                if price * qty < 0.0001:
                    return
                else:
                    order_qty = 0.0001/price
            order = client.limit_order_sell(symbol=symbol, quantity=order_qty, price=price)
            d.log_transaction(alt,"sell",price, (price * order_qty), order_qty)


def buy():
    #if BTC dominance up, price up or sideways, and strong movement towards greed
    #add 30 day sma?
    if (d.get_btc_dominance_change() > 0 
    and d.get_current_price("BTCUSDT") - d.get_sma(30, "BTCUSDT") > 0 
    and (d.get_fear_index_change_nominal("d") > 20 or d.get_fear_index_change_nominal("w") > 20)):
        return True
    return False

def sell():
    if (d.get_btc_dominance_change() < 0 
    and d.get_current_price("BTCUSDT") - d.get_sma(30,"BTCUSDT") < 0 
    and (d.get_fear_index_change_nominal("d") < -20 or d.get_fear_index_change_nominal("w") < -20)):
        return True
    return False

def get_last_24h(buy_or_sell):
    if not os.path.exists("transactions.log"):
        return []
    with open("transactions.log", 'r') as t:
        alts = []
        reader = csv.reader(t)
        for row in reversed(list(reader)):
            if row[1] != buy_or_sell:
                continue
            time = row[-1]
            time_obj = dt.datetime.striptime(time, "%d/%m/%Y %H:%M:%S")
            now = dt.datetime.now()
            if now - dt.timedelta(hours=24) <= time_obj <= now:
                alts.append(row[0])
            else:
                return alts
    return alts

def choose_alt_buy():
    prices = get_relative_prices()
    #remove alts that have trades in the last 24 hrs 
    rm = get_last_24h("buy")
    #rate limiting
    tdelta = last_buy_timestamp - dt.datetime.now().timestamp()
    if next_buytime != 0:
        if dt.datetime.now() < next_buytime:
            return None
    #mechanism for not buying asset in freefall (3 red days)
    for key, val in prices.items():
        symbol = key+"BTC"
        if d.get_sma(3, symbol) > d.get_sma(2, symbol) > d.get_sma(1, symbol):
            rm.append(key)
    #remove unwanted buys 
    for key in rm:
        del prices[key]
    #find best prices buy option
    target = min(prices.values())
    for key, value in prices.items():
        if value == target:
            return key

def get_relative_prices():
    relative_prices = {}
    for alt in alts:
        symbol = alt+"BTC"
        relative_prices[alt] = (d.get_current_price(symbol) - d.get_sma(30, symbol))/d.get_sma(30, symbol)
    return relative_prices

def choose_alt_sell():
    prices = get_relative_prices()
    target = max(prices.values())
    for key in get_last_24h("sell"):
        del prices[key]
    while True == True:
        for key, value in prices.items():
            if value == target:
                if d.get_current_price(key+"BTC") > d.get_avg_buy_price(key):
                    return key
                else:
                    prices[key] = -math.inf
                    target = max(prices.values())
        if prices.values().count(-math.inf) == len(prices.values()):
            return None


if __name__ == '__main__':
    main()