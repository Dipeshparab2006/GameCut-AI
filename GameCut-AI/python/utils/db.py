import os
from contextlib import contextmanager

import mysql.connector
from mysql.connector import Error


def _env(name, default=None):
    value = os.getenv(name)
    return default if value is None or value == "" else value


def get_db_config():
    return {
        "host": _env("GAMECUT_DB_HOST", "127.0.0.1"),
        "port": int(_env("GAMECUT_DB_PORT", "3306")),
        "database": _env("GAMECUT_DB_NAME", "gamecut_ai"),
        "user": _env("GAMECUT_DB_USER", "root"),
        "password": _env("GAMECUT_DB_PASS", ""),
        "charset": "utf8mb4",
        "use_unicode": True,
    }


def get_db_connection():
    return mysql.connector.connect(**get_db_config())


@contextmanager
def db_cursor(dictionary=False):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=dictionary)
    try:
        yield connection, cursor
    finally:
        cursor.close()
        connection.close()


def dependency_status():
    status = {"mysql_connector": True, "database": False}
    try:
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT 1")
            cursor.fetchone()
            status["database"] = True
    except Error as exc:
        status["database_error"] = exc.__class__.__name__
    return status


def table_columns(cursor, table_name):
    cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
    return {row[0] for row in cursor.fetchall()}


def fetch_job_status(job_id):
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT id, status, progress, current_step, error_message, updated_at
            FROM ai_jobs
            WHERE id = %s
            """,
            (job_id,),
        )
        return cursor.fetchone()
