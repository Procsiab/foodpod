import logging

from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler
from telegram.ext import Updater, Filters
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update, CallbackQuery
from telegram.error import BadRequest
from TelegramSecretsSingleton import TelegramSecretsSingleton
from DbConnectionSingleton import DbConnectionSingleton


class FoodPodBot:

    def __init__(self, secrets: TelegramSecretsSingleton, db: DbConnectionSingleton):
        self._updater = Updater(token=secrets.get_telegram_bot_token(), use_context=True,
                                request_kwargs={"connect_timeout": 20})
        self._dispatcher = self._updater.dispatcher
        self._job_queue = self._updater.job_queue
        self._auth_users = secrets.get_auth_users_list()
        self._db_connection = db
        # Add handlers and jobs to the dispatcher
        start_handler = CommandHandler('start', self._callback_start)
        self._dispatcher.add_handler(start_handler)
        info_handler = CommandHandler('server_info', self._callback_info)
        self._dispatcher.add_handler(info_handler)
        items_handler = CommandHandler('items', self._callback_items)
        self._dispatcher.add_handler(items_handler)
        stop_handler = CommandHandler('stop', self._callback_stop)
        self._dispatcher.add_handler(stop_handler)
        check_handler = CommandHandler('check', self._callback_check)
        self._dispatcher.add_handler(check_handler)
        inline_button_handler = CallbackQueryHandler(self._callback_inline_button)
        self._dispatcher.add_handler(inline_button_handler)
        # Handler for unknown commands, add last
        unknown_handler = MessageHandler(Filters.command, self._callback_unknown)
        self._dispatcher.add_handler(unknown_handler)
        # Handler for any string message, used to parse user input
        string_handler = MessageHandler(Filters.update.message & Filters.text & (~Filters.command),
                                        self._callback_message)
        self._dispatcher.add_handler(string_handler)
        # Handler to print error messages
#        self._dispatcher.add_error_handler(self._callback_error)

    def _callback_start(self, update, context):
        _username = update.message.from_user.username
        _chatid = str(update.message.chat.id)
        if _chatid in self._auth_users:
            context.bot.send_message(chat_id=_chatid,
                                     text="🔧 Welcome, {}".format(_username))
            self._register_new_pod(_chatid, context.bot)
        else:
            context.bot.send_message(chat_id=_chatid,
                                     text="🚧 This bot will only talk to authorized users!")
            logging.info("The unauthorized user {} [{}] has called the start function"
                         .format(_username, _chatid))

    def _callback_stop(self, update, context):
        _chatid = str(update.message.chat.id)
        cmd_name = self._db_connection.get_global_cmd_name(_chatid)
        if (cmd_name == "none"):
            update.message.reply_text("There's no action in progress to cancel")
        else:
            _username = update.message.from_user.username
            logging.info("The user {} [{}] has cancelled the operation '{}'"
                         .format(_username, _chatid, cmd_name))
            self._db_connection.set_global_cmd_name(_chatid, "none")
            self._db_connection.set_global_cmd_arg(_chatid, "none")
            update.message.reply_text("Operation cancelled")

    def _callback_info(self, update, context):
        _username = update.message.from_user.username
        _chatid = str(update.message.chat.id)
        logging.info("The user {} [{}] has called the server_info function"
                     .format(_username, _chatid))
        if _chatid in self._auth_users:
            context.bot.send_message(chat_id=_chatid,
                                     text=self._db_connection.get_info())

    def _callback_unknown(self, update, context):
        _chatid = str(update.message.chat.id)
        context.bot.send_message(chat_id=_chatid,
                                 text="🚧 The provided command was not recognized!")
        _username = update.message.from_user.username
        logging.info("The user {} [{}] has sent an unknown command: '{}'"
                     .format(_username, _chatid, update.message.text))

    def _callback_error(self, update, context):
        try:
            _chatid = str(update.message.chat.id)
            if (_chatid is not None):
                context.bot.send_message(chat_id=_chatid,
                                         text="🚨 The following error occurred, contact an administrator: {}"
                                         .format(context.error))
        except AttributeError:
            pass
        logging.warning("Could not send the error notification to the user: unable to get the chat ID")
        logging.error("During update {}, an error occurred: {}"
                      .format(update, context.error))

    def _register_new_pod(self, chatid, bot):
        if (not self._db_connection.is_pod_registered(chatid)):
            self._db_connection.add_pod(chatid)
            self._db_connection.set_global_cmd_name(chatid, "none")
            self._db_connection.set_global_cmd_arg(chatid, "none")
            bot.send_message(chat_id=chatid,
                             text="🔧 You have registered this chat as a new 'Food Pod'; " +
                             "use the bot's commands to add food storages and assign items to them")
            logging.info("Registered new Food Pod with ID '{}'"
                         .format(chatid))
        else:
            bot.send_message(chat_id=chatid,
                             text="🚧 This chat was already registered as a Food Pod!")

    def _callback_items(self, update, context):
        _chatid = str(update.message.chat.id)
        _username = update.message.from_user.username
        self._list_storage(update, _chatid)
        logging.debug("The user {} [{}] called the items function"
                      .format(_username, _chatid))

    def _callback_inline_button(self, update, context):
        _query = update.callback_query
        selected_button_list = _query.data.split(':')
        pressed_button = {
            "foodpod_id": selected_button_list[0],
            "button_type": selected_button_list[1],
            "button_value": selected_button_list[2]
        }
        logging.debug("Inline button callback: {}".format(pressed_button))
        cmd_name = pressed_button["button_value"]
        cmd_arg = self._db_connection.get_global_cmd_arg(pressed_button["foodpod_id"])
        if (pressed_button["button_type"] == "storage_button"):
            self._list_items(_query,
                             pressed_button["foodpod_id"],
                             cmd_name)
            cmd_arg = cmd_name
        elif (pressed_button["button_type"] == "add_button"):
            if (cmd_name == "new_storage"):
                _query.edit_message_text(text="Write the new storage location name, use /stop to abort")
                cmd_arg = "none"
            if (cmd_name == "new_item"):
                _query.edit_message_text(text="Write the new item name, use /stop to abort")
        elif (pressed_button["button_type"] == "modify_item"):
            item_string = pressed_button["button_value"].split('@')
            storage_name = item_string[0]
            item_name = item_string[1]
            _query.edit_message_text(text="Write the quantity as an integer, use /stop to abort")
            cmd_arg = cmd_name
            cmd_name = "modify_item"
        elif (pressed_button["button_type"] == "del_button"):
            if (cmd_name == "del_storage"):
                self._del_storage_dialog(_query, pressed_button["foodpod_id"], cmd_arg)
            if ("del_item" in cmd_name):
                self._del_item_dialog(_query, pressed_button["foodpod_id"], cmd_arg, cmd_name)
            if ("del_expired@" in cmd_name):
                storage_name = cmd_name.split('@')[1]
                self._db_connection.empty_expired(pressed_button["foodpod_id"], storage_name)
                cmd_name = storage_name
                cmd_arg = cmd_name
                self._list_items(_query, pressed_button["foodpod_id"], cmd_name)
        elif (pressed_button["button_type"] == "del_storage_confirm"):
            self._db_connection.del_storage(pressed_button["foodpod_id"], cmd_arg)
            _query.edit_message_text(text="Deleted storage {}".format(cmd_arg))
            cmd_name = "none"
            cmd_arg = "none"
        elif (pressed_button["button_type"] == "del_item_confirm"):
            item_string = pressed_button["button_value"].split('@')
            storage_name = item_string[0]
            item_name = item_string[1]
            self._db_connection.del_item(pressed_button["foodpod_id"], storage_name, item_name)
            _query.edit_message_text(text="Deleted item {} from storage {}".format(item_name, storage_name))
            cmd_name = "none"
            cmd_arg = "none"
        elif (pressed_button["button_type"] == "expired_button"):
            self._list_storage_expired_items(_query, pressed_button["foodpod_id"], cmd_name)
        elif (pressed_button["button_type"] == "back_button"):
            if (cmd_name == "back_bot"):
                _query.edit_message_text(text="Back to the main bot's chat")
                cmd_name = "none"
                cmd_arg = "none"
            if (cmd_name == "back_storage"):
                cmd_name = cmd_arg
                self._list_storage(_query, pressed_button["foodpod_id"])
            if ("back_item_list@" in cmd_name):
                cmd_name = pressed_button["button_value"].split('@')[1]
                self._list_items(_query, pressed_button["foodpod_id"], cmd_name)
            if ("back_item@" in cmd_name):
                cmd_name = pressed_button["button_value"].split('@')[1]
                self._show_item(_query, pressed_button["foodpod_id"], cmd_arg, cmd_name)
        elif (pressed_button["button_type"] == "item_button"):
            item_name = cmd_name
            if ("item_expired@" in cmd_name):
                item_name = cmd_name.split("@")[1]
            self._show_item(_query,
                            pressed_button["foodpod_id"],
                            cmd_arg,
                            item_name)
        elif (pressed_button["button_type"] == "item_check_button"):
            if (cmd_name == "show_list"):
                self._callback_check(_query, context)
            else:
                item_name = cmd_name.split("@")[0]
                storage_name = cmd_name.split("@")[1]
                cmd_arg = "item_check_button"
                self._db_connection.set_global_cmd_arg(pressed_button["foodpod_id"], cmd_arg)
                self._show_item(_query,
                                pressed_button["foodpod_id"],
                                storage_name,
                                item_name)
        else:
            logging.warning("Callback not caught inside _callback_inline_button function, due to unknown button type '{}'".format(pressed_button["button_type"]))
        self._db_connection.set_global_cmd_name(pressed_button["foodpod_id"],
                                                cmd_name)
        self._db_connection.set_global_cmd_arg(pressed_button["foodpod_id"],
                                               cmd_arg)

    def _callback_message(self, update, context):
        _chatid = str(update.message.chat.id)
        cmd_name = self._db_connection.get_global_cmd_name(_chatid)
        cmd_arg = self._db_connection.get_global_cmd_arg(_chatid)
        reply_text = None
        keyboard_markup = None
        is_invalid_callback = False
        if (cmd_name == "new_storage"):
            storage_name = update.message.text
            self._db_connection.add_storage(_chatid, storage_name)
            reply_text = "Storage '{}' added to the Food Pod".format(storage_name)
            cmd_name = "none"
            cmd_arg = "none"
        elif (cmd_name == "new_item"):
            item_name = update.message.text
            storage_name = cmd_arg
            self._db_connection.add_item(_chatid, storage_name, item_name)
            reply_text = "Item '{}' added to the storage '{}'\nWrite the quantity as an integer, use /stop to abort".format(item_name, storage_name)
            cmd_arg = storage_name+"@"+item_name
            cmd_name = "modify_item"
        elif (cmd_name == "modify_item"):
            item_quantity = update.message.text
            item_string = cmd_arg.split('@')
            storage_name = item_string[0]
            item_name = item_string[1]
            self._db_connection.set_item_quantity(_chatid, storage_name, item_name, item_quantity)
            reply_text = "Write the expiration date in ISO format, use /stop to abort"
            cmd_name = "modify_item2"
        elif (cmd_name == "modify_item2"):
            item_expiry = update.message.text
            item_string = cmd_arg.split('@')
            storage_name = item_string[0]
            item_name = item_string[1]
            self._db_connection.set_item_expiry(_chatid, storage_name, item_name, item_expiry)
            reply_text = "Saved changes for item '{}'".format(item_name)
            cmd_name = "none"
            cmd_arg = "none"
        else:
            logging.warning("Callback not caught inside _callback_message function, due to unknown global command name '{}'".format(cmd_name))
            is_invalid_callback = True
        if (not is_invalid_callback):
            self._db_connection.set_global_cmd_name(_chatid, cmd_name)
            self._db_connection.set_global_cmd_arg(_chatid, cmd_arg)
            update.message.reply_text(reply_text, reply_markup=keyboard_markup)

    def _callback_check(self, query, context):
        _chatid = str(query.message.chat.id)
        _null_inline_button = [InlineKeyboardButton("~ Empty ~", callback_data=_chatid+":empty_button:none")]
        inline_keyboard = [_null_inline_button]
        item_list = self._db_connection.get_item_expiring_or_bad_list(_chatid)
        if (len(item_list) > 0):
            inline_keyboard.pop()
            for item_dict in item_list:
                name_fmt_str = "{} ({} days ago)"
                if (int(item_dict["days_expired"]) < 0):
                    name_fmt_str = "{} (in {} days)"
                item_name = name_fmt_str.format(self._decorate_item_name(_chatid,
                                                                         item_dict["storage"],
                                                                         item_dict["item_name"]),
                                                abs(int(item_dict["days_expired"])))
                inline_button = [InlineKeyboardButton(item_name,
                                                      callback_data=_chatid+":item_check_button:"+item_dict["item_name"]+"@"+item_dict["storage"])]
                inline_keyboard.append(inline_button)
        inline_keyboard.append([])
        inline_keyboard[-1].append(InlineKeyboardButton("⬅️  Back", callback_data=_chatid+":back_button:back_bot"))
        keyboard_markup = InlineKeyboardMarkup(inline_keyboard)
        reply_text = "The following items are going to expire shortly or have already gone bad"
        if (type(query) is Update):
            query.message.reply_text(reply_text,
                                     reply_markup=keyboard_markup)
        elif (type(query is CallbackQuery)):
            msg_id = query.message.message_id
            chat_id = query.message.chat.id
            query.bot.edit_message_text(reply_text,
                                        message_id=msg_id, chat_id=chat_id,
                                        reply_markup=keyboard_markup)

    def _list_storage(self, query, chatid):
        _null_inline_button = [InlineKeyboardButton("~ Empty ~", callback_data=chatid+":empty_button:none")]
        inline_keyboard = [_null_inline_button]
        storage_list = self._db_connection.get_storage_list(chatid)
        if (len(storage_list) > 0):
            inline_keyboard.pop()
            for storage_location in storage_list:
                inline_button = [InlineKeyboardButton(storage_location,
                                                      callback_data=chatid+":storage_button:"+storage_location)]
                inline_keyboard.append(inline_button)
        inline_keyboard.append([])
        inline_keyboard[-1].append(InlineKeyboardButton("🔄 Add", callback_data=chatid+":add_button:new_storage"))
        inline_keyboard[-1].append(InlineKeyboardButton("⬅️  Back", callback_data=chatid+":back_button:back_bot"))
        keyboard_markup = InlineKeyboardMarkup(inline_keyboard)
        reply_text = "Select a storage location to list its contents"
        if (type(query) is Update):
            query.message.reply_text(reply_text,
                                     reply_markup=keyboard_markup)
        elif (type(query is CallbackQuery)):
            msg_id = query.message.message_id
            chat_id = query.message.chat.id
            query.bot.edit_message_text(reply_text,
                                        message_id=msg_id, chat_id=chat_id,
                                        reply_markup=keyboard_markup)
        else:
            logging.warning("Unknown type '{}' for query argument in function _list_storage (pod ID: {})".format(type(query), chatid))

    def _list_items(self, query, chatid, storage):
        _null_inline_button = [InlineKeyboardButton("~ Empty ~", callback_data=chatid+":empty_button:none")]
        inline_keyboard = [_null_inline_button]
        item_list = self._db_connection.get_item_list(chatid, storage)
        if (len(item_list) > 0):
            inline_keyboard.pop()
            for item_name in item_list:
                button_label = self._decorate_item_name(chatid, storage, item_name)
                inline_button = [InlineKeyboardButton(button_label,
                                                      callback_data=chatid+":item_button:"+item_name)]
                inline_keyboard.append(inline_button)
        inline_keyboard.append([])
        inline_keyboard[-1].append(InlineKeyboardButton("🔄 Add", callback_data=chatid+":add_button:new_item"))
        inline_keyboard[-1].append(InlineKeyboardButton("⬅️  Back", callback_data=chatid+":back_button:back_storage"))
        if (len(item_list) > 0):
            inline_keyboard.append([InlineKeyboardButton("😵  Filter expired",
                                                         callback_data=chatid+":expired_button:"+storage)])
        inline_keyboard.append([InlineKeyboardButton("⤵️  Delete {}".format(storage),
                                                     callback_data=chatid+":del_button:del_storage")])
        keyboard_markup = InlineKeyboardMarkup(inline_keyboard)
        msg_id = query.message.message_id
        chat_id = query.message.chat.id
        query.bot.edit_message_text("📦 Storage: *{}*\nSelect an item to list its properties"
                                    .format(storage),
                                    message_id=msg_id, chat_id=chat_id,
                                    reply_markup=keyboard_markup,
                                    parse_mode="markdown")

    def _decorate_item_name(self, chatid, storage, item):
        if (self._db_connection.get_item_quantity(chatid, storage, item) == 0):
            return item + "❔"
        else:
            item_expiry = self._db_connection.get_item_expiry(chatid, storage, item)
            current_date = self._db_connection.get_current_date()
            expires_in = (item_expiry - current_date).days
            if (expires_in < 0):
                return item+"‼️ "
            elif (expires_in == 0):
                return item+"❗️"
            elif (expires_in <= 2):
                return item+"❕"
            else:
                return item

    def _list_storage_expired_items(self, query, chatid, storage):
        _null_inline_button = [InlineKeyboardButton("~ Empty ~", callback_data=chatid+":empty_button:none")]
        inline_keyboard = [_null_inline_button]
        item_list = self._db_connection.get_item_expired_list(chatid, storage)
        if (len(item_list) > 0):
            inline_keyboard.pop()
            for item_dict in item_list:
                item_name = "{} ({} days ago)".format(item_dict["item_name"],
                                                        item_dict["days_expired"])
                inline_button = [InlineKeyboardButton(item_name,
                                                      callback_data=chatid+":item_button:item_expired@"+item_dict["item_name"])]
                inline_keyboard.append(inline_button)
        inline_keyboard.append([])
        inline_keyboard.append([InlineKeyboardButton("⬅️  Back",
                                                     callback_data=chatid+":back_button:back_item_list@"+storage)])
        if (len(item_list) > 0):
            inline_keyboard.append([InlineKeyboardButton("🗑 Empty all expired",
                                                         callback_data=chatid+":del_button:del_expired@"+storage)])
        keyboard_markup = InlineKeyboardMarkup(inline_keyboard)
        msg_id = query.message.message_id
        chat_id = query.message.chat.id
        query.bot.edit_message_text("😵 *Expired* (_{}_)\nSelect an item to list its properties"
                                    .format(storage),
                                    message_id=msg_id, chat_id=chat_id,
                                    reply_markup=keyboard_markup,
                                    parse_mode="markdown")

    def _show_item(self, query, chatid, storage_name, item_name):
        inline_keyboard = []
        inline_keyboard.append([])
        inline_keyboard[-1].append(InlineKeyboardButton("ℹ️  Modify", callback_data=chatid+":"+"modify_item"+":"+storage_name+"@"+item_name))
        callback_button_value = query.data.split(':')[2]
        if ("item_expired@" in callback_button_value):
            inline_keyboard[-1].append(InlineKeyboardButton("⬅️  Back", callback_data=chatid+":expired_button:"+storage_name))
        elif (self._db_connection.get_global_cmd_arg(chatid) == "item_check_button"):
            inline_keyboard[-1].append(InlineKeyboardButton("⬅️  Back", callback_data=chatid+":item_check_button:show_list"))
        else:
            inline_keyboard[-1].append(InlineKeyboardButton("⬅️  Back", callback_data=chatid+":back_button:back_item_list@"+storage_name))
        inline_keyboard.append([InlineKeyboardButton("⤵️  Delete {}".format(item_name),
                                                     callback_data=chatid+":del_button:del_item@"+item_name)])
        keyboard_markup = InlineKeyboardMarkup(inline_keyboard)
        msg_id = query.message.message_id
        chat_id = query.message.chat.id
        msg_text = "🍴 Item: *{}* ({})\n\n🔢 _Quantity_: `{}`\n📅 _Expires on_: `{}`".format(item_name.upper(), storage_name,
                                                                      self._db_connection.get_item_quantity(chatid, storage_name, item_name),
                                                                      self._db_connection.get_item_expiry(chatid, storage_name, item_name))
        try:
            query.bot.edit_message_text(msg_text,
                                        message_id=msg_id, chat_id=chat_id,
                                        reply_markup=keyboard_markup,
                                        parse_mode="markdown")
        except BadRequest:
            pass

    def _del_storage_dialog(self, query, chatid, storage):
        inline_keyboard = []
        inline_keyboard.append([])
        inline_keyboard[-1].append(InlineKeyboardButton("YES", callback_data=chatid+":del_storage_confirm:"+storage))
        inline_keyboard[-1].append(InlineKeyboardButton("NO", callback_data=chatid+":back_button:back_item_list@"+storage))
        keyboard_markup = InlineKeyboardMarkup(inline_keyboard)
        msg_id = query.message.message_id
        chat_id = query.message.chat.id
        query.bot.edit_message_text("Are you sure you want to delete '{}' storage and its {} items?"
                                    .format(storage, self._db_connection.get_item_list_len(chatid, storage)),
                                    message_id=msg_id, chat_id=chat_id,
                                    reply_markup=keyboard_markup)

    def _del_item_dialog(self, query, chatid, storage, item):
        item_name = item.split('@')[1]
        inline_keyboard = []
        inline_keyboard.append([])
        inline_keyboard[-1].append(InlineKeyboardButton("YES", callback_data=chatid+":del_item_confirm:"+storage+"@"+item_name))
        inline_keyboard[-1].append(InlineKeyboardButton("NO", callback_data=chatid+":back_button:back_item@"+item_name))
        keyboard_markup = InlineKeyboardMarkup(inline_keyboard)
        msg_id = query.message.message_id
        chat_id = query.message.chat.id
        query.bot.edit_message_text("Are you sure you want to delete '{}' item from '{}' storage?"
                                    .format(item_name, storage),
                                    message_id=msg_id, chat_id=chat_id,
                                    reply_markup=keyboard_markup)

    def run(self):
        self._updater.start_polling()
        logging.info("Bot started, press CTRL+C to stop it")
        self._updater.idle()

    def halt(self):
        logging.info("Tearing down the Bot service")
        self._updater.stop()
