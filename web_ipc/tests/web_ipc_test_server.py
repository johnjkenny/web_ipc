from threading import Event, Thread
from multiprocessing import Queue
from time import sleep

from web_ipc.web_server import WebServer
from web_ipc.web_client import WebClient
from web_ipc.logger import get_logger


class TestServer():
    def __init__(self, name: str = 'localhost', ip: str = '127.0.0.1', port: int = 0, protocol: str = 'https',
                 log_level: str = 'info'):
        self.log = get_logger('web-ipc-test-server', log_level)
        self.__service_stop = Event()
        self.__queue = Queue(20)
        self.web_server = WebServer(name, ip, port, protocol, self.__queue, self.log)

    def __handle_sigterm(self, *_, **kwargs):
        if self.web_server.is_running:
            self.web_server.stop()
        exit(kwargs.get('exit_code', 0))

    def __message_handler(self, msg: dict):
        if isinstance(msg, dict):
            self.log.info(f'Received message: {msg}')
        else:
            self.log.error(f'Invalid message type received: {type(msg)}')
        del msg

    def __run_service(self):
        self.__service_stop.clear()
        while not self.__service_stop.is_set():
            try:
                self.__message_handler(self.__queue.get(timeout=1))
            except Exception:
                continue
        return True

    def start(self):
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

    def stop(self):
        self.__service_stop.set()
        return True


def run_test(name, ip, port, protocol, log_level, test_qty: int = 100):
    test_server = TestServer(name, ip, port, protocol, log_level)
    test_client = WebClient(name, ip, test_server.web_server._port, protocol, logger=test_server.log)
    thread = Thread(target=test_server.start, name='test-server-thread', daemon=True)
    thread.start()
    sleep(1)
    for i in range(1, test_qty + 1):
        test_client.send_msg({'test': i})
        sleep(.1)
    test_server.stop()
    thread.join()
    return True
