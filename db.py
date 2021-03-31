from pymongo import MongoClient

import config

from datetime import datetime, timedelta

timeformat = "%Y-%m-%d_%H:%M:%S"

def timeparse(timestring):
    return datetime.strptime(timestring, timeformat)

mc = MongoClient()
db = mc[config.data.mongo_db]

def update_expert(user, categories, info):
    expert_data = {"id": user.id,
                   "categories": categories,
                   "info": info}
    if user.username: expert_data["username"] = user.username
    db.experts.update({"id": user.id}, 
                      {"$set": expert_data},
                      upsert=True)

def remove_expert(username):
    db.experts.delete_one({"username": username})

def experts_within(category):
    return list(db.experts.find({"categories": category}))

def all_experts():
    return list(db.experts.find())

def get_expert(user):
    return db.experts.find_one({"id": user.id})

def new_user(user):
    exists = db.users.find_one({"id": user.id})
    if not exists:
        db.users.insert_one({"id": user.id,
                             "username": user.username,
                             "registered": datetime.now().strftime(timeformat),
                             "subscriptions": [],
                             "questions": []})
    return not exists

def question(category, text, message_id, user_id):
    return {
        "from_user": user_id,
        "message_id": message_id,
        "created": datetime.now().strftime(timeformat),
        "text": text,
        "category": category
    }

def add_new_question(category, message, forwarded):
    q = question(category, message.text, message.message_id, message.from_user.id)
    db.users.update_one({"id": q["from_user"]},
                        {"$push": {"questions": q}})
    q.update({"answers": [], "forwarded_id": forwarded.message_id})
    db.questions.insert_one(q)

def add_answer(forwarded_id, answer):
    print('answer', forwarded_id, answer)
    db.questions.update_one({"forwarded_id": forwarded_id},
                            {"$push": {"answers": {"id": answer.message_id,
                                                   "text": answer.text}
                                      }})

def check_read_answer(answer_id):
    ...
    # todo

def unanswered_questions():
    return list(db.questions.find({"answers": []}))

def last_questions(user_id):
    user = get_user(user_id)
    now = datetime.now()
    return list(filter(lambda q: (now-timeparse(q['created'])).total_seconds() < 12*60*60,
                       user['questions']))

def subscription(days):
    return {"applied": datetime.now().strftime(timeformat),
            "days": days,
            "ending": (datetime.now()+timedelta(days=days)).strftime(timeformat)}

def subscribe_user(id, days):
    db.users.update_one({"id": id},
                        {"$push": {"subscriptions": subscription(days)}})
    return check_subscription(id)

def get_user(id):
    return db.users.find_one({"id": id})

def get_user_by_username(username):
    return db.users.find_one({"username": username})

def check_subscription(id):
    user = get_user(id)
    if user:
        try:
            last_sub = user["subscriptions"][-1]
        except IndexError:
            pass
        else:
            ending = datetime.strptime(last_sub["ending"], timeformat)
            time_left = ending - datetime.now()
            return {
                "days": time_left.days,
                "active": time_left.total_seconds() >= 0
            }
    return False

