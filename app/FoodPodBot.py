import logging

from telegram.ext import (
    CallbackContext,
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    Updater,
)
from telegram import Update
from TelegramSecretsSingleton import TelegramSecretsSingleton
from DbConnectionSingleton import DbConnectionSingleton
from StateList import Status


class FoodPodBot:

    def __init__(self, secrets: TelegramSecretsSingleton, db: DbConnectionSingleton):
        self._updater = Updater(token=secrets.get_telegram_bot_token(), use_context=True,
                                request_kwargs={"connect_timeout": 20})
        self._dispatcher = self._updater.dispatcher
        self._job_queue = self._updater.job_queue
        self._auth_users = secrets.get_auth_users_list()
        self._db_connection = db
        # Add daily recurring job for the report notification
        self._job_queue.run_daily(self._callback_notify_expiry,
                                  time=self._db_connection.get_notify_time())
        # Add handlers and jobs to the dispatcher
        start_handler = CommandHandler('start', self._callback_start)
        self._dispatcher.add_handler(start_handler)
        pods_handler = CommandHandler('pods', self._callback_pods)
        self._dispatcher.add_handler(pods_handler)
        stop_handler = CommandHandler('stop', self._callback_stop)
        self._dispatcher.add_handler(stop_handler)
        check_handler = CommandHandler('check', self._callback_check)
        self._dispatcher.add_handler(check_handler)
        # Handler for unknown commands, add last
        unknown_handler = MessageHandler(Filters.command, self._callback_unknown)
        self._dispatcher.add_handler(unknown_handler)
        # Handler to print error messages
        self._dispatcher.add_error_handler(self._callback_error)

        # Manage FSM conversation implementation
        conversation_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self._callback_start)],
            states={
                Status.POD_LIST: [CommandHandler('pods', self._callback_pods)],
            },
            fallbacks=[CommandHandler('stop', self._callback_stop)],
        )
        self._dispatcher.add_handler(conversation_handler)

    def _callback_start(self, update: Update, context: CallbackContext) -> int:
        """Register the chat for a new FoodPod account, if not registered yet"""
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
        return Status.POD_LIST

    def _callback_stop(self, update, context):
        pass
        # Reset FSM status

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
                                         text="🚨 The following error occurred: {}"
                                         .format(str(context.error)))
        except AttributeError:
            logging.warning("Could not notify the user: unable to get the chat ID")
        finally:
            logging.error("During update {}, an error occurred: {}"
                          .format(update, context.error))

    def _callback_pods(self, query, context):
        pass
        # List available pods for registered chat

    def _callback_notify_expiry(self, context: CallbackContext):
        pass
        # Bad items notification

    def _callback_check(self, query, context):
        pass
        # Manually check bad items

    def _register_new_pod(self, chatid: str, bot: CallbackContext):
        if (not self._db_connection.is_pod_registered(chatid)):
            self._db_connection.add_pod(chatid)
            bot.send_message(chat_id=chatid,
                             text="🔧 You have registered this chat as a new 'Food Pod'; " +
                             "use the bot's commands to add pods and assign items to them")
            logging.info("Registered new Food Pod with ID '{}'"
                         .format(chatid))
        else:
            bot.send_message(chat_id=chatid,
                             text="🚧 This chat was already registered as a Food Pod!")

    def run(self):
        self._updater.start_polling()
        logging.info("Bot started, press CTRL+C to stop it")
        self._updater.idle()

    def halt(self):
        logging.info("Tearing down the Bot service")
        self._updater.stop()
