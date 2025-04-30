import os
from datetime import datetime, timezone, timedelta
from functools import wraps
from typing import TypedDict, Dict, List, Any

import bcrypt
import jwt
from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from pymongo import MongoClient
from flask_cors import CORS


class User(TypedDict):
    username: str
    password: str


class Task(TypedDict):
    title: str
    description: str
    completed: bool
    user_id: ObjectId
    created_at: datetime
    updated_at: datetime


app = Flask(__name__)
CORS(app)

load_dotenv()
SECRET_KEY = os.getenv('SECRET_KEY')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
TOKEN_EXPIRE_HOURS = float(os.getenv('TOKEN_EXPIRE_HOURS', '24'))

uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/todo')
client = MongoClient(uri)
database = client.get_database('todo')
users_collection = database.get_collection('users')
tasks_collection = database.get_collection('tasks')


def token_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')

        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({
                'success': False,
                'message': 'Authentication required',
                'data': None
            }), 401

        try:
            decoded_token = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
            current_user = users_collection.find_one({'_id': ObjectId(decoded_token['user_id'])})
            if not current_user:
                return jsonify({
                    'success': False,
                    'message': 'User not found',
                    'data': None
                }), 404
        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'message': 'Token expired',
                'data': None
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                'success': False,
                'message': 'Invalid token',
                'data': None
            }), 401

        return f(current_user, *args, **kwargs)

    return decorator


@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({
        'success': True,
        'message': 'Service is running',
        'data': {'timestamp': datetime.now().isoformat()}
    }), 200


def hash_password(password):
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
    return hashed_password


@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.json
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({
                'success': False,
                'message': 'Username and password required',
                'data': None
            }), 400

        if users_collection.find_one({'username': data['username']}):
            return jsonify({
                'success': False,
                'message': 'Username already exists',
                'data': None
            }), 409

        hashed_password = hash_password(data['password'])
        user_id = users_collection.insert_one({
            'username': data['username'],
            'password': hashed_password,
            'created_at': datetime.now()
        }).inserted_id

        return jsonify({
            'success': True,
            'message': 'User created successfully',
            'data': {'userId': str(user_id)}
        }), 201
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e),
            'data': None
        }), 500


@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.json
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({
                'success': False,
                'message': 'Username and password required',
                'data': None
            }), 400

        user = users_collection.find_one({'username': data['username']})
        if not user:
            return jsonify({
                'success': False,
                'message': 'Invalid credentials',
                'data': None
            }), 401

        is_valid = bcrypt.checkpw(
            data['password'].encode('utf-8'),
            user['password'].encode('utf-8')
        )

        if is_valid:
            expiration = datetime.now(tz=timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
            token = jwt.encode({
                'user_id': str(user['_id']),
                'username': user['username'],
                'exp': expiration
            }, SECRET_KEY, algorithm=JWT_ALGORITHM)

            return jsonify({
                'success': True,
                'message': 'Login successful',
                'data': {
                    'token': token,
                    'userId': str(user['_id']),
                    'username': user['username'],
                    'expiresAt': expiration.isoformat()
                }
            }), 200

        return jsonify({
            'success': False,
            'message': 'Invalid credentials',
            'data': None
        }), 401
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e),
            'data': None
        }), 500


@app.route('/api/tasks', methods=['GET'])
@token_required
def get_tasks(current_user):
    try:
        tasks = tasks_collection.find({'user_id': current_user['_id']})

        task_list = []
        for task in tasks:
            task_data = {
                'id': str(task['_id']),
                'title': task['title'],
                'description': task.get('description', ''),
                'completed': task.get('completed', False),
                'createdAt': task.get('created_at', '').isoformat() if isinstance(task.get('created_at'),
                                                                                  datetime) else '',
                'updatedAt': task.get('updated_at', '').isoformat() if isinstance(task.get('updated_at'),
                                                                                  datetime) else ''
            }

            if 'category' in task:
                task_data['category'] = task['category']

            if 'deadline' in task:
                if isinstance(task['deadline'], datetime):
                    task_data['deadline'] = task['deadline'].isoformat()
                else:
                    task_data['deadline'] = str(task['deadline'])

            task_list.append(task_data)

        return jsonify({
            'success': True,
            'message': 'Tasks retrieved successfully',
            'data': task_list
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e),
            'data': None
        }), 500


@app.route('/api/tasks', methods=['POST'])
@token_required
def create_task(current_user):
    try:
        data = request.json
        if not data or not data.get('title'):
            return jsonify({
                'success': False,
                'message': 'Title is required',
                'data': None
            }), 400

        now = datetime.now()
        task_data = {
            'title': data['title'],
            'description': data.get('description', ''),
            'completed': data.get('completed', False),
            'user_id': current_user['_id'],
            'created_at': now,
            'updated_at': now
        }

        if 'category' in data:
            task_data['category'] = data['category']

        if 'deadline' in data:
            task_data['deadline'] = data['deadline']

        task_id = tasks_collection.insert_one(task_data).inserted_id

        response_data = {
            'id': str(task_id),
            'title': data['title'],
            'description': data.get('description', ''),
            'completed': data.get('completed', False),
            'createdAt': now.isoformat(),
            'updatedAt': now.isoformat()
        }

        if 'category' in task_data:
            response_data['category'] = task_data['category']
        if 'deadline' in task_data:
            response_data['deadline'] = task_data['deadline']

        return jsonify({
            'success': True,
            'message': 'Task created successfully',
            'data': response_data
        }), 201
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e),
            'data': None
        }), 500


@app.route('/api/tasks/<task_id>', methods=['PUT'])
@token_required
def update_task(current_user, task_id):
    try:
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided',
                'data': None
            }), 400

        task_object_id = ObjectId(task_id)
        task = tasks_collection.find_one({'_id': task_object_id})

        if not task:
            return jsonify({
                'success': False,
                'message': 'Task not found',
                'data': None
            }), 404

        if task['user_id'] != current_user['_id']:
            return jsonify({
                'success': False,
                'message': 'Not authorized to update this task',
                'data': None
            }), 403

        update_data = {
            'updated_at': datetime.now()
        }

        if 'title' in data:
            update_data['title'] = data['title']
        if 'description' in data:
            update_data['description'] = data['description']
        if 'completed' in data:
            update_data['completed'] = data['completed']

        tasks_collection.update_one(
            {'_id': task_object_id},
            {'$set': update_data}
        )

        updated_task = tasks_collection.find_one({'_id': task_object_id})

        return jsonify({
            'success': True,
            'message': 'Task updated successfully',
            'data': {
                'id': str(updated_task['_id']),
                'title': updated_task['title'],
                'description': updated_task.get('description', ''),
                'completed': updated_task.get('completed', False),
                'createdAt': updated_task.get('created_at', '').isoformat() if isinstance(
                    updated_task.get('created_at'), datetime) else '',
                'updatedAt': updated_task.get('updated_at', '').isoformat() if isinstance(
                    updated_task.get('updated_at'), datetime) else ''
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e),
            'data': None
        }), 500


@app.route('/api/tasks/<task_id>/complete', methods=['PATCH'])
@token_required
def complete_task(current_user, task_id):
    try:
        task_object_id = ObjectId(task_id)
        task = tasks_collection.find_one({'_id': task_object_id})

        if not task:
            return jsonify({
                'success': False,
                'message': 'Task not found',
                'data': None
            }), 404

        if task['user_id'] != current_user['_id']:
            return jsonify({
                'success': False,
                'message': 'Not authorized to update this task',
                'data': None
            }), 403

        tasks_collection.update_one(
            {'_id': task_object_id},
            {'$set': {'completed': True, 'updated_at': datetime.now()}}
        )

        return jsonify({
            'success': True,
            'message': 'Task marked as completed',
            'data': {'id': task_id}
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e),
            'data': None
        }), 500


@app.route('/api/tasks', methods=['DELETE'])
@token_required
def delete_all_tasks(current_user):
    try:
        result = tasks_collection.delete_many({'user_id': current_user['_id']})

        return jsonify({
            'success': True,
            'message': f'{result.deleted_count} tasks deleted successfully',
            'data': None
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e),
            'data': None
        }), 500


@app.route('/api/tasks/<task_id>', methods=['DELETE'])
@token_required
def delete_task(current_user, task_id):
    try:
        task_object_id = ObjectId(task_id)
        task = tasks_collection.find_one({'_id': task_object_id})

        if not task:
            return jsonify({
                'success': False,
                'message': 'Task not found',
                'data': None
            }), 404

        if task['user_id'] != current_user['_id']:
            return jsonify({
                'success': False,
                'message': 'Not authorized to delete this task',
                'data': None
            }), 403

        tasks_collection.delete_one({'_id': task_object_id})

        return jsonify({
            'success': True,
            'message': 'Task deleted successfully',
            'data': {'id': task_id}
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e),
            'data': None
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)