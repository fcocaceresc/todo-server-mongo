from flask import Flask, jsonify

app = Flask(__name__)


@app.route('/status', methods=['GET'])
def status():
    return jsonify({'message': 'ok'}), 200


if __name__ == '__main__':
    app.run()
