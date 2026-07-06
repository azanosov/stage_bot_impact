"""
Credentials utility for interacting with Windows Credential Manager.

All credentials are prefixed with 'iaAutomate:' for namespace isolation.
"""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import Optional

# Windows Credential Manager constants
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2

CREDENTIAL_PREFIX = "iaAutomate:"

@dataclass
class Credential:
    """Represents a credential from Windows Credential Manager."""

    name: str
    username: str
    password: str

    @property
    def full_target_name(self) -> str:
        """Returns the full target name including prefix."""
        return f"{CREDENTIAL_PREFIX}{self.name}"


class _CREDENTIAL(ctypes.Structure):
    """Windows CREDENTIAL structure."""

    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


# Load advapi32.dll for credential functions
_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

_CredReadW = _advapi32.CredReadW
_CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(_CREDENTIAL))]
_CredReadW.restype = wintypes.BOOL

_CredWriteW = _advapi32.CredWriteW
_CredWriteW.argtypes = [ctypes.POINTER(_CREDENTIAL), wintypes.DWORD]
_CredWriteW.restype = wintypes.BOOL

_CredDeleteW = _advapi32.CredDeleteW
_CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
_CredDeleteW.restype = wintypes.BOOL

_CredEnumerateW = _advapi32.CredEnumerateW
_CredEnumerateW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(ctypes.POINTER(ctypes.POINTER(_CREDENTIAL))),
]
_CredEnumerateW.restype = wintypes.BOOL

_CredFree = _advapi32.CredFree
_CredFree.argtypes = [ctypes.c_void_p]
_CredFree.restype = None

def __repr__(self) -> str:
    return f"Credential(name={self.name!r}, username={self.username!r}, password='***')"

def _get_full_target_name(name: str) -> str:
    """Prepend the iaAutomate prefix to a credential name."""
    if name.startswith(CREDENTIAL_PREFIX):
        return name
    return f"{CREDENTIAL_PREFIX}{name}"


def _strip_prefix(target_name: str) -> str:
    """Remove the iaAutomate prefix from a credential name."""
    if target_name.startswith(CREDENTIAL_PREFIX):
        return target_name[len(CREDENTIAL_PREFIX) :]
    return target_name


def get_credential(name: str) -> Optional[Credential]:
    """
    Retrieve a credential from Windows Credential Manager.

    Args:
        name: The credential name (without the iaAutomate: prefix)

    Returns:
        Credential object if found, None otherwise

    Example:
        >>> cred = get_credential("my_service")
        >>> if cred:
        ...     print(f"Username: {cred.username}")
        ...     print(f"Password: {cred.password}")
    """
    target_name = _get_full_target_name(name)
    cred_ptr = ctypes.POINTER(_CREDENTIAL)()

    if not _CredReadW(target_name, CRED_TYPE_GENERIC, 0, ctypes.byref(cred_ptr)):
        return None

    try:
        cred = cred_ptr.contents
        username = cred.UserName or ""

        # Extract password from CredentialBlob
        password = ""
        if cred.CredentialBlobSize > 0 and cred.CredentialBlob:
            blob_bytes = bytes(cred.CredentialBlob[i] for i in range(cred.CredentialBlobSize))
            password = blob_bytes.decode("utf-16-le")

        return Credential(name=_strip_prefix(cred.TargetName), username=username, password=password)
    finally:
        _CredFree(cred_ptr)
