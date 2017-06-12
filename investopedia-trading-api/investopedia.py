import mechanicalsoup
from enum import Enum
from collections import namedtuple
from bs4 import BeautifulSoup
import re


Status = namedtuple("Status", "account_val buying_power cash annual_return")
Portfolio = namedtuple("Portfolio", "bought options shorted")
Security = namedtuple("Security", "symbol description quantity purchase_price current_price current_value gain_loss")
Trade = namedtuple("Trade", "date_time description symbol quantity")


class Action(Enum):
    buy = 1
    sell = 2
    short = 3
    cover = 4


class Duration(Enum):
    day_order = 1
    good_cancel = 2


class Account:
    BASE_URL = 'http://www.investopedia.com'

    def __init__(self, email, password):
        """
        Logs a user into Investopedia's trading simulator,
        given a *username* and *password*.
        """

        self.br = br = mechanicalsoup.Browser()
        login_page = self.fetch("/accounts/login.aspx?returnurl=http://www.investopedia.com/simulator/")

        # you have to select the form before you can input information to it
        # the login form used to be at nr=2, now it's at nr=0
        login_form = login_page.soup.select("form#account-api-form")[0]
        login_form.select("#edit-email")[0]["value"] = email
        login_form.select("#edit-password")[0]["value"] = password
        br.submit(login_form, login_page.url)

    def fetch(self, url):
        url = '%s%s' % (self.BASE_URL, url)
        return self.br.get(url)

    def get_portfolio_status(self):
        """
        Returns a Status object containing account value,
        buying power, cash on hand, and annual return.
        Annual return is a percentage.
        """

        response = self.fetch('/simulator/portfolio/')

        parsed_html = response.soup

        # The ids of all the account information values
        acct_val_id = "ctl00_MainPlaceHolder_currencyFilter_ctrlPortfolioDetails_PortfolioSummary_lblAccountValue"
        buying_power_id = "ctl00_MainPlaceHolder_currencyFilter_ctrlPortfolioDetails_PortfolioSummary_lblBuyingPower"
        cash_id = "ctl00_MainPlaceHolder_currencyFilter_ctrlPortfolioDetails_PortfolioSummary_lblCash"
        return_id = "ctl00_MainPlaceHolder_currencyFilter_ctrlPortfolioDetails_PortfolioSummary_lblAnnualReturn"

        # Use BeautifulSoup to extract the relevant values based on html ID tags
        account_value = parsed_html.find('span', attrs={'id': acct_val_id}).text
        buying_power = parsed_html.find('span', attrs={'id': buying_power_id}).text
        cash = parsed_html.find('span', attrs={'id': cash_id}).text
        annual_return = parsed_html.find('span', attrs={'id': return_id}).text

        # We want our returned values to be floats
        # Use regex to remove non-numerical or decimal characters, but keep - (negative sign)
        regexp = "[^0-9.-]"
        account_value = float(re.sub(regexp, '', account_value))
        buying_power = float(re.sub(regexp, '', buying_power))
        cash = float(re.sub(regexp, '', cash))
        annual_return = float(re.sub(regexp, '', annual_return))

        return Status(
            account_val=account_value,
            buying_power=buying_power,
            cash=cash,
            annual_return=annual_return,
        )

    def get_current_securities(self):
        """
        Returns a Portfolio object containing:
        bought securities, options, and shorted securities
        Each of theses are lists of Securities objects containing:
        symbol description quantity purchase_price current_price current_value gain_loss
        """
        response = self.fetch('/simulator/portfolio/')
        soup = BeautifulSoup(response.content, "html.parser")

        stock_table = soup.find("table", id="stock-portfolio-table").find("tbody")
        option_table = soup.find("table", id="option-portfolio-table").find("tbody")
        short_table = soup.find("table", id="short-portfolio-table").find("tbody")

        print(stock_table.find_all("tr"))


    def get_open_trades(self):
        """
        Return ___ Object of the currently open trades
        """
        response = self.fetch('/simulator/trade/showopentrades.aspx')
        parsed_html = response.soup

        openTable = parsed_html.find('table', attrs={'class':'table1'}).text
        openTable_trimmed = openTable.split("\n")[15:-3]
        i = 0
        openTrades = []
        while i+1 < len(openTable_trimmed):
            trade = Trade(
                date_time=openTable_trimmed[i+2],
                description=openTable_trimmed[i+3],
                symbol=openTable_trimmed[i+4],
                quantity=float(openTable_trimmed[i+5])
            )
            openTrades.append(trade)
            i=i+12
        return openTrades

    def trade(self, symbol, orderType, quantity, priceType="Market", price=False, duration=Duration.good_cancel):
        """
        Executes trades on the platform. See the readme.md file
        for examples on use and inputs. Returns True if the
        trade was successful. Else an exception will be
        raised.

        client.trade("GOOG", Action.buy, 10)
        client.trade("GOOG", Action.buy, 10, "Limit", 500)
        """

        br = self.br
        trade_page = self.fetch('/simulator/trade/tradestock.aspx')
        trade_form = trade_page.soup.select("form#orderForm")[0]

        # input symbol, quantity, etc.
        trade_form.select("input#symbolTextbox")[0]["value"] = symbol
        trade_form.select("input#quantityTextbox")[0]["value"] = str(quantity)

        # input transaction type
        [option.attrs.pop("selected","") for option in trade_form.select("select#transactionTypeDropDown")[0]("option")]
        trade_form.select("select#transactionTypeDropDown")[0].find("option", {"value":str(orderType.value)})["selected"] = True

        # input price type
        [radio.attrs.pop("checked","") for radio in trade_form("input", {"name":"Price"})]
        trade_form.find("input", {"name":"Price", "value": priceType})["checked"]=True

        # input duration type
        [option.attrs.pop("selected","") for option in trade_form.select("select#durationTypeDropDown")[0]("option")]
        trade_form.select("select#durationTypeDropDown")[0].find("option", {"value":str(duration.value)})["selected"] = True

        # if a limit or stop order is made, we have to specify the price
        if price and priceType == "Limit":
            trade_form.select("input#limitPriceTextBox")[0]["value"] = str(price)

        elif price and priceType == "Stop":
            trade_form.select("input#stopPriceTextBox")[0]["value"] = str(price)

        prev_page = br.submit(trade_form, trade_page.url)
        prev_form = prev_page.soup.find("form", {"name": "simTradePreview"})
        br.submit(prev_form, prev_page.url)

        return True


def get_quote(symbol):
    BASE_URL = 'http://www.investopedia.com'
    """
    Returns the Investopedia delayed price of a given symbol
    """
    br = mechanicalsoup.Browser()
    response = br.get(BASE_URL + '/markets/stocks/'+symbol.lower())
    quote_id = "quotePrice"
    parsed_html = response.soup
    try:
        quote = parsed_html.find('td', attrs={'id': quote_id}).text
    except:
        print("Security not found.")
        return False
    return float(quote)
