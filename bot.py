#!/home/untorojati/python/id_azanbot/id_azanbot_env/bin/python

# Constants
from constants import (STOREBOT_REVIEW_URL, STATES, LEADTIME, 
                       LOCAL_DAY, LOCAL_MONTH, HIJRI_MONTH, 
                       MAX_MESSAGE, LOG_DIR, LATENCY_LIMIT, JOB_LIMIT)

# File utilities
import os, sys

# [START Enable logging]
import logging
#logging.basicConfig(format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
#                    level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# create console handler and set level to info
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# create error file handler and set level to error
handler = logging.FileHandler(os.path.join(LOG_DIR, "error.log"),"w", delay="true")
handler.setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# create debug file handler and set level to debug
handler = logging.FileHandler(os.path.join(LOG_DIR, "all.log"),"w")
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
# [END Enable logging]

# Date/Time utilities
import datetime, time

# Hijri conversion utilities
from umalqurra.hijri_date import HijriDate

# MongoDB connection
from pymongo import MongoClient
from credentials import DBNAME, DBUSER, DBPASS, DBAUTH
client = MongoClient()
db = client[DBNAME]
db.authenticate(DBUSER, DBPASS, source=DBAUTH)

# Telegram Bot utilities
from credentials import TOKEN, HOSTNAME, PORT, LOG_CHATID, ADMIN_LIST, BOTAN_TOKEN
from telegram.ext import Updater, Job, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

from telegram import (InlineKeyboardButton, InlineKeyboardMarkup, ForceReply, 
                      ReplyKeyboardMarkup, ReplyKeyboardRemove)

from telegram.error import (TelegramError, Unauthorized, BadRequest, 
                            TimedOut, ChatMigrated, NetworkError)

from telegram.ext.dispatcher import run_async

from functools import wraps

from telegram.contrib.botan import Botan


# [START Utility methods]
def restricted(func):
    @wraps(func)
    def wrapped(bot, update, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN_LIST:
            logger.error('[Access Denied] Unauthorized access denied {} for {}!'.format(func, user_id))
            return
        return func(bot, update, *args, **kwargs)
    return wrapped
# [END Utility methods]


# [START Handler methods]
def prayerinfomenu():
    keyboard = []
    for lv_state in STATES:
        lstate = []
        lv_row = InlineKeyboardButton(lv_state, callback_data='zfo_set_state_{}'.format(lv_state))
        lstate.append(lv_row)
        keyboard.append(lstate)

    keyboard.append([InlineKeyboardButton('< Tutup >', callback_data='zfo_close')])

    return keyboard


def prayertime(lv_zones): 
    doc_czones_qry = db.czones.find_one({"_id": lv_zones, "fxpara": {"$ne": "default"}})
    lv_ftzone = doc_czones_qry.get('ftzone')
    lv_txzone = ' '
    
    if lv_ftzone == 7:
        lv_txzone = 'WIB'
    elif lv_ftzone == 8:
        lv_txzone = 'WITA'
    elif lv_ftzone == 9:
        lv_txzone = 'WIT'

    utctime = datetime.datetime.utcnow()
    utctime = utctime.replace(minute=0, second=0, microsecond=0)
    localtime = utctime + datetime.timedelta(hours = lv_ftzone)

    #Getting midnight of localtime
    localtime = localtime.replace(hour=0)

    #Getting utctime for midnight of localtime
    utcbegtime = localtime + datetime.timedelta(hours = -1*lv_ftzone)
    utcendtime = utcbegtime + datetime.timedelta(hours = 24)

    #Hijri function
    hijritime = HijriDate(localtime.date().year, localtime.date().month, localtime.date().day, gr=True)

    doc_chijri_qry = db.chijri.find_one({"_id": int(hijritime.month)})
    lv_orihijriday = hijritime.day
    hijritime.day = hijritime.day + doc_chijri_qry.get('fadjst')
    if int(hijritime.day) == 30:
        if doc_chijri_qry.get('f29flg') == True:
            hijritime.day = 1
            if hijritime.month == 12:
                hijritime.month = 1
                hijritime.year = hijritime.year + 1
            else:
                hijritime.month = hijritime.month + 1
    elif int(lv_orihijriday) == 1:
        if int(hijritime.month) == 1:
            doc_chijri_qry = db.chijri.find_one({"_id": 12})
        else:
            doc_chijri_qry = db.chijri.find_one({"_id": int(hijritime.month)-1})

        if doc_chijri_qry.get('f30flg') == True:
            hijritime.day = 30
            if int(hijritime.month) == 1:
                hijritime.month = 12
                hijritime.year = hijritime.year - 1
            else:
                hijritime.month = hijritime.month - 1
    #End of Hijri function

    msg = '*[Waktu Salat Hari Ini]*\n'
    msg = '{}_{}, {} {} {} | '.format(msg, LOCAL_DAY[localtime.weekday()], localtime.day, LOCAL_MONTH[localtime.month], localtime.year)
    msg = '{}{} {} {}\n'.format(msg, int(hijritime.day), HIJRI_MONTH[int(hijritime.month)], int(hijritime.year))
    msg = '{}{} - {}_\n\n'.format(msg, doc_czones_qry.get('fdescr'), doc_czones_qry.get('fstate'))
    msg = '{}```'.format(msg)

    csched_qry = db.csched.find({"_id": {"$gt": utcbegtime, "$lt": utcendtime}, "fazfor.czones_id": lv_zones}).sort("_id", 1)
    
    for doc_csched_qry in csched_qry:
        for lv_fazfor in doc_csched_qry['fazfor']:
            if lv_fazfor.get('czones_id') == lv_zones:
                localtime = doc_csched_qry.get('_id') + datetime.timedelta(hours = lv_ftzone)
                msg = '{}\n'.format(msg)
                msg = '{}{:<6} - {} {}'.format(msg, lv_fazfor.get('ftypes'), localtime.strftime('%H:%M'), lv_txzone)

    msg = '{}```'.format(msg)
    
    return msg


def settingmenu(chat_id):
    doc_cusers_qry = db.cusers.find_one({"_id": chat_id})

    if doc_cusers_qry.get('czones_id') == None:
        current_zone = ' -None- '
    else:
        doc_czones_qry = db.czones.find_one({"_id": doc_cusers_qry.get('czones_id'), "fxpara": {"$ne": "default"}})
        current_zone = '{} - {}'.format(doc_czones_qry.get('fdescr'), doc_czones_qry.get('fstate'))

    current_imsak = doc_cusers_qry.get('fimsak')
    if current_imsak == True:
        current_imsak = 'aktif'
    else:
        current_imsak = 'nonaktif'

    current_syurk = doc_cusers_qry.get('fsyurk')
    if current_syurk == True:
        current_syurk = 'aktif'
    else:
        current_syurk = 'nonaktif'

    current_rmndr = doc_cusers_qry.get('frmndr')

    keyboard = [[InlineKeyboardButton('Zona [{}]'.format(current_zone), callback_data='cfg_current_zone')],
                [InlineKeyboardButton('Notifikasi Imsak [{}]'.format(current_imsak.title()), callback_data='cfg_current_imsak_{}'.format(current_imsak))],
                [InlineKeyboardButton('Notifikasi Terbit [{}]'.format(current_syurk.title()), callback_data='cfg_current_syurk_{}'.format(current_syurk))],
                [InlineKeyboardButton('Reminder (menit) [{}]'.format(current_rmndr), callback_data='cfg_current_rmndr')],
                [InlineKeyboardButton('< Tutup >', callback_data='cfg_close')]]

    return keyboard


@run_async
@restricted
def botstat(bot, update):
    cusers_qry_stat_member = db.cusers.find({"fblock": False}).count()
    cusers_qry_stat_mbrzns = db.cusers.find({"fblock": False, "czones_id": {"$ne": None}}).count()
    cusers_qry_stat_mbrntf = db.cusers.find({"fdsble": False, "fblock": False, "czones_id": {"$ne": None}}).count()

    msg = '*[Statistics]*\n'
    msg = '{}Active Subscriber: {}\n'.format(msg, cusers_qry_stat_member)
    msg = '{}Active Subscriber w/ Zone data: {}\n'.format(msg, cusers_qry_stat_mbrzns)
    msg = '{}Active Subscriber w/ Zone data & notification: {}'.format(msg, cusers_qry_stat_mbrntf)

    update.message.reply_text(msg, parse_mode='Markdown')

    if not 'test' in DBNAME:
        Botan(BOTAN_TOKEN).track(update.message, event_name='botstat')


def button(bot, update):
    query = update.callback_query
    chat_id = query.message.chat_id
    message_id = query.message.message_id

    if '_set_state_' in query.data:

        lv_cmd = query.data[0:3]
        lv_state = query.data.replace('{}_set_state_'.format(lv_cmd),'')

        czones_qry = db.czones.find({"fstate": lv_state, "fxpara": {"$ne": "default"}}).sort("fdescr", 1)

        keyboard = []
        for doc_czones_qry in czones_qry:
            lzone = []
            lv_row = InlineKeyboardButton(doc_czones_qry.get('fdescr'), callback_data='{}_set_zone_{}'.format(lv_cmd, doc_czones_qry.get('_id')))
            lzone.append(lv_row)
            keyboard.append(lzone)

        if lv_cmd == 'cfg':
            keyboard.append([InlineKeyboardButton('<< Kembali', callback_data='cfg_current_zone'),
                         InlineKeyboardButton('< Tutup >', callback_data='cfg_close')])
        elif lv_cmd == 'zfo':
            keyboard.append([InlineKeyboardButton('<< Kembali', callback_data='zfo_main'),
                         InlineKeyboardButton('< Tutup >', callback_data='zfo_close')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.editMessageText(text='Pilih zona:',
                            chat_id=chat_id,
                            message_id=message_id, reply_markup=reply_markup)

    elif 'cfg_current_imsak_' in query.data:
        lv_current_imsak = query.data.replace('cfg_current_imsak_','')
        if lv_current_imsak == 'aktif':
            lv_set_imsak = 'nonaktif'
        else:
            lv_set_imsak = 'aktif'

        keyboard = [[InlineKeyboardButton('{}kan notifikasi Imsak'.format(lv_set_imsak.title()), callback_data='cfg_set_imsak_{}'.format(lv_set_imsak))],
                    [InlineKeyboardButton('<< Kembali', callback_data='cfg_main'),
                     InlineKeyboardButton('< Tutup >', callback_data='cfg_close')]]

        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.editMessageText(text='Set notifikasi Imsak:',
                            chat_id=chat_id,
                            message_id=message_id, reply_markup=reply_markup)

    elif 'cfg_current_syurk_' in query.data:
        lv_current_syurk = query.data.replace('cfg_current_syurk_','')
        if lv_current_syurk == 'aktif':
            lv_set_syurk = 'nonaktif'
        else:
            lv_set_syurk = 'aktif'

        keyboard = [[InlineKeyboardButton('{}kan notifikasi Terbit'.format(lv_set_syurk.title()), callback_data='cfg_set_syurk_{}'.format(lv_set_syurk))],
                    [InlineKeyboardButton('<< Kembali', callback_data='cfg_main'),
                     InlineKeyboardButton('< Tutup >', callback_data='cfg_close')]]

        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.editMessageText(text='Set notifikasi Terbit:',
                            chat_id=chat_id,
                            message_id=message_id, reply_markup=reply_markup)

    elif 'cfg_set_imsak_' in query.data:
        lv_set_imsak = query.data.replace('cfg_set_imsak_','')
        if lv_set_imsak == 'aktif':
            cusers_upd = db.cusers.update_one(
                            {"_id": chat_id}, 
                            {"$set": {"fimsak": True}}
                         )

        else:
            cusers_upd = db.cusers.update_one(
                            {"_id": chat_id}, 
                            {"$set": {"fimsak": False}}
                         )

        reply_markup = InlineKeyboardMarkup(settingmenu(chat_id))

        bot.editMessageText(text='Notifikasi waktu Imsak: {}\n\nSetting:'.format(lv_set_imsak),
                            chat_id=chat_id,
                            message_id=message_id, reply_markup=reply_markup)

    elif 'cfg_set_syurk_' in query.data:
        lv_set_syurk = query.data.replace('cfg_set_syurk_','')
        if lv_set_syurk == 'aktif':
            cusers_upd = db.cusers.update_one(
                            {"_id": chat_id}, 
                            {"$set": {"fsyurk": True}}
                         )

        else:
            cusers_upd = db.cusers.update_one(
                            {"_id": chat_id}, 
                            {"$set": {"fsyurk": False}}
                         )

        reply_markup = InlineKeyboardMarkup(settingmenu(chat_id))

        bot.editMessageText(text='Notifikasi waktu Terbit: {}\n\nSetting:'.format(lv_set_syurk),
                            chat_id=chat_id,
                            message_id=message_id, reply_markup=reply_markup)

    elif 'cfg_set_rmndr_' in query.data:
        lv_set_rmndr = int(query.data.replace('cfg_set_rmndr_',''))
        cusers_upd = db.cusers.update_one(
                        {"_id": chat_id}, 
                        {"$set": {"frmndr": lv_set_rmndr}}
                     )
        reply_markup = InlineKeyboardMarkup(settingmenu(chat_id))

        bot.editMessageText(text='Reminder telah diset pada {} menit\n\nSetting:'.format(lv_set_rmndr),
                            chat_id=chat_id,
                            message_id=message_id, reply_markup=reply_markup)

    elif query.data == 'cfg_current_zone':
        keyboard = []
        for lv_state in STATES:
            lstate = []
            lv_row = InlineKeyboardButton(lv_state, callback_data='cfg_set_state_{}'.format(lv_state))
            lstate.append(lv_row)
            keyboard.append(lstate)

        keyboard.append([InlineKeyboardButton('<< Kembali', callback_data='cfg_main'),
                     InlineKeyboardButton('< Tutup >', callback_data='cfg_close')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.editMessageText(text='Pilih propinsi:',
                            chat_id=chat_id,
                            message_id=message_id, reply_markup=reply_markup)

    elif query.data == 'cfg_current_rmndr':
        keyboard = []

        keyboard.append([InlineKeyboardButton('0', callback_data='cfg_set_rmndr_0')])

        keyboard.append([InlineKeyboardButton('1', callback_data='cfg_set_rmndr_1'),
                     InlineKeyboardButton('2', callback_data='cfg_set_rmndr_2')])

        keyboard.append([InlineKeyboardButton('3', callback_data='cfg_set_rmndr_3'),
                     InlineKeyboardButton('4', callback_data='cfg_set_rmndr_4')])

        keyboard.append([InlineKeyboardButton('5', callback_data='cfg_set_rmndr_5'),
                     InlineKeyboardButton('6', callback_data='cfg_set_rmndr_6')])

        keyboard.append([InlineKeyboardButton('7', callback_data='cfg_set_rmndr_7'),
                     InlineKeyboardButton('8', callback_data='cfg_set_rmndr_8')])

        keyboard.append([InlineKeyboardButton('9', callback_data='cfg_set_rmndr_9'),
                     InlineKeyboardButton('10', callback_data='cfg_set_rmndr_10')])

        keyboard.append([InlineKeyboardButton('<< Kembali', callback_data='cfg_main'),
                     InlineKeyboardButton('< Tutup >', callback_data='cfg_close')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.editMessageText(text='Set reminder (menit):',
                            chat_id=chat_id,
                            message_id=message_id, reply_markup=reply_markup)

    elif 'cfg_set_zone_' in query.data:
        lv_zones = int(query.data.replace('cfg_set_zone_',''))
        doc_czones_qry = db.czones.find_one({"_id": lv_zones, "fxpara": {"$ne": "default"}})
        cusers_upd = db.cusers.update_one(
                        {"_id": chat_id}, 
                        {"$set": {"czones_id": lv_zones}}
                     )
        reply_markup = InlineKeyboardMarkup(settingmenu(chat_id))

        bot.editMessageText(text='Zona Anda: {} - {}\n\nSetting:'.format(doc_czones_qry.get('fdescr'), doc_czones_qry.get('fstate')),
                            chat_id=chat_id,
                            message_id=message_id, reply_markup=reply_markup)

    elif query.data == 'cfg_main':
        reply_markup = InlineKeyboardMarkup(settingmenu(chat_id))

        bot.editMessageText(text='Setting:',
                            chat_id=chat_id,
                            message_id=message_id, reply_markup=reply_markup)

    elif query.data == 'cfg_close':
        bot.editMessageText(text='Menu Setting telah ditutup',
                            chat_id=chat_id,
                            message_id=message_id)

    elif query.data == 'zfo_close':
        bot.editMessageText(text='Menu Prayer info telah ditutup',
                            chat_id=chat_id,
                            message_id=message_id)

    elif query.data == 'zfo_main':
        reply_markup = InlineKeyboardMarkup(prayerinfomenu())

        bot.editMessageText(text='Waktu Salat Hari Ini.\n\nPilih propinsi:',
                            chat_id=chat_id,
                            message_id=message_id, reply_markup=reply_markup)

    elif 'zfo_set_zone_' in query.data:
        lv_zones = int(query.data.replace('zfo_set_zone_',''))
        msg = prayertime(lv_zones)

        bot.editMessageText(text=msg,
                            chat_id=chat_id,
                            message_id=message_id, 
                            parse_mode='Markdown')

    else:
        bot.editMessageText(text='Error! No definition for {}'.format(query.data),
                            chat_id=chat_id,
                            message_id=message_id)


def cancel(bot,update):
    update.message.reply_text('Sesi Feedback telah dibatalkan', reply_markup=ReplyKeyboardRemove())
    user = update.message.from_user
    logger.info("First name: {}, Last name: {}, Username: {}, canceled the feedback.".format(user.first_name, user.last_name, user.username))
    return ConversationHandler.END

    if not 'test' in DBNAME:
        Botan(BOTAN_TOKEN).track(update.message, event_name='cancel')


def chatid(bot, update):
    chat_id = update.message.chat_id
    update.message.reply_text(str(chat_id))

    if not 'test' in DBNAME:
        Botan(BOTAN_TOKEN).track(update.message, event_name='chatid')


def dummy(bot, update):
    return ConversationHandler.END


def echo(bot, update):
    chat_id = update.message.chat_id
    bot.send_message(chat_id=chat_id, text=update.message.text)

    if not 'test' in DBNAME:
        Botan(BOTAN_TOKEN).track(update.message, event_name='echo')


def echoreply(bot, update):
    update.message.reply_text(update.message.text)

    if not 'test' in DBNAME:
        Botan(BOTAN_TOKEN).track(update.message, event_name='echoreply')


@run_async
def error(bot, update, error):
    try:
        raise error

    except Unauthorized:
        # handle blocked bot
        logger.warning('[Unauthorized] Update "{}" caused error "{}"'.format(update, error))

    except BadRequest as e:
        # handle malformed requests
        logger.warning('[BadRequest] Update "{}" caused error "{}": "{}"'.format(update, error, e.message))

    except TimedOut:
        # handle slow connection problems
        logger.warning('[TimedOut] Update "{}" caused error "{}"'.format(update, error))

    except NetworkError as e:
        # handle other connection problems
        logger.warning('[NetworkError] Update "{}" caused error "{}": "{}"'.format(update, error, e.message))

    except ChatMigrated as e:
        # the chat_id of a group has changed, use e.new_chat_id instead
        chat_id = update.message.chat_id
        new_chat_id = e.new_chat_id

        msg = 'Telegram group Anda memiliki ID baru. Data telah diperbaharui.\n'
        msg = '{}Bot dapat Anda gunakan kembali.'.format(msg)
        bot.send_message(chat_id=new_chat_id, text=msg, parse_mode='Markdown')

        #eusers = kusers.get_by_id(new_chat_id)
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

        logger.warning('[ChatMigrated] Chat {} is migrated to {}'.format(chat_id, new_chat_id))

    except TelegramError:
        # handle all other telegram related errors
        logger.warning('[TelegramError] Update "{}" caused error "{}"'.format(update, error))


def feedb_msg(bot, update):
    chat_id = update.message.chat_id
    update.message.reply_text('Terima kasih! Kami akan segera mereview dan terus mengembangkan bot ini.', reply_markup=ReplyKeyboardRemove())
    user = update.message.from_user
    lv_subject = ''
    if 'test' in DBNAME:
        lv_subject = 'TEST '

    logger.info("[Feedback] Chat ID: {} First name: {}, Last name: {}, Username: {}. Feedback: {}".format(chat_id, user.first_name, user.last_name, user.username, update.message.text))
    bot.send_message(chat_id=LOG_CHATID, text='[{}Feedback] Chat ID: {}, First name: {}, Last name: {}, Username: {}. Feedback: {}'.format(lv_subject, chat_id, user.first_name, user.last_name, user.username, update.message.text))
    return ConversationHandler.END


@run_async
def feedback(bot, update):
    ##update.message.reply_text('REPLY pesan ini untuk mengirimkan saran atau melaporkan bugs.\nKETIK dan KIRIM  `/cancel`  untuk membatalkan sesi feedback.\n\n', parse_mode='Markdown', reply_markup=ForceReply())
    ##return FEEDB_MSG
    update.message.reply_text('Gunakan link ke Facebook page kami untuk mengirimkan saran atau melaporkan bugs: https://fb.me/IDAzanBot ', disable_web_page_preview=True)
    
    if not 'test' in DBNAME:
        Botan(BOTAN_TOKEN).track(update.message, event_name='feedback')


@run_async
def help(bot, update):
    msg = "Assalaamu'alaikum\n\n"
    msg = '{}Berikut ini daftar perintah yang dapat Anda berikan pada bot:\n\n'.format(msg)
    msg = '{}/start  - untuk mengaktifkan bot dan notifikasi. Gunakan juga perintah ini untuk mengaktifkan kembali notifikasi jika sebelumnya Anda telah menggunakan perintah  /stop  .\n\n'.format(msg)
    msg = '{}/stop  - untuk menonaktifkan notifikasi dari bot. Anda masih tetap dapat mempergunakan semua perintah yang ada, seperti  /today  atau  /prayerinfo  untuk informasi jadwal salat hari ini.\n\n'.format(msg)
    msg = '{}/help  - untuk menampilkan menu help ini.\n\n'.format(msg)
    msg = '{}/next  - untuk menampilkan informasi berapa lama ke notifikasi yang berikutnya.\n\n'.format(msg)
    msg = '{}/n  - alias untuk  /next  . Memiliki fungsi yang sama dengan perintah  /next  .\n\n'.format(msg)
    msg = '{}/setting  - menu setting. Set zona Anda, atur notifikasi untuk notifikasi waktu Imsak dan Terbit dan pengaturan fungsi Reminder.\n\n'.format(msg)
    msg = "{}/today  - meminta bot untuk mengirimkan jadwal waktu salat hari ini untuk zona Anda.\n\n".format(msg)
    msg = "{}/t  - alias untuk  /today  . Memiliki fungsi yang sama dengan perintah  /today  .\n\n".format(msg)
    msg = "{}/prayerinfo  - meminta bot untuk mengirimkan jadwal waktu salat hari ini untuk zona tertentu.\n\n".format(msg)
    msg = '{}/feedback  - input dan saran dari Anda sangat kami nantikan. Gunakan pula perintah ini untuk melaporkan bugs yang Anda jumpai.\n\n'.format(msg)
    #msg = '{}`/cancel`  - untuk membatalkan sesi feedback. Perintah ini hanya akan aktif jika Anda berada di dalam sesi feedback.\n\n'
    msg = '{}/rateme  - berikan rating Anda untuk bot ini.\n\n'.format(msg)
    update.message.reply_text(msg, parse_mode='Markdown')

    if not 'test' in DBNAME:
        Botan(BOTAN_TOKEN).track(update.message, event_name='help')


@run_async
def next(bot, update):
    chat_id = update.message.chat_id
    doc_cusers_qry = db.cusers.find_one({"_id": chat_id})
    if doc_cusers_qry is not None:
        lv_zones = doc_cusers_qry.get('czones_id')
        if lv_zones is not None:
            doc_czones_qry = db.czones.find_one({"_id": lv_zones, "fxpara": {"$ne": "default"}})
            lv_ftzone = doc_czones_qry.get('ftzone')
            lv_txzone = ' '
            
            if lv_ftzone == 7:
                lv_txzone = 'WIB'
            elif lv_ftzone == 8:
                lv_txzone = 'WITA'
            elif lv_ftzone == 9:
                lv_txzone = 'WIT'

            utctime = datetime.datetime.utcnow()
            localtime = utctime + datetime.timedelta(hours = lv_ftzone)
            localtime = localtime.replace(hour=0, minute=0, second=0, microsecond=0)

            #Getting midnight of localtime
#            localtime = localtime.replace(hour=0)

            #Getting utctime for midnight of localtime
#            utcbegtime = localtime + datetime.timedelta(hours = -1*lv_ftzone)
#            utcendtime = utcbegtime + datetime.timedelta(hours = 24)

            csched_qry = db.csched.find({"_id": {"$gt": utctime}, "fazfor.czones_id": lv_zones}).sort("_id", 1)
            
            msg = ''

            for doc_csched_qry in csched_qry:
                for lv_fazfor in doc_csched_qry['fazfor']:
                    if lv_fazfor.get('czones_id') == lv_zones:
                        localtime = doc_csched_qry.get('_id')
                        lv_diffs = (localtime - utctime).total_seconds()
                        localtime = localtime + datetime.timedelta(hours = lv_ftzone)                      
                        msg = '{}`{} - {} {}`\n\n'.format(msg, lv_fazfor.get('ftypes'), localtime.strftime('%H:%M'), lv_txzone)
                        break
                break

            #Hijri function
            hijritime = HijriDate(localtime.date().year, localtime.date().month, localtime.date().day, gr=True)

            doc_chijri_qry = db.chijri.find_one({"_id": int(hijritime.month)})
            lv_orihijriday = hijritime.day
            hijritime.day = hijritime.day + doc_chijri_qry.get('fadjst')
            if int(hijritime.day) == 30:
                if doc_chijri_qry.get('f29flg') == True:
                    hijritime.day = 1
                    if hijritime.month == 12:
                        hijritime.month = 1
                        hijritime.year = hijritime.year + 1
                    else:
                        hijritime.month = hijritime.month + 1
            elif int(lv_orihijriday) == 1:
                if int(hijritime.month) == 1:
                    doc_chijri_qry = db.chijri.find_one({"_id": 12})
                else:
                    doc_chijri_qry = db.chijri.find_one({"_id": int(hijritime.month)-1})

                if doc_chijri_qry.get('f30flg') == True:
                    hijritime.day = 30
                    if int(hijritime.month) == 1:
                        hijritime.month = 12
                        hijritime.year = hijritime.year - 1
                    else:
                        hijritime.month = hijritime.month - 1
            #End of Hijri function

            msg = '{}_{}, {} {} {} | '.format(msg, LOCAL_DAY[localtime.weekday()], localtime.day, LOCAL_MONTH[localtime.month], localtime.year)
            msg = '{}{} {} {}\n'.format(msg, int(hijritime.day), HIJRI_MONTH[int(hijritime.month)], int(hijritime.year))
            msg = '{}{} - {}_'.format(msg, doc_czones_qry.get('fdescr'), doc_czones_qry.get('fstate'))
            
            lv_diffh = int(lv_diffs / 3600)
            lv_diffm = int((lv_diffs % 3600) / 60) + ((lv_diffs % 3600) % 60 > 0)
            if lv_diffm == 60:
                lv_diffm = 0
                lv_diffh += 1

            if lv_diffh == 0 and lv_diffm > 0:
                msg = '`{} menit menuju waktu `{}'.format(lv_diffm, msg)
            elif lv_diffh == 0 and lv_diffm == 0:
                msg = '`Tepat saat waktu `{}'.format(msg)
            elif lv_diffh > 0 and lv_diffm == 0:
                msg = '`{} jam menuju waktu `{}'.format(lv_diffh, msg)
            elif lv_diffh > 0 and lv_diffm > 0:    
                msg = '`{} jam dan {} menit menuju waktu `{}'.format(lv_diffh, lv_diffm, msg)

            update.message.reply_text(msg, parse_mode='Markdown')
        else:
            update.message.reply_text('Setting Zona belum dilakukan.\nGunakan perintah  /setting  untuk melakukan setting Zona.')   

    else:
        update.message.reply_text('Setting Zona belum dilakukan.\nGunakan perintah  /setting  untuk melakukan setting Zona.')

    if not 'test' in DBNAME:
        Botan(BOTAN_TOKEN).track(update.message, event_name='next')


@run_async
def prayerinfo(bot, update):
    reply_markup = InlineKeyboardMarkup(prayerinfomenu())
    update.message.reply_text('Waktu Salat Hari Ini.\n\nPilih propinsi:', reply_markup=reply_markup)

    if not 'test' in DBNAME:
        Botan(BOTAN_TOKEN).track(update.message, event_name='prayerinfo')


@run_async
def rateme(bot, update):
    update.message.reply_text('Ikuti link berikut untuk memberi rating: {}'.format(STOREBOT_REVIEW_URL), disable_web_page_preview=True)

    if not 'test' in DBNAME:
        Botan(BOTAN_TOKEN).track(update.message, event_name='rateme')


@restricted
def restart(bot, update):
    bot.send_message(update.message.chat_id, "Bot is restarting...")

    if not 'test' in DBNAME:
        Botan(BOTAN_TOKEN).track(update.message, event_name='restart')

    time.sleep(0.2)
    os.execl(sys.executable, sys.executable, *sys.argv)


@run_async
def setting(bot, update):
    chat_id = update.message.chat_id
    doc_cusers_qry = db.cusers.find_one({"_id": chat_id})
    lv_notiflog = False

    if doc_cusers_qry == None:
        cusers_ins = db.cusers.insert_one(
                        {"_id": chat_id, 
                         "czones_id": None, 
                         "fblock": False, 
                         "fdaily": False, 
                         "fdsble": False, 
                         "frmndr": 0, 
                         "fsyurk": False, 
                         "fimsak": False}
                     )

        lv_notiflog = True

    reply_markup = InlineKeyboardMarkup(settingmenu(chat_id))
    update.message.reply_text('Setting:', reply_markup=reply_markup)

    if lv_notiflog == True:
        user = update.message.from_user
        lv_subject = ''
        if 'test' in DBNAME:
            lv_subject = 'TEST '

        logger.info("[New User] Chat ID: {}, First name: {}, Last name: {}, Username: {}.".format(chat_id, user.first_name, user.last_name, user.username))

        try:
            bot.send_message(chat_id=LOG_CHATID, text='[{}New User] Chat ID: {}, First name: {}, Last name: {}, Username: {}'.format(lv_subject, chat_id, user.first_name, user.last_name, user.username))
        
        except TelegramError as e:
            logger.error('[TelegramError] Notification of New User {} caused error: {}'.format(chat_id, e.message))
    
    if not 'test' in DBNAME:
        Botan(BOTAN_TOKEN).track(update.message, event_name='setting')


@run_async
def start(bot, update):
    chat_id = update.message.chat_id
    doc_cusers_qry = db.cusers.find_one({"_id": chat_id}, {"_id": 1})
    if doc_cusers_qry is not None: 
        cusers_upd = db.cusers.update_one(
                        {"_id": chat_id}, 
                        {"$set": {"fdsble": False, "fblock": False }}  
                     )
    
    msg = "Assalaamu'alaikum\n\n"
    msg = '{}Silakan melakukan setting Zona terlebih dahulu dengan mengirimkan perintah  /setting  .\n\n'.format(msg)
    msg = '{}Notifikasi akan dikirim otomatis saat memasuki waktu salat.\n\n'.format(msg)
    msg = '{}Gunakan perintah  /today  untuk mengetahui jadwal waktu salat hari ini bagi zona Anda atau perintah  '.format(msg)
    msg = '{}/prayerinfo  untuk mendapatkan jadwal waktu salat zona-zona lainnya.\n\n'.format(msg)
    msg = '{}Untuk informasi perintah-perintah lain yang dapat diberikan pada bot, Anda dapat mengirimkan  /help  .\n\n'.format(msg)
    msg = '{}Follow kami di Facebook page -  https://fb.me/IDAzanBot  \n'.format(msg)
    #msg = '{}\n'.format(msg)
    #msg = '{}ID_AzanBot menggunakan data waktu salat dari Kementerian Agama Republik Indonesia.'.format(msg)
    update.message.reply_text(msg, disable_web_page_preview=True)

    if not 'test' in DBNAME:
        Botan(BOTAN_TOKEN).track(update.message, event_name='start')


@run_async
def stop(bot, update):
    chat_id = update.message.chat_id
    doc_cusers_qry = db.cusers.find_one({"_id": chat_id}, {"_id": 1})
    if doc_cusers_qry is not None: 
        cusers_upd = db.cusers.update_one(
                        {"_id": chat_id}, 
                        {"$set": {"fdsble": True}}
                     )

        update.message.reply_text('Notifikasi telah dinonaktifkan. Notifikasi dapat Anda aktifkan kembali dengan mengirimkan perintah  /start  .')
    else:
        update.message.reply_text('Error! Setting Zona belum dilakukan. Gunakan perintah  /setting  untuk melakukan setting Zona.')
    
    if not 'test' in DBNAME:
        Botan(BOTAN_TOKEN).track(update.message, event_name='stop')


@run_async
def today(bot, update):
    chat_id = update.message.chat_id
    doc_cusers_qry = db.cusers.find_one({"_id": chat_id})
    if doc_cusers_qry is not None:
        lv_zones = doc_cusers_qry.get('czones_id')
        if lv_zones is not None:
            msg = prayertime(lv_zones)
            update.message.reply_text(msg, parse_mode='Markdown')
        else:
            update.message.reply_text('Setting Zona belum dilakukan.\nGunakan perintah  /setting  untuk melakukan setting Zona.')   

    else:
        update.message.reply_text('Setting Zona belum dilakukan.\nGunakan perintah  /setting  untuk melakukan setting Zona.')

    if not 'test' in DBNAME:
        Botan(BOTAN_TOKEN).track(update.message, event_name='today')


# [END Handler method]

# [START Job method]
@run_async
def set_azan(bot, job):
    #lv_context = []
    #lv_context.append(chat_id)
    #lv_context.append(msg)
    #lv_context.append(job.name)
    #lv_context.append(utctime)
    #lv_context.append(lv_zones)

    chat_id = job.context[0]
    msg = job.context[1]
    logger.info('[START]  Message sent on {} job {:<11} zone {:<4} chat_id {}'.format(job.context[3], job.context[2], job.context[4], chat_id))

    try:
        bot.send_message(chat_id, text=msg, parse_mode='Markdown')
        # #Testing purpose
        # if chat_id == xxxxxxx:
        #     bot.send_message(chat_id, text=msg, parse_mode='Markdown')
        # else:

        #     logger.info('[SENDING] {}: chat_id {}'.format(msg, chat_id))
        #     time.sleep(0.4)

    except Unauthorized:
        # handle blocked bot
        doc_cusers_qry = db.cusers.find_one({"_id": chat_id})

        if doc_cusers_qry is not None:
            cusers_upd = db.cusers.update_one(
                            {"_id": chat_id}, 
                            {"$set": {"fblock": True }}
                         )

        logger.warning('[Unauthorized] Send message to {} caused error'.format(chat_id))

    except BadRequest as e:
        # handle malformed requests
        logger.warning('[BadRequest] Send message to {} caused error: {}'.format(chat_id, e.message))

    except TimedOut:
        # handle slow connection problems
        logger.warning('[TimedOut] Send message to {} caused error'.format(chat_id))

    except NetworkError as e:
        # handle other connection problems
        logger.warning('[NetworkError] Send message to {} caused error: {}'.format(chat_id, e.message))

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

        logger.warning('[ChatMigrated] Chat {} is migrated to {}'.format(chat_id, new_chat_id))

    except TelegramError as e:
        # handle all other telegram related errors
        logger.warning('[TelegramError] Send message to {} caused error: {}'.format(chat_id, e.message))

    else:
        logger.info('[END]    Message sent on {} job {:<11} zone {:<4} chat_id {}'.format(job.context[3], job.context[2], job.context[4], chat_id))


@run_async
def get_azan(bot, job):
    global add_job

    # Latency monitoring 1
    d1 = datetime.datetime.utcnow()

    #Manipulate UTCTime to consider lead time of data fetching
    utctime = datetime.datetime.utcnow() + datetime.timedelta(minutes = LEADTIME)
    #Testing purpose
    #utctime = datetime.datetime(2017, 7, 12, 4, 58)
    utctime = utctime.replace(second=0, microsecond=0)

    lv_mindt = job.context
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
                lv_orihijriday = hijritime.day
                hijritime.day = hijritime.day + doc_chijri_qry.get('fadjst')
                if int(hijritime.day) == 30:
                    if doc_chijri_qry.get('f29flg') == True:
                        hijritime.day = 1
                        if hijritime.month == 12:
                            hijritime.month = 1
                            hijritime.year = hijritime.year + 1
                        else:
                            hijritime.month = hijritime.month + 1
                elif int(lv_orihijriday) == 1:
                    if int(hijritime.month) == 1:
                        doc_chijri_qry = db.chijri.find_one({"_id": 12})
                    else:
                        doc_chijri_qry = db.chijri.find_one({"_id": int(hijritime.month)-1})

                    if doc_chijri_qry.get('f30flg') == True:
                        hijritime.day = 30
                        if int(hijritime.month) == 1:
                            hijritime.month = 12
                            hijritime.year = hijritime.year - 1
                        else:
                            hijritime.month = hijritime.month - 1
                #End of Hijri function
           
                lv_msg = ''

                if lv_ftypes != 'Imsak' and lv_ftypes != 'Terbit':
                    lv_msg = '{}*[Azan]* '.format(lv_msg)

                lv_msg = '{}`{} - {} {}`\n\n'.format(lv_msg, lv_ftypes, localtime.strftime('%H:%M'), lv_txzone)
                lv_msg = '{}_{}, {} {} {} | '.format(lv_msg, LOCAL_DAY[localtime.weekday()], localtime.day, LOCAL_MONTH[localtime.month], localtime.year)
                lv_msg = '{}{} {} {}\n'.format(lv_msg, int(hijritime.day), HIJRI_MONTH[int(hijritime.month)], int(hijritime.year))
                lv_msg = '{}{} - {}_'.format(lv_msg, doc_czones_qry.get('fdescr'), doc_czones_qry.get('fstate'))

                lv_counter = 0
                lv_second = 0

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
                        #Testing purpose
                        #chat_id = xxxxxxxx

                        jobtime = utctime + datetime.timedelta(seconds = lv_second)
                        
                        lv_context = []
                        lv_context.append(chat_id)
                        lv_context.append(msg)
                        lv_context.append(job.name)
                        lv_context.append(utctime)
                        lv_context.append(lv_zones)
                        
                        if lv_ftypes == 'Imsak':
                            if doc_cusers_qry.get('fimsak') == True:
                                add_job.run_once(set_azan, jobtime, context=lv_context)
                                lv_counter += 1

                        elif lv_ftypes == 'Terbit':
                            if doc_cusers_qry.get('fsyurk') == True:
                                add_job.run_once(set_azan, jobtime, context=lv_context)
                                lv_counter += 1

                        else:    
                            add_job.run_once(set_azan, jobtime, context=lv_context)
                            lv_counter += 1

                        if lv_counter%MAX_MESSAGE == 0:
                            lv_second += 1

                        # Job limit monitoring
                        #Testing purpose
                        #JOB_LIMIT = -1
                        if lv_second > JOB_LIMIT:
                            logger.error('[JOB LIMIT] Processing on {} exceeds the {}th second limit: {} seconds!'.format(utctime, JOB_LIMIT, lv_second))
                            try:
                                bot.send_message(chat_id=LOG_CHATID, text='[JOB LIMIT] Processing on {} exceeds the {}th second limit: {} seconds!'.format(utctime, JOB_LIMIT, lv_second))
                            
                            except TelegramError as e:
                                logger.error('[JOB LIMIT NOTIFICATION] Failed to send job limit notification error: {}'.format(e.message))


                        
            else:
                logger.info('No message to be sent on {} job {:<11} zone {:<4}'.format(utctime, job.name, lv_zones))
                           
    else:
        logger.info('No message to be sent on {} job {:<11}'.format(utctime, job.name))
               
    # Latency monitoring 2
    d2 = datetime.datetime.utcnow()
    lv_latency = (d2 - d1).total_seconds()
    
    #Testing purpose
    #LATENCY_LIMIT = 0
    if lv_latency > LATENCY_LIMIT:
        logger.error('[LATENCY] Processing on {} job {:<11} exceeds {} seconds limit: {} seconds!'.format(utctime, job.name, LATENCY_LIMIT, lv_latency))
        try:
            bot.send_message(chat_id=LOG_CHATID, text='[LATENCY] Processing on {} job {:<11} exceeds {} seconds limit: {} seconds!'.format(utctime, job.name, LATENCY_LIMIT, lv_latency))
        
        except TelegramError as e:
            logger.error('[LATENCY NOTIFICATION] Failed to send latency notification error: {}'.format(e.message))

    #LEADTIME fine tuning purpose
    #logger.warning('[LATENCY MONITORING] Processing on {} job {:<11} took {} seconds!'.format(utctime, job.name, lv_latency))
                    

# [END Job method]


def main():
    logger.info('Starting...')
    global updater
    updater = Updater(token=TOKEN)

# Register job
    global add_job
    add_job = updater.job_queue
    #Jobtime to be set to start on next minute and zero second!
    utctime = datetime.datetime.utcnow()
    utctime = utctime.replace(second=0, microsecond=0)
    jobtime = utctime + datetime.timedelta(minutes = 1)
    add_job.run_repeating(get_azan, 60, first=jobtime, context=0, name='get_azan_0')
    add_job.run_repeating(get_azan, 60, first=jobtime, context=1, name='get_azan_1')
    add_job.run_repeating(get_azan, 60, first=jobtime, context=2, name='get_azan_2')
    add_job.run_repeating(get_azan, 60, first=jobtime, context=3, name='get_azan_3')
    add_job.run_repeating(get_azan, 60, first=jobtime, context=4, name='get_azan_4')
    add_job.run_repeating(get_azan, 60, first=jobtime, context=5, name='get_azan_5')
    add_job.run_repeating(get_azan, 60, first=jobtime, context=6, name='get_azan_6')
    add_job.run_repeating(get_azan, 60, first=jobtime, context=7, name='get_azan_7')
    add_job.run_repeating(get_azan, 60, first=jobtime, context=8, name='get_azan_8')
    add_job.run_repeating(get_azan, 60, first=jobtime, context=9, name='get_azan_9')
    add_job.run_repeating(get_azan, 60, first=jobtime, context=10, name='get_azan_10')

# Get the dispatcher to register handlers
    dp = updater.dispatcher

# [START Register handlers]
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(CommandHandler("botstat", botstat))
    dp.add_handler(CommandHandler("chatid", chatid))
    dp.add_handler(CommandHandler("feedback", feedback))
    dp.add_error_handler(error)
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("next", next))
    dp.add_handler(CommandHandler("n", next))
    dp.add_handler(CommandHandler("prayerinfo", prayerinfo))
    dp.add_handler(CommandHandler("rateme", rateme))
    dp.add_handler(CommandHandler("restart", restart))
    dp.add_handler(CommandHandler("setting", setting))
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("today", today))
    dp.add_handler(CommandHandler("t", today))

# [END Register handlers]    

# [START Webhook setup]
    updater.start_webhook(listen='127.0.0.1', port=PORT, url_path=TOKEN)
    s = updater.bot.set_webhook(url='https://{}/{}'.format(HOSTNAME, TOKEN),
                            certificate=open('cert.pem', 'rb'))
    if s:
        logger.info('Webhook is set successfully!')
        updater.idle()
    else:
        logger.info('Webhook setup is failed!')

# [END Webhook setup]
    


if __name__ == '__main__':
    main()
