import logging
import requests

from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from datetime import datetime

TELEGRAM_TOKEN = "{!PUT TELEGRAM BOT TOKEN HERE!}"
WATCH_COUNTRY = "Russia"
EREP_BATTLES_URL = "https://www.erepublik.com/en/military/campaignsJson/list"
EREP_BATTLE_URL = "https://www.erepublik.com/en/military/battlefield/"

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)
chats = dict()


def start(update: Update, context: CallbackContext) -> None:
    global chats
    update.message.reply_text('Hi!')
    chat_id = update.message.chat_id
    if chat_id not in chats.keys():
        context.job_queue.run_once(
            alarm, 10, context=chat_id, name=str(chat_id))
        chats[chat_id] = set()


def stop(update: Update, context: CallbackContext) -> None:
    global chats
    update.message.reply_text('Bye!')
    chat_id = update.message.chat_id
    current_jobs = context.job_queue.get_jobs_by_name(chat_id)
    if current_jobs:
        for job in current_jobs:
            job.schedule_removal()
    if chat_id in chats.keys():
        del chats[chat_id]


def helpme(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        'Hi! /start, /stop, /help and /list are supported. Try it...')


def get_wall(b): return list(b['div'].values())[0]['wall']


def inv_co(b): return max([0] + [i['reward']
                                 for i in list(b['div'].values())[0]['co']['inv']]) // 1000


def def_co(b): return max([0] + [i['reward']
                                 for i in list(b['div'].values())[0]['co']['def']]) // 1000


def wall(b):
    w = get_wall(b)
    larrow = "&gt;" if w['dom'] == 50.0 or w['for'] == b['inv']['id'] else '&lt;'
    rarrow = "&lt;" if w['dom'] == 50.0 or w['for'] == b['def']['id'] else '&gt;'
    return f"{larrow} {int(w['dom'])}% {rarrow}"


def battle_time(b):
    return int((datetime.utcnow() - datetime.utcfromtimestamp(int(b['start']))).total_seconds() // 60)


def create_message(b, c):
    t = battle_time(b)
    co_inv, co_def = inv_co(b), def_co(b)
    co_inv = f", {co_inv}k" if co_inv > 0 else ""
    co_def = f", {co_def}k" if co_def > 0 else ""
    erep_url = f"{EREP_BATTLE_URL}{b['id']}"
    b_id = f"{b['id']}-R{b['zone_id']}"
    country_inv = c[b['inv']['id']]
    country_def = c[b['def']['id']]
    return f"{country_inv} ({b['inv']['points']}{co_inv}) {wall(b)} {country_def} ({b['def']['points']}{co_def})\n" +\
        f"<a href='{erep_url}'>{b_id}-T{t}: {b['region']['name']}/{b['city']['name']}</a>"


def load_battles():
    response = requests.get(EREP_BATTLES_URL).json()
    battles = response['battles']
    countries = response['countries']
    country = next((v['id'] for k, v in countries.items()
                    if v['name'] == WATCH_COUNTRY))
    countries = dict([(v['id'], v['name']) for k, v in countries.items()])
    battles = [b for b in battles.values() if b['type'] ==
               'aircraft' and country == b['inv']['id']]

    return battles, countries


def alarm(context) -> None:
    global chats
    job = context.job
    chat_id = job.context
    if chat_id not in chats.keys():
        return

    monitor = chats[chat_id]
    context.job_queue.run_once(alarm, 60, context=chat_id, name=str(chat_id))

    battles, countries = load_battles()
    ids = set()
    for b in battles:
        ids.add(str(b['id']))
        w = get_wall(b)
        if w['for'] == b['def']['id']:
            continue
        t = battle_time(b)
        if t < 30:
            continue
        t = 30 * (t // 30)
        bname = f"{b['id']}-R{b['zone_id']}-T{t}"
        if bname not in monitor:
            monitor.add(bname)
            context.bot.send_message(
                chat_id,
                text=create_message(b, countries),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
    for b in [i for i in monitor if i.split('-')[0] not in ids]:
        monitor.remove(b)


def show_battles(update: Update, context: CallbackContext) -> None:
    global chats
    chat_id = update.message.chat_id
    battles, countries = load_battles()
    monitor = chats.get(chat_id)
    if not monitor:
        update.message.reply_text('Try /start first...')
        return

    if monitor:
        update.message.reply_text(str(monitor))
    else:
        update.message.reply_text('No battles.')


def main() -> None:
    updater = Updater(
        TELEGRAM_TOKEN,
        use_context=True
    )

    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("stop", stop))
    dispatcher.add_handler(CommandHandler("help", helpme))
    dispatcher.add_handler(CommandHandler("list", show_battles))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
