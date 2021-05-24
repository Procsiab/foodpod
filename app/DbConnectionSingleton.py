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

    def get_info(self):
        try:
            res = self._db_instance.info(section='Server')
        except redis.exceptions.ConnectionError:
            res = "🚨 Error contacting the database backend"
            logging.error("Error contacting the database backend: ConnectionError at {}:{}"
                          .format(self._db_host, self._db_port))
        finally:
            return res

    def is_pod_registered(self, chatid):
        # TODO: Check why lpos method is not available for a redis.Redis instance
        global_pods = self.get_pods()
        for registered_id in global_pods:
            if registered_id == chatid:
                return True
        return False

    def _validate_input_text(self, user_input):
        if (len(user_input) > 20 or ':' in user_input or '@' in user_input):
            raise Exception("Wrong input! You must enter at most 20 characters, avoiding ':' and '@'")

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

    def add_pod(self, chatid):
        self._db_instance.lpush("global:pods", chatid)

    def get_pods(self):
        return self._db_instance.lrange("global:pods", 0, -1)

    def set_global_cmd_name(self, chatid, cmd_name):
        self._db_instance.hset(chatid+":global_command", "Name", cmd_name)

    def set_global_cmd_arg(self, chatid, cmd_arg):
        self._db_instance.hset(chatid+":global_command", "Arg", cmd_arg)

    def get_global_cmd_name(self, chatid):
        return self._db_instance.hget(chatid+":global_command", "Name")

    def get_global_cmd_arg(self, chatid):
        return self._db_instance.hget(chatid+":global_command", "Arg")

    def add_storage(self, chatid, name):
        self._db_instance.lpush(chatid + ":storage_list", name)

    def get_storage_list(self, chatid):
        return self._db_instance.lrange(chatid + ":storage_list", 0, -1)

    def del_storage(self, chatid, storage):
        for item in self.get_item_list(chatid, storage):
            self._db_instance.delete(chatid + ":" + storage + ":" + item)
        self._db_instance.delete(chatid + ":" + storage + ":item_list")
        self._db_instance.lrem(chatid + ":storage_list", 1, storage)

    def add_item(self, chatid, storage, item_name):
        self._db_instance.lpush(chatid + ":" + storage + ":item_list", item_name)
        self.set_item_quantity(chatid, storage, item_name, 0)
        self.set_item_expiry(chatid, storage, item_name, "2000-12-31")

    def del_item(self, chatid, storage, item_name):
        self._db_instance.delete(chatid + ":" + storage + ":" + item_name)
        self._db_instance.lrem(chatid + ":" + storage + ":item_list", 1, item_name)

    def get_item_quantity(self, chatid, storage, item_name):
        return int(self._db_instance.hget(chatid + ":" + storage + ":" + item_name, "Quantity"))

    def get_item_expiry(self, chatid, storage, item_name):
        return datetime.strptime(self._db_instance.hget(chatid+":"+storage+":"+item_name, "Expire"),
                                 "%Y-%m-%d").date()

    def set_item_quantity(self, chatid, storage, item_name, quantity):
        self._db_instance.hset(chatid + ":" + storage + ":" + item_name, "Quantity", quantity)

    def set_item_expiry(self, chatid, storage, item_name, expiry):
        self._db_instance.hset(chatid + ":" + storage + ":" + item_name, "Expire", expiry)

    def get_item_list(self, chatid, storage):
        return self._db_instance.lrange(chatid + ":" + storage + ":item_list", 0, -1)

    def get_item_list_len(self, chatid, storage):
        return self._db_instance.llen(chatid + ":" + storage + ":item_list")

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

    def get_item_expired_list(self, chatid, storage):
        item_list = self._db_instance.lrange(chatid + ":" + storage + ":item_list", 0, -1)
        current_date = self.get_current_date()
        expired_items_list = []
        for item_name in item_list:
            item_expiry_date = self.get_item_expiry(chatid, storage, item_name)
            item_quantity = int(self.get_item_quantity(chatid, storage, item_name))
            if (item_quantity > 0 and current_date > item_expiry_date):
                days_expired_delta = (current_date - item_expiry_date).days
                expired_items_list.append({"item_name": item_name,
                                           "storage": storage,
                                           "days_expired": int(days_expired_delta)})
        return sorted(expired_items_list, key=lambda k: k["days_expired"], reverse=True)

    def get_item_expiring_or_bad_list(self, chatid):
        current_date = self.get_current_date()
        storage_list = self._db_instance.lrange(chatid + ":storage_list", 0, -1)
        expired_items_list = []
        for storage_name in storage_list:
            item_list = self._db_instance.lrange(chatid+":"+storage_name+":item_list", 0, -1)
            for item_name in item_list:
                item_expiry_date = self.get_item_expiry(chatid, storage_name, item_name)
                item_quantity = self.get_item_quantity(chatid, storage_name, item_name)
                days_expired_delta = (current_date - item_expiry_date).days
                if (item_quantity > 0 and days_expired_delta >= -2):
                    expired_items_list.append({"item_name": item_name,
                                               "storage": storage_name,
                                               "days_expired": int(days_expired_delta)})
        return sorted(expired_items_list, key=lambda k: k["days_expired"], reverse=True)

    def empty_expired(self, chatid, storage):
        expired_item_list = self.get_item_expired_list(chatid, storage)
        for expired_item_dict in expired_item_list:
            expired_item_name = expired_item_dict["item_name"]
            self.set_item_quantity(chatid, storage, expired_item_name, 0)
