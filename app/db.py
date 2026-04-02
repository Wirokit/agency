from psycopg2 import pool
from psycopg2.extras import RealDictCursor, register_uuid
from psycopg2.extensions import connection
from flask import g

# We define the pool globally, but initialize it in the factory
db_pool = None


class UUIDConnection(connection):
    """Register the UUID type so we can use it properly"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This runs ONCE when the connection is physically created
        register_uuid(conn_or_curs=self)


def init_db(app):
    """Initialize the connection pool using app config."""
    global db_pool
    db_pool = pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=20,
        dsn=app.config["DATABASE_URL"],
        connection_factory=UUIDConnection,
        cursor_factory=RealDictCursor,
    )


def get_db() -> connection:
    """Get a connection from the pool for the current request."""
    if "db" not in g:
        g.db = db_pool.getconn()
    return g.db


def close_db(e=None):
    """Return the connection to the pool after the request ends."""
    db = g.pop("db", None)
    if db is not None:
        db_pool.putconn(db)
