from argparse import REMAINDER

from web_ipc.arg_parser import ArgParser
from web_ipc.init import Init


def parse_parent_args(args: dict):
    if args.get('certs'):
        return web_certs(args['certs'])
    if args.get('init'):
        return web_init(args['init'])
    if args.get('test'):
        return web_test(args['test'])
    if args.get('users'):
        return web_users(args['users'])
    return True


def web_parent():
    args = ArgParser('Web IPC Commands', None, {
        'certs': {
            'short': 'c',
            'help': 'Generate SSL certificates',
            'nargs': REMAINDER
        },
        'init': {
            'short': 'I',
            'help': 'Initialize Web-IPC (web-ipc-init)',
            'nargs': REMAINDER
        },
        'users': {
            'short': 'u',
            'help': 'User Commands (web-ipc-user)',
            'nargs': REMAINDER
        },
        'test': {
            'short': 't',
            'help': 'Test Web-IPC (wbe-ipc-test)',
            'nargs': REMAINDER
        },
    }).set_arguments()
    if not parse_parent_args(args):
        exit(1)
    exit(0)


def parse_cert_args(args: dict):
    from web_ipc.cert_auth import CertStore
    if args.get('name'):
        return CertStore().create(args['name'], args['altNames'])
    return True


def web_certs(parent_args: list = None):
    args = ArgParser('Web IPC SSL Certs', parent_args, {
        'name': {
            'short': 'n',
            'help': 'Name for IPC server or client',
        },
        'altNames': {
            'short': 'a',
            'help': 'Alternative names for new cert',
            'nargs': '+'
        },
    }).set_arguments()
    if not parse_cert_args(args):
        exit(1)
    exit(0)


def parse_init_args(args: dict):
    if args.get('run'):
        return Init(args['force'])._run()
    return True


def web_init(parent_args: list = None):
    args = ArgParser('Web IPC Initialization', parent_args, {
        'run': {
            'short': 'r',
            'help': 'Run initialization',
            'action': 'store_true',
        },
        'force': {
            'short': 'F',
            'help': 'Force action',
            'action': 'store_true',
        }
    }).set_arguments()
    if not parse_init_args(args):
        exit(1)
    exit(0)


def parse_user_args(args: dict):
    from web_ipc.web_utils import WebUtils, User
    if args.get('add'):
        if not args.get('user') or not args.get('password'):
            print('Username and password are required')
            return False
        return WebUtils().db.add_user(args['user'], args['password'])
    if args.get('list'):
        users = WebUtils().db.get_session().query(User).all()
        for user in users:
            print(f'Username: {user.username}')
    if args.get('testCredentials'):
        if not args.get('user') or not args.get('password'):
            print('Username and password are required')
            return False
        if WebUtils().db.authenticate_user(args['user'], args['password']):
            print('Credentials verified')
            return True
        return False
    if args.get('delete'):
        if not args.get('user'):
            print('Username is required')
            return False
        utils = WebUtils()
        if utils.db.user_exists(args['user']):
            session = utils.db.get_session()
            session.query(User).filter_by(username=args['user']).delete()
            session.commit()
            print(f'User {args["user"]} deleted')
            return True
        print(f'User {args["user"]} does not exist')
        return False
    return True


def web_users(parent_args: list = None):
    args = ArgParser('Web IPC User Handler', parent_args, {
        'add': {
            'short': 'a',
            'help': 'Add user',
            'action': 'store_true',
        },
        'delete': {
            'short': 'd',
            'help': 'Delete user',
            'action': 'store_true',
        },
        'user': {
            'short': 'u',
            'help': 'Username',
        },
        'password': {
            'short': 'p',
            'help': 'Password',
        },
        'list': {
            'short': 'l',
            'help': 'List users',
            'action': 'store_true',
        },
        'testCredentials': {
            'short': 't',
            'help': 'Test credentials',
            'action': 'store_true',
        }
    }).set_arguments()
    if not parse_user_args(args):
        exit(1)
    exit(0)


def parse_test_args(args: dict):
    from web_ipc.tests.web_ipc_test_server import run_test
    if args.get('run'):
        return run_test(args['name'], args['ip'], args['port'], args['protocol'], args['logLevel'], args['qty'])
    return True


def web_test(parent_args: list = None):
    args = ArgParser('Web IPC Test', parent_args, {
        'run': {
            'short': 'r',
            'help': 'Run server',
            'action': 'store_true',
        },
        'name': {
            'short': 'n',
            'help': 'Web server name. Default: localhost',
            'default': 'localhost',
        },
        'ip': {
            'short': 'i',
            'help': 'Host IP. Default: 127.0.0.1',
            'default': '127.0.0.1',
        },
        'port': {
            'short': 'p',
            'help': 'Port number. Default: 0 and will find available port between 3000-4000',
            'type': int,
            'default': 0,
        },
        'protocol': {
            'short': 'P',
            'help': 'Protocol. Default: https',
            'default': 'https',
        },
        'logLevel': {
            'short': 'l',
            'help': 'Log level. Default: info',
            'choices': ['debug', 'info', 'warning', 'error', 'critical'],
            'default': 'info',
        },
        'qty': {
            'short': 'q',
            'help': 'Number of test messages to send to server from client. Default: 100',
            'type': int,
            'default': 100,
        },
    }).set_arguments()
    if not parse_test_args(args):
        exit(1)
    exit(0)
