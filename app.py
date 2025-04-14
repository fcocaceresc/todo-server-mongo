from typing import TypedDict

from flask import Flask, jsonify, request
from pymongo import MongoClient


class Task(TypedDict):
    title: str
    description: str


app = Flask(__name__)

uri = 'mongodb://localhost:27017/todo'
client = MongoClient(uri)

database = client.get_database('todo')
tasks_collection = database.get_collection('tasks')


@app.route('/status', methods=['GET'])
def status():
    return jsonify({'message': 'ok'}), 200


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


if __name__ == '__main__':
    app.run()
