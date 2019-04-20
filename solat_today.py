#!/home/untorojati/python/id_azanbot/id_azanbot_env/bin/python

# Enable logging
import logging
logging.basicConfig(format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Date/Time utilities
import datetime

# Argument utilities
import sys, getopt

# File utilities
import re

# JSON utilities
import json

# MongoDB connection
from pymongo import MongoClient
from credentials import DBNAME, DBUSER, DBPASS, DBAUTH
client = MongoClient()
db = client[DBNAME]
db.authenticate(DBUSER, DBPASS, source=DBAUTH)

# Constants
from constants import KEMENAG_DIR

# Global variable
gv_usage = 'solat.py -d <time difference with UTC>'


def prayertimeupdate(lv_localtimezone, localtime, lv_time, lv_doc_czones_qry_id, lv_ftypes):
    lv_time = lv_time.replace('.',':')
    if ':' in lv_time:
        ftimes = datetime.datetime.strptime('{} {}'.format(localtime.date(), lv_time), '%Y-%m-%d %H:%M')

        #converting ptimes to UTC for the storing into collection
        utcftimes = ftimes + datetime.timedelta(hours = -1*lv_localtimezone)

        doc_csched_qry = db.csched.find_one({"_id": utcftimes, "fazfor.czones_id": lv_doc_czones_qry_id, "fazfor.ftypes": lv_ftypes})

        if doc_csched_qry == None:
            csched_upd = db.csched.update_one(
                            {"_id": utcftimes}, 
                            #{"$addToSet": { "fazfor": { "$each": [ { "czones_id": lv_doc_czones_qry_id, "ftypes": lv_ftypes } ] } } }, 
                            {"$addToSet": {"fazfor": {"czones_id": lv_doc_czones_qry_id, "ftypes": lv_ftypes}}} , 
                            upsert = True
                         )
            logging.info('Update is done for {} {} {}.'.format(utcftimes, lv_doc_czones_qry_id, lv_ftypes))
    else:
        logging.exception('{} contains incorrect time format for {}!'.format(lv_doc_czones_qry_id, lv_ftypes))


def prayertimeparser(lv_localtimezone, localtime, czones_qry):
        curyrmo = localtime.date().year*100 + localtime.date().month

        #Read prayer time from file list
        for doc_czones_qry in czones_qry:
            #lv_filename = '{}{}_{}.html'.format(KEMENAG_DIR, curyrmo, doc_czones_qry.get('_id'))
            #Change and start using json
            lv_filename = '{}{}_{}.json'.format(KEMENAG_DIR, curyrmo, doc_czones_qry.get('_id'))
            try:
                with open(lv_filename) as out_file:
                    file_content = out_file.read()

            except:
                logging.exception('Caught exception reading file {}'.format(lv_filename))

            else:
                #ltimes_all = re.findall('\d{1,2}[:.]\d{1,2}',file_content)
                ltimes_all = json.loads(file_content)

                if not ltimes_all:
                    logging.exception('{} has no prayer time!'.format(lv_filename))
                else:
                    #Updating csched colletion
                    prayertimeupdate(lv_localtimezone, localtime, ltimes_all['data']['{0:%Y-%m-%d}'.format(localtime)]['imsak'], doc_czones_qry.get('_id'), 'Imsak')
                    prayertimeupdate(lv_localtimezone, localtime, ltimes_all['data']['{0:%Y-%m-%d}'.format(localtime)]['subuh'], doc_czones_qry.get('_id'), 'Subuh')
                    prayertimeupdate(lv_localtimezone, localtime, ltimes_all['data']['{0:%Y-%m-%d}'.format(localtime)]['terbit'], doc_czones_qry.get('_id'), 'Terbit')
                    prayertimeupdate(lv_localtimezone, localtime, ltimes_all['data']['{0:%Y-%m-%d}'.format(localtime)]['dzuhur'], doc_czones_qry.get('_id'), 'Zuhur')
                    prayertimeupdate(lv_localtimezone, localtime, ltimes_all['data']['{0:%Y-%m-%d}'.format(localtime)]['ashar'], doc_czones_qry.get('_id'), 'Asar')
                    prayertimeupdate(lv_localtimezone, localtime, ltimes_all['data']['{0:%Y-%m-%d}'.format(localtime)]['maghrib'], doc_czones_qry.get('_id'), 'Magrib')
                    prayertimeupdate(lv_localtimezone, localtime, ltimes_all['data']['{0:%Y-%m-%d}'.format(localtime)]['isya'], doc_czones_qry.get('_id'), 'Isya')


def main(argv):
    # [START checking arguments]
    if not argv:
        print(gv_usage)
        sys.exit()
    else:
        try:
            opts, args = getopt.getopt(argv,"hd:",["help", "diff="])
        except getopt.GetoptError:
            print(gv_usage)
            sys.exit(2)

        for opt, arg in opts:
            if opt in ('-h', '--help'):
                print(gv_usage)
                sys.exit()
            elif opt in ('-d', '--diff'):
                try:
                    lv_localtimezone = float(arg)
                except ValueError:
                    print(gv_usage)
                    sys.exit()
    # [END checking arguments]

    utctime = datetime.datetime.utcnow()
    #Get one day after to be able to get next day schedule
    #utctime += datetime.timedelta(days = 1)
    #Testing purpose
    utctime += datetime.timedelta(days = 0)

    utctime = utctime.replace(minute=0, second=0, microsecond=0)
    localtime = utctime + datetime.timedelta(hours = lv_localtimezone)

    #Getting midnight of localtime
    localtime = localtime.replace(hour=0)

    #Getting utctime for midnight of localtime
    utctime = localtime + datetime.timedelta(hours = -1*lv_localtimezone)

    #To get zones that already migrated to new key. fxpara is used for this checking
    czones_qry = db.czones.find({"ftzone": lv_localtimezone, "fxpara": {"$ne": "default"}}, {"_id": 1})
    #Testing purpose
    #czones_qry = db.czones.find({"_id": 667, "ftzone": lv_localtimezone}, {"_id": 1})

    if czones_qry.count() > 0:
        #Parsing KEMENAG file
        prayertimeparser(lv_localtimezone, localtime, czones_qry)
    else:
        logging.exception('UTC{} is not found in czones collection!'.format(lv_localtimezone)) 


if __name__ == "__main__":
    main(sys.argv[1:])
