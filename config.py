import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config(object):
    DATABASE_URL = os.environ.get('DATABASE_URL') or '-'
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT')
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ARCH_DATA_DIR = os.environ.get('ARCH_DATA_DIR')
    ADMINS = ['widoyo@gmail.com']

class ProductionConfig(Config):
    FLASK_ENV = 'production'


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DATABASE_URL = os.getenv('TEST_DATABASE_URL',
                                        default=f"sqlite:///{os.path.join(basedir, 'instance', 'test.db')}")
    WTF_CSRF_ENABLED = False

