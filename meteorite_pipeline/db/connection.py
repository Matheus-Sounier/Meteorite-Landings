import os

import psycopg
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg.connect(
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
    )


def get_dash_connection():
    return psycopg.connect(
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["DASH_DB_USER"],
        password=os.environ["DASH_DB_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        connect_timeout=5,
    )


def get_chat_connection():
    return psycopg.connect(
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["CHAT_DB_USER"],
        password=os.environ["CHAT_DB_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        connect_timeout=5,
    )