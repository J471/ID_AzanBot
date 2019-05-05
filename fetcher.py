#!/home/untorojati/python/id_azanbot/id_azanbot_env/bin/python

# Constants
from constants import KEMENAG_DIR

# Enable logging
import logging
logging.basicConfig(format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# HTTP get utilities
import requests, shutil

# Date/Time utilities
import datetime

# Argument utilities
import sys, getopt

# File utilities
import os

# JSON utilities
import json

# MongoDB connection
from pymongo import MongoClient
from credentials import DBNAME, DBUSER, DBPASS, DBAUTH
client = MongoClient()
db = client[DBNAME]
db.authenticate(DBUSER, DBPASS, source=DBAUTH)

# Global variable
gv_usage = 'fetcher.py -m <month delta in positive integer>'


def main(argv):
    # [START checking arguments]
    if not argv:
        print(gv_usage)
        sys.exit()
    else:
        try:
            opts, args = getopt.getopt(argv,"hm:",["help", "month="])
        except getopt.GetoptError:
            print(gv_usage)
            sys.exit(2)

        for opt, arg in opts:
            if opt in ('-h', '--help'):
                print(gv_usage)
                sys.exit()
            elif opt in ('-m', '--month'):
                try:
                    lv_curmo = int(arg)
                except ValueError:
                    print(gv_usage)
                    sys.exit()
                else:
                    if lv_curmo < 0:
                        print(gv_usage)
                        sys.exit()
    # [END checking arguments]
           
    utctime = datetime.datetime.utcnow()
    utctime = utctime.replace(hour=0, minute=0, second=0, microsecond=0)
    utctime = utctime + datetime.timedelta(lv_curmo*365/12)

    curyrmo = utctime.date().year*100 + utctime.date().month
    lv_year = utctime.date().year
    lv_month = utctime.date().month

    #To get zones that already migrated to new key. fxpara is used for this checking
    czones_qry = db.czones.find({"flstfl": {"$lt": curyrmo}, "fxpara": {"$ne": "default"}})
    #Testing purpose
    #czones_qry = db.czones.find({"_id": 667, "flstfl": {"$lt": curyrmo}})

    if czones_qry.count() > 0:
        #lt_headers = []

        lv_cookies = {
            'PHPSESSID': '9e7o76vqm58eko31pbi3n82pu1',
            'cookiesession1': '52CC16C5LVZCRPUOGEJQNB3AMDK781A8',
            'ci_session': 'a%3A5%3A%7Bs%3A10%3A%22session_id%22%3Bs%3A32%3A%228f7a3746f330b4f5c1bb8cd434c63ed3%22%3Bs%3A10%3A%22ip_address%22%3Bs%3A12%3A%22103.7.15.100%22%3Bs%3A10%3A%22user_agent%22%3Bs%3A115%3A%22Mozilla%2F5.0+%28Windows+NT+10.0%3B+Win64%3B+x64%29+AppleWebKit%2F537.36+%28KHTML%2C+like+Gecko%29+Chrome%2F73.0.3683.103+Safari%2F537.36%22%3Bs%3A13%3A%22last_activity%22%3Bi%3A1556065208%3Bs%3A9%3A%22user_data%22%3Bs%3A0%3A%22%22%3B%7D5f7e5c53d6dbe752d5fca3534c689c9f',
        }

        lv_headers = {
            'Origin': 'https://bimasislam.kemenag.go.id',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Referer': 'https://bimasislam.kemenag.go.id/jadwalshalat',
            'X-Requested-With': 'XMLHttpRequest',
            'Connection': 'keep-alive',
        }

        lv_url = 'https://bimasislam.kemenag.go.id/ajax/getShalatbln'

        for doc_czones_qry in czones_qry:

            lv_data = {
                'x': doc_czones_qry.get('fxpara'),
                'y': doc_czones_qry.get('fypara'),
                'bln': str(lv_month),
                'thn': str(lv_year),
            }

            #url = 'https://bimasislam.kemenag.go.id/ajax/getShalatbln{}&bulan={}&lokasi={}&h=0&type=html'.format(lv_year, lv_month, doc_czones_qry.get('fnewid'))
            try:
                r = requests.post(lv_url, headers=lv_headers, cookies=lv_cookies, data=lv_data)

            except requests.exceptions.RequestException as e:
                logging.exception('Requests Exception: {}'.format(e))
                break
            else:
                if r.status_code == 200:
                    #lv_filename = '{}{}_{}.html'.format(KEMENAG_DIR, curyrmo, doc_czones_qry.get('_id'))
                    #Change from html and start using json
                    lv_filename = '{}{}_{}.json'.format(KEMENAG_DIR, curyrmo, doc_czones_qry.get('_id'))

                    if r.json()['message'] == 'Success':
                        #with open(lv_filename, 'wb') as out_file:
                        with open(lv_filename, 'w') as out_file:
                            #shutil.copyfileobj(r.raw, out_file)
                            json.dump(r.json(), out_file)

                        if os.path.getsize(lv_filename) < 1:
                            os.remove(lv_filename)
                            logging.exception('Error creating file {}!'.format(lv_filename))
                            del r
                        else:
                            czones_upd = db.czones.update_one(
                                            {"_id": doc_czones_qry.get('_id')}, 
                                            {"$set": {"flstfl": curyrmo }}                            
                                         )

                            logging.info('File {} is created successfully.'.format(lv_filename))
                            del r
                            
                    else:
                        logging.exception('Requests Parameter Error: {} - {}'.format(r, doc_czones_qry.get('_id')))
                        break
                    
                else:
                    logging.exception('Requests Status Error: {}'.format(r))
                    break
    else:
        logging.info('No files need to be downloaded!')


if __name__ == "__main__":
    main(sys.argv[1:])