from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import SingletonThreadPool
from sqlalchemy.ext.declarative import declarative_base
from hodl_net.globals import local, session
import os

Base = declarative_base()


class DBWorker:
    def __init__(self):
        self.filename: str = None
        self.engine = None

    def create_connection(self, filename):
        self.filename = filename
        self.engine = create_engine(f'sqlite:///{filename}', poolclass=SingletonThreadPool,
                                    connect_args={'check_same_thread': False})

    def with_session(self, func):
        def wrapper(*args, **kwargs):
            local.session = self.get_session()
            try:
                return func(*args, **kwargs)
            except Exception as ex:
                local.session.rollback()
                raise ex
            finally:
                local.session.close()

        return wrapper

    @staticmethod
    def close_session(ses):
        ses.rollback()
        ses.close()

    def get_session(self):
        return sessionmaker(bind=self.engine)()


db_worker = DBWorker()


@db_worker.with_session
def create_db(with_drop=False):
    if with_drop:
        drop_db()
    Base.metadata.create_all(db_worker.engine)
    session.commit()


def drop_db():
    try:
        os.remove(db_worker.filename)
    except FileNotFoundError:
        pass
