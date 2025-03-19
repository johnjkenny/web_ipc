import requests
from time import sleep
from logging import Logger
from typing import Dict
from pathlib import Path

from web_ipc.web_utils import WebUtils


class WebClient(WebUtils):
    def __init__(self, server_name: str, server_ip: str, server_port: int, protocol: str = 'https',
                 auth: Dict = None, logger: Logger = None):
        """Web Client for sending messages to a Web Server

        Args:
            server_name (str): server name
            server_ip (str): server ip
            server_port (int): server port
            protocol (str, optional): web protocol to use (http or https). Defaults to 'https'.
            auth (Dict, optional): auth dict. Must have 'username' 'password' keys. Defaults to None and will use
                default admin user
            logger (Logger, optional): logging object to use. Defaults to None.

        Raises:
            ValueError: Invalid auth credentials. Requires username and password
        """
        super().__init__(server_name, protocol, logger)
        self.server_ip = server_ip
        self.server_port = server_port
        if auth:
            if 'username' not in auth or 'password' not in auth:
                raise ValueError('Invalid auth credentials. Requires username and password')
        self.__auth = auth

    def __request_kwargs(self) -> dict:
        """Formatter for request kwargs

        Returns:
            dict: request kwargs
        """
        if self.protocol == 'http':
            return {}
        certs = self._get_https_certs()
        if certs:
            return {'cert': (certs[1], certs[2]), 'verify': certs[0]}
        return {}

    def __get_creds(self) -> dict:
        """Get credentials for authentication for the default admin user

        Returns:
            dict: auth credentials
        """
        if not self.__auth:
            self.__auth = self.pickle_load(f'{Path(__file__).parent}/web_env/.ipca')
        return self.__auth

    def _authenticate(self) -> bool:
        """Authenticate with the server using the default admin user or the credentials set in the constructor.
        Checks if the server is running before attempting to authenticate

        Returns:
            bool: True if authenticated, False otherwise
        """
        if self._is_running_check():
            url = f'{self.protocol}://{self.server_name}:{self.server_port}/client/auth'
            self.__get_creds()
            payload = self.pickle_dumps(self.__auth, self.key)
            if payload:
                if self.__send_post_request(url, payload) == 200:
                    return True
                self.log.error(f'Failed to authenticate with server: {self.server_ip}')
                return False
        return False

    def _is_running_check(self) -> bool:
        """Check if the server is running. Should always return 200 unless the server is not running or the client
        cannot communicate with the server

        Returns:
            bool: True if server is running, False otherwise
        """
        url = f'{self.protocol}://{self.server_name}:{self.server_port}/is/running'
        rsp = requests.get(url, **self.__request_kwargs())
        if rsp.status_code == 200:
            return True
        self.log.error(f'URL {url} is not running: {rsp.reason}')
        return False

    def __send_post_request(self, url: str, payload: bytes) -> int:
        """Send a POST request to the server

        Args:
            url (str): url to send the request to
            payload (bytes): payload to send

        Returns:
            int: status code of the request
        """
        try:
            return requests.post(url, payload, **self.__request_kwargs()).status_code
        except requests.exceptions.ConnectionError:
            return 405  # Connection Error
        except KeyboardInterrupt:
            return 200
        except Exception:
            self.log.exception(f'Error sending update data to URL: {self.server_ip}')
        return 500

    def __post_retry_request(self, url: str, payload: bytes) -> bool:
        """Handler to retry sending a POST request to the server incase of a failure. Will retry 3 times before failing.
        Will self authenticate if the server returns a 401 or 419 status codes. Will stop the retry if the
        authentication fails

        Args:
            url (str): url to send the request to
            payload (bytes): payload to send

        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        attempt = 1
        while attempt < 4:
            rsp = self.__send_post_request(url, payload)
            if rsp == 200:
                return True
            elif rsp == 401:  # Unauthorized/invalid credentials
                self.log.info(f'Failed to authenticate with server: {self.server_ip}')
                self._authenticate()
            elif rsp == 419:
                self.log.info(f'[{rsp}] Authentication timeout, re-authenticating')
                self._authenticate()
            elif rsp == 405:
                self.log.info(f'Failed to connect to host {self.server_ip} on attempt {attempt} of 3')
                sleep(2)
            attempt += 1
        return False

    def send_msg(self, msg: dict) -> bool:
        """Send a message to the server. Enforces the message to be a dict type. Encrypts the message before sending

        Args:
            msg (dict): message to send to the server

        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        if isinstance(msg, dict):
            url = f'{self.protocol}://{self.server_name}:{self.server_port}/message/submit'
            payload = self.pickle_dumps(msg, self.key)
            if payload:
                return self.__post_retry_request(url, payload)
        else:
            self.log.error(f'Invalid message type received: {type(msg)}')
        return False
