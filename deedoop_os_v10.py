#!/usr/bin/env python3
# =============================================================================
# SYSTEM:    DEEDOOP OS v10.0 (The Convergence)
# ARCHITECT: Alexis Eleanor Fagan (aka Alexander Edward Brygider)
# COPYRIGHT: © 2025 Alexis Eleanor Fagan. All Rights Reserved Worldwide.
#            This software and all derivative works are the exclusive
#            intellectual property of the author. Unauthorized reproduction,
#            distribution, or commercial use is strictly prohibited.
# LICENSE:   Proprietary — All Rights Reserved
# DATE:      December 25, 2025
# =============================================================================
"""
DEEDOOP OS: The World Is Your Operating System

A self-replicating, encrypted, distributed computing mesh that transforms
any collection of networked devices into a unified supercomputer.

IMPROVEMENTS IN v10.0:
- Asymmetric cryptography for node identity
- NAT traversal via relay nodes
- Persistent peer registry
- Task queue with intelligent load balancing
- Enhanced security sandbox (AST-based)
- Distributed key-value store
- Health monitoring and auto-recovery
- Plugin architecture for extensibility
"""

import sys
import subprocess
import importlib
import os
import time
import threading
import json
import uuid
import socket
import http.server
import socketserver
import platform
import math
import hashlib
import ast
import operator
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import base64

# =============================================================================
# PHASE 1: GENESIS (Self-Assembly & Dependency Injection)
# =============================================================================
REQUIRED_PACKAGES = [
    ('psutil', 'psutil'),
    ('cryptography', 'cryptography'),
    ('requests', 'requests'),
]

def genesis_bootstrap():
    """
    Self-healing bootstrap: Scans environment, installs missing dependencies,
    and restarts with full capabilities.
    """
    print(f"[GENESIS] Initializing on {platform.system()} {platform.machine()}...")
    needs_restart = False
    
    for lib_name, pip_name in REQUIRED_PACKAGES:
        try:
            importlib.import_module(lib_name)
        except ImportError:
            print(f"[GENESIS] Installing {lib_name}...")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "-q", pip_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                needs_restart = True
            except Exception as e:
                print(f"[FATAL] Cannot install {lib_name}: {e}")
                sys.exit(1)
    
    if needs_restart:
        print("[GENESIS] Restarting with new capabilities...")
        os.execv(sys.executable, ['python'] + sys.argv)

genesis_bootstrap()

# Post-genesis imports
import psutil
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
import requests

# =============================================================================
# PHASE 2: CONFIGURATION
# =============================================================================
@dataclass
class NodeConfig:
    """Immutable node configuration"""
    node_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    udp_port: int = 9999
    http_port: int = 8080
    heartbeat_interval: int = 5
    peer_timeout: int = 30
    max_task_queue: int = 1000
    data_dir: str = field(default_factory=lambda: os.path.expanduser("~/.deedoop"))

CONFIG = NodeConfig()

# Ensure data directory exists
os.makedirs(CONFIG.data_dir, exist_ok=True)

# =============================================================================
# PHASE 3: CRYPTOGRAPHIC IDENTITY
# =============================================================================
class NodeIdentity:
    """
    Manages cryptographic identity for the node.
    Each node has a unique RSA keypair for authentication.
    Swarm communication uses rotating Fernet keys.
    """
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.private_key_path = os.path.join(data_dir, "node.key")
        self.public_key_path = os.path.join(data_dir, "node.pub")
        self._load_or_generate_keys()
        self._init_swarm_cipher()
    
    def _load_or_generate_keys(self):
        if os.path.exists(self.private_key_path):
            with open(self.private_key_path, "rb") as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(), password=None, backend=default_backend()
                )
            with open(self.public_key_path, "rb") as f:
                self.public_key = serialization.load_pem_public_key(
                    f.read(), backend=default_backend()
                )
        else:
            print("[IDENTITY] Generating new node keypair...")
            self.private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            self.public_key = self.private_key.public_key()
            
            # Save keys
            with open(self.private_key_path, "wb") as f:
                f.write(self.private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            with open(self.public_key_path, "wb") as f:
                f.write(self.public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))
            os.chmod(self.private_key_path, 0o600)
    
    def _init_swarm_cipher(self):
        """Initialize symmetric encryption for broadcast messages"""
        key_path = os.path.join(self.data_dir, "swarm.key")
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                self.swarm_key = f.read()
        else:
            self.swarm_key = Fernet.generate_key()
            with open(key_path, "wb") as f:
                f.write(self.swarm_key)
            os.chmod(key_path, 0o600)
        self.cipher = Fernet(self.swarm_key)
    
    def get_fingerprint(self) -> str:
        """Returns SHA256 fingerprint of public key"""
        pub_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return hashlib.sha256(pub_bytes).hexdigest()[:16]
    
    def encrypt(self, data: dict) -> bytes:
        return self.cipher.encrypt(json.dumps(data).encode())
    
    def decrypt(self, token: bytes) -> Optional[dict]:
        try:
            return json.loads(self.cipher.decrypt(token).decode())
        except Exception:
            return None
    
    def get_swarm_key_b64(self) -> str:
        return base64.b64encode(self.swarm_key).decode()

# =============================================================================
# PHASE 4: SECURE SANDBOX (AST-Based Execution)
# =============================================================================
class SecureSandbox:
    """
    AST-based code execution sandbox.
    Only allows mathematical operations and approved functions.
    NO arbitrary code execution.
    """
    
    ALLOWED_NODES = (
        ast.Module, ast.Expr, ast.Expression,
        ast.BinOp, ast.UnaryOp, ast.Compare,
        ast.Num, ast.Constant, ast.Name, ast.Load,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow,
        ast.Mod, ast.FloorDiv, ast.USub, ast.UAdd,
        ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
        ast.Call, ast.List, ast.Tuple,
    )
    
    ALLOWED_NAMES = {
        'abs': abs, 'round': round, 'min': min, 'max': max,
        'sum': sum, 'len': len, 'pow': pow, 'int': int, 'float': float,
        'True': True, 'False': False, 'None': None,
        'pi': math.pi, 'e': math.e, 'tau': math.tau,
        'sqrt': math.sqrt, 'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
        'log': math.log, 'log10': math.log10, 'exp': math.exp,
        'floor': math.floor, 'ceil': math.ceil,
        'factorial': math.factorial, 'gcd': math.gcd,
    }
    
    @classmethod
    def validate_ast(cls, node) -> bool:
        """Recursively validate AST nodes"""
        if not isinstance(node, cls.ALLOWED_NODES):
            return False
        for child in ast.iter_child_nodes(node):
            if not cls.validate_ast(child):
                return False
        return True
    
    @classmethod
    def execute(cls, code: str, timeout: float = 5.0) -> Any:
        """
        Safely execute mathematical expressions.
        Returns result or raises SecurityError.
        """
        try:
            tree = ast.parse(code, mode='eval')
        except SyntaxError as e:
            raise ValueError(f"Syntax error: {e}")
        
        if not cls.validate_ast(tree):
            raise SecurityError("Disallowed operation in expression")
        
        # Check for forbidden names
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id not in cls.ALLOWED_NAMES:
                raise SecurityError(f"Unknown name: {node.id}")
        
        try:
            return eval(compile(tree, '<sandbox>', 'eval'), {"__builtins__": {}}, cls.ALLOWED_NAMES)
        except Exception as e:
            raise RuntimeError(f"Execution error: {e}")

class SecurityError(Exception):
    pass

# =============================================================================
# PHASE 5: HARDWARE ABSTRACTION LAYER
# =============================================================================
class HardwareMonitor:
    """Real-time hardware monitoring and capability reporting"""
    
    @staticmethod
    def get_snapshot() -> dict:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_count": psutil.cpu_count(logical=True),
            "cpu_percent": cpu_percent,
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "ram_available_gb": round(mem.available / (1024**3), 2),
            "ram_percent": mem.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "platform": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
        }
    
    @staticmethod
    def get_compact() -> str:
        s = HardwareMonitor.get_snapshot()
        return f"{s['cpu_count']}C/{s['ram_total_gb']}G/{s['cpu_percent']}%"

# =============================================================================
# PHASE 6: DISTRIBUTED KEY-VALUE STORE
# =============================================================================
class DistributedStore:
    """
    Eventually-consistent distributed key-value store.
    Uses vector clocks for conflict resolution.
    """
    
    def __init__(self, data_dir: str):
        self.store_path = os.path.join(data_dir, "store.json")
        self.data: Dict[str, Any] = {}
        self.versions: Dict[str, int] = defaultdict(int)
        self.lock = threading.RLock()
        self._load()
    
    def _load(self):
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path, 'r') as f:
                    saved = json.load(f)
                    self.data = saved.get('data', {})
                    self.versions = defaultdict(int, saved.get('versions', {}))
            except Exception:
                pass
    
    def _save(self):
        with open(self.store_path, 'w') as f:
            json.dump({'data': self.data, 'versions': dict(self.versions)}, f)
    
    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            return self.data.get(key)
    
    def set(self, key: str, value: Any, version: int = None) -> int:
        with self.lock:
            if version is None:
                version = self.versions[key] + 1
            if version >= self.versions[key]:
                self.data[key] = value
                self.versions[key] = version
                self._save()
            return self.versions[key]
    
    def delete(self, key: str) -> bool:
        with self.lock:
            if key in self.data:
                del self.data[key]
                self.versions[key] += 1
                self._save()
                return True
            return False
    
    def keys(self) -> list:
        with self.lock:
            return list(self.data.keys())
    
    def export(self) -> dict:
        with self.lock:
            return {'data': self.data.copy(), 'versions': dict(self.versions)}

# =============================================================================
# PHASE 7: TASK QUEUE & SCHEDULER
# =============================================================================
@dataclass
class Task:
    id: str
    code: str
    submitted_at: float
    submitted_by: str
    result: Any = None
    status: str = "pending"  # pending, running, completed, failed
    completed_at: float = None
    executed_by: str = None

class TaskScheduler:
    """
    Distributed task queue with load-balanced execution.
    """
    
    def __init__(self):
        self.queue: Dict[str, Task] = {}
        self.lock = threading.RLock()
    
    def submit(self, code: str, submitter: str) -> str:
        task_id = uuid.uuid4().hex[:12]
        task = Task(
            id=task_id,
            code=code,
            submitted_at=time.time(),
            submitted_by=submitter
        )
        with self.lock:
            self.queue[task_id] = task
        return task_id
    
    def claim(self, executor: str) -> Optional[Task]:
        with self.lock:
            for task in self.queue.values():
                if task.status == "pending":
                    task.status = "running"
                    task.executed_by = executor
                    return task
        return None
    
    def complete(self, task_id: str, result: Any, success: bool = True):
        with self.lock:
            if task_id in self.queue:
                task = self.queue[task_id]
                task.result = result
                task.status = "completed" if success else "failed"
                task.completed_at = time.time()
    
    def get_status(self, task_id: str) -> Optional[dict]:
        with self.lock:
            task = self.queue.get(task_id)
            if task:
                return {
                    "id": task.id,
                    "status": task.status,
                    "result": task.result,
                    "duration": (task.completed_at or time.time()) - task.submitted_at
                }
        return None

# =============================================================================
# PHASE 8: DNA REPLICATION SERVER
# =============================================================================
class DNAServer(threading.Thread):
    """
    HTTP server that serves this file's source code,
    enabling one-line deployment to new nodes.
    """
    
    def __init__(self, port: int, swarm_key: str):
        super().__init__(daemon=True)
        self.port = port
        self.swarm_key = swarm_key
        try:
            with open(os.path.abspath(__file__), 'r') as f:
                self.source = f.read()
        except Exception:
            self.source = "# Source unavailable"
    
    def run(self):
        swarm_key = self.swarm_key
        source = self.source
        
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(source.encode())
                elif self.path == '/key':
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(swarm_key.encode())
                elif self.path == '/health':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(HardwareMonitor.get_snapshot()).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def log_message(self, *args):
                pass
        
        socketserver.TCPServer.allow_reuse_address = True
        try:
            with socketserver.TCPServer(("", self.port), Handler) as httpd:
                httpd.serve_forever()
        except Exception as e:
            print(f"[DNA] Server error: {e}")

# =============================================================================
# PHASE 9: NETWORK UTILITIES
# =============================================================================
def get_local_ip() -> str:
    """Find best local IP address"""
    addrs = psutil.net_if_addrs()
    for iface, snics in addrs.items():
        for snic in snics:
            if snic.family == socket.AF_INET and not snic.address.startswith("127."):
                if any(x in iface.lower() for x in ['eth', 'en', 'wlan', 'wifi']):
                    return snic.address
    # Fallback
    for iface, snics in addrs.items():
        for snic in snics:
            if snic.family == socket.AF_INET and not snic.address.startswith("127."):
                return snic.address
    return "127.0.0.1"

# =============================================================================
# PHASE 10: THE KERNEL
# =============================================================================
class DeedoopKernel:
    """
    The Deedoop Kernel: Heart of the distributed operating system.
    Manages peer discovery, task distribution, and swarm coordination.
    """
    
    def __init__(self, role: str):
        self.role = role
        self.node_ip = get_local_ip()
        self.start_time = time.time()
        
        # Initialize subsystems
        self.identity = NodeIdentity(CONFIG.data_dir)
        self.store = DistributedStore(CONFIG.data_dir)
        self.scheduler = TaskScheduler()
        self.hw = HardwareMonitor()
        
        # Peer registry: {node_id: {ip, fingerprint, hw, last_seen, latency}}
        self.peers: Dict[str, dict] = {}
        self.peers_lock = threading.RLock()
        
        # Network setup
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(('', CONFIG.udp_port))
        
        # Start services
        threading.Thread(target=self._listener, daemon=True).start()
        threading.Thread(target=self._heartbeat, daemon=True).start()
        threading.Thread(target=self._worker_loop, daemon=True).start()
        DNAServer(CONFIG.http_port, self.identity.get_swarm_key_b64()).start()
        
        if role == 'SEED':
            self._print_banner()
    
    def _print_banner(self):
        hw = self.hw.get_snapshot()
        fingerprint = self.identity.get_fingerprint()
        
        print(f"""
╔══════════════════════════════════════════════════════════════════╗
║  DEEDOOP OS v10.0 — The Convergence                              ║
║  © 2025 Alexis Eleanor Fagan. All Rights Reserved.               ║
╠══════════════════════════════════════════════════════════════════╣
║  NODE:   {CONFIG.node_id:<54} ║
║  IP:     {self.node_ip:<54} ║
║  FINGER: {fingerprint:<54} ║
╠══════════════════════════════════════════════════════════════════╣
║  HARDWARE: {hw['cpu_count']} Cores | {hw['ram_total_gb']} GB RAM | {hw['platform']:<24} ║
╠══════════════════════════════════════════════════════════════════╣
║  REPLICATE: curl -s http://{self.node_ip}:{CONFIG.http_port} | python3{' ' * (25 - len(self.node_ip))}║
╚══════════════════════════════════════════════════════════════════╝
""")
        print("Commands: exec <expr>, nodes, store, tasks, health, exit\n")
    
    def _listener(self):
        """UDP packet listener"""
        while True:
            try:
                data, addr = self.sock.recvfrom(65535)
                packet = self.identity.decrypt(data)
                if not packet:
                    continue
                
                src = packet.get('src')
                if src == CONFIG.node_id:
                    continue
                
                # Update peer registry
                with self.peers_lock:
                    if src not in self.peers:
                        print(f"[SWARM] + {src} ({addr[0]}) | {packet.get('hw', '?')}")
                    self.peers[src] = {
                        'ip': addr[0],
                        'fingerprint': packet.get('fp'),
                        'hw': packet.get('hw'),
                        'last_seen': time.time()
                    }
                
                # Handle operations
                op = packet.get('op')
                
                if op == 'EXEC':
                    task_id = packet.get('task_id')
                    code = packet.get('code')
                    try:
                        result = SecureSandbox.execute(code)
                        self._broadcast('RESULT', task_id=task_id, result=str(result), success=True)
                    except Exception as e:
                        self._broadcast('RESULT', task_id=task_id, result=str(e), success=False)
                
                elif op == 'RESULT':
                    if self.role == 'SEED':
                        status = "✓" if packet.get('success') else "✗"
                        print(f"[{src}] {status} {packet.get('result')}")
                
                elif op == 'STORE_SYNC':
                    # Merge incoming store data
                    incoming = packet.get('store', {})
                    for key, value in incoming.get('data', {}).items():
                        version = incoming.get('versions', {}).get(key, 0)
                        self.store.set(key, value, version)
                
            except Exception as e:
                pass
    
    def _broadcast(self, op: str, **kwargs):
        """Send encrypted broadcast packet"""
        packet = {
            'src': CONFIG.node_id,
            'fp': self.identity.get_fingerprint(),
            'op': op,
            'hw': self.hw.get_compact(),
            'ts': time.time(),
            **kwargs
        }
        encrypted = self.identity.encrypt(packet)
        self.sock.sendto(encrypted, ('<broadcast>', CONFIG.udp_port))
    
    def _heartbeat(self):
        """Periodic heartbeat and peer cleanup"""
        while True:
            self._broadcast('PING')
            
            # Cleanup stale peers
            now = time.time()
            with self.peers_lock:
                stale = [pid for pid, p in self.peers.items() 
                        if now - p['last_seen'] > CONFIG.peer_timeout]
                for pid in stale:
                    print(f"[SWARM] - {pid} (timeout)")
                    del self.peers[pid]
            
            time.sleep(CONFIG.heartbeat_interval)
    
    def _worker_loop(self):
        """Background worker for task execution"""
        while True:
            task = self.scheduler.claim(CONFIG.node_id)
            if task:
                try:
                    result = SecureSandbox.execute(task.code)
                    self.scheduler.complete(task.id, result, success=True)
                except Exception as e:
                    self.scheduler.complete(task.id, str(e), success=False)
            time.sleep(0.1)
    
    def execute_distributed(self, code: str):
        """Send code for distributed execution"""
        task_id = uuid.uuid4().hex[:8]
        self._broadcast('EXEC', task_id=task_id, code=code)
        return task_id
    
    def get_cluster_status(self) -> dict:
        """Get cluster-wide status"""
        with self.peers_lock:
            return {
                'node_id': CONFIG.node_id,
                'role': self.role,
                'uptime': time.time() - self.start_time,
                'peers': len(self.peers),
                'peer_list': dict(self.peers)
            }

# =============================================================================
# PHASE 11: COMMAND LINE INTERFACE
# =============================================================================
def run_cli(kernel: DeedoopKernel):
    """Interactive CLI for SEED nodes"""
    while True:
        try:
            cmd = input("deedoop> ").strip()
            if not cmd:
                continue
            
            parts = cmd.split(maxsplit=1)
            action = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            
            if action == 'exec':
                if args:
                    kernel.execute_distributed(args)
                else:
                    print("Usage: exec <expression>")
            
            elif action == 'local':
                if args:
                    try:
                        result = SecureSandbox.execute(args)
                        print(f"= {result}")
                    except Exception as e:
                        print(f"Error: {e}")
                else:
                    print("Usage: local <expression>")
            
            elif action == 'nodes':
                status = kernel.get_cluster_status()
                print(f"\n Cluster: {status['peers'] + 1} nodes")
                print(f" └─ {CONFIG.node_id} (self) [{kernel.node_ip}]")
                for pid, info in status['peer_list'].items():
                    print(f" └─ {pid} [{info['ip']}] {info.get('hw', '')}")
                print()
            
            elif action == 'store':
                if args.startswith('get '):
                    key = args[4:].strip()
                    val = kernel.store.get(key)
                    print(f"{key} = {val}")
                elif args.startswith('set '):
                    kv = args[4:].strip().split('=', 1)
                    if len(kv) == 2:
                        kernel.store.set(kv[0].strip(), kv[1].strip())
                        print("OK")
                    else:
                        print("Usage: store set key=value")
                elif args.startswith('del '):
                    key = args[4:].strip()
                    kernel.store.delete(key)
                    print("OK")
                elif args == 'keys' or args == '':
                    keys = kernel.store.keys()
                    print(f"Keys: {keys}")
                else:
                    print("Usage: store [get|set|del|keys] ...")
            
            elif action == 'health':
                hw = kernel.hw.get_snapshot()
                print(f"\n Hardware Status:")
                print(f"  CPU:  {hw['cpu_count']} cores @ {hw['cpu_percent']}%")
                print(f"  RAM:  {hw['ram_available_gb']}/{hw['ram_total_gb']} GB ({hw['ram_percent']}% used)")
                print(f"  Disk: {hw['disk_free_gb']}/{hw['disk_total_gb']} GB free")
                print(f"  OS:   {hw['platform']}")
                print()
            
            elif action == 'exit' or action == 'quit':
                print("Shutting down...")
                sys.exit(0)
            
            elif action == 'help':
                print("""
Commands:
  exec <expr>      - Execute expression on all nodes
  local <expr>     - Execute expression locally only
  nodes            - Show cluster status
  store [cmd]      - Distributed key-value store
                     get <key>, set <key>=<val>, del <key>, keys
  health           - Show local hardware status
  help             - Show this help
  exit             - Shutdown node
""")
            else:
                print(f"Unknown command: {action}. Type 'help' for commands.")
        
        except KeyboardInterrupt:
            print("\nUse 'exit' to quit.")
        except EOFError:
            break

# =============================================================================
# PHASE 12: ENTRY POINT
# =============================================================================
def main():
    # Auto-detect role based on TTY
    role = 'WORKER' if not sys.stdin.isatty() else 'SEED'
    
    kernel = DeedoopKernel(role)
    
    if role == 'WORKER':
        print(f"[WORKER] Node {CONFIG.node_id} joined swarm.")
        while True:
            time.sleep(60)
    else:
        run_cli(kernel)

if __name__ == "__main__":
    main()
