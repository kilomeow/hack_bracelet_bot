# libs
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler, MessageFilter
from telegram import Bot, ReplyKeyboardMarkup, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.utils.request import Request

import config
import db

# creating bot

bot = Bot(config.data.token)
upd = Updater(bot=bot, use_context=True)
dp = upd.dispatcher

# logging
import logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)

import time
import datetime


## contstructing UI

# categories 
categories = ["Психология", "Гинекология", "Грудное вскармливание"]
other = ["Другое"]

def parse_faq(text):
    return [tuple(e.split("\n", 1)) for e in text.split("\n\n")]

def faq_from_txt(filename):
    return parse_faq(open(filename+".txt").read())

FAQ = {
    "Психология": faq_from_txt('psychology'),
    "Гинекология": faq_from_txt('gynecology'),
    "Грудное вскармливание": faq_from_txt('breast_feeding')
    }


# buttons

cancel = ["Отмена"]
menu_return = ["Вернуться"]
ready = ["✅ Готово"]
remove_mark = "❌ "
ok = "Понятно"

def ok_keyboard(data):
    return InlineKeyboardMarkup.from_button(InlineKeyboardButton(text=ok, callback_data=data))

# menu

menu = [
    {
        'type': "faq", 
        'text': "Частые вопросы",
        'subscription': False
    }, {
        'type': "expert",
        'text': "Задать вопрос специалисту",
        'subscription': True
    }, {
        'type': "contacts",
        'text': "Контакты специалистов",
        'subscription': False
    }, {
        'type': "feedback",
        'text': "Обратная связь",
        'subscription': False
    }
]

def keyboard_from_list(buttons):
    group_menu = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    return ReplyKeyboardMarkup(group_menu, one_time_keyboard=True)

menu_dict = {e['type']:e for e in menu}

def menu_keyboard(subscription):
    menu_list = [e['text'] for e in filter(lambda e: (not e['subscription']) or subscription['active'], menu)]
    return keyboard_from_list(menu_list)

def menu_handler(menu_type, manually=False):
    option = menu_dict[menu_type]
    def wrapper(callback):
        if option['subscription']:
            def new_cb(update, context):
                user_id = update.message.from_user.id
                sub = db.check_subscription(user_id)
                if sub['active']:
                    return callback(update, context)
                else:
                    bot.send_message(chat_id=update.effective_chat.id,
                        text="wrapper\n" + subscription_end_message,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=menu_keyboard(sub))
                    return ConversationHandler.END
        else:
            new_cb = callback
        handler = MessageHandler(Filters.text([option['text']]), new_cb)
        if not manually: dp.add_handler(handler)
        return handler
    return wrapper

# hello and scubscription

intro_message = "Привет, New Mama! Я твой помощник в общении с нашими экспертами. " +\
                "В течение месяца ты можешь смело задавать свои вопросы, а я переадресую их специалисту. " +\
                "По завершении *30 дней* подписка деактивируется, но ты всегда можешь обратиться за личной " +\
                "консультацией напрямую к нашим экспертам!"

hello_again = "Рады видеть тебя снова в нашем приложении."

subscription_end_message = "К сожалению, 30-дневная подписка на чат-бот *истекла*. " +\
                "Но ты можешь напрямую обратиться к специалистам за личной консультацией! " +\
                "Их контакты можно найти в меню."

def subscription_info(sub):
    if sub["active"]:
        last_digit = sub['days'] % 10
        decade = (sub['days'] // 10) % 10
        return f"Твоя подписка будет действовать еще " +\
            f"*{sub['days']} {'дней' if last_digit in map(int, '056789') or decade == 1 else 'день' if last_digit == 1 and decade != 1 else 'дня'}*"
    else:
         return subscription_end_message


def hello(update, context):
    user = update.message.from_user
    sub = db.check_subscription(user.id)
    if sub:
        text = hello_again + " " + subscription_info(sub)
    else:
        db.new_user(user)
        sub = db.subscribe_user(user.id, 31)
        text = intro_message
    bot.send_message(chat_id=update.effective_chat.id,
                    text=text,
                    reply_markup=menu_keyboard(sub),
                    parse_mode=ParseMode.MARKDOWN
                    )

# show menu again
def menu_again(update, context):
        show_menu(update.effective_chat.id)
        return ConversationHandler.END

def show_menu(chat_id):
    sub = db.check_subscription(chat_id)
    bot.send_message(chat_id=chat_id,
                     text="Я могу помочь чем-то еще?",
                     reply_markup=menu_keyboard(sub))


dp.add_handler(CommandHandler('start', hello))

## ask expert scenario

CATEGORY, QUESTION, FORWARD = range(3)

MAX_QUESTIONS = 99

def ask_expert(update, context):
    questions = db.last_questions(update.message.from_user.id)
    if len(questions) < MAX_QUESTIONS:
        bot.send_message(chat_id=update.effective_chat.id,
                     text="Выбери категорию специалиста, к которому хочешь обратиться:",
                     reply_markup=keyboard_from_list(categories+other+cancel))
        return CATEGORY
    else:
        bot.send_message(chat_id=update.effective_chat.id,
                         text="Наши эксперты обрабатывают твой вопрос, им нужно немного времени! " +\
                              "Новый вопрос ты можешь задать уже завтра.")
        time.sleep(5)
        return menu_again(update, context)


def accept_category(update, context):
    context.user_data["category"] = update.message.text
    update.message.reply_text("Введи и отправь свой вопрос:", 
                              reply_markup=keyboard_from_list(cancel))
    return QUESTION


def remind_experts(category):
    experts_usernames = filter(bool, map(lambda d: d.get("username"), db.experts_within(category)))
    experts_usertags = list(map(lambda un: "@"+un, experts_usernames))
    return f"Обратите внимание: {' '.join(experts_usertags)} !" if experts_usertags else ""

def forward_to_expert(update, context):
    category = context.user_data["category"]
    
    bot.send_message(chat_id=config.data.experts_chat,
                     text=f"Запрос категории *{category}*. " + \
                          remind_experts(category),
                     parse_mode=ParseMode.MARKDOWN)
    forwarded = update.message.forward(config.data.experts_chat)
    db.add_new_question(category, update.message, forwarded)
    update.message.reply_text("Спасибо, специалисты уже получили твой вопрос и изучат его. Жди ответа в ближайшее время!")
    return menu_again(update, context)


dp.add_handler(
    ConversationHandler(
        entry_points=[menu_handler('expert', manually=True)(ask_expert)],

        states={
            CATEGORY: [MessageHandler(Filters.text(categories+other), accept_category)],

            QUESTION: [MessageHandler(~Filters.text(cancel) & ~Filters.command, forward_to_expert)]
        },

        fallbacks=[MessageHandler(Filters.text(cancel), menu_again),
                   CommandHandler("start", menu_again)]
    )
)


## reply to user scenario

# filter replies to forwarded messages
class _ReplyToBotForwardedFilter(MessageFilter):
    def filter(self, message):
        try:
            reply = message.reply_to_message
            return bool((reply.from_user.id == bot.id) and (reply.forward_from))
        except AttributeError:
            return False

ReplyToBotForwardedFilter =  _ReplyToBotForwardedFilter()
        
def reply_to_user(update, context):
    expert = db.get_expert(update.message.from_user)
    if not expert:
        update.message.reply_text("Сначала зарегистрируйтесь как специалист используя команду /register !")
    else:
        forwarded = update.message.reply_to_message
        chat_asked_id = forwarded.forward_from.id
        db.add_answer(forwarded.message_id, update.message)
        bot.send_message(chat_id=chat_asked_id,
                         text="*Ответ специалиста:*\n"+update.message.text,
                         parse_mode=ParseMode.MARKDOWN)
        bot.send_message(chat_id=chat_asked_id,
                         text="*Информация о специалисте:*\n"+expert["info"],
                         reply_markup=ok_keyboard(f'read_{update.message.message_id}'),
                         parse_mode=ParseMode.MARKDOWN)


dp.add_handler(MessageHandler(Filters.chat(int(config.data.experts_chat)) & ReplyToBotForwardedFilter, reply_to_user))

def get_answer(update, context):
    update.callback_query.answer()
    data = update.callback_query.data
    if data.startswith('read'):
        db.check_read_answer(int(data.split('_')[1]))
    print(int(data.split('_')[1]))
    show_menu(update.effective_chat.id)

dp.add_handler(CallbackQueryHandler(get_answer, pattern="^read"))


## contacts

@menu_handler('contacts')
def contacts(update, context):
    experts = db.all_experts()
    update.message.reply_text(
                     text="\n\n".join(map(lambda d: d["info"], experts)),
                     parse_mode=ParseMode.MARKDOWN)
    time.sleep(8)
    return menu_again(update, context)


## FAQ

FAQ_CATEGORY = 123

def faq(update, context):
    bot.send_message(chat_id=update.effective_chat.id,
                 text="Выберите категорию, в которой тебя интересует вопрос:",
                 reply_markup=keyboard_from_list(categories+cancel))
    return FAQ_CATEGORY

def faq_of_category(update, context):
    category = update.message.text
    text = ""
    for question, answer in FAQ[category]:
        text += f"*{question}*\n{answer}\n\n"
    bot.send_message(chat_id=update.effective_chat.id,
                     text=text,
                     parse_mode=ParseMode.MARKDOWN,
                     reply_markup=keyboard_from_list(categories+menu_return))
    return FAQ_CATEGORY


dp.add_handler(
    ConversationHandler(
        entry_points=[menu_handler('faq', manually=True)(faq)],

        states={
            FAQ_CATEGORY: [MessageHandler(Filters.text(categories), faq_of_category)]
        },

        fallbacks=[MessageHandler(Filters.text(cancel+menu_return), menu_again),
                   CommandHandler("start", menu_again)]
    )
)

## Feedback

ENTER_FEEDBACK = 234

def feedback(update, context):
    update.message.reply_text("Здесь можно сообщить обо всех проблемах с сервисом. " +\
                              "Введите сообщение:",
                              reply_markup=ReplyKeyboardMarkup.from_row(cancel))
    return ENTER_FEEDBACK

def proceed_feedback(update, context):
    update.message.forward(config.data.admin_chat)
    update.message.reply_text("Администраторы бота получили сообщение, спасибо! " +\
        "Мы свяжемся с вами при необходимости.")
    time.sleep(5)
    return menu_again(update, context)

def wrong_feedback(update, context):
    update.message.reply_text("К сожалению я не могу отправить это. Сообщение должно быть текстовым")
    time.sleep(5)
    return menu_again(update, context)

dp.add_handler(ConversationHandler(
    entry_points=[menu_handler('feedback', manually=True)(feedback)],

    states={
        ENTER_FEEDBACK: [MessageHandler(Filters.text & ~Filters.text(cancel), proceed_feedback), 
                         MessageHandler(Filters.all & ~Filters.text(cancel), wrong_feedback)]
    },

    fallbacks=[MessageHandler(Filters.text(cancel), menu_again)]
))


## expert regestration

CHOOSE_CATEGORIES, SAVE_INFO = range(10, 12)

def display_text_and_options(choosen_categories):
    result = dict()
    if choosen_categories:
        result["text"] = "Вы выбрали:\n" + "\n".join(choosen_categories)
        result["options"] = [(remove_mark+c if c in choosen_categories else c) for c in categories] + ready
    else:
        result["text"] = "Выберите категории в которых вы компетентны:"
        result["options"] = categories.copy()
    return result

def column_keyboard(options):
    buttons = [InlineKeyboardButton(text=option, callback_data=option) for option in options]
    return InlineKeyboardMarkup.from_column(buttons)

def start_register(update, context):
    context.user_data["expert_categories"] = list()
    d = display_text_and_options(context.user_data["expert_categories"])
    update.message.reply_text("Выберите свою категорию",
                              reply_markup=column_keyboard(categories+cancel))
    return CHOOSE_CATEGORIES

def categories_button(update, context):
    query = update.callback_query
    query.answer()
    if query.data in cancel:
        query.message.delete()
        return ConversationHandler.END
    else:
        context.user_data["expert_categories"].append(query.data)
        query.message.edit_text(f"Ваша категория: *{query.data}* \n\n" +\
            "Введите одним сообщением информацию о себе и контактные данные. " +\
            "Она будет отображаться пользователям каждый раз, когда вы будете отвечать на их вопросы, а также будет указана в блоке контактов.",
            parse_mode=ParseMode.MARKDOWN)
        return SAVE_INFO

def save_info(update, context):
    db.update_expert(update.effective_user, context.user_data["expert_categories"], update.message.text)
    update.message.reply_text("Спасибо! Я зарегистрировал вас как специалиста. Я буду отмечать вас когда будут поступать вопросы в вашей категории.")
    return ConversationHandler.END


dp.add_handler(
    ConversationHandler(
        entry_points=[CommandHandler("register", start_register, filters=Filters.chat(int(config.data.experts_chat)))],
        
        states={
            CHOOSE_CATEGORIES: [CallbackQueryHandler(categories_button)],
            SAVE_INFO: [MessageHandler(Filters.text & ~Filters.command, save_info)]
        },

        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
)


## register notification

def new_experts(update, context):
    update.message.reply_text("Рады видеть вас в чате экспертной помощи. " +\
    "Используйте команду /register чтобы зарегистрироваться как специалист")

dp.add_handler(MessageHandler(Filters.status_update.new_chat_members & Filters.chat(int(config.data.experts_chat)), new_experts))


## answer notification

def remind_unanswered():
    questions = db.unanswered_questions()
    for category in categories+other:
        category_questions = list(filter(lambda q: q['category'] == category, questions))
        if category_questions:
            bot.send_message(chat_id=config.data.experts_chat,
                             text=f"Вопросы без ответа категории *{category}*." +\
                                  remind_experts(category),
                             parse_mode=ParseMode.MARKDOWN)
            for question in category_questions:
                bot.forward_message(chat_id=config.data.experts_chat,
                                    from_chat_id=config.data.experts_chat,
                                    message_id=question['forwarded_id'])


upd.job_queue.run_daily(lambda c: remind_unanswered(), datetime.time(hour=12))

## admin tools

import json

def pretty_single(d):
    if d is None: return str(None)
    outd = d.copy()
    if '_id' in outd.keys(): outd.pop('_id')
    return json.dumps(outd, indent=2, sort_keys=True, ensure_ascii=False)

def pretty(seq):
    return "\n\n".join(map(pretty_single, seq))

def say_chat_id(update, context):
    update.message.reply_text(update.message.chat_id)

#dp.add_handler(CommandHandler('chatid', say_chat_id))

def unanswered(update, context):
    update.message.reply_text(f"```\n{pretty(db.unanswered_questions())}\n```",
        parse_mode=ParseMode.MARKDOWN)

dp.add_handler(CommandHandler('unanswered', unanswered, filters=Filters.chat(config.data.admin_chat)))
dp.add_handler(CommandHandler('remind', lambda u, c: remind_unanswered(), filters=Filters.chat(config.data.admin_chat)))

def remove_expert(update, context):
    for usertag in filter(lambda w: w.startswith('@'), update.message.text.split()):
        db.remove_expert(usertag[1:])
    update.message.reply_text('done')

dp.add_handler(CommandHandler('remove', remove_expert, filters=Filters.chat(config.data.admin_chat)))

def experts(update, context):
    update.message.reply_text(f"```\n{pretty(db.all_experts())}\n```",
        parse_mode=ParseMode.MARKDOWN)

dp.add_handler(CommandHandler('experts', experts, filters=Filters.chat(config.data.admin_chat)))

def user(update, context):
    for usertag in filter(lambda w: w.startswith('@'), update.message.text.split()):
        update.message.reply_text(f"```\n{pretty_single(db.get_user_by_username(usertag[1:]))}\n```",
            parse_mode=ParseMode.MARKDOWN)

def users(update, context):
    users_list = list()
    for raw_user in db.db.users.find():
        user = {
            'questions_amount': len(raw_user['questions']),
            'registered': raw_user['registered'],
            'username': raw_user['username'],
            'subscription': db.check_subscription(raw_user['id'])
        }
        users_list.append(user)
    for i in range(0, len(users_list), 5):
        update.message.reply_text(f"```\n{pretty(users_list[i:i+5])}\n```",
            parse_mode=ParseMode.MARKDOWN)

dp.add_handler(CommandHandler('user', user, filters=Filters.chat(config.data.admin_chat)))
dp.add_handler(CommandHandler('users', users, filters=Filters.chat(config.data.admin_chat)))



def main():
    upd.start_polling()
    upd.idle()

if __name__ == '__main__':
    main()