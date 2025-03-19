from logging import Logger
from datetime import datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption, load_pem_private_key

from web_ipc.logger import get_logger


class CertStore():
    def __init__(self, logger: Logger = None):
        self.log = logger or get_logger('web-ipc')
        self.__ca_name = 'web-ipc-ca'
        self.__private_key = None
        self.__subject = None
        self.__subject_alt_name = None
        self.__certificate = None

    def __next_serial(self) -> int:
        """Get the next serial number of the certificate authority

        Returns:
            int: The next serial number
        """
        try:
            with open(Path(f'{Path(__file__).parent}/web_env/ca-serial'), 'r+') as file:
                serial = int(file.read().strip()) + 1
                file.seek(0)
                file.write(str(serial))
                file.truncate()
                return serial
        except Exception:
            self.log.exception('Failed to get next serial number from serial cache object')
        return 0

    def __generate_private_key(self) -> bool:
        """Generate private key

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.__private_key = rsa.generate_private_key(65537, 4096)
            return True
        except Exception:
            self.log.exception('Failed to generate private key')
        return False

    def __create_subject(self, common_name: str, **kwargs: dict) -> bool:
        """Create the cert subject

        Returns:
           bool: True if self.__subject set successfully, False otherwise
        """
        try:
            self.__subject = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, kwargs.get('country', 'US')),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, kwargs.get('state', 'US-STATE')),
                x509.NameAttribute(NameOID.LOCALITY_NAME, kwargs.get('city', 'US-CITY')),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, kwargs.get('company', 'US-Company')),
                x509.NameAttribute(NameOID.COMMON_NAME, common_name),
                x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, kwargs.get('department', 'US-Department')),
                x509.NameAttribute(NameOID.EMAIL_ADDRESS, kwargs.get('email', 'myEmail@email.com'))])
            return True
        except Exception:
            self.log.exception('Failed to create subject')
        return False

    def __create_subject_alternative(self, names: list) -> bool:
        """ Create subject alternative names

        Args:
            names (list, optional): List of alternative names.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.__subject_alt_name = x509.SubjectAlternativeName([x509.DNSName(name) for name in names])
            return True
        except Exception:
            self.log.exception('Failed to create subject alternative names')
        return False

    def __define_cert(self, issuer: object, sign_key: bytes, cert_authority: bool = False) -> bool:
        """Define certificate

        Args:
            issuer (object): The issuer of the certificate.
            sign_key (bytes): The signing key.
            cert_authority (bool, optional): Determines if the certificate is a CA. Defaults to False.

        Returns:
            bool: True if successful, False otherwise
        """
        serial = self.__next_serial()
        if serial:
            try:
                now = datetime.now()
                self.__certificate = (
                    x509.CertificateBuilder()
                    .subject_name(self.__subject)
                    .issuer_name(issuer)
                    .public_key(self.__private_key.public_key())
                    .serial_number(serial)
                    .not_valid_before(now)
                    .not_valid_after(now + timedelta(days=36500))  # 100 years
                    .add_extension(self.__subject_alt_name, False)
                )
                if cert_authority:
                    self.__certificate = self.__certificate.add_extension(x509.BasicConstraints(True, None), True)
                self.__certificate = self.__certificate.sign(sign_key, SHA256())
                return True
            except Exception:
                self.log.exception('Failed to define certificate')
        return False

    def __save_cert(self, name: str) -> bool:
        """Save certificate

        Args:
            name (str): The name of the certificate

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(f'{name}.crt', 'wb') as file:
                file.write(self.__certificate.public_bytes(Encoding.PEM))
            return True
        except Exception:
            self.log.exception('Failed to save certificate')
        return False

    def __save_key(self, name: str) -> bool:
        """Save key

        Args:
            name (str): The name of the key

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(f'{name}.key', 'wb') as file:
                file.write(self.__private_key.private_bytes(
                    Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
            return True
        except Exception:
            self.log.exception('Failed to save key')
        return False

    def __save_cert_and_key(self, name: str) -> bool:
        """Save certificate and key

        Args:
            name (str): The name of the certificate and key

        Returns:
            bool: True if successful, False otherwise
        """
        name = f'{Path(__file__).parent}/web_env/{name}'
        return self.__save_cert(name) and self.__save_key(name)

    def __create_cert_authority_subject(self) -> bool:
        """Create the CA subject

        Returns:
           bool: True if successful, False otherwise
        """
        return self.__create_subject('web-ipc-ca') and self.__create_subject_alternative(['web-ipc-ca'])

    def __define_ca_cert(self) -> bool:
        """Define the CA certificate

        Returns:
            Certificate object: The CA certificate on success, None otherwise
        """
        return self.__define_cert(self.__subject, self.__private_key, True)

    def _initialize_cert_authority(self, force: bool = False) -> bool:
        """Initialize the cluster certificate authority

        Args:
            force (bool, optional): Force the initialization. Defaults to False.

        Returns:
            bool: True if successful, False otherwise
        """
        if force or not Path(f'{Path(__file__).parent}/web_env/{self.__ca_name}.crt').exists():
            for func in [self.__generate_private_key, self.__create_cert_authority_subject, self.__define_ca_cert]:
                if not func():
                    return False
            return self.__save_cert_and_key(self.__ca_name)
        return True

    def __load_ca_cert_and_key(self) -> dict:
        """Load the CA certificate and key

        Returns:
            dict: The CA certificate and key objects
        """
        try:
            name = f'{Path(__file__).parent}/web_env/{self.__ca_name}'
            with open(f'{name}.crt', 'rb') as file:
                cert = x509.load_pem_x509_certificate(file.read())
            with open(f'{name}.key', 'rb') as file:
                key = load_pem_private_key(file.read(), None)
            return {'cert': cert, 'key': key}
        except Exception:
            self.log.exception('Failed to load CA certificate and key')
        return {}

    def create(self, common_name: str, subject_alt: list = None, **kwargs: dict) -> bool:
        """Create a certificate

        Args:
            common_name (str): The common name. Name of the service or entity.
            subject_alt (list): The subject alternative names. Defaults to [].

        Kwargs:
            country (str): The country. Defaults to 'US'.
            state (str): The state'
            city (str): The city'
            company (str): The company'
            department (str): The department'.
            email (str): The email'

        Returns:
            bool: True if successful, False otherwise
        """
        if subject_alt is None:
            subject_alt = [common_name]
        ca = self.__load_ca_cert_and_key()
        if ca:
            return self.__generate_private_key() and \
                self.__create_subject(common_name, **kwargs) and \
                self.__create_subject_alternative(subject_alt) and \
                self.__define_cert(ca.get('cert').subject, ca.get('key')) and \
                self.__save_cert_and_key(common_name)
        return False
