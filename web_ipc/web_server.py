import ssl
from logging import Logger
from time import sleep
from threading import Thread, Event
from multiprocessing import Process, Queue, Manager
from datetime import datetime, timedelta

import uvicorn
from fastapi import FastAPI, Request, Response

from web_ipc.web_utils import WebUtils


class WebServer(WebUtils):
    def __init__(self, name: str = 'localhost', host: str = '127.0.0.1', port: int = 0, protocol: str = 'https',
                 queue: Queue = None, logger: Logger = None):
        """Web Server for receiving messages from a client. Has three routes:
            - /is/running (GET): returns a 200 response if the server is running
            - /message/submit (POST): receives a message from a client and puts it in the queue
            - /client/auth (POST): receives a message from a client and validates the credentials

        Args:
            name (str): Name of the server. Defaults to 'localhost'.
            host (str, optional): server IP to use. Defaults to '127.0.0.1'.
            port (int, optional): server port to use. Defaults to 0 and will find an available port between 3000-4000.
            protocol (str, optional): web protocol to use (http or https). Defaults to 'https'.
            queue (Queue, optional): queue to pass the received message to. Defaults to None and will print the message.
            logger (Logger, optional): logger to use. Defaults to None.
        """
        super().__init__(name, protocol, logger)
        self._app = FastAPI()
        self._host = host
        self._port = port or self.find_server_port()
        self.__clients = Manager().dict()
        self.__msg_queue = queue
        self.__thread: Thread | None = None
        self.__thread_stop = Event()
        self.__process: Process | None = None

        @self._app.get('/is/running')
        def is_running_route():
            """Check if the server is running route

            Returns:
                Response: 200 response if the server is running
            """
            return Response('Web-Server is running', 200)

        @self._app.post('/message/submit')
        async def msg_submit_route(request: Request) -> Response:
            """Submit message route. The main route for receiving messages from a client

            Args:
                request (Request): request object

            Returns:
                Response: response based on the message received
            """
            raw_msg = await request.body()
            state = ('failed', 500)
            try:
                if isinstance(raw_msg, bytes):
                    msg = self.pickle_loads(raw_msg, self.key)
                    if isinstance(msg, dict):
                        if self.__credentials_not_expired(self.__get_client_ip(request)):
                            state = ('success', 200)
                            if self.__msg_queue:
                                self.__msg_queue.put(msg)
                            else:
                                self.log.info(f'[NoQueueHandlerSet]Received message: {msg}')
                        else:
                            state = ('expired', 419)
                    else:
                        self.log.error(f'Invalid message type received: {type(msg)}')
                else:
                    self.log.error(f'Invalid message type received: {type(raw_msg)}')
            except Exception:
                self.log.exception('Failed to handle client update')
                state = ('failed', 500)
            del raw_msg
            return Response(*state)

        @self._app.post('/client/auth')
        async def client_auth_route(request: Request) -> Response:
            """Client authentication route. Validates the client credentials

            Args:
                request (Request): request object

            Returns:
                Response: response based on the client credentials
            """
            raw_msg = await request.body()
            try:
                state = False
                if isinstance(raw_msg, bytes):
                    msg = self.pickle_loads(raw_msg, self.key)
                    if isinstance(msg, dict):
                        state = self.__validate_credentials(msg, self.__get_client_ip(request))
                    else:
                        self.log.error(f'Invalid message type received: {type(msg)}')
                    del msg
                else:
                    self.log.error(f'Invalid message type received: {type(raw_msg)}')
                del raw_msg
                return Response('success', 200) if state else Response('Unauthorized', 401)
            except Exception:
                self.log.exception('Failed to handle client auth request')
            return Response('failed', 500)

    @property
    def is_running(self) -> bool:
        """Check if the web server is running

        Returns:
            bool: True if the server is running, False otherwise
        """
        if self.__thread is not None:
            return self.__thread.is_alive()
        return False

    def __get_client_ip(self, request: Request) -> str:
        """Get the client IP from the request. Will check for x-forwarded-for header first incase of a proxy, then
        fallback to the client host

        Args:
            request (Request): request object

        Returns:
            str: client IP address
        """
        forwarded_ip = request.headers.get('x-forwarded-for')
        return forwarded_ip.split(",")[0] if forwarded_ip else request.client.host

    def __credentials_not_expired(self, client_ip: str) -> bool:
        """Check if the client credentials are still valid

        Args:
            client_ip (str): client IP address

        Returns:
            bool: True if the client credentials are still valid, False otherwise
        """
        if client_ip in self.__clients:
            try:
                if self.__clients[client_ip] > datetime.now():
                    return True
            except TypeError:
                self.log.exception('Failed to validate client credentials')
            del self.__clients[client_ip]
        return False

    def __validate_credentials(self, data: dict, client_ip: str) -> bool:
        """Validate the client credentials against the database. Sets the client IP to expire in 1 hour to enforce
        re-authentication

        Args:
            data (dict): client credentials
            client_ip (str): client IP address

        Returns:
            bool: True if the client credentials are valid, False otherwise
        """
        if self.db.authenticate_user(data.get('username', 'N/A'), data.get('password', 'N/A')):
            self.__clients[client_ip] = datetime.now() + timedelta(hours=1)
            return True
        self.log.error(f'Failed to validate credentials for IP {client_ip}')
        return False

    def __start_web_server_process(self) -> bool:
        """Start the web server process in a separate process

        Returns:
            bool: True if the server started successfully, False otherwise
        """
        if self.__process and self.__process.is_alive():
            self.log.info('Server is already running')
            return True
        try:
            name = f'web-server-{self.server_name}:{self._port}-process'
            self.__process = Process(target=self.__start_web_server, name=name, daemon=True)
            self.__process.start()
            sleep(1)  # Give the server time to start
            return True
        except Exception:
            self.log.exception('Failed to start web server process')
        return False

    def __start_web_server(self) -> bool:
        """The web server process. Stays running and is handled by the parent process

        Returns:
            bool: True on successful start and stop. False otherwise
        """
        if self.protocol == 'https':
            certs = self._get_https_certs()
            __certs = {'ssl_ca_certs': certs[0], 'ssl_certfile': certs[1],
                       'ssl_keyfile': certs[2], 'ssl_cert_reqs': ssl.CERT_REQUIRED}
        else:
            __certs = {}
        try:
            uvicorn.run(self._app, host=self._host, port=self._port, **__certs)
            return True
        except Exception:
            self.log.exception('Exception occurred in web server')
        return False

    def __clear_expired_clients(self) -> None:
        """Clear expired clients from the client list"""
        try:
            now = datetime.now()
            for ip in list(self.__clients.keys()):
                if now >= self.__clients.get(ip):
                    del self.__clients[ip]
        except Exception:
            self.log.exception('Failed to clear expired clients')

    def __terminate_web_process(self) -> bool:
        """Terminate the web server process

        Returns:
            bool: True if the server terminated successfully, False otherwise
        """
        if self.__process and self.__process.is_alive():
            self.__process.terminate()
            self.__process.join(3)
            if self.__process.is_alive():
                self.log.error('Failed to terminate web server process')
                return False
            self.__process = None
            self.log.info('Web server process terminated')
        return True

    def __web_cleaner_thread(self) -> bool:
        """Web server cleaner thread. Stats the web web server process then checks for expired clients every 60 seconds.
        Exits if the web process stops running. Receives a stop signal from the parent thread to stop the process.

        Returns:
            bool: True if the thread ran successfully, False otherwise
        """
        try:
            if self.__start_web_server_process():
                cnt = 0
                while not self.__thread_stop.is_set():
                    sleep(1)
                    cnt += 1
                    if cnt == 60:
                        self.__clear_expired_clients()
                        if not self.__process.is_alive():
                            self.log.error('Web server process has stopped')
                            return False
                        cnt = 0
                return self.__terminate_web_process()
            return False
        except Exception:
            self.log.exception('Exception occurred in web cleaner thread')
            return False

    def __create_web_cleaner_thread(self) -> bool:
        """Create the web server cleaner thread

        Returns:
            bool: True if the thread was created successfully, False otherwise
        """
        try:
            name = f'web-cleaner-{self.server_name}:{self._port}-thread'
            self.__thread = Thread(target=self.__web_cleaner_thread, name=name, daemon=True)
            self.__thread.start()
            return True
        except Exception:
            self.log.exception('Failed to create web server thread')
            return False

    def start(self) -> bool:
        """Start the web server cleaner thread and start the web server

        Returns:
            bool: True if the server started successfully, False otherwise
        """
        self.log.info(f'Starting web server {self.server_name}:{self._port}')
        self.__thread_stop.clear()
        if self.__thread is not None:
            if self.__thread.is_alive():
                self.log.info(f'Web server {self.server_name}:{self._port} is already running')
                return True
            self.__thread = None
        return self.__create_web_cleaner_thread()

    def stop(self) -> bool:
        """Stop the web server and the web server cleaner thread

        Returns:
            bool: True if the server stopped successfully, False otherwise
        """
        self.log.info(f'Stopping web server {self.server_name}:{self._port}')
        try:
            if self.__thread is not None:
                if self.__thread.is_alive():
                    self.__thread_stop.set()
                    self.__thread.join(5)
                    if self.__thread.is_alive():
                        self.log.error('Failed to stop web server thread')
                        return False
                self.__thread = None
                return True
            self.log.info(f'Web server {self.server_name}:{self._port} is not running')
            return True
        except Exception:
            self.log.exception('Failed to stop web server')
        return False
