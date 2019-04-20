#!/usr/bin/env python

import logging
from pymongo import MongoClient
from credentials import DBNAME, DBUSER, DBPASS, DBAUTH

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

# MongoDB connection
client = MongoClient()
db = client[DBNAME]
db.authenticate(DBUSER, DBPASS, source=DBAUTH)

CHIJRI_CONTENTS = [
{"_id": 1, "f29flg": False, "f30flg": False, "fadjst": 0}, 
{"_id": 2, "f29flg": False, "f30flg": False, "fadjst": 0}, 
{"_id": 3, "f29flg": False, "f30flg": False, "fadjst": 0}, 
{"_id": 4, "f29flg": False, "f30flg": False, "fadjst": 0}, 
{"_id": 5, "f29flg": False, "f30flg": False, "fadjst": 0}, 
{"_id": 6, "f29flg": False, "f30flg": False, "fadjst": 0}, 
{"_id": 7, "f29flg": False, "f30flg": False, "fadjst": 0}, 
{"_id": 8, "f29flg": False, "f30flg": False, "fadjst": 0}, 
{"_id": 9, "f29flg": False, "f30flg": False, "fadjst": 0}, 
{"_id": 10, "f29flg": False, "f30flg": False, "fadjst": 0}, 
{"_id": 11, "f29flg": False, "f30flg": False, "fadjst": 0}, 
{"_id": 12, "f29flg": False, "f30flg": False, "fadjst": 0}, 
]


def main():
    db.chijri.insert_many(CHIJRI_CONTENTS)

if __name__ == '__main__':
    main()