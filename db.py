from pymongo import MongoClient

import config

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