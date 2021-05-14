import logging
import redis

from os import environ
from copy import copy
from datetime import date, datetime


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
        except KeyError:
            logging.warning("Unable to load DB connection settings from environment variables:"
                            " falling back to defaults")
            self._db_host = 'localhost'
            self._db_port = 6379
            self._db_name = 0
            self._db_pass = None
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
        global_pods = self._db_instance.lrange("global:pods", 0, -1)
        for registered_id in global_pods:
            if registered_id == chatid:
                return True
        return False

    def add_pod(self, chatid):
        self._db_instance.lpush("global:pods", chatid)

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
        return self._db_instance.hget(chatid + ":" + storage + ":" + item_name, "Expire")

    def set_item_quantity(self, chatid, storage, item_name, quantity):
        self._db_instance.hset(chatid + ":" + storage + ":" + item_name, "Quantity", quantity)

    def set_item_expiry(self, chatid, storage, item_name, expiry):
        self._db_instance.hset(chatid + ":" + storage + ":" + item_name, "Expire", expiry)

    def get_item_list(self, chatid, storage):
        return self._db_instance.lrange(chatid + ":" + storage + ":item_list", 0, -1)

    def get_item_list_len(self, chatid, storage):
        return self._db_instance.llen(chatid + ":" + storage + ":item_list")

    def get_item_expired_list(self, chatid, storage):
        item_list = self._db_instance.lrange(chatid + ":" + storage + ":item_list", 0, -1)
        current_date = date.today()
        expired_items_list = []
        for item_name in item_list:
            item_expiry_date = datetime.strptime(self.get_item_expiry(chatid,
                                                                      storage,
                                                                      item_name),
                                                 "%Y-%m-%d").date()
            item_quantity = int(self.get_item_quantity(chatid, storage, item_name))
            if (item_quantity > 0 and current_date > item_expiry_date):
                days_expired_delta = (current_date - item_expiry_date).days
                expired_items_list.append({"item_name": item_name,
                                           "days_expired": days_expired_delta})
        return sorted(expired_items_list, key=lambda k: k["days_expired"], reverse=True)

    def empty_expired(self, chatid, storage):
        expired_item_list = self.get_item_expired_list(chatid, storage)
        for expired_item_dict in expired_item_list:
            expired_item_name = expired_item_dict["item_name"]
            self.set_item_quantity(chatid, storage, expired_item_name, 0)
