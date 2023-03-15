import logging
import redis

from os import environ
from copy import copy
from datetime import date, datetime, time
import pytz


class DbConnectionSingleton:

    __instance = None

    @staticmethod
    def getInstance():
        if DbConnectionSingleton.__instance is None:
            DbConnectionSingleton()
        return DbConnectionSingleton.__instance

    def __init__(self):
        if DbConnectionSingleton.__instance is not None:
            raise Exception("This class is a singleton, and an instance exists yet!")
        else:
            DbConnectionSingleton.__instance = self
            self._db_connect()

    def _db_connect(self):
        try:
            self._db_host = environ['REDIS_HOST']
            self._db_port = environ['REDIS_PORT']
            self._db_name = environ['REDIS_DB']
            self._db_pass = environ['REDIS_PASS']
            self._timezone = pytz.timezone(environ["TZ"])
        except KeyError:
            logging.warning("Unable to load DB connection settings from environment variables:"
                            " falling back to defaults")
            self._db_host = 'localhost'
            self._db_port = 6379
            self._db_name = 0
            self._db_pass = None
            self._timezone = pytz.timezone("Europe/Rome")

        finally:
            self._db_instance = redis.Redis(host=self._db_host,
                                            port=self._db_port,
                                            db=self._db_name,
                                            password=self._db_pass,
                                            decode_responses=True)

    def get_db_host(self):
        return copy(self._db_host)

    def get_db_port(self):
        return copy(self._db_port)

    def get_db_name(self):
        return copy(self._db_name)

    def get_db_pass(self):
        return copy(self._db_pass)

    def _validate_input_text(self, user_input):
        if (len(user_input) > 63):
            raise Exception("Wrong input! You must enter at most 63 characters")

    def _validate_input_date(self, user_input):
        try:
            datetime.strptime(user_input, "%Y-%m-%d").date()
        except ValueError:
            raise Exception("Wrong input! You must enter a date in the format YYYY-MM-DD")

    def _validate_input_quantity(self, user_input):
        try:
            int(user_input)
        except ValueError:
            raise Exception("Wrong input! You must enter an integer")

    def get_current_date(self):
        return date.today()

    def get_notify_time(self):
        # The job_queue timers will use the offset from TZ env var!
        _notify_time = time(8, 0, 0)
        _notify_date = self.get_current_date()
        _notify_at = datetime(year=_notify_date.year,
                              month=_notify_date.month,
                              day=_notify_date.day,
                              hour=_notify_time.hour,
                              minute=_notify_time.minute,
                              second=_notify_time.second,
                              tzinfo=self._timezone)
        return _notify_at

    def add_pod(self, chatid: str) -> None:
        pass

    def is_pod_registered(self, chatid: str) -> bool:
        return True
