"""Kernel task leases and bounded public URL original acquisition.

URL connections are pinned to validated DNS results, including every redirect.
The downloader has no proxy or automatic redirect behavior and never logs URLs.
"""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import os
from pathlib import Path
import queue
import socket
import threading
import time
from urllib.parse import urljoin, urlsplit

from filelock import FileLock


def task_lock(store_path, task_id):
    directory = Path(store_path).parent / '.ingest-task-locks'
    directory.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha256(task_id.encode('utf-8')).hexdigest() + '.lock'
    # Scheduling occurs on the event loop; execution occurs in a worker thread.
    return FileLock(str(directory / name), thread_local=False)


def _resolve(host, port, timeout):
    # getaddrinfo has no platform timeout; do not let it hold an ingest worker.
    results = queue.Queue(maxsize=1)
    def lookup():
        try:
            results.put(socket.getaddrinfo(host, port, type=socket.SOCK_STREAM))
        except Exception:
            results.put(None)
    threading.Thread(target=lookup, daemon=True).start()
    value = results.get(timeout=timeout)
    if not value:
        raise ValueError('source_download_failed')
    return list(dict.fromkeys(row[4][0] for row in value))


def materialize_original(url, target, *, max_bytes, timeout=60, max_redirects=5,
                         address_allowed=None):
    """Write a new task-local original, or remove only our incomplete creation.

    address_allowed is an explicit callable for local synthetic origin tests;
    application callers always use the public-address policy below.
    """
    deadline = time.monotonic() + timeout
    target = Path(target)
    created = False
    connection = None
    sockets = []
    socket_guard = threading.Lock()
    expired = False

    def abort_socket(sock):
        # close alone does not interrupt a file object's blocking read on Windows.
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()

    def expire():
        nonlocal expired
        with socket_guard:
            expired = True
            active = tuple(sockets)
        for sock in active:
            abort_socket(sock)

    def retain(sock):
        with socket_guard:
            timed_out = expired
            if not timed_out:
                sockets.append(sock)
        if timed_out:
            abort_socket(sock)
            raise TimeoutError()
        return sock

    def remaining():
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError()
        return min(left, 10)
    # A socket inactivity timeout cannot bound a peer that continuously drips
    # headers or TLS records. This independent deadline interrupts every socket
    # retained across redirects, including the TLS socket before its handshake.
    watchdog = threading.Timer(max(0, deadline - time.monotonic()), expire)
    watchdog.name = 'ingest-deadline-watchdog'
    watchdog.daemon = True
    watchdog.start()
    try:
        for hop in range(max_redirects + 1):
            parsed = urlsplit(url)
            if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or any(ord(char) < 32 or ord(char) == 127 for char in url)):
                raise ValueError()
            host = parsed.hostname.encode('idna').decode('ascii')
            port = parsed.port or (443 if parsed.scheme == 'https' else 80)
            addresses = _resolve(host, port, remaining())
            for address in addresses:
                ip = ipaddress.ip_address(address)
                if not (address_allowed(ip) if address_allowed is not None
                        else ip.is_global and not ip.is_multicast and not ip.is_reserved):
                    raise ValueError()
            ip = addresses[0]
            cls = http.client.HTTPSConnection if parsed.scheme == 'https' else http.client.HTTPConnection
            connection = cls(host, port, timeout=remaining())
            # Keep the hostname for Host and TLS SNI/certificate verification;
            # connect directly to the validated address without a second lookup.
            connection._create_connection = lambda address, timeout, source_address=None: retain(
                socket.create_connection((ip, port), timeout, source_address))
            if parsed.scheme == 'https':
                def connect_https():
                    http.client.HTTPConnection.connect(connection)
                    connection.sock = retain(connection._context.wrap_socket(
                        connection.sock, server_hostname=host, do_handshake_on_connect=False))
                    connection.sock.settimeout(remaining())
                    connection.sock.do_handshake()
                connection.connect = connect_https
            path = parsed.path or '/'
            if parsed.query:
                path += '?' + parsed.query
            connection.request('GET', path, headers={'Accept-Encoding':'identity', 'Connection':'close'})
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader('Location')
                if not location or hop == max_redirects:
                    raise ValueError()
                url = urljoin(url, location)
                connection.close()
                connection = None
                continue
            if response.status != 200 or response.getheader('Content-Encoding', 'identity').lower() != 'identity':
                raise ValueError()
            declared = response.getheader('Content-Length')
            if declared is not None and (int(declared) < 0 or int(declared) > max_bytes):
                raise ValueError()
            count = 0
            with target.open('xb') as output:
                created = True
                while True:
                    response_socket = connection.sock or getattr(getattr(response.fp, 'raw', None), '_sock', None)
                    if response_socket is not None:
                        response_socket.settimeout(remaining())
                    block = response.read1(min(65536, max_bytes - count + 1))
                    remaining()
                    if not block:
                        break
                    count += len(block)
                    if count > max_bytes:
                        raise ValueError()
                    output.write(block)
                if declared is not None and count != int(declared):
                    raise ValueError()
                output.flush()
                os.fsync(output.fileno())
            remaining()
            return str(target), count
        raise ValueError()
    except FileExistsError:
        raise
    except Exception:
        if created:
            target.unlink(missing_ok=True)
        # No credential-bearing URL or transport exception reaches task/logs.
        raise ValueError('source_download_failed') from None
    finally:
        watchdog.cancel()
        watchdog.join()
        if connection is not None:
            connection.close()
        for sock in sockets:
            sock.close()
