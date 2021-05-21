import logging

from pathlib import Path
from copy import copy


class TelegramSecretsSingleton:

    __instance = None

    @staticmethod
    def getInstance():
        if TelegramSecretsSingleton.__instance is None:
            TelegramSecretsSingleton()
        return TelegramSecretsSingleton.__instance

    def __init__(self):
        if TelegramSecretsSingleton.__instance is not None:
            raise Exception("This class is a singleton, and an instance exists yet!")
        else:
            TelegramSecretsSingleton.__instance = self
            # Look for a secrets folder mounted in the root / (for the Linux container);
            # if not present, assume the folder is in the same directory from where the
            # program was launched
            _secrets_path = '/auth/'
            _secrets_folder = Path(_secrets_path)
            if not _secrets_folder.exists():
                _secrets_path = './.secrets/'
            try:
                with open(_secrets_path + 'TOKEN.secret', 'r') as secret:
                    self._telegram_bot_token = secret.read().rstrip()
                logging.debug("Constructor read {} value for 'telegram_bot_token': {}"
                              .format(type(self._telegram_bot_token), self._telegram_bot_token))
                with open(_secrets_path + 'AUTH_USERS.secret', 'r') as secret:
                    self._auth_users_list = []
                    for line in secret:
                        self._auth_users_list.append(line.rstrip())
                logging.debug("Constructor read {} value for 'auth_users_list': {}"
                              .format(type(self._auth_users_list), self._auth_users_list))
            except FileNotFoundError as fnf:
                logging.error("Unable to read the required secrets to contact Telegram's API: {}"
                              .format(fnf.filename))
                raise SecretsReadError

    def get_telegram_bot_token(self):
        return copy(self._telegram_bot_token)

    def get_auth_users_list(self):
        return copy(self._auth_users_list)


class SecretsReadError(Exception):
    # Raised if the constructor fails to load the required secrets
    pass
