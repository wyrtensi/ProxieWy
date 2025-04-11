import time
import threading
import socket
import socketserver
import select
from urllib.parse import urlparse
import base64 # For HTTP Basic Auth encoding
import urllib.request
import urllib.error
import platform # Needed for windows proxy setting

# Try importing PySocks, but make it optional for now if only HTTP needed initially
try:
    import socks
except ImportError:
    socks = None
    print("[Engine] Warning: PySocks not found. SOCKS5 proxy support will be disabled.")

from PySide6.QtCore import QObject, Signal

# Import the matcher using a relative path
from .rule_matcher import RuleMatcher

# Define default listening port
DEFAULT_LISTENING_PORT = 8080
BUFFER_SIZE = 8192 # Increase buffer size slightly

class HTTPResponseParser:
    def __init__(self, sock):
        self.sock = sock
        self._buffer = b""

    def _read_line(self):
        while b"\r\n" not in self._buffer:
            # Add timeout to socket read to prevent infinite block
            self.sock.settimeout(10.0) # 10 second timeout for reading line
            try:
                data = self.sock.recv(BUFFER_SIZE)
            finally:
                self.sock.settimeout(None) # Reset timeout

            if not data:
                raise EOFError("Socket closed before finding line terminator")
            self._buffer += data
        line, self._buffer = self._buffer.split(b"\r\n", 1)
        return line

    def parse_response(self):
        try:
            # Read status line
            status_line = self._read_line().decode()
            version, status_code, message = status_line.split(" ", 2)
            status_code = int(status_code)

            # Read headers
            headers = {}
            while True:
                line = self._read_line()
                if not line:  # Empty line indicates end of headers
                    break
                # Handle potential ':' missing in header line gracefully
                if b":" in line:
                    key, value = line.decode().split(":", 1)
                    headers[key.strip().lower()] = value.strip()
                else:
                    print(f"[Parser] Warning: Malformed header line skipped: {line}")

            return status_code, message, headers
        except (ValueError, EOFError, socket.timeout) as e:
            print(f"[Parser] Error parsing HTTP response: {e}")
            # Return error indicator instead of raising? Depends on usage.
            # For CONNECT check, raising is okay.
            raise ConnectionRefusedError(f"Failed to parse proxy response: {e}")
        except Exception as e:
             print(f"[Parser] Unexpected error parsing response: {e}")
             raise ConnectionRefusedError(f"Unexpected error parsing proxy response: {e}")

class ProxyRequestHandler(socketserver.BaseRequestHandler):
    """Handles individual client connections accepted by the TCPServer."""

    # Class variables to access engine state (set by the server)
    engine = None

    def handle(self):
        """Processes an incoming client connection."""
        print(f"[Handler {self.client_address}] New connection") # Add address to logs
        target_host = "Unknown" # Initialize for logging
        server_socket = None # Initialize server socket
        is_connect = False # Initialize connect flag

        try:
            # 1. Receive initial data
            # Use select for non-blocking read initially to get headers
            self.request.setblocking(False)
            ready = select.select([self.request], [], [], 5.0) # 5 sec timeout
            if not ready[0]:
                 print(f"[Handler {self.client_address}] No data received from {self.client_address} within timeout.")
                 return
            initial_data = self.request.recv(BUFFER_SIZE)
            if not initial_data:
                 print(f"[Handler {self.client_address}] Client {self.client_address} disconnected immediately.")
                 return
            self.request.setblocking(True) # Set back to blocking for relay
            print(f"[Handler {self.client_address}] Received initial {len(initial_data)} bytes.")

            # 2. Parse target host and port
            target_host, target_port, is_connect, remaining_data = self._parse_request(initial_data)
            if not target_host or not target_port:
                 print(f"[Handler {self.client_address}] Failed to parse target.")
                 self._send_error_response(400, "Bad Request") # Use 400 for bad client request
                 return

            print(f"[Handler {self.client_address}] Target: {target_host}:{target_port}, CONNECT={is_connect}")

            # 3. Match domain against rules
            matched_proxy_id = None
            matched_rule_id = None
            target_proxy_info = None
            # Ensure match is attempted *before* deciding route
            print(f"[Handler {self.client_address}] Attempting rule match for '{target_host}'...")
            matched_proxy_id, matched_rule_id = self.engine.rule_matcher.match(target_host)

            if matched_proxy_id and matched_proxy_id in self.engine._proxies: # Check against engine's proxy list
                target_proxy_info = self.engine._proxies[matched_proxy_id]
                proxy_name = target_proxy_info.get('name', f"ID:{matched_proxy_id[:6]}...")
                print(f"[Handler {self.client_address}] Routing '{target_host}' via proxy '{proxy_name}' (Rule: {matched_rule_id})")
            else:
                # Log even if no match or proxy not found
                if matched_proxy_id:
                    print(f"[Handler {self.client_address}] Rule matched proxy '{matched_proxy_id}' but proxy config not found. Routing directly.")
                else:
                    print(f"[Handler {self.client_address}] No rule matched '{target_host}'. Routing directly.")
                # Route directly if no match or proxy missing
                target_proxy_info = None # Ensure it's None for direct route

            # 4. Establish upstream connection
            connection_start_time = time.time()
            print(f"[Handler {self.client_address}] Attempting upstream connection to {target_host}:{target_port} {'via proxy' if target_proxy_info else 'directly'}...")
            if target_proxy_info:
                 server_socket = self._connect_via_proxy(target_proxy_info, matched_proxy_id, target_host, target_port)
            else:
                 server_socket = self._connect_directly(target_host, target_port)

            connection_time = time.time() - connection_start_time
            print(f"[Handler {self.client_address}] Upstream connection established in {connection_time:.3f}s.")

            # 5. Handle CONNECT method (send 200 OK) or forward initial data
            if is_connect:
                 # Send 200 OK response *immediately* after successful upstream connection
                 print(f"[Handler {self.client_address}] Sending '200 Connection Established' to client.")
                 self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                 print(f"[Handler {self.client_address}] Sent 200 OK.")
                 # Do NOT forward any initial data for CONNECT requests
            else:
                 # Forward the initial data for non-CONNECT requests
                 if remaining_data:
                     print(f"[Handler {self.client_address}] Forwarding initial {len(remaining_data)} bytes to {target_host}")
                     server_socket.sendall(remaining_data)
                 else:
                     print(f"[Handler {self.client_address}] No initial data buffered to forward for non-CONNECT.")

            # 6. Relay data bidirectionally
            print(f"[Handler {self.client_address}] Starting data relay between client and {target_host}")
            self._relay_data(server_socket)
            print(f"[Handler {self.client_address}] Data relay finished.")

        except ConnectionRefusedError as e:
             print(f"[Handler {self.client_address}] Connection Refused for '{target_host}': {e}")
             # Only send error if we haven't established the tunnel yet
             if not is_connect or server_socket is None:
                  self._send_error_response(502, "Connection Refused")
        except socket.timeout:
             print(f"[Handler {self.client_address}] Timeout during connection/relay for '{target_host}'")
             if not is_connect or server_socket is None:
                  self._send_error_response(504, "Gateway Timeout")
        except (NotImplementedError, socks.ProxyConnectionError if socks else None, socks.GeneralProxyError if socks else None) as e:
             proxy_name_err = target_proxy_info.get('name','Unknown Proxy') if target_proxy_info else 'N/A'
             print(f"[Handler {self.client_address}] Proxy Error for '{target_host}' via '{proxy_name_err}': {e}")
             if not is_connect or server_socket is None:
                  self._send_error_response(502, "Bad Gateway (Proxy Error)")
        except socket.gaierror as e: # Catch DNS errors
             print(f"[Handler {self.client_address}] DNS Error for '{target_host}': {e}")
             if not is_connect or server_socket is None:
                  self._send_error_response(502, "Bad Gateway (DNS Error)")
        except Exception as e:
             print(f"[Handler {self.client_address}] Unexpected error handling connection for '{target_host}': {e}", exc_info=True)
             # Send error only if before successful CONNECT response or if not a CONNECT request at all
             if not is_connect or server_socket is None:
                 # Check if socket is still writable before sending error
                 try:
                     # A brief timeout to check writability without blocking forever
                     _, write_ready, _ = select.select([], [self.request], [], 0.1)
                     if write_ready:
                         self._send_error_response(500, "Internal Server Error")
                     else:
                         print(f"[Handler {self.client_address}] Client socket not writable, cannot send error.")
                 except Exception as send_err:
                     print(f"[Handler {self.client_address}] Error trying to send error response: {send_err}")
        finally:
             if server_socket:
                 print(f"[Handler {self.client_address}] Closing upstream socket to {target_host}.")
                 server_socket.close()
             print(f"[Handler {self.client_address}] Closing client connection.")
             # self.request (client socket) is closed by socketserver

    def _parse_request(self, data: bytes):
        """Very basic parsing of HTTP request to find Host or CONNECT target."""
        try:
            lines = data.split(b'\r\n')
            request_line = lines[0].decode('utf-8', errors='ignore')
            parts = request_line.split()
            if len(parts) < 2: return None, None, False, data

            method = parts[0].upper()
            url = parts[1]

            host = None
            port = None
            is_connect = (method == "CONNECT")

            if is_connect:
                # CONNECT target.com:443 HTTP/1.1
                host_port = url.split(':')
                host = host_port[0]
                port = int(host_port[1]) if len(host_port) > 1 else 443 # Default HTTPS port
            else:
                # Look for Host header
                host_header = next((line for line in lines[1:] if line.lower().startswith(b'host:')), None)
                if host_header:
                    host_value = host_header.split(b':', 1)[1].strip().decode('utf-8', errors='ignore')
                    # Check if host header includes port
                    if ':' in host_value:
                         host, port_str = host_value.split(':', 1)
                         port = int(port_str)
                    else:
                         host = host_value
                         # Guess port based on URL scheme if available, else default 80
                         parsed_url = urlparse(url)
                         port = 443 if parsed_url.scheme == 'https' else 80 # Default HTTP/HTTPS ports
                else:
                    # Fallback: Try parsing host from URL (less reliable for proxies)
                    parsed_url = urlparse(url)
                    host = parsed_url.hostname
                    # Corrected ternary expression for port fallback
                    port = parsed_url.port if parsed_url.port else (443 if parsed_url.scheme == 'https' else 80)


            return host, port, is_connect, data # Return original data as remaining for non-CONNECT
        except Exception as e:
            print(f"[Handler] Error parsing request: {e}\nData: {data[:200]}")
            return None, None, False, data


    def _connect_directly(self, host: str, port: int, timeout=10):
        """Establishes a direct TCP connection."""
        try:
            print(f"[Handler] Connecting directly to {host}:{port}...")
            # Use create_connection which handles IPv4/IPv6 and DNS resolution
            s = socket.create_connection((host, port), timeout=timeout)
            print(f"[Handler] Direct connection established to {s.getpeername()}.")
            return s
        except socket.gaierror as e:
             print(f"[Handler] DNS Error connecting directly to {host}: {e}")
             raise # Re-raise to be caught by main handler exception block
        except socket.timeout as e:
            print(f"[Handler] Timeout connecting directly to {host}:{port}")
            raise # Re-raise
        except ConnectionRefusedError as e:
            print(f"[Handler] Connection refused connecting directly to {host}:{port}")
            raise # Re-raise
        except Exception as e:
            print(f"[Handler] Error connecting directly to {host}:{port}: {e}")
            raise # Re-raise

    def _connect_via_proxy(self, proxy_info: dict, proxy_id: str, target_host: str, target_port: int, timeout=15):
        """Establishes a connection through the specified proxy."""
        proxy_type = proxy_info.get('type', 'HTTP').upper()
        proxy_addr = proxy_info.get('address')
        proxy_port = proxy_info.get('port')
        requires_auth = proxy_info.get('requires_auth', False)
        proxy_user = proxy_info.get('username') if requires_auth else None
        proxy_pass = proxy_info.get('password') if requires_auth else None

        if not proxy_addr or not proxy_port:
            print(f"[Handler] Error: Invalid proxy info for ID {proxy_id}")
            return None # Or raise error?

        proxy_name = proxy_info.get('name', f"ID:{proxy_id[:6]}...")
        print(f"[Handler] Connecting via {proxy_type} proxy '{proxy_name}' ({proxy_addr}:{proxy_port}) to {target_host}:{target_port}...")
        s = None
        try:
            if proxy_type in ["HTTP", "HTTPS"]:
                s = socket.create_connection((proxy_addr, proxy_port), timeout=timeout)
                connect_headers = [
                    f"CONNECT {target_host}:{target_port} HTTP/1.1",
                    f"Host: {target_host}:{target_port}",
                    "Proxy-Connection: keep-alive",
                    "Connection: keep-alive"
                ]
                if proxy_user is not None and proxy_pass is not None:
                    auth_str = f"{proxy_user}:{proxy_pass}"
                    auth_b64 = base64.b64encode(auth_str.encode()).decode()
                    connect_headers.append(f"Proxy-Authorization: Basic {auth_b64}")

                connect_request = "\r\n".join(connect_headers) + "\r\n\r\n"
                s.sendall(connect_request.encode())

                # More robust response reading
                response_parser = HTTPResponseParser(s)
                try:
                     status_code, status_msg, headers = response_parser.parse_response()
                     print(f"[Handler] Proxy '{proxy_name}' CONNECT response: {status_code} {status_msg}")
                     # Drain any potential remaining body data from error responses (e.g., HTML page from proxy)
                     # This is crucial if the proxy sends content after the headers for non-200 responses.
                     if status_code != 200:
                          # Check for Content-Length or Transfer-Encoding to drain body
                          content_length = int(headers.get('content-length', 0))
                          if content_length > 0:
                                print(f"[Handler] Draining {content_length} bytes from proxy error response.")
                                received = 0
                                while received < content_length:
                                     chunk = s.recv(min(BUFFER_SIZE, content_length - received))
                                     if not chunk: break
                                     received += len(chunk)
                          elif headers.get('transfer-encoding', '').lower() == 'chunked':
                                print("[Handler] Draining chunked body from proxy error response.")
                                while True: # Read chunks until 0-length chunk
                                    line = response_parser._read_line() # Use parser's internal line reader
                                    chunk_size_hex = line.split(b';', 1)[0]
                                    chunk_size = int(chunk_size_hex, 16)
                                    if chunk_size == 0:
                                         response_parser._read_line() # Read final CRLF
                                         break
                                    # Read chunk data + CRLF
                                    received = 0
                                    while received < chunk_size + 2: # Include CRLF
                                        chunk = s.recv(min(BUFFER_SIZE, chunk_size + 2 - received))
                                        if not chunk: raise EOFError("Socket closed during chunked body read")
                                        received += len(chunk)

                          # Now raise the appropriate error
                          if status_code == 407: raise ConnectionRefusedError(f"Proxy '{proxy_name}' authentication required/failed ({status_code})")
                          else: raise ConnectionRefusedError(f"Proxy '{proxy_name}' refused connection: {status_code} {status_msg}")

                     # If status_code == 200, tunnel is established
                except ConnectionRefusedError: # Re-raise specifically caught errors
                     raise
                except Exception as parse_exc: # Catch errors during parsing/draining
                     raise ConnectionRefusedError(f"Failed reading/parsing proxy response: {parse_exc}")

            elif proxy_type == "SOCKS5":
                if not socks: raise NotImplementedError("SOCKS5 support disabled (PySocks not installed).")
                s = socks.socksocket()
                s.set_proxy(socks.SOCKS5, proxy_addr, proxy_port, username=proxy_user, password=proxy_pass)
                s.settimeout(timeout)
                s.connect((target_host, target_port))

            else:
                raise NotImplementedError(f"Unsupported proxy type: {proxy_type}")

            print(f"[Handler] Connection via proxy '{proxy_name}' established.")
            return s

        # Keep specific exception catching for proxy errors
        except (socks.ProxyConnectionError, socks.GeneralProxyError, ConnectionRefusedError) as e:
            print(f"[Handler] Proxy connection error via '{proxy_name}': {e}")
            if s: s.close()
            raise e
        except Exception as e:
                print(f"[Handler] Error connecting via proxy '{proxy_name}': {e}", exc_info=True) # Add exc_info
                if s: s.close()
                raise e


    def _relay_data(self, server_socket):
        """Relays data between self.request (client) and server_socket (upstream)."""
        client_socket = self.request
        sockets = [client_socket, server_socket]
        client_addr = self.client_address # Cache for logging
        target_peer = server_socket.getpeername() if server_socket else "N/A" # Cache for logging

        while True:
            try:
                # Wait for readiness or error using select
                readable, writable, exceptional = select.select(sockets, [], sockets, 15.0) # Increased timeout slightly

                if exceptional:
                     print(f"[Relay {client_addr} <-> {target_peer}] Exceptional condition on socket.")
                     break # Abort relay

                if not readable:
                     # Timeout: Check if sockets are still valid, otherwise break
                     # Basic check: try a non-blocking recv of 0 bytes
                     try:
                         if client_socket.recv(0, socket.MSG_PEEK) == b'' or server_socket.recv(0, socket.MSG_PEEK) == b'':
                             print(f"[Relay {client_addr} <-> {target_peer}] Socket closed during idle timeout check.")
                             break
                     except BlockingIOError: pass # Expected if socket is alive and idle
                     except Exception as check_err:
                         print(f"[Relay {client_addr} <-> {target_peer}] Error checking socket liveness: {check_err}")
                         break
                     continue # Continue loop if sockets seem okay

                for sock in readable:
                    peer = server_socket if sock is client_socket else client_socket
                    data = sock.recv(BUFFER_SIZE)
                    if not data:
                        # Socket closed by peer
                        peer_desc = 'client' if sock is client_socket else 'server'
                        print(f"[Relay {client_addr} <-> {target_peer}] Peer ({peer_desc}) disconnected.")
                        return # End relay normally

                    # print(f"[Relay {client_addr} -> {'server' if sock is client_socket else 'client'}] Sending {len(data)} bytes") # Very verbose
                    peer.sendall(data)

            except socket.error as e:
                # More specific error handling (e.g., ConnectionResetError)
                print(f"[Relay {client_addr} <-> {target_peer}] Socket error during relay: {e}")
                return # End relay on error
            except Exception as e:
                 print(f"[Relay {client_addr} <-> {target_peer}] Unexpected error during relay: {e}", exc_info=True)
                 return # End relay on error

    def _send_error_response(self, code: int, message: str):
        """Sends a basic HTTP error response to the client."""
        try:
            response = f"HTTP/1.1 {code} {message}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n"
            self.request.sendall(response.encode())
        except socket.error as e:
             print(f"[Handler] Error sending error response to client: {e}")


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Override server_bind to allow address reuse."""
    allow_reuse_address = True
    daemon_threads = True # Ensure handler threads don't block exit

    # Store reference to engine instance
    engine_instance = None


class ProxyEngine(QObject):
    """Handles the core proxying logic and state."""

    # Signals to update UI
    status_changed = Signal(str) # Overall engine status
    error_occurred = Signal(str)
    proxy_test_result = Signal(str, bool) # Emits (proxy_id, is_ok)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_active = False
        self._rules = {}
        self._proxies = {}
        self.rule_matcher = RuleMatcher()
        self._lock = threading.Lock()
        self._tcp_server = None
        self._server_thread = None
        self.listening_port = DEFAULT_LISTENING_PORT
        self.active_profile_id = None

        # --- Network Interception ---
        # The current implementation uses socketserver to create an explicit proxy
        # listener on localhost:listening_port. Clients (e.g., browsers) must be
        # manually configured to use this proxy address (e.g., 127.0.0.1:8080).
        #
        # Implementing transparent proxying (e.g., intercepting all traffic or
        # modifying system-wide settings automatically) requires platform-specific
        # libraries and potentially elevated privileges (e.g., modifying system
        # proxy settings, using packet filtering APIs like nfqueue on Linux,
        # NetworkExtension framework on macOS, WinDivert/WFP on Windows).
        # This is currently outside the scope of this implementation.
        # ---

    @property
    def is_active(self):
        return self._is_active

    def update_config(self, rules: dict, proxies: dict, active_profile_id: str):
        """Updates the rules and proxies used by the engine."""
        self.proxies = proxies
        self.active_profile_id = active_profile_id # Store the profile ID for reference

        # Update internal state used by handlers if needed (assuming handlers access self.engine._proxies etc.)
        # Add lock if these are accessed by handler threads
        with self._lock: # Use the lock defined in __init__
             self._proxies = proxies.copy() # Update internal copy for handlers
             self._rules = rules.copy()     # Update internal copy for handlers

        print(f"[Engine] Updating config. Received {len(rules)} rules and {len(proxies)} proxies for profile '{active_profile_id}'.")
        self.rule_matcher.update_rules(rules) # Pass the original rules dict to the matcher
        print(f"[Engine] Configuration updated. Matcher has {self.rule_matcher.rule_count()} rules.") # <- Ensure no underscore here
        # Optionally, inform the user if the engine needs a restart for certain changes
        # print("[Engine] Note: Restart engine (toggle off/on) might be needed for fundamental changes.")

    def start(self):
        """Starts the proxy engine."""
        if self._is_active: return True
        print("[Engine] Starting...")
        self.status_changed.emit("starting") # Emit 'starting' status
        # Update rule matcher with the *current* internal rules before starting
        with self._lock:
            # Pass the engine's internal copy of rules to the matcher
            self.rule_matcher.update_rules(self._rules) # Ensure matcher uses the locked copy
            if not self._rules: print("[Engine] Warning: Starting with no rules defined.")

        try:
            ProxyRequestHandler.engine = self
            print(f"[Engine] Starting TCP server on port {self.listening_port}...")
            self._tcp_server = ThreadingTCPServer(("", self.listening_port), ProxyRequestHandler)
            self._tcp_server.engine_instance = self # Pass engine reference to server
            self._server_thread = threading.Thread(target=self._tcp_server.serve_forever, daemon=True)
            self._server_thread.start()
            print(f"[Engine] Server thread started.")
            self._is_active = True
            time.sleep(0.2)
            if not self._server_thread.is_alive():
                 raise RuntimeError(f"Server thread failed (Port {self.listening_port} likely in use).")

            self.status_changed.emit("active") # Emit 'active' on success
            print("[Engine] Started successfully.")
            return True
        except Exception as e:
            error_msg = f"Failed to start proxy engine: {e}"
            print(f"[Engine] Error: {error_msg}")
            self.error_occurred.emit(error_msg)
            self.status_changed.emit("error") # Ensure status is error
            self._is_active = False
            if self._tcp_server:
                try: self._tcp_server.server_close()
                except: pass
            self._tcp_server = None
            self._server_thread = None
            return False

    def stop(self):
        """Stops the proxy engine."""
        if not self._is_active or not self._tcp_server:
            if self._is_active: # Ensure state is correct if called when already stopped
                 self._is_active = False
                 self.status_changed.emit("inactive")
            return

        print("[Engine] Stopping...")
        self.status_changed.emit("stopping") # Emit 'stopping' status

        try:
             print("[Engine] Shutting down TCP server...")
             self._tcp_server.shutdown() # Signal serve_forever to stop
             self._tcp_server.server_close() # Close listening socket
             print("[Engine] TCP server shut down.")
        except Exception as e: print(f"[Engine] Error during server shutdown: {e}")

        if self._server_thread and self._server_thread.is_alive():
            print("[Engine] Waiting for server thread...")
            self._server_thread.join(timeout=2)
            if self._server_thread.is_alive(): print("[Engine] Warning: Server thread did not stop.")

        self._tcp_server = None
        self._server_thread = None
        self._is_active = False
        self.status_changed.emit("inactive") # Emit 'inactive' on completion
        print("[Engine] Stopped.")

    def test_proxy(self, proxy_id: str):
        """Tests connectivity through a specific proxy (async)."""
        print(f"[Engine] Requesting test for proxy ID: {proxy_id}")
        # Run the actual test in a separate thread to avoid blocking the UI/Engine
        thread = threading.Thread(target=self._run_proxy_test, args=(proxy_id,), daemon=True)
        thread.start()

    def test_all_proxies(self):
        """Tests connectivity for all configured proxies."""
        print("[Engine] Testing all proxies...")
        with self._lock:
            proxy_ids = list(self._proxies.keys()) # Get IDs under lock
        for proxy_id in proxy_ids:
            self.test_proxy(proxy_id) # Start test for each

    def _run_proxy_test(self, proxy_id: str):
        """The actual test logic performed in a thread."""
        is_ok = False
        error_msg = "Unknown error"
        with self._lock: # Get proxy info under lock
            proxy_info = self._proxies.get(proxy_id)

        if not proxy_info:
            print(f"[Proxy Test {proxy_id}] Error: Proxy info not found.")
            self.proxy_test_result.emit(proxy_id, False)
            return

        proxy_name = proxy_info.get('name', 'Unknown')
        proxy_type = proxy_info.get('type', 'HTTP').upper()
        proxy_addr = proxy_info.get('address')
        proxy_port = proxy_info.get('port')
        requires_auth = proxy_info.get('requires_auth', False)
        proxy_user = proxy_info.get('username') if requires_auth else None
        proxy_pass = proxy_info.get('password') if requires_auth else None

        print(f"[Proxy Test {proxy_id}] Testing '{proxy_name}' ({proxy_type} @ {proxy_addr}:{proxy_port})...")

        # --- Enhanced Test Logic ---
        test_url = "http://httpbin.org/ip"
        timeout = 8

        try:
            handlers = []
            proxy_uri = f"{proxy_addr}:{proxy_port}"

            if proxy_type in ["HTTP", "HTTPS"]:
                # Use http(s)://user:pass@host:port format for urllib handler
                auth_part = ""
                if requires_auth and proxy_user is not None: # Password can be empty
                    auth_str = f"{proxy_user}:{proxy_pass}"
                    # Need to URL-encode user/pass if they contain special chars
                    from urllib.parse import quote
                    auth_part = f"{quote(proxy_user)}:{quote(proxy_pass or '')}@" # Handle empty password

                proxy_full_uri = f"http://{auth_part}{proxy_uri}" # Assume HTTP proxy for test handler
                proxy_handler = urllib.request.ProxyHandler({'http': proxy_full_uri, 'https': proxy_full_uri})
                handlers.append(proxy_handler)

            elif proxy_type == "SOCKS5":
                if not socks:
                    raise NotImplementedError("PySocks not installed, cannot test SOCKS5.")

                # Need to configure socks module globally (or use requests library with socks adapter)
                # This global configuration is messy, ideally use a library like 'requests'
                # that allows per-request proxy settings with SOCKS support.
                # For now, demonstrate basic connection test via socksocket as fallback.

                # --- SOCKS Test using socket directly ---
                s = socks.socksocket()
                s.set_proxy(socks.SOCKS5, proxy_addr, proxy_port, username=proxy_user, password=proxy_pass)
                s.settimeout(timeout)
                # Try connecting to the *test URL's host* through the proxy
                parsed_url = urlparse(test_url)
                target_test_host = parsed_url.hostname
                target_test_port = parsed_url.port or 80 # HTTP port for test URL
                print(f"[Proxy Test {proxy_id}] SOCKS: Attempting connect to {target_test_host}:{target_test_port}...")
                s.connect((target_test_host, target_test_port))
                print(f"[Proxy Test {proxy_id}] SOCKS: Connection successful.")
                s.close()
                is_ok = True
                # Skip the urllib test below for SOCKS for now
                self.proxy_test_result.emit(proxy_id, is_ok)
                print(f"[Proxy Test {proxy_id}] Result: OK")
                return
                # --- End SOCKS Test ---

            else:
                raise NotImplementedError(f"Testing not implemented for proxy type: {proxy_type}")

            # Build opener with proxy handler for HTTP/HTTPS tests
            opener = urllib.request.build_opener(*handlers)
            print(f"[Proxy Test {proxy_id}] Attempting request to {test_url}...")
            # Perform the request
            with opener.open(test_url, timeout=timeout) as response:
                status_code = response.getcode()
                # content = response.read().decode('utf-8', errors='ignore') # Optionally read content
                print(f"[Proxy Test {proxy_id}] Received status code: {status_code}")
                # Consider any 2xx/3xx status as success for basic test
                if 200 <= status_code < 400:
                    is_ok = True
                else:
                    error_msg = f"Received non-success status: {status_code}"

        except urllib.error.URLError as e:
             # Handle specific URLErrors (includes connection errors, timeouts, proxy errors)
             error_msg = f"URLError: {e.reason}"
             print(f"[Proxy Test {proxy_id}] Test failed: {error_msg}")
             is_ok = False
        except (NotImplementedError, socket.timeout, ConnectionRefusedError, OSError, ValueError, socks.ProxyError if socks else None) as e:
            error_msg = str(e)
            print(f"[Proxy Test {proxy_id}] Test failed: {error_msg}")
            is_ok = False
        except Exception as e:
             error_msg = str(e)
             print(f"[Proxy Test {proxy_id}] Unexpected error: {error_msg}")
             is_ok = False
        # --- End Enhanced Test Logic ---

        print(f"[Proxy Test {proxy_id}] Result: {'OK' if is_ok else 'FAIL'} ({error_msg if not is_ok else ''})")
        self.proxy_test_result.emit(proxy_id, is_ok)

    def get_status(self) -> str:
        """Returns the current status."""
        if self._is_active and (not self._server_thread or not self._server_thread.is_alive()):
             print("[Engine] Warning: Server thread died unexpectedly.")
             self.stop()
             self.error_occurred.emit("Listener thread terminated unexpectedly.")
             return "error" # Return error immediately after attempting stop
        return "active" if self._is_active else "inactive" 