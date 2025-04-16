# Tutorial

1. Clone repository
```bash
git clone git@github.com:fcocaceresc/todo-server-mongo.git
```

2. Fill .env_template
3. Change .env_template name to .env
```bash
mv .env_template .env
```
4. Make a python virtual environment
```bash
python3 -m venv venv
```

5. Activate the virtual environment
```bash
source venv/bin/activate
```
6. Install dependencies
```bash
pip install -r requirements.txt
```
7. Install MongoDB
https://www.mongodb.com/docs/manual/installation/
8. Run the server
```bash
python3 app.py
```