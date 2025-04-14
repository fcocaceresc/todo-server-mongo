import os
from datetime import datetime, timezone, timedelta
from functools import wraps
from typing import TypedDict

import bcrypt
import jwt
from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from pymongo import MongoClient


class User(TypedDict):
    username: str
    password: str


class Task(TypedDict):
    title: str
    description: str
    user_id: ObjectId


app = Flask(__name__)

load_dotenv()
SECRET_KEY = os.getenv('SECRET_KEY')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM')
TOKEN_EXPIRE_HOURS = os.getenv('TOKEN_EXPIRE_HOURS')

uri = 'mongodb://localhost:27017/todo'
client = MongoClient(uri)

database = client.get_database('todo')
users_collection = database.get_collection('users')
tasks_collection = database.get_collection('tasks')


def token_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]

        if not token:
            return jsonify({'message': 'token is missing'}), 401

        try:
            decoded_token = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
            current_user = users_collection.find_one({'_id': ObjectId(decoded_token['user_id'])})
            if not current_user:
                return jsonify({'message': 'user not found'}), 404
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'invalid token'}), 401

        return f(current_user, *args, **kwargs)

    return decorator


@app.route('/status', methods=['GET'])
def status():
    return jsonify({'message': 'ok'}), 200


def hash_password(password):
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
    return hashed_password


@app.route('/signup', methods=['POST'])
def sign_up():
    user_data = request.json
    hashed_password = hash_password(user_data['password'])
    users_collection.insert_one(
        User(
            username=user_data['username'],
            password=hashed_password
        )
    )
    return jsonify({'message': 'user created successfully'}), 201


def generate_token_payload(user_id):
    token_payload = {
        'user_id': user_id,
        'exp': datetime.now(tz=timezone.utc) + timedelta(hours=float(TOKEN_EXPIRE_HOURS))
    }
    token = jwt.encode(token_payload, SECRET_KEY, JWT_ALGORITHM)
    return token


@app.route('/login', methods=['POST'])
def login():
    user_data = request.json

    user = users_collection.find_one({'username': user_data['username']})
    if not user:
        return jsonify({'message': 'invalid username'}), 401

    stored_password_hash = user['password']

    password_bytes = user_data['password'].encode('utf-8')
    hashed_password_bytes = stored_password_hash.encode('utf-8')

    is_valid = bcrypt.checkpw(password_bytes, hashed_password_bytes)

    if is_valid:
        token = generate_token_payload(str(user['_id']))
        return jsonify({'token': token}), 200
    return jsonify({'message': 'invalid password'}), 401


@app.route('/todos', methods=['POST'])
@token_required
def create_task(current_user):
    task_data = request.json
    tasks_collection.insert_one(
        Task(
            title=task_data['title'],
            description=task_data['description'],
            user_id=current_user['_id']
        )
    )
    return jsonify({'message': 'task created successfully'}), 201


@app.route('/todos', methods=['GET'])
@token_required
def get_tasks(current_user):
    user_object_id = ObjectId(current_user['_id'])

    tasks = tasks_collection.find({'user_id': user_object_id})
    tasks_list = [{**task, '_id': str(task['_id']), 'user_id': str(task['user_id'])} for task in tasks]

    return jsonify({
        'message': 'tasks retrieved successfully',
        'tasks': tasks_list
    }), 200


@app.route('/todos/<task_id>', methods=['PUT'])
@token_required
def update_task(current_user, task_id):
    task_object_id = ObjectId(task_id)

    task = tasks_collection.find_one({'_id': task_object_id})
    if task['user_id'] != ObjectId(current_user['_id']):
        return jsonify({'message': 'unauthorized to update this task'}), 403

    updated_task_data = request.json
    tasks_collection.update_one({'_id': task_object_id}, {'$set': updated_task_data})

    return jsonify({'message': 'task updated successfully'}), 200


@app.route('/todos/<task_id>', methods=['DELETE'])
@token_required
def delete_task(current_user, task_id):
    task_object_id = ObjectId(task_id)

    task = tasks_collection.find_one({'_id': task_object_id})
    if task['user_id'] != ObjectId(current_user['_id']):
        return jsonify({'message': 'unauthorized to delete this task'}), 403

    tasks_collection.delete_one({'_id': task_object_id})

    return jsonify({'message': 'task deleted successfully'}), 200


if __name__ == '__main__':
    app.run()
