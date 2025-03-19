from setuptools import setup


try:
    setup(
        name='web-ipc',
        version='1.0.0',
        include_package_data=True,
        package_data={'web-ipc': ['logs', 'web_env']},
        entry_points={'console_scripts': [
            'web-ipc = web_ipc.cli:web_parent',
            'web-ipc-certs = web_ipc.cli:web_certs',
            'web-ipc-init = web_ipc.cli:web_init',
            'web-ipc-users = web_ipc.cli:web_users',
            'web-ipc-test = web_ipc.cli:web_test',
        ]},
    )
    exit(0)
except Exception as error:
    print(f'Failed to setup package: {error}')
    exit(1)
