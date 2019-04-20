#!/home/untorojati/python/id_azanbot/id_azanbot_env/bin/python

# Constants
from constants import (LOCAL_DAY, LOCAL_MONTH, HIJRI_MONTH,
                       MAX_OFFSET, SLEEPDURATION, MAX_MESSAGE)

# Enable logging
import logging
logging.basicConfig(format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Date/Time utilities
import datetime, time

# Argument utilities
import sys, getopt

# Hijri conversion utilities
from umalqurra.hijri_date import HijriDate

# MongoDB connection
from pymongo import MongoClient
from credentials import DBNAME, DBUSER, DBPASS, DBAUTH
client = MongoClient()
db = client[DBNAME]
db.authenticate(DBUSER, DBPASS, source=DBAUTH)

# Telegram Bot utilities
#import telegram
from credentials import TOKEN, HOSTNAME, LOG_CHATID
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

from telegram import (Bot, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply, 
                      ReplyKeyboardMarkup, ReplyKeyboardRemove)

from telegram.error import (TelegramError, Unauthorized, BadRequest, 
                            TimedOut, ChatMigrated, NetworkError)


# Global variable
bot = Bot(TOKEN)
gv_usage = 'azan.py -m <minutes before azan>'
msgcounter = 0


def sendmsg(chat_id, msg):
    global msgcounter 
    
    try:
        bot.send_message(chat_id, text=msg, parse_mode='Markdown')

    except Unauthorized:
        # handle blocked bot
        doc_cusers_qry = db.cusers.find_one({"_id": chat_id})

        if doc_cusers_qry is not None:
            cusers_upd = db.cusers.update_one(
                            {"_id": chat_id}, 
                            {"$set": {"fblock": True }}
                         )

        logger.info('[Unauthorized] Send message to {} caused error'.format(chat_id))

    except BadRequest as e:
        # handle malformed requests
        logger.warn('[BadRequest] Send message to {} caused error: {}'.format(chat_id, e.message))

    except TimedOut:
        # handle slow connection problems
        logger.warn('[TimedOut] Send message to {} caused error'.format(chat_id))

    except NetworkError as e:
        # handle other connection problems
        logger.warn('[NetworkError] Send message to {} caused error: {}'.format(chat_id, e.message))

    except ChatMigrated as e:
        # the chat_id of a group has changed, use e.new_chat_id instead
        new_chat_id = e.new_chat_id
        bot.send_message(new_chat_id, text=msg, parse_mode='Markdown')

        doc_cusers_qry = db.cusers.find_one({"_id": new_chat_id})

        if doc_cusers_qry is not None:
            cusers_upd = db.cusers.update_one(
                            {"_id": new_chat_id}, 
                            {"$set": {"fdsble": False, "fblock": False }}
                         )

            cusers_upd = db.cusers.update_one(
                            {"_id": chat_id}, 
                            {"$set": {"fdsble": True, "fblock": True }}
                         )

        else:
            old_doc_cusers_qry = db.cusers.find_one({"_id": chat_id})
            cusers_ins = db.cusers.insert_one(
                            {"_id": new_chat_id, 
                             "czones_id": old_doc_cusers_qry.get('czones_id'), 
                             "fblock": old_doc_cusers_qry.get('fblock'), 
                             "fdaily": old_doc_cusers_qry.get('fdaily'), 
                             "fdsble": old_doc_cusers_qry.get('fdsble'), 
                             "frmndr": old_doc_cusers_qry.get('frmndr'), 
                             "fsyurk": old_doc_cusers_qry.get('fsyurk'), 
                             "fimsak": old_doc_cusers_qry.get('fimsak')}
                         )

        logger.warn('[ChatMigrated] Chat {} is migrated to {}'.format(chat_id, new_chat_id))

    except TelegramError as e:
        # handle all other telegram related errors
        logger.warn('[TelegramError] Send message to {} caused error: {}'.format(chat_id, e.message))

    else:
        msgcounter = msgcounter + 1
        if msgcounter%MAX_MESSAGE == 0:
            time.sleep(SLEEPDURATION)


def main(argv):

    # [START checking arguments]
    if not argv:
        print(gv_usage)
        sys.exit()
    else:
        try:
            opts, args = getopt.getopt(argv,"hm:",["help", "mins="])
        except getopt.GetoptError:
            print(gv_usage)
            sys.exit(2)

        for opt, arg in opts:
            if opt in ('-h', '--help'):
                print(gv_usage)
                sys.exit()
            elif opt in ('-m', '--mins'):
                try:
                    lv_mindt = int(arg)
                except ValueError:
                    print(gv_usage)
                    sys.exit()
                else:
                    if lv_mindt < 0:
                        print(gv_usage)
                        sys.exit()
    # [END checking arguments]

    utctime = datetime.datetime.utcnow()
    #Testing purpose
    #utctime = datetime.datetime(2017, 7, 12, 4, 58)
    utctime = utctime.replace(second=0, microsecond=0)

    utcadjtime = utctime + datetime.timedelta(minutes = lv_mindt)

    doc_csched_qry = db.csched.find_one({"_id": utcadjtime})

    if doc_csched_qry is not None:
        for lv_fazfor in doc_csched_qry['fazfor']:
            lv_zones = lv_fazfor.get('czones_id')
            lv_ftypes = lv_fazfor.get('ftypes')
            doc_czones_qry = db.czones.find_one({"_id": lv_zones, "fxpara": {"$ne": "default"}})

            lv_ftzone = doc_czones_qry.get('ftzone')
            lv_txzone = ' '

            if lv_ftzone == 7:
                lv_txzone = 'WIB'
            elif lv_ftzone == 8:
                lv_txzone = 'WITA'
            elif lv_ftzone == 9:
                lv_txzone = 'WIT'

            cusers_qry = db.cusers.find({"czones_id": lv_zones, "fdsble": False, "fblock": False})

            if cusers_qry.count() > 0:
                localtime = utcadjtime + datetime.timedelta(hours = lv_ftzone)

                #Hijri function
                hijritime = HijriDate(localtime.date().year, localtime.date().month, localtime.date().day, gr=True)

                doc_chijri_qry = db.chijri.find_one({"_id": int(hijritime.month)})
                hijritime.day = hijritime.day + doc_chijri_qry.get('fadjst')
                if int(hijritime.day) == 30:
                    if doc_chijri_qry.get('f29flg') == True:
                        hijritime.day = 1
                        hijritime.month = hijritime.month + 1
                elif int(hijritime.day) == 1:
                    doc_chijri_qry = db.chijri.find_one({"_id": int(hijritime.month)-1})
                    if doc_chijri_qry.get('f30flg') == True:
                        hijritime.day = 30
                        hijritime.month = hijritime.month - 1
                #End of Hijri function
           
                lv_msg = ''

                if lv_ftypes != 'Imsak' and lv_ftypes != 'Terbit':
                    lv_msg = '{}*[Azan]* '.format(lv_msg)

                lv_msg = '{}`{} - {} {}`\n\n'.format(lv_msg, lv_ftypes, localtime.strftime('%H:%M'), lv_txzone)
                lv_msg = '{}_{}, {} {} {} | '.format(lv_msg, LOCAL_DAY[localtime.weekday()], localtime.day, LOCAL_MONTH[localtime.month], localtime.year)
                lv_msg = '{}{} {} {}\n'.format(lv_msg, int(hijritime.day), HIJRI_MONTH[int(hijritime.month)], int(hijritime.year))
                lv_msg = '{}{} - {}_'.format(lv_msg, doc_czones_qry.get('fdescr'), doc_czones_qry.get('fstate'))

                for doc_cusers_qry in cusers_qry:
                    lv_frmndr = doc_cusers_qry.get('frmndr')
                    msgtype = 0
                    msg = ''
                    utcrmndr = utctime + datetime.timedelta(minutes = lv_frmndr)
                    if utcadjtime == utctime:
                        msgtype = 1         # Notif
                        msg = lv_msg

                    elif utcadjtime == utcrmndr and lv_frmndr > 0:
                        msgtype = 2         # Reminder
                        msg = '*[Reminder]* `{} menit menuju waktu `{}'.format(lv_frmndr, lv_msg.replace('*[Azan]* ',''))

                    if msgtype > 0:
                        chat_id = doc_cusers_qry.get('_id')
                        logger.info('[START]  Send message on {} -m {:<2} zone {:<4} chat_id {}'.format(utctime, lv_mindt, lv_zones, chat_id))
                        if lv_ftypes == 'Imsak':
                            if doc_cusers_qry.get('fimsak') == True:
                                sendmsg(chat_id, msg)

                        elif lv_ftypes == 'Terbit':
                            if doc_cusers_qry.get('fsyurk') == True:
                                sendmsg(chat_id, msg)
                        else:    
                            sendmsg(chat_id, msg)
                        logger.info('[END]    Send message on {} -m {:<2} zone {:<4} chat_id {}'.format(utctime, lv_mindt, lv_zones, chat_id))
            else:
                logger.info('No message to be sent on {} -m {:<2} zone {:<4}'.format(utctime, lv_mindt, lv_zones))
    else:
        logger.info('No message to be sent on {} -m {:<2}'.format(utctime, lv_mindt))


if __name__ == "__main__":
    main(sys.argv[1:])
