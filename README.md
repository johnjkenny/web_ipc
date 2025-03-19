# Inter Process Communication (IPC) using HTTPS

This is an Asynchronous Inter Process Communication (IPC) module that uses HTTP or HTTPS for simple communication
between processes. It is designed to be secure and simple to use. It is built on top of FastAPI and Uvicorn. It allows
you to send encrypted python dict objects from client to server for the server to process. As well as HTTPS (if
enforced) data is also encrypted client side and decrypted on server side using Cipher AES-128-CBC. The server
enforces username and password authentication from clients every hour after the initial auth.


## Configure the environment

The following steps will guide you on how to create the python virtual environment and install the required packages.
It will also install the console scripts that will be used to run the server and client CLI commands.

After the initialization, the local SQlite database will be created and the default admin user will be created with a 
unique password. The credentials for the default admin user will be encrypted and stashed locally. If you do not want to
use the default admin user within your environment, you can create a new user with the `--users --add` command (see
below, but be sure to delete the default user if you want to enforce no admin user). A certificate authority will be
created locally and SSL certificates will be created for the default server name (localhost). Follow the instructions
below to create SSL certificates for a different server name if you need to communicate to remote hosts. An encryption
key is created and stored locally for the encryption decryption of data before and after flight.


### Create virtual environment
```bash
python3 -m venv venv
```

### Activate virtual environment
```bash
source venv/bin/activate
```

### Install requirements
```bash
pip install -r requirements.txt
```

### Install Console Scripts
```bash
pip install -e .
```

### Initialize the Environment
```bash
web-ipc --init --run
```

## CLI Commands

### Run Test:
```bash
web-ipc --test --run --qty 3

# Example outout:
[2025-03-19 19:38:50,608][INFO][web_ipc_test_server,40]: Starting Web-IPC-Test localhost:3000
[2025-03-19 19:38:50,608][INFO][web_server,182]: Starting web server localhost:3000
INFO:     Started server process [6787]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on https://127.0.0.1:3000 (Press CTRL+C to quit)
INFO:     127.0.0.1:35976 - "POST /message/submit HTTP/1.1" 419 
[2025-03-19 19:38:51,635][INFO][web_client,75]: [419] Authentication timeout, re-authenticating
INFO:     127.0.0.1:35978 - "GET /is/running HTTP/1.1" 200 OK
INFO:     127.0.0.1:35980 - "POST /client/auth HTTP/1.1" 200 OK
INFO:     127.0.0.1:35994 - "POST /message/submit HTTP/1.1" 200 OK
[2025-03-19 19:38:51,870][INFO][web_ipc_test_server,25]: Received message: {'test': 1}
INFO:     127.0.0.1:35998 - "POST /message/submit HTTP/1.1" 200 OK
[2025-03-19 19:38:51,988][INFO][web_ipc_test_server,25]: Received message: {'test': 2}
INFO:     127.0.0.1:36000 - "POST /message/submit HTTP/1.1" 200 OK
[2025-03-19 19:38:52,110][INFO][web_ipc_test_server,25]: Received message: {'test': 3}
INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process [6787]
```

### Create SSL certificates for non default server name (localhost):
```bash
web-ipc --certs --name testServer1 --altNames testServer1 testServer1.local localhost 127.0.0.1

# add a host entry for servername and correct IP address
echo "127.0.0.1 testServer1" >> /etc/hosts

# Run test using newly created certs and server name (set -i and -p flags accordingly)
web-ipc -t -r -n testServer1 -q 3

# Example output:
[2025-03-19 21:08:31,915][INFO][web_ipc_test_server,40]: Starting Web-IPC-Test testServer1:3000
[2025-03-19 21:08:31,915][INFO][web_server,182]: Starting web server testServer1:3000
INFO:     Started server process [8543]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on https://127.0.0.1:3000 (Press CTRL+C to quit)
INFO:     127.0.0.1:34982 - "POST /message/submit HTTP/1.1" 419 
[2025-03-19 21:08:32,940][INFO][web_client,75]: [419] Authentication timeout, re-authenticating
INFO:     127.0.0.1:34992 - "GET /is/running HTTP/1.1" 200 OK
INFO:     127.0.0.1:34994 - "POST /client/auth HTTP/1.1" 200 OK
INFO:     127.0.0.1:35002 - "POST /message/submit HTTP/1.1" 200 OK
[2025-03-19 21:08:33,175][INFO][web_ipc_test_server,25]: Received message: {'test': 1}
INFO:     127.0.0.1:35008 - "POST /message/submit HTTP/1.1" 200 OK
[2025-03-19 21:08:33,303][INFO][web_ipc_test_server,25]: Received message: {'test': 2}
INFO:     127.0.0.1:35024 - "POST /message/submit HTTP/1.1" 200 OK
[2025-03-19 21:08:33,420][INFO][web_ipc_test_server,25]: Received message: {'test': 3}
INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process [8543]
```

### Create Authentication users other than the default admin user:
```bash
web-ipc --users --add --user test1 --password pass321
[2025-03-19 21:16:16,346][INFO][web_utils,58]: Successfully created user test1
```

### List users:
```bash
web-ipc --users --list                               
Username: ipc-admin
Username: test1
```

### Validate Credentials:
```bash
web-ipc -u -t -u test1 -p pass321
Credentials verified
```

### Remove user:
```bash
web-ipc -u -d -u test1           
User test1 deleted

web-ipc --users --list           
Username: ipc-admin
```

## Implementation

Use `web_env/tests/web_ipc_test_server.py` example to help implement your own IPC, but as a brief overview you can use
the following to help implement the web server and client functionality in your own services.

### Web Server:
```python
from multiprocessing import Queue

from web_ipc.web_server import WebServer

queue = Queue(20)
web_server = WebServer(name='localhost', host='127.0.0.1', port=3000, queue=queue)
web_server.start()
while True:
    try:
        msg = queue.get(timeout=1)
        if isinstance(msg, dict):
            print(f'Received message: {msg}')
    except Exception:
        continue
```

### Web Client:
```python
from time import sleep

from web_ipc.web_client import WebClient

client = WebClient(server_name='localhost', server_ip='127.0.0.1', server_port=3000)
for i in range(1, 4):
    client.send_msg({'test': i})
    sleep(.1)
```
