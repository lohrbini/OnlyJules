import sqlite3
from flask import g
import os

DATABASE = str(os.environ.get('DB_NAME', 'app.db'))

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    with open('schema.sql', 'r') as f:
        db.executescript(f.read())

def init_app(app):
    app.teardown_appcontext(close_db)
