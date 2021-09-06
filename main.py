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


def hello(update, context):
    bot.send_message(chat_id=update.effective_chat.id,
                    text="""
Чобы попасть на наше мероприятие, мы просим вас ответить на три вопроса:

1) Как к вам лучше обратиться?

2) Когда вы хотите прийти? В субботу на лекции и знакомство, в воскресенье мастерить браслет, или на оба дня?

3) Есть ли в вашей жизни какая-то веселая практика связанная с экологией? Или возможно вы мечтаете такую найти?

Отвечайте сообщением здесь в боте, сохраняя нумерацию""")

dp.add_handler(CommandHandler('start', hello))

kb = lambda chat_id: InlineKeyboardMarkup([[InlineKeyboardButton("Пустить", callback_data=f"add_{chat_id}"),
                                            InlineKeyboardButton("Отклонить", callback_data=f"reject_{chat_id}")]])

def forward_to_expert(update, context):
    forwarded = update.message.forward(config.data.experts_chat)
    bot.send_message(chat_id=config.data.experts_chat, text="?", reply_markup=kb(update.effective_chat.id))
    update.message.reply_text("Спасибо, мы получили твою заявку! Жди ответа в ближайшее время")

dp.add_handler(MessageHandler(~Filters.command & ~Filters.chat(int(config.data.experts_chat)), forward_to_expert))

class _ReplyToBotForwardedFilter(MessageFilter):
    def filter(self, message):
        try:
            reply = message.reply_to_message
            return bool((reply.from_user.id == bot.id) and (reply.forward_from))
        except AttributeError:
            return False

ReplyToBotForwardedFilter =  _ReplyToBotForwardedFilter()
        
def accept_user(update, context):
    user_id = update.callback_query.data.split('_')[1]
    update.callback_query.answer()
    try:
        bot.send_message(chat_id=user_id,
                        text=f'Заходи в <a href="{config.data.invite_link}">чат</a> ✨ ',
                        parse_mode=ParseMode.HTML)
    except:
        update.message.reply_text("Ответ не дошел пользователю")
    else:
        update.callback_query.message.edit_text("#пустили")

def reject_user(update, context):
    user_id = update.callback_query.data.split('_')[1]
    update.callback_query.answer()
    try:
        bot.send_message(chat_id=user_id,
                        text=f'Увы, мы не можем пригласить вас')
    except:
        update.message.reply_text("Ответ не дошел пользователю")
    else:
        update.callback_query.message.edit_text("#отклонили")


dp.add_handler(CallbackQueryHandler(accept_user, pattern="^add"))
dp.add_handler(CallbackQueryHandler(reject_user, pattern="^reject"))

def forward_reply(update, context):
    forwarded = update.message.reply_to_message
    chat_asked_id = forwarded.forward_from.id
    bot.copy_message(chat_id=chat_asked_id, from_chat_id=update.effective_chat.id, message_id=update.message.message_id)

dp.add_handler(MessageHandler(ReplyToBotForwardedFilter & Filters.chat(int(config.data.experts_chat)), forward_reply))

def chatid(update, context):
    update.message.reply_text(update.effective_chat.id)

dp.add_handler(CommandHandler('chatid', chatid))


def main():
    upd.start_polling()
    upd.idle()

if __name__ == '__main__':
    main()