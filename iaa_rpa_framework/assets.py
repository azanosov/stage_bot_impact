"""
Strongly-typed asset classes for the IAA RPA Framework.

This module provides concrete asset types that can be retrieved from the orchestrator,
giving developers type-safe access to credential fields without needing to parse JSON manually.

Usage:
    from iaa_rpa_framework import UserCredential, DatabaseCredential

    # In your RPA process:
    cred = agent.get_asset("MyLoginCred", UserCredential)
    print(cred.username)
    print(cred.password)

    db_cred = agent.get_asset("MyDbConnection", DatabaseCredential)
    print(db_cred.hostname)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TypeVar, Type, Dict, Any, Optional, List, cast
import json
import base64


class AssetParseError(Exception):
    """Raised when an asset cannot be parsed into the requested type."""
    pass


@dataclass
class Asset(ABC):
    
    #Base class for all asset types.

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Asset":
        pass

    @classmethod
    def from_json(cls, json_string: str) -> "Asset":
        """
        Create an asset instance from a JSON string.
        """
        try:
            data = json.loads(json_string)
        except json.JSONDecodeError as e:
            raise AssetParseError(f"Invalid JSON: {e}")

        return cls.from_dict(data)


# Type variable for generic asset retrieval
AssetT = TypeVar("AssetT", bound=Asset)


# --- Simple Value Types ---

@dataclass
class StringAsset(Asset):
    """
    Simple text asset (not encrypted).
    """
    value: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StringAsset":
        try:
            # Handle both direct value and nested structure
            if isinstance(data, str):
                return cls(value=data)
            return cls(value=data.get("value") or data.get("Value") or str(data))
        except (KeyError, TypeError) as e:
            raise AssetParseError(f"Invalid data for StringAsset: {e}")


@dataclass
class SecretAsset(Asset):
    """
    Simple text asset (encrypted). The value is decrypted by the orchestrator.
    """
    value: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SecretAsset":
        try:
            if isinstance(data, str):
                return cls(value=data)
            return cls(value=data.get("value") or data.get("Value") or str(data))
        except (KeyError, TypeError) as e:
            raise AssetParseError(f"Invalid data for SecretAsset: {e}")


# --- Contact ---

@dataclass
class Contact(Asset):
    """
    Contact information asset.
    """
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Contact":
        first_name = data.get("first_name") or data.get("firstName") or data.get("FirstName")
        last_name = data.get("last_name") or data.get("lastName") or data.get("LastName")
        email = data.get("email") or data.get("Email")
        if first_name is None or last_name is None or email is None:
            raise AssetParseError("Missing required field for Contact: first_name, last_name, or email")
        return cls(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=data.get("phone") or data.get("Phone")
        )


# --- Credential Types ---

@dataclass
class RobotCredential(Asset):
    """
    Credential for robot/service account authentication with domain support.
    """
    username: str
    password: str
    domain: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RobotCredential":
        username = data.get("username") or data.get("Username")
        password = data.get("password") or data.get("Password")
        if username is None or password is None:
            raise AssetParseError("Missing required field for RobotCredential: username or password")
        return cls(
            username=username,
            password=password,
            domain=data.get("domain") or data.get("Domain")
        )


@dataclass
class UserCredential(Asset):
    """
    Credential for user authentication with optional MFA support.
    """
    username: str
    password: str
    mfa_key: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserCredential":
        username = data.get("username") or data.get("Username")
        password = data.get("password") or data.get("Password")
        if username is None or password is None:
            raise AssetParseError("Missing required field for UserCredential: username or password")
        return cls(
            username=username,
            password=password,
            mfa_key=data.get("mfa_key") or data.get("mfaKey") or data.get("MFAKey") or data.get("mfa_token")
        )


@dataclass
class APICredential(Asset):
    """
    Credential for API/OAuth authentication.
    """
    client_id: str
    client_secret: str
    tenant_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "APICredential":
        client_id = data.get("client_id") or data.get("clientId") or data.get("ClientId") or data.get("ClientID")
        client_secret = data.get("client_secret") or data.get("clientSecret") or data.get("ClientSecret")
        if client_id is None or client_secret is None:
            raise AssetParseError("Missing required field for APICredential: client_id or client_secret")
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=data.get("tenant_id") or data.get("tenantId") or data.get("TenantId") or data.get("TenantID")
        )


@dataclass
class DatabaseCredential(Asset):
    """
    Credential for database connections.
    """
    hostname: str
    port: int
    database: str
    username: str
    password: str
    schema: Optional[str] = None
    options: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatabaseCredential":
        try:
            hostname = data.get("hostname") or data.get("Hostname") or data.get("host") or data.get("Host")
            database = data.get("database") or data.get("Database") or data.get("database_name") or data.get("databaseName")
            username = data.get("username") or data.get("Username")
            password = data.get("password") or data.get("Password")
            if hostname is None or database is None or username is None or password is None:
                raise AssetParseError("Missing required field for DatabaseCredential: hostname, database, username, or password")
            return cls(
                hostname=hostname,
                port=int(data.get("port") or data.get("Port") or 0),
                database=database,
                username=username,
                password=password,
                schema=data.get("schema") or data.get("Schema") or data.get("schema_name") or data.get("schemaName"),
                options=data.get("options") or data.get("Options")
            )
        except (ValueError, TypeError) as e:
            raise AssetParseError(f"Invalid field value for DatabaseCredential: {e}")


@dataclass
class SSHCredential(Asset):
    """
    Credential for SSH connections.
    """
    hostname: str
    username: str
    port: int = 22
    password: Optional[str] = None
    private_key: Optional[str] = None
    passphrase: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SSHCredential":
        hostname = data.get("hostname") or data.get("Hostname") or data.get("host") or data.get("Host")
        username = data.get("username") or data.get("Username")
        if hostname is None or username is None:
            raise AssetParseError("Missing required field for SSHCredential: hostname or username")
        return cls(
            hostname=hostname,
            port=int(data.get("port") or data.get("Port") or 22),
            username=username,
            password=data.get("password") or data.get("Password"),
            private_key=data.get("private_key") or data.get("privateKey") or data.get("PrivateKey"),
            passphrase=data.get("passphrase") or data.get("Passphrase")
        )


# --- Binary Data ---

@dataclass
class BinaryAsset(Asset):
    """
    Binary data asset (e.g., files, certificates).
    """
    filename: Optional[str] = None
    content: bytes = field(default_factory=bytes)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BinaryAsset":
        try:
            content_raw = data.get("content") or data.get("Content") or data.get("data") or data.get("Data") or ""
            # Decode base64 content if it's a string
            if isinstance(content_raw, str):
                content = base64.b64decode(content_raw)
            elif isinstance(content_raw, bytes):
                content = content_raw
            else:
                content = bytes()

            return cls(
                filename=data.get("filename") or data.get("Filename") or data.get("file_name") or data.get("fileName"),
                content=content
            )
        except Exception as e:
            raise AssetParseError(f"Invalid data for BinaryAsset: {e}")

    def save_to_file(self, path: str) -> None:
        """Save the binary content to a file."""
        with open(path, "wb") as f:
            f.write(self.content)


# --- Email Template ---

@dataclass
class EmailTemplate(Asset):
    """
    Email template asset.
    """
    subject: str
    body: str
    to: Optional[List[str]] = None
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmailTemplate":
        try:
            # Handle to/cc/bcc as either list or comma-separated string
            def parse_recipients(value) -> Optional[List[str]]:
                if value is None:
                    return None
                if isinstance(value, list):
                    return value
                if isinstance(value, str):
                    return [r.strip() for r in value.split(",") if r.strip()]
                return None

            return cls(
                subject=data.get("subject") or data.get("Subject") or "",
                body=data.get("body") or data.get("Body") or "",
                to=parse_recipients(data.get("to") or data.get("To")),
                cc=parse_recipients(data.get("cc") or data.get("Cc") or data.get("CC")),
                bcc=parse_recipients(data.get("bcc") or data.get("Bcc") or data.get("BCC"))
            )
        except KeyError as e:
            raise AssetParseError(f"Missing required field for EmailTemplate: {e}")


# --- Generic Asset ---

@dataclass
class GenericAsset(Asset):
    """
    A generic asset type for unstructured or custom asset data.

    Use this when you need to access an asset that doesn't fit
    the predefined types, or when you want raw access to all fields.
    """
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GenericAsset":
        return cls(data=data)

    def __getattr__(self, name: str) -> Any:
        """Allow attribute-style access to data fields."""
        if name == "data":
            return super().__getattribute__("data")
        try:
            return self.data[name]
        except KeyError:
            raise AttributeError(f"GenericAsset has no field '{name}'")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a field value with an optional default."""
        return self.data.get(key, default)


# --- Factory ---

class AssetFactory:
    @staticmethod
    def create(asset_type: Type[AssetT], data: Dict[str, Any]) -> AssetT:
        if not isinstance(asset_type, type) or not issubclass(asset_type, Asset):
            raise TypeError(f"{asset_type} is not a valid Asset type")

        return cast(AssetT, asset_type.from_dict(data))

    @staticmethod
    def create_from_json(asset_type: Type[AssetT], json_string: str) -> AssetT:
        if not isinstance(asset_type, type) or not issubclass(asset_type, Asset):
            raise TypeError(f"{asset_type} is not a valid Asset type")

        return cast(AssetT, asset_type.from_json(json_string))
