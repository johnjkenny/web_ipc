from pathlib import Path
from os import remove

from web_ipc.web_utils import WebUtils
from web_ipc.cert_auth import CertStore


class Init():
    def __init__(self, force: bool = False):
        """Initialize the web server environment

        Args:
            force (bool, optional): Option to recreate env objects. Defaults to False.
        """
        self.utils = WebUtils()
        self.__user = 'ipc-admin'
        self.__password = self.utils.generate_password()
        self.__force = force

    def __create_db(self) -> bool:
        """Create the database. If force is set, delete the db file and recreate it

        Returns:
            bool: True if successful, False otherwise
        """
        path = Path(f'{Path(__file__).parent}/web_env/users.db')
        if not path.exists():
            return self.utils.db._initialize()
        if self.__force:
            remove(path)
            return self.utils.db._initialize()
        return True

    def __create_keys(self) -> bool:
        """Create the encryption keys. Will override the keys if force is set

        Returns:
            bool: True if successful, False otherwise
        """
        if self.__force or not Path(self.utils.encrypt.key_file).exists():
            return self.utils.encrypt._create_key()
        return True

    def __add_user(self) -> bool:
        """Create the default admin using (ipc-admin, random_password) in the database. Pickles and encrypts the creds
        locally so user does not need to directly know about the credentials for the default admin account. Will
        override the data if force is set

        Returns:
            bool: True if successful, False otherwise
        """
        if self.utils.db.user_exists(self.__user):
            return True
        if self.utils.db.add_user(self.__user, self.__password):
            return self.utils.pickle_dump(f'{Path(__file__).parent}/web_env/.ipca',
                                          {'username': self.__user, 'password': self.__password})
        return False

    def __create_ca_serial_handler(self) -> bool:
        """Create the CA serial file. If force is set, delete the file and recreate it

        Returns:
            bool: True if successful, False otherwise
        """
        path = f'{Path(__file__).parent}/web_env/ca-serial'
        if not Path(path).exists():
            try:
                with open(path, 'w') as file:
                    file.write('1')
                return True
            except Exception:
                self.utils.log.exception('Failed to create CA serial file')
                return False
        if self.__force:
            remove(path)
            return self.__create_ca_serial_handler()
        return True

    def __initialize_cert_authority(self) -> bool:
        """Initialize the certificate authority by creating the CA cert and key. Then create the localhost cert
        and key using the CA. If force is set, recreate the CA cert and key

        Returns:
            bool: _description_
        """
        cert_auth = CertStore(self.utils.log)
        if cert_auth._initialize_cert_authority(self.__force):
            return cert_auth.create('localhost', ['localhost', '127.0.0.1'])
        return False

    def _run(self) -> bool:
        """Run the initialization process

        Returns:
            bool: True if successful, False otherwise
        """
        for method in [self.__create_db, self.__create_keys, self.__add_user, self.__create_ca_serial_handler,
                       self.__initialize_cert_authority]:
            if not method():
                return False
        return True
