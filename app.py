from typing import TypedDict

from bson import ObjectId
from flask import Flask, jsonify, request
from pymongo import MongoClient


class User(TypedDict):
    username: str
    password: str


class Task(TypedDict):
    title: str
    description: str


app = Flask(__name__)

uri = 'mongodb://localhost:27017/todo'
client = MongoClient(uri)

database = client.get_database('todo')
users_collection = database.get_collection('users')
tasks_collection = database.get_collection('tasks')


@app.route('/status', methods=['GET'])
def status():
    return jsonify({'message': 'ok'}), 200


@app.route('/signup', methods=['POST'])
def sign_up():
    user_data = request.json
    users_collection.insert_one(
        User(
            username=user_data['username'],
            password=user_data['password']
        )
    )
    return jsonify({'message': 'user created successfully'}), 201


@app.route('/todos', methods=['POST'])
def create_task():
    task_data = request.json
    tasks_collection.insert_one(
        Task(
            title=task_data['title'],
            description=task_data['description']
        )
    )
    return jsonify({'message': 'task created successfully'}), 201


@app.route('/todos', methods=['GET'])
def get_tasks():
    tasks = tasks_collection.find()

    tasks_list = [
        {**task, '_id': str(task['_id'])}
        for task in tasks
    ]

    return jsonify({
        'message': 'tasks retrieved successfully',
        'tasks': tasks_list
    }), 200


@app.route('/todos/<task_id>', methods=['PUT'])
def update_task(task_id):
    task_object_id = ObjectId(task_id)
    updated_task_data = request.json

    tasks_collection.update_one({'_id': task_object_id}, {'$set': updated_task_data})

    return jsonify({'message': 'task updated successfully'}), 200


@app.route('/todos/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    task_object_id = ObjectId(task_id)

    tasks_collection.delete_one({'_id': task_object_id})

    return jsonify({'message': 'task deleted successfully'}), 200


if __name__ == '__main__':
    app.run()
