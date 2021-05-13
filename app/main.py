#!/usr/bin/env python3

import logging

from FoodPodBot import FoodPodBot as BOT
from TelegramSecretsSingleton import TelegramSecretsSingleton as TELEGRAM_SECRETS
from TelegramSecretsSingleton import SecretsReadError
from DbConnectionSingleton import DbConnectionSingleton as DB_CONNECTION

from sys import exit

logging.basicConfig(format='%(levelname)s | %(asctime)s | %(name)s | %(message)s',
                    level=logging.INFO)


# Main routine
def main():
    try:
        mySecrets = TELEGRAM_SECRETS()
        myDbConn = DB_CONNECTION()
    except SecretsReadError:
        logging.error("Without providing secrets, the Bot will not run")
        exit(1)
    myBot = BOT(mySecrets, myDbConn)
    try:
        myBot.run()
    except Exception as e:
        logging.error("System error: {}".format(e.message))
    finally:
        myBot.halt()


# Run Main
if __name__ == "__main__":
    main()
