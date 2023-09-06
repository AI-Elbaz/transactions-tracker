import os
import requests
import gspread
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup, SoupStrainer

load_dotenv()


class Tracker:
    KHAMSAT_URL = "https://khamsat.com/credit"
    MOSTAQL_URL = "https://mostaql.com/payments"
    HEADERS = {
        "accept": "application/json",
        "accept-language": "en-US,en;q=0.9,ar;q=0.8",
        "content-type": "application/json; charset=UTF-8",
        "sec-ch-ua": "\"Not/A)Brand\";v=\"99\", \"Google Chrome\";v=\"115\", \"Chromium\";v=\"115\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-locale": "ar",
        "x-ui-version": "4efcf446-a4c6-412e-8d69-8fa9344b35fe",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    KHAMSAT_COOKIES = {
        'rack.session': os.environ.get('KHAMSAT_SESSION'),
    }
    MOSTAQL_COOKIES = {
        'mostaqlweb': os.environ.get('MOSTAQL_SESSION'),
    }
    SESSION = requests.Session()
    SESSION.headers.update(HEADERS)

    def __init__(self) -> None:
        pass

    @classmethod
    def get_transactions(cls):
        khamsat = cls._get_khamsat_transactions()
        mostaql = cls._get_mostaql_transactions()

        transactions = khamsat + mostaql
        transactions.sort(key=lambda a: a['date'])

        for t in transactions:
            t['date'] = t['date'].strftime('%m/%d/%Y')

        return transactions

    @classmethod
    def _get_khamsat_transactions(cls):
        result = []

        with cls.SESSION as s:
            s.cookies.update(cls.KHAMSAT_COOKIES)
            r = s.get(cls.KHAMSAT_URL)

            soup = BeautifulSoup(
                r.text, "lxml",
                parse_only=SoupStrainer('table', {"id": "payments_table"})
            )

            payments = soup.find_all('tr')

            for payment in payments:
                amount = float(
                    payment.find(
                        'div', {"class": "payment_amount"}
                    ).find_all('span')[-1].text.replace('$', ''))

                link = f"https://khamsat.com{payment.find('a')['href']}"
                date = payment.find(
                    'ul', {'class': 'details-list'}).find('li').text.strip()

                result.append({
                    'id': link.split('/')[-1],
                    'amount': amount,
                    'link': link,
                    'date': datetime.strptime(date, "%d/%m/%Y"),
                })

        result.reverse()
        return result

    @classmethod
    def _get_mostaql_transactions(cls):
        result = []

        with cls.SESSION as s:
            s.cookies.update(cls.MOSTAQL_COOKIES)
            r = s.get(cls.MOSTAQL_URL)

            with open('index.html', 'w', encoding='utf-8') as f:
                f.write(r.text)

            soup = BeautifulSoup(
                r.text, "lxml",
                parse_only=SoupStrainer(
                    'tbody', {"data-filter": "paymentsCollection"})
            )

            payments = soup.find_all('tr')

            for payment in payments:
                amount = float(
                    payment.find(
                        'div', {"class": "payment__amount"}
                    ).find('span').text.replace('$', ''))

                link = payment.find('a')['href'].split('-')[0]
                date = payment.find('time').text.strip()

                result.append({
                    'id': link.split('/')[-1],
                    'amount': amount,
                    'link': link,
                    'date': datetime.strptime(date, "%d/%m/%Y"),
                })

        result.reverse()
        return result


if __name__ == '__main__':
    client = gspread.service_account("credentials.json")
    SHEET = client.open_by_url(os.environ.get('SHEET_URL')).sheet1

    old_transations = SHEET.col_values(1)
    transactions = Tracker.get_transactions()

    index = len(old_transations)

    for transaction in [i for i in transactions if not i['id'] in old_transations]:

        SHEET.append_row(
            [transaction[key] for key in ['id', 'date', 'amount']],
            table_range=f'A:C',
            value_input_option='USER_ENTERED'
        )
