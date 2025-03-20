from threading import Event, Thread
from multiprocessing import Queue
from time import sleep

from web_ipc.web_server import WebServer
from web_ipc.web_client import WebClient
from web_ipc.logger import get_logger


class TestServer():
    def __init__(self, name: str = 'localhost', ip: str = '127.0.0.1', port: int = 0, protocol: str = 'https',
                 log_level: str = 'info'):
        """Test server to validate web_ipc is working correctly with the set configuration

        Args:
            name (str, optional): sever name. Defaults to 'localhost'.
            ip (str, optional): server IP. Defaults to '127.0.0.1'.
            port (int, optional): server port. Defaults to 0.
            protocol (str, optional): web protocol (http or https). Defaults to 'https'.
            log_level (str, optional): log level to set. Defaults to 'info'.
        """
        self.log = get_logger('web-ipc-test-server', log_level)
        self.__service_stop = Event()
        self.__queue = Queue(20)
        self.web_server = WebServer(name, ip, port, protocol, self.__queue, self.log)

    def __handle_sigterm(self, *_, **kwargs) -> None:
        """Handle web server shutdown and exit"""
        if self.web_server.is_running:
            self.web_server.stop()
        exit(kwargs.get('exit_code', 0))

    def __message_handler(self, msg: dict) -> None:
        """Handle incoming messages

        Args:
            msg (dict): incoming message
        """
        if isinstance(msg, dict):
            self.log.info(f'Received message: {msg}')
        else:
            self.log.error(f'Invalid message type received: {type(msg)}')
        del msg

    def __run_service(self) -> bool:
        """Run the web server service in a loop until service_stop is set

        Returns:
            bool: True
        """
        self.__service_stop.clear()
        while not self.__service_stop.is_set():
            try:
                self.__message_handler(self.__queue.get(timeout=1))
            except Exception:
                continue
        return True

    def start(self) -> bool | None:
        """Start the web server service and handle exceptions

        Returns:
            bool: True if service started successfully, False or None otherwise
        """
        self.log.info(f'Starting Web-IPC-Test {self.web_server.server_name}:{self.web_server._port}')
        if self.web_server.start():
            try:
                return self.__run_service()
            except KeyboardInterrupt:
                self.log.info('Received keyboard interrupt, initiating sigterm with exit 0')
                return self.__handle_sigterm(exit_code=0)
            except Exception:
                self.log.exception('Service stopped unexpectedly, initiating sigterm with exit 1')
                return self.__handle_sigterm(exit_code=1)
        self.log.error('Failed to start service, initiating sigterm with exit 1')
        return exit(1)

    def stop(self) -> bool:
        """Stop the web server service by setting the service_stop event

        Returns:
            bool: True
        """
        self.__service_stop.set()
        return True


def run_test(name, ip, port, protocol, log_level, test_qty: int = 100) -> bool:
    """Run a test server and client to validate web_ipc is working correctly with the set configuration

    Args:
        name (_type_): server name
        ip (_type_): server IP
        port (_type_): server port
        protocol (_type_): web protocol (http or https)
        log_level (_type_): log level to set
        test_qty (int, optional): the qty of messages to send to server from client. Defaults to 100.

    Returns:
        bool: True if test ran successfully, False otherwise
    """
    test_server = TestServer(name, ip, port, protocol, log_level)
    test_client = WebClient(name, ip, test_server.web_server._port, protocol, logger=test_server.log)
    thread = Thread(target=test_server.start, name='test-server-thread', daemon=True)
    thread.start()
    sleep(1)
    for i in range(1, test_qty + 1):
        if not test_client.send_msg({'test': i}):
            return False
        sleep(.1)
    test_server.stop()
    thread.join()
    return True
