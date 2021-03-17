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


categories = ["Стоматология", "Педиатрия", "Магия"]
other = ["Другое"]
cancel = ["Отмена"]
ready = ["✅ Готово"]
remove_mark = "❌ "

menu = [("faq", "Частые вопросы"),
        ("expert", "Задать вопрос специалисту"),
        ("contacts", "Контакты специалистов"),
        ("subscription", "Информация о подписке")]

menu_dict = dict(menu)
menu_list = list(map(lambda p: p[1], menu))

CATEGORY, QUESTION, FORWARD = range(3)

# start message
def hello(update, context):
    bot.send_message(chat_id=update.effective_chat.id,
                     text="Здравствуйте! Я бот-помощник для молодых мам. Я могу вам чем-то помочь?",
                     reply_markup=ReplyKeyboardMarkup.from_column(menu_list, one_time_keyboard=True))

# show menu again
def menu_again(update, context):
        bot.send_message(chat_id=update.effective_chat.id,
                     text="Я помочь вам чем-то еще?",
                     reply_markup=ReplyKeyboardMarkup.from_column(menu_list, one_time_keyboard=True))
        return ConversationHandler.END


dp.add_handler(CommandHandler('start', hello))

## ask expert scenario

def ask_expert(update, context):
    bot.send_message(chat_id=update.effective_chat.id,
                     text="Выберите категорию специалиста, к которому вы хотите обратиться:",
                     reply_markup=ReplyKeyboardMarkup.from_column(categories+other+cancel, one_time_keyboard=True))
    return CATEGORY


def accept_category(update, context):
    context.user_data["category"] = update.message.text
    update.message.reply_text("Введите и отправьте ваш вопрос:", 
                              reply_markup=ReplyKeyboardMarkup([cancel], one_time_keyboard=True))
    return QUESTION


def forward_to_expert(update, context):
    category = context.user_data["category"]
    experts_usernames = filter(bool, map(lambda d: d.get("username"), db.experts_within(category)))
    experts_usertags = list(map(lambda un: "@"+un, experts_usernames))
    bot.send_message(chat_id=config.data.experts_chat,
                     text=f"Запрос категории *{category}*. " + \
                     (f"Обратите внимание: {' '.join(experts_usertags)} !" if experts_usertags else ""),
                     parse_mode=ParseMode.MARKDOWN)
    update.message.forward(config.data.experts_chat)
    update.message.reply_text("Спасибо, специалисты получили ваш вопрос и изучат его. Ждите ответа в ближайшую среду")
    return menu_again(update, context)


dp.add_handler(
    ConversationHandler(
        entry_points=[MessageHandler(Filters.text([menu_dict["expert"]]), ask_expert)],

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
        chat_asked_id = update.message.reply_to_message.forward_from.id
        bot.send_message(chat_id=chat_asked_id,
                         text="*Ответ специалиста:*\n"+update.message.text,
                         parse_mode=ParseMode.MARKDOWN)
        bot.send_message(chat_id=chat_asked_id,
                         text="*Информация о специалисте:*\n"+expert["info"],
                         parse_mode=ParseMode.MARKDOWN)


dp.add_handler(MessageHandler(Filters.chat(int(config.data.experts_chat)) & ReplyToBotForwardedFilter, reply_to_user))

## other menu options

def contacts(update, context):
    experts = db.all_experts()
    print(list(experts))
    update.message.reply_text(
                     text="\n\n".join(map(lambda d: d["info"], experts)),
                     parse_mode=ParseMode.MARKDOWN)
    return menu_again(update, context)

def faq(update, context):
    update.message.reply_text("здесь будет текст")
    return menu_again(update, context)

def subscription(update, context):
    #todo
    update.message.reply_text("todo")
    return menu_again(update, context)

dp.add_handler(MessageHandler(Filters.text([menu_dict["contacts"]]), contacts))
dp.add_handler(MessageHandler(Filters.text([menu_dict["faq"]]), faq))
dp.add_handler(MessageHandler(Filters.text([menu_dict["subscription"]]), subscription))

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
    update.message.reply_text(d["text"],
                              reply_markup=column_keyboard(d["options"]))
    return CHOOSE_CATEGORIES

def categories_button(update, context):
    query = update.callback_query
    query.answer()
    if query.data in ready:
        return ask_info(update, context)
    elif query.data.startswith(remove_mark):
        context.user_data["expert_categories"].remove(query.data[len(remove_mark):])
    else:
        context.user_data["expert_categories"].append(query.data)
    d = display_text_and_options(context.user_data["expert_categories"])
    query.edit_message_text(text=d["text"],
                            reply_markup=column_keyboard(d["options"]))
    return CHOOSE_CATEGORIES

def ask_info(update, context):
    bot.send_message(chat_id=update.effective_chat.id,
                     text="Введите одним сообщением информацию о себе и контактные данные. " +\
                     "Она будет отображаться пользователям каждый раз когда вы будете отвечать на их вопросы, а также будет указана в блоке контактов.")
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


# dev tools
def say_chat_id(update, context):
    update.message.reply_text(update.message.chat_id)

dp.add_handler(CommandHandler('chatid', say_chat_id))



def main():
    upd.start_polling()
    upd.idle()

if __name__ == '__main__':
    main()