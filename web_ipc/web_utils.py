import secrets
import string
import pickle
from logging import Logger
from pathlib import Path

import psutil
import bcrypt
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from web_ipc.logger import get_logger
from web_ipc.encrypt import Cipher


BASE = declarative_base()


class User(BASE):
    """User class for database ORM

    Args:
        BASE (declarative_base): sqlalchemy declarative base
    """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)

    def set_password(self, password: str) -> None:
        """Set the password hash for the user

        Args:
            password (str): password to hash
        """
        self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, password: str) -> bool:
        """Check if the password matches the stored hash

        Args:
            password (str): password to check

        Returns:
            bool: True if password matches, False otherwise
        """
        return bcrypt.checkpw(password.encode(), self.password_hash.encode())


class WebDB():
    def __init__(self, logger: Logger):
        """Web Database class for handling users and authentication

        Args:
            logger (Logger): logging object
        """
        self.log = logger
        self.__engine = create_engine(f'sqlite:///{Path(__file__).parent}/web_env/users.db')

    def _initialize(self) -> bool:
        """Initialize the database schema

        Returns:
            bool: True if schema was created successfully, False otherwise
        """
        try:
            BASE.metadata.create_all(self.__engine)
            return True
        except Exception:
            self.log.exception('Failed to initialize database')
            return False

    def get_session(self):
        """Get a session object for the database

        Returns:
            session: sqlalchemy session object
        """
        return sessionmaker(bind=self.__engine)()

    def add_user(self, username: str, password: str) -> bool:
        """Add a user to the database

        Args:
            username (str): username to create
            password (str): password for the user

        Returns:
            bool: True if user was created successfully, False otherwise
        """
        try:
            session = self.get_session()
            user = User(username=username)
            user.set_password(password)
            session.add(user)
            session.commit()
            session.close()
            self.log.info(f'Successfully created user {username}')
            return True
        except Exception:
            self.log.exception(f'Failed to create user {username}')
            return False

    def authenticate_user(self, username: str, password: str) -> bool:
        """Authenticate a user with the database

        Args:
            username (str): username to authenticate
            password (str): password to authenticate

        Returns:
            bool: True if user was authenticated, False otherwise
        """
        session = self.get_session()
        user = session.query(User).filter_by(username=username).first()
        session.close()
        if user and user.check_password(password):
            self.log.debug('Credentials verified')
            return True
        self.log.error('Invalid credentials')
        return False

    def user_exists(self, username: str) -> bool:
        """Check if a user exists in the database

        Args:
            username (str): username to check

        Returns:
            bool: True if user exists, False otherwise
        """
        session = self.get_session()
        user = session.query(User).filter_by(username=username).first()
        session.close()
        return user is not None


class WebUtils():
    def __init__(self, server_name: str = 'localhost', protocol: str = 'https', logger: Logger = None):
        """Web Utilities class for handling encryption, database, and other web related functions

        Args:
            server_name (str, optional): server name. Defaults to 'localhost'.
            protocol (str, optional): web protocol to use (http or https). Defaults to 'https'.
            logger (Logger, optional): logger to use. Defaults to None.
        """
        self.server_name = server_name
        self.protocol = protocol
        self.log = logger or get_logger('web-ipc')
        self.__key: bytes | None = None

    @property
    def encrypt(self) -> Cipher:
        """Get the Cipher object for encryption

        Returns:
            Cipher: Cipher object
        """
        return Cipher(self.log)

    @property
    def db(self) -> WebDB:
        """Get the WebDB object for database operations

        Returns:
            WebDB: WebDB object
        """
        return WebDB(self.log)

    @property
    def key(self) -> bytes:
        """Encryption key for XOR cipher

        Returns:
            bytes: encryption key
        """
        if not self.__key:
            self.__key = self.encrypt.load_key()
        return self.__key

    def generate_password(self, length: int = 128) -> str:
        """Generate a random password

        Args:
            length (int, optional): password length. Defaults to 128.

        Returns:
            str: generated password
        """
        characters = string.ascii_letters + string.digits + string.punctuation
        password = ''.join(secrets.choice(characters) for _ in range(length))
        return password

    def generate_username(self, length: int = 32) -> str:
        """Generate a random username

        Args:
            length (int, optional): username length. Defaults to 32.

        Returns:
            str: generated username
        """
        return ''.join(secrets.choice(string.ascii_letters) for _ in range(length))

    def _get_https_certs(self) -> tuple:
        """Get the HTTPS certificates for the server based on the server name set in the constructor. If they do not
        exists, use the web-ipc --certs CLI command to generate them.

        Returns:
            tuple: (ca cert, server cert, server key)
        """
        cert_dir = f'{Path(__file__).parent}/web_env'
        server_cert = f'{cert_dir}/{self.server_name}'
        return (f'{cert_dir}/web-ipc-ca.crt', f'{server_cert}.crt', f'{server_cert}.key')

    def find_server_port(self) -> int:
        """Find an available port between 3000 and 4000

        Returns:
            int: available port or 0 if none found
        """
        connections = psutil.net_connections()
        used_ports = set()
        for conn in connections:
            if conn.status == psutil.CONN_LISTEN or conn.status == psutil.CONN_ESTABLISHED:
                used_ports.add(conn.laddr.port)
        used_ports = list(used_ports)
        for use_port in range(3000, 4000):
            if use_port not in used_ports:
                self.log.debug(f'Found available port: {use_port}')
                return use_port
        return 0

    def pickle_dump(self, file_name: str, data: object, key: bytes = None):
        """Dump data to file using pickle and XOR encryption.

        Args:
            file_name (str): file name to save data to
            data (object): data to save
            key (bytes, optional): xor key for encryption. Defaults to None.

        Returns:
            bool: True if data was saved successfully, False otherwise
        """
        data = self.pickle_dumps(data, key)
        if data is None:
            return False
        try:
            with open(file_name, 'wb') as file:
                file.write(data)
            return True
        except Exception:
            self.log.exception(f'Failed to write data to file: {file_name}')
        return False

    def pickle_dumps(self, data: object, key: bytes = None) -> bytes | None:
        """Dump data to pickle bytes and encrypt using XOR cipher.

        Args:
            data (object): data to dump
            key (bytes, optional): xor key for encryption. Defaults to None.

        Returns:
            bytes: pickle data bytes or None if failed
        """
        try:
            return Cipher.encrypt(pickle.dumps(data), key or self.key)
        except Exception:
            self.log.exception('Failed to dump data to pickle bytes')
        return None

    def pickle_load(self, file_name: str, key: bytes = None):
        """Load data from file using pickle and XOR decryption.

        Args:
            file_name (str): file name to load data from
            key (bytes, optional): xor key for decryption. Defaults to None.

        Returns:
            object | None: loaded data from file or None if failed
        """
        with open(file_name, 'rb') as file:
            return self.pickle_loads(file.read(), key)
        return None

    def pickle_loads(self, data: bytes, key: bytes = None):
        """Load data from pickle bytes and decrypt using XOR cipher.

        Args:
            data (bytes): data to decrypt and pickle load
            key (bytes, optional): xor decrypt key. Defaults to None.

        Returns:
            object | None: loaded data or None if failed
        """
        try:
            return pickle.loads(Cipher.decrypt(data, key or self.key))
        except Exception:
            self.log.exception('Failed to load pickle data')
        return None
