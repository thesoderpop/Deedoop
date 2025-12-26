#!/usr/bin/env python3
# =============================================================================
# SYSTEM:    DEEDOOP OS v13.0 (The Hydra)
# ARCHITECT: Alexis Eleanor Fagan (aka Alexander Edward Brygider)
# COPYRIGHT: © 2025 Alexis Eleanor Fagan. All Rights Reserved Worldwide.
# LICENSE:   Proprietary — All Rights Reserved
# DATE:      December 25, 2025
# =============================================================================
# THE HYDRA: A streaming capability-based quine operating system.
# DNA is not one file, but a stream of self-describing capabilities.
# Each capability is its own quine fragment that can be:
#   - Streamed on-demand
#   - Hot-swapped at runtime
#   - Shared across the mesh
#   - Evolved independently
# =============================================================================
"""
DEEDOOP OS v13.0 — THE HYDRA

Architecture:
                         ┌─────────────────────────────────┐
                         │      CAPABILITY STREAM          │
                         │  ┌─────┐ ┌─────┐ ┌─────┐       │
                         │  │ CAP │→│ CAP │→│ CAP │→ ...  │
                         │  └─────┘ └─────┘ └─────┘       │
                         └────────────────┬────────────────┘
                                          │
    ┌─────────────────────────────────────┼─────────────────────────────────────┐
    │                          CAPABILITY RUNTIME                                │
    │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
    │  │   LOADER   │  │  REGISTRY  │  │  RESOLVER  │  │   CACHE    │           │
    │  │ (bootstrap)│  │ (manifest) │  │   (deps)   │  │  (loaded)  │           │
    │  └────────────┘  └────────────┘  └────────────┘  └────────────┘           │
    └───────────────────────────────────────────────────────────────────────────┘
                                          │
          ┌───────────────┬───────────────┼───────────────┬───────────────┐
          ▼               ▼               ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
    │  CORE    │   │ COMPUTE  │   │ STORAGE  │   │ NETWORK  │   │  QUINE   │
    │ crypto   │   │ docker   │   │ kv-store │   │ p2p-mesh │   │ self-ref │
    │ identity │   │ tensorflow│  │ chunked  │   │ discovery│   │ mutate   │
    │ config   │   │ blender  │   │ artifact │   │ broadcast│   │ evolve   │
    └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘

Each box is a CAPABILITY — a self-describing quine fragment that:
  1. Carries its own compressed source
  2. Declares its dependencies
  3. Can be streamed on-demand
  4. Can be hot-swapped at runtime
  5. Verifies itself via hash
"""

import sys,os,time,threading,json,uuid,socket,http.server,socketserver
import platform,hashlib,base64,zlib,importlib,subprocess,queue
from dataclasses import dataclass,field,asdict
from typing import Dict,List,Any,Optional,Set,Callable,Tuple
from collections import defaultdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import struct,io,gzip,tempfile,shutil

# =============================================================================
# PHASE 1: MINIMAL BOOTSTRAP (This is the only "fixed" code)
# =============================================================================
# The bootstrap is intentionally minimal. Everything else streams as capabilities.

def _ensure_deps():
    """Minimal dependency bootstrap"""
    for lib,pip in[('psutil','psutil'),('cryptography','cryptography'),('requests','requests')]:
        try:importlib.import_module(lib)
        except ImportError:
            subprocess.check_call([sys.executable,"-m","pip","install","-q",pip],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            os.execv(sys.executable,['python']+sys.argv)

_ensure_deps()

import psutil
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.backends import default_backend

# =============================================================================
# PHASE 2: CAPABILITY PRIMITIVES
# =============================================================================

class CapabilityType(Enum):
    """Types of capabilities in the streaming genome"""
    CORE = "core"           # Essential: crypto, identity, config
    COMPUTE = "compute"     # Workloads: docker, tensorflow, blender
    STORAGE = "storage"     # Data: kv-store, artifacts, chunked transfer
    NETWORK = "network"     # Mesh: p2p, discovery, broadcast
    QUINE = "quine"         # Self-reference: genome, mutate, evolve
    EXECUTOR = "executor"   # Job execution: python, script, container
    PLUGIN = "plugin"       # User-defined extensions

class CapabilityState(Enum):
    """Lifecycle states of a capability"""
    DECLARED = "declared"   # Known to exist
    RESOLVING = "resolving" # Dependencies being resolved
    STREAMING = "streaming" # Being downloaded
    LOADED = "loaded"       # In memory, not activated
    ACTIVE = "active"       # Running
    SUSPENDED = "suspended" # Temporarily disabled
    FAILED = "failed"       # Error state

@dataclass
class CapabilityManifest:
    """
    Manifest describing a capability.
    This is the "DNA fragment header" for each capability.
    """
    id: str                           # Unique identifier
    name: str                         # Human-readable name
    version: str                      # Semantic version
    type: CapabilityType              # Category
    description: str                  # What it does
    dependencies: List[str]           # Required capability IDs
    provides: List[str]               # What it provides (for resolution)
    author: str = "Alexis Eleanor Fagan"
    
    # Code
    genome: str = ""                  # Compressed source code
    genome_hash: str = ""             # SHA256 of uncompressed source
    genome_size: int = 0              # Uncompressed size
    
    # Metadata
    created: float = field(default_factory=time.time)
    priority: int = 0                 # Load order priority (lower = earlier)
    hot_swappable: bool = True        # Can be replaced at runtime
    
    # Runtime
    entry_point: str = ""             # Function to call on activation
    exports: List[str] = field(default_factory=list)  # Exported symbols
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d['type'] = self.type.value
        return d
    
    @classmethod
    def from_dict(cls, d: dict) -> 'CapabilityManifest':
        d['type'] = CapabilityType(d['type'])
        return cls(**d)

@dataclass
class Capability:
    """
    A loaded capability — a living quine fragment.
    """
    manifest: CapabilityManifest
    state: CapabilityState = CapabilityState.DECLARED
    source: str = ""                  # Decompressed source
    namespace: Dict[str, Any] = field(default_factory=dict)  # Execution namespace
    error: str = ""
    loaded_at: float = 0
    activated_at: float = 0
    
    @property
    def id(self) -> str:
        return self.manifest.id
    
    @property
    def type(self) -> CapabilityType:
        return self.manifest.type

# =============================================================================
# PHASE 3: CAPABILITY CODEC (Compress/Decompress Quine Fragments)
# =============================================================================

class CapabilityCodec:
    """Encode/decode capability quine fragments"""
    
    @staticmethod
    def compress(source: str) -> Tuple[str, str, int]:
        """Compress source to genome, return (genome, hash, original_size)"""
        data = source.encode('utf-8')
        compressed = zlib.compress(data, level=9)
        genome = base64.b64encode(compressed).decode('ascii')
        genome_hash = hashlib.sha256(data).hexdigest()[:16]
        return genome, genome_hash, len(data)
    
    @staticmethod
    def decompress(genome: str) -> str:
        """Decompress genome back to source"""
        try:
            data = base64.b64decode(genome.encode('ascii'))
            return zlib.decompress(data).decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to decompress genome: {e}")
    
    @staticmethod
    def verify(genome: str, expected_hash: str) -> bool:
        """Verify genome matches expected hash"""
        try:
            source = CapabilityCodec.decompress(genome)
            actual_hash = hashlib.sha256(source.encode()).hexdigest()[:16]
            return actual_hash == expected_hash
        except:
            return False
    
    @staticmethod
    def create_manifest(id: str, name: str, type: CapabilityType, source: str,
                       dependencies: List[str] = None, provides: List[str] = None,
                       entry_point: str = "", exports: List[str] = None,
                       description: str = "", priority: int = 50) -> CapabilityManifest:
        """Create a capability manifest from source code"""
        genome, genome_hash, genome_size = CapabilityCodec.compress(source)
        return CapabilityManifest(
            id=id,
            name=name,
            version="1.0.0",
            type=type,
            description=description or f"{name} capability",
            dependencies=dependencies or [],
            provides=provides or [id],
            genome=genome,
            genome_hash=genome_hash,
            genome_size=genome_size,
            priority=priority,
            entry_point=entry_point,
            exports=exports or []
        )

# =============================================================================
# PHASE 4: CAPABILITY STREAM
# =============================================================================

class CapabilityStream:
    """
    A stream of capabilities — the living DNA.
    Capabilities flow through this stream to be loaded and activated.
    """
    
    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._subscribers: List[Callable[[CapabilityManifest], None]] = []
        self._lock = threading.RLock()
        self._running = True
        self._thread = threading.Thread(target=self._process_stream, daemon=True)
        self._thread.start()
    
    def publish(self, manifest: CapabilityManifest):
        """Publish a capability to the stream"""
        self._queue.put(manifest)
    
    def subscribe(self, callback: Callable[[CapabilityManifest], None]):
        """Subscribe to capability events"""
        with self._lock:
            self._subscribers.append(callback)
    
    def _process_stream(self):
        """Process incoming capabilities"""
        while self._running:
            try:
                manifest = self._queue.get(timeout=1)
                with self._lock:
                    for callback in self._subscribers:
                        try:
                            callback(manifest)
                        except Exception as e:
                            print(f"[STREAM] Subscriber error: {e}")
            except queue.Empty:
                pass
    
    def stop(self):
        self._running = False

# =============================================================================
# PHASE 5: CAPABILITY REGISTRY
# =============================================================================

class CapabilityRegistry:
    """
    Registry of all known capabilities.
    This is the "genome database" — the complete set of available DNA fragments.
    """
    
    def __init__(self):
        self._manifests: Dict[str, CapabilityManifest] = {}
        self._by_type: Dict[CapabilityType, List[str]] = defaultdict(list)
        self._provides: Dict[str, str] = {}  # provided -> capability_id
        self._lock = threading.RLock()
    
    def register(self, manifest: CapabilityManifest) -> bool:
        """Register a capability manifest"""
        with self._lock:
            if manifest.id in self._manifests:
                existing = self._manifests[manifest.id]
                if existing.genome_hash == manifest.genome_hash:
                    return False  # Already registered, same version
            
            self._manifests[manifest.id] = manifest
            self._by_type[manifest.type].append(manifest.id)
            
            for provided in manifest.provides:
                self._provides[provided] = manifest.id
            
            return True
    
    def get(self, id: str) -> Optional[CapabilityManifest]:
        """Get a capability manifest by ID"""
        return self._manifests.get(id)
    
    def find_provider(self, requirement: str) -> Optional[str]:
        """Find capability that provides a requirement"""
        return self._provides.get(requirement)
    
    def list_by_type(self, type: CapabilityType) -> List[CapabilityManifest]:
        """List all capabilities of a type"""
        with self._lock:
            return [self._manifests[id] for id in self._by_type.get(type, [])]
    
    def all(self) -> List[CapabilityManifest]:
        """Get all registered manifests"""
        with self._lock:
            return list(self._manifests.values())
    
    def export(self) -> List[dict]:
        """Export all manifests for transmission"""
        return [m.to_dict() for m in self.all()]

# =============================================================================
# PHASE 6: CAPABILITY RESOLVER (Dependency Resolution)
# =============================================================================

class CapabilityResolver:
    """
    Resolves capability dependencies.
    Builds a DAG of capabilities and determines load order.
    """
    
    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry
    
    def resolve(self, capability_id: str) -> List[str]:
        """
        Resolve all dependencies for a capability.
        Returns list of capability IDs in load order.
        """
        result = []
        visited = set()
        
        def visit(id: str):
            if id in visited:
                return
            visited.add(id)
            
            manifest = self.registry.get(id)
            if not manifest:
                # Try to find a provider
                provider = self.registry.find_provider(id)
                if provider:
                    manifest = self.registry.get(provider)
                    id = provider
            
            if not manifest:
                raise ValueError(f"Cannot resolve capability: {id}")
            
            # Visit dependencies first
            for dep in manifest.dependencies:
                visit(dep)
            
            result.append(id)
        
        visit(capability_id)
        return result
    
    def resolve_all(self, capability_ids: List[str]) -> List[str]:
        """Resolve multiple capabilities, returning unified load order"""
        all_deps = []
        seen = set()
        
        for id in capability_ids:
            for dep in self.resolve(id):
                if dep not in seen:
                    seen.add(dep)
                    all_deps.append(dep)
        
        return all_deps

# =============================================================================
# PHASE 7: CAPABILITY LOADER (The Heart of the Hydra)
# =============================================================================

class CapabilityLoader:
    """
    Loads and activates capabilities.
    This is the "gene expression" system — turning DNA into living code.
    """
    
    def __init__(self, registry: CapabilityRegistry, stream: CapabilityStream):
        self.registry = registry
        self.stream = stream
        self.resolver = CapabilityResolver(registry)
        
        self._loaded: Dict[str, Capability] = {}
        self._active: Dict[str, Capability] = {}
        self._lock = threading.RLock()
        
        # Subscribe to stream
        stream.subscribe(self._on_capability_received)
        
        # Shared namespace for inter-capability communication
        self._shared_namespace: Dict[str, Any] = {
            '__builtins__': __builtins__,
            'HYDRA': self,  # Self-reference
        }
    
    def _on_capability_received(self, manifest: CapabilityManifest):
        """Handle incoming capability from stream"""
        if self.registry.register(manifest):
            print(f"[HYDRA] Received capability: {manifest.name} ({manifest.id})")
    
    def load(self, capability_id: str) -> Capability:
        """Load a capability (decompress and prepare)"""
        with self._lock:
            if capability_id in self._loaded:
                return self._loaded[capability_id]
            
            manifest = self.registry.get(capability_id)
            if not manifest:
                raise ValueError(f"Unknown capability: {capability_id}")
            
            # Verify integrity
            if not CapabilityCodec.verify(manifest.genome, manifest.genome_hash):
                raise ValueError(f"Genome integrity check failed: {capability_id}")
            
            # Decompress
            source = CapabilityCodec.decompress(manifest.genome)
            
            capability = Capability(
                manifest=manifest,
                state=CapabilityState.LOADED,
                source=source,
                loaded_at=time.time()
            )
            
            self._loaded[capability_id] = capability
            return capability
    
    def activate(self, capability_id: str) -> Capability:
        """Activate a capability (execute its code)"""
        with self._lock:
            if capability_id in self._active:
                return self._active[capability_id]
            
            # Resolve and load dependencies first
            load_order = self.resolver.resolve(capability_id)
            
            for dep_id in load_order:
                if dep_id not in self._active:
                    cap = self.load(dep_id)
                    self._activate_single(cap)
            
            return self._active[capability_id]
    
    def _activate_single(self, capability: Capability):
        """Activate a single capability"""
        try:
            # Create isolated namespace with access to shared symbols
            namespace = {
                **self._shared_namespace,
                '__capability_id__': capability.id,
                '__capability_manifest__': capability.manifest,
            }
            
            # Execute the capability code
            exec(capability.source, namespace)
            
            # Store namespace
            capability.namespace = namespace
            capability.state = CapabilityState.ACTIVE
            capability.activated_at = time.time()
            
            # Export symbols to shared namespace
            for export in capability.manifest.exports:
                if export in namespace:
                    self._shared_namespace[export] = namespace[export]
            
            # Call entry point if defined
            if capability.manifest.entry_point:
                entry = namespace.get(capability.manifest.entry_point)
                if callable(entry):
                    entry()
            
            self._active[capability.id] = capability
            
        except Exception as e:
            capability.state = CapabilityState.FAILED
            capability.error = str(e)
            raise
    
    def deactivate(self, capability_id: str):
        """Deactivate a capability"""
        with self._lock:
            if capability_id in self._active:
                cap = self._active[capability_id]
                
                # Call cleanup if defined
                cleanup = cap.namespace.get('__cleanup__')
                if callable(cleanup):
                    try:
                        cleanup()
                    except:
                        pass
                
                cap.state = CapabilityState.SUSPENDED
                del self._active[capability_id]
    
    def hot_swap(self, new_manifest: CapabilityManifest) -> bool:
        """Hot-swap a capability with a new version"""
        old_cap = self._active.get(new_manifest.id)
        
        if old_cap and not old_cap.manifest.hot_swappable:
            return False
        
        # Deactivate old version
        if old_cap:
            self.deactivate(new_manifest.id)
            del self._loaded[new_manifest.id]
        
        # Register and activate new version
        self.registry.register(new_manifest)
        self.activate(new_manifest.id)
        
        return True
    
    def get_symbol(self, name: str) -> Any:
        """Get a symbol from the shared namespace"""
        return self._shared_namespace.get(name)
    
    def set_symbol(self, name: str, value: Any):
        """Set a symbol in the shared namespace"""
        self._shared_namespace[name] = value
    
    def list_active(self) -> List[Capability]:
        """List all active capabilities"""
        return list(self._active.values())

# =============================================================================
# PHASE 8: BUILT-IN CAPABILITIES (The Core Genome)
# =============================================================================

# Each capability is defined as source code that will be compressed and streamed.

CAP_CORE_IDENTITY = '''
# =============================================================================
# CAPABILITY: core.identity
# Provides: RSA keypairs, node fingerprinting, swarm encryption
# =============================================================================
import os
import hashlib
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

class NodeIdentity:
    def __init__(self, data_dir):
        self.dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._load_keys()
        self._init_cipher()
    
    def _load_keys(self):
        kp = os.path.join(self.dir, "node.key")
        pp = os.path.join(self.dir, "node.pub")
        if os.path.exists(kp):
            with open(kp, "rb") as f:
                self.priv = serialization.load_pem_private_key(f.read(), None, default_backend())
            with open(pp, "rb") as f:
                self.pub = serialization.load_pem_public_key(f.read(), default_backend())
        else:
            self.priv = rsa.generate_private_key(65537, 2048, default_backend())
            self.pub = self.priv.public_key()
            with open(kp, "wb") as f:
                f.write(self.priv.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption()))
            with open(pp, "wb") as f:
                f.write(self.pub.public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo))
            os.chmod(kp, 0o600)
    
    def _init_cipher(self):
        sp = os.path.join(self.dir, "swarm.key")
        if os.path.exists(sp):
            with open(sp, "rb") as f:
                self.skey = f.read()
        else:
            self.skey = Fernet.generate_key()
            with open(sp, "wb") as f:
                f.write(self.skey)
            os.chmod(sp, 0o600)
        self.cipher = Fernet(self.skey)
    
    def fingerprint(self):
        return hashlib.sha256(self.pub.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo)).hexdigest()[:16]
    
    def encrypt(self, data):
        import json
        return self.cipher.encrypt(json.dumps(data, default=str).encode())
    
    def decrypt(self, token):
        import json
        try:
            return json.loads(self.cipher.decrypt(token).decode())
        except:
            return None
    
    def swarm_key_b64(self):
        return base64.b64encode(self.skey).decode()

# Export
IDENTITY_CLASS = NodeIdentity
'''

CAP_CORE_CONFIG = '''
# =============================================================================
# CAPABILITY: core.config
# Provides: Configuration management
# =============================================================================
import os
import uuid
from dataclasses import dataclass, field

@dataclass
class HydraConfig:
    node_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    cluster: str = "deedoop"
    udp_port: int = 9999
    http_port: int = 8080
    heartbeat: int = 5
    timeout: int = 30
    data_dir: str = field(default_factory=lambda: os.path.expanduser("~/.deedoop"))
    work_dir: str = field(default_factory=lambda: os.path.expanduser("~/.deedoop/work"))
    max_jobs: int = 4
    
    def __post_init__(self):
        for d in [self.data_dir, self.work_dir]:
            os.makedirs(d, exist_ok=True)

CONFIG = HydraConfig()
'''

CAP_CORE_HARDWARE = '''
# =============================================================================
# CAPABILITY: core.hardware
# Provides: Hardware detection and monitoring
# =============================================================================
import subprocess
import psutil
from dataclasses import dataclass

@dataclass
class NodeResources:
    cpu_total: int = 0
    cpu_avail: int = 0
    ram_total: float = 0
    ram_avail: float = 0
    gpu_total: int = 0
    gpu_avail: int = 0
    disk_total: float = 0
    disk_free: float = 0
    has_docker: bool = False
    has_nvidia: bool = False
    has_blender: bool = False
    cuda: str = ""

class HardwareProbe:
    @staticmethod
    def gpus():
        try:
            r = subprocess.run(['nvidia-smi', '--query-gpu=count,memory.total',
                '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                lines = r.stdout.strip().split("\\n")
                mem = sum(float(l.split(",")[1].strip())/1024 for l in lines if "," in l)
                cv = subprocess.run(['nvidia-smi', '--query-gpu=driver_version',
                    '--format=csv,noheader'], capture_output=True, text=True, timeout=5)
                return len(lines), mem, cv.stdout.strip().split("\\n")[0] if cv.returncode == 0 else "", True
        except:
            pass
        return 0, 0.0, "", False
    
    @staticmethod
    def docker():
        try:
            r = subprocess.run(['docker', '--version'], capture_output=True, text=True, timeout=5)
            return r.returncode == 0
        except:
            return False
    
    @staticmethod
    def blender():
        try:
            return subprocess.run(['blender', '--version'], capture_output=True, timeout=5).returncode == 0
        except:
            return False
    
    @staticmethod
    def snapshot():
        cpu = psutil.cpu_count(logical=True)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        gc, gm, cv, nv = HardwareProbe.gpus()
        return NodeResources(
            cpu, cpu,
            round(mem.total/(1024**3), 2), round(mem.available/(1024**3), 2),
            gc, gc,
            round(disk.total/(1024**3), 2), round(disk.free/(1024**3), 2),
            HardwareProbe.docker(), nv, HardwareProbe.blender(), cv
        )
    
    @staticmethod
    def compact():
        r = HardwareProbe.snapshot()
        p = [f"{r.cpu_total}C", f"{r.ram_total}G"]
        if r.gpu_total:
            p.append(f"GPU×{r.gpu_total}")
        if r.has_docker:
            p.append("🐳")
        return "/".join(p)

HARDWARE_PROBE = HardwareProbe
RESOURCES_CLASS = NodeResources
'''

CAP_NETWORK_MESH = '''
# =============================================================================
# CAPABILITY: network.mesh
# Provides: P2P mesh networking, peer discovery, broadcast
# =============================================================================
import socket
import threading
import time
import json
from dataclasses import asdict

class MeshNetwork:
    def __init__(self, identity, config, on_packet=None):
        self.identity = identity
        self.config = config
        self.on_packet = on_packet
        self.peers = {}
        self.peers_lock = threading.RLock()
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(('', config.udp_port))
        
        self._running = True
        threading.Thread(target=self._listen, daemon=True).start()
        threading.Thread(target=self._heartbeat, daemon=True).start()
    
    def _listen(self):
        while self._running:
            try:
                data, addr = self.sock.recvfrom(65535)
                pkt = self.identity.decrypt(data)
                if not pkt or pkt.get('src') == self.config.node_id:
                    continue
                
                src = pkt['src']
                with self.peers_lock:
                    is_new = src not in self.peers
                    self.peers[src] = {
                        'ip': addr[0],
                        'data': pkt.get('data', {}),
                        'seen': time.time(),
                        'caps': pkt.get('caps', [])
                    }
                    if is_new:
                        print(f"[MESH] + {src} ({addr[0]})")
                
                if self.on_packet:
                    self.on_packet(pkt, addr)
                    
            except Exception as e:
                pass
    
    def broadcast(self, op, **data):
        pkt = {
            'src': self.config.node_id,
            'op': op,
            'ts': time.time(),
            'data': data
        }
        encrypted = self.identity.encrypt(pkt)
        self.sock.sendto(encrypted, ('<broadcast>', self.config.udp_port))
    
    def _heartbeat(self):
        while self._running:
            self.broadcast('PING')
            
            # Cleanup stale peers
            now = time.time()
            with self.peers_lock:
                stale = [p for p, d in self.peers.items() if now - d['seen'] > self.config.timeout]
                for p in stale:
                    print(f"[MESH] - {p} (timeout)")
                    del self.peers[p]
            
            time.sleep(self.config.heartbeat)
    
    def stop(self):
        self._running = False
    
    def peer_count(self):
        return len(self.peers)
    
    def get_peers(self):
        with self.peers_lock:
            return dict(self.peers)

MESH_CLASS = MeshNetwork
'''

CAP_COMPUTE_CONTAINER = '''
# =============================================================================
# CAPABILITY: compute.container
# Provides: Docker/Podman container execution
# =============================================================================
import subprocess
import os

class ContainerRuntime:
    def __init__(self, work_dir):
        self.work_dir = work_dir
        self.rt = self._detect()
    
    def _detect(self):
        for rt in ['docker', 'podman']:
            try:
                if subprocess.run([rt, 'version'], capture_output=True, timeout=5).returncode == 0:
                    return rt
            except:
                pass
        return None
    
    @property
    def available(self):
        return self.rt is not None
    
    def pull(self, image):
        if not self.rt:
            return False
        try:
            return subprocess.run([self.rt, 'pull', image], 
                capture_output=True, timeout=600).returncode == 0
        except:
            return False
    
    def run(self, job_id, image, command=None, env=None, gpu=False, cpu=1, ram=1, timeout=3600):
        if not self.rt:
            return 1, "", "No container runtime"
        
        cmd = [self.rt, 'run', '--rm']
        cmd.extend(['--cpus', str(cpu)])
        cmd.extend(['--memory', f'{ram}g'])
        
        if gpu and self.rt == 'docker':
            cmd.extend(['--gpus', 'all'])
        
        for k, v in (env or {}).items():
            cmd.extend(['-e', f'{k}={v}'])
        
        jd = os.path.join(self.work_dir, job_id)
        os.makedirs(jd, exist_ok=True)
        cmd.extend(['-v', f'{jd}:/work', '-w', '/work'])
        
        cmd.append(image)
        if command:
            cmd.extend(command if isinstance(command, list) else command.split())
        
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return r.returncode, r.stdout, r.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Timeout"
        except Exception as e:
            return 1, "", str(e)

CONTAINER_CLASS = ContainerRuntime
'''

CAP_COMPUTE_PYTHON = '''
# =============================================================================
# CAPABILITY: compute.python
# Provides: Python script execution
# =============================================================================
import subprocess
import sys
import os

class PythonExecutor:
    def __init__(self, work_dir):
        self.work_dir = work_dir
    
    def execute(self, job_id, code=None, script=None, args=None, env=None, timeout=3600):
        jd = os.path.join(self.work_dir, job_id)
        os.makedirs(jd, exist_ok=True)
        
        if code:
            sp = os.path.join(jd, 'job.py')
            with open(sp, 'w') as f:
                f.write(code)
        else:
            sp = script
        
        if not sp:
            return 1, "", "No code or script"
        
        try:
            r = subprocess.run(
                [sys.executable, sp] + (args or []),
                capture_output=True, text=True, timeout=timeout,
                cwd=jd, env={**os.environ, **(env or {})}
            )
            return r.returncode, r.stdout, r.stderr
        except Exception as e:
            return 1, "", str(e)

PYTHON_EXECUTOR = PythonExecutor
'''

CAP_COMPUTE_BLENDER = '''
# =============================================================================
# CAPABILITY: compute.blender
# Provides: Blender rendering
# =============================================================================
import subprocess
import os

class BlenderExecutor:
    def __init__(self, work_dir):
        self.work_dir = work_dir
    
    def render(self, job_id, blend_file, frame_start=1, frame_end=1, 
               engine='CYCLES', device='GPU', timeout=3600):
        output = os.path.join(self.work_dir, job_id, 'render_')
        os.makedirs(os.path.dirname(output), exist_ok=True)
        
        cmd = ['blender', '-b', blend_file, '-E', engine, '-o', output,
               '-s', str(frame_start), '-e', str(frame_end), '-a']
        
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return r.returncode, r.stdout, r.stderr
        except FileNotFoundError:
            return 1, "", "Blender not installed"
        except Exception as e:
            return 1, "", str(e)

BLENDER_EXECUTOR = BlenderExecutor
'''

CAP_QUINE_SELF = '''
# =============================================================================
# CAPABILITY: quine.self
# Provides: Self-reference operations
# =============================================================================

class QuineSelf:
    def __init__(self, loader):
        self.loader = loader
    
    def get_genome_stream(self):
        """Get all capabilities as a genome stream"""
        manifests = self.loader.registry.all()
        return [m.to_dict() for m in manifests]
    
    def get_active_capabilities(self):
        """Get list of active capabilities"""
        return [(c.id, c.manifest.name, c.manifest.type.value) 
                for c in self.loader.list_active()]
    
    def inject_capability(self, manifest_dict):
        """Inject a new capability into the system"""
        from dataclasses import fields
        manifest = CapabilityManifest.from_dict(manifest_dict)
        self.loader.registry.register(manifest)
        return manifest.id
    
    def evolve(self, capability_id, new_source):
        """Evolve a capability with new source code"""
        old_manifest = self.loader.registry.get(capability_id)
        if not old_manifest:
            return None
        
        # Create new manifest with updated genome
        genome, ghash, gsize = CapabilityCodec.compress(new_source)
        
        new_manifest = CapabilityManifest(
            id=old_manifest.id,
            name=old_manifest.name,
            version=f"{old_manifest.version}.evolved",
            type=old_manifest.type,
            description=old_manifest.description,
            dependencies=old_manifest.dependencies,
            provides=old_manifest.provides,
            genome=genome,
            genome_hash=ghash,
            genome_size=gsize,
            entry_point=old_manifest.entry_point,
            exports=old_manifest.exports,
            hot_swappable=old_manifest.hot_swappable
        )
        
        # Hot swap
        self.loader.hot_swap(new_manifest)
        return new_manifest.genome_hash

QUINE_SELF_CLASS = QuineSelf
'''

# =============================================================================
# PHASE 9: CAPABILITY FACTORY (Creates built-in capabilities)
# =============================================================================

class CapabilityFactory:
    """Factory for creating built-in capabilities"""
    
    @staticmethod
    def create_core_capabilities() -> List[CapabilityManifest]:
        """Create the core capability set"""
        return [
            CapabilityCodec.create_manifest(
                id="core.identity",
                name="Identity",
                type=CapabilityType.CORE,
                source=CAP_CORE_IDENTITY,
                dependencies=[],
                provides=["identity", "crypto", "encryption"],
                exports=["IDENTITY_CLASS"],
                priority=1,
                description="RSA keypairs and swarm encryption"
            ),
            CapabilityCodec.create_manifest(
                id="core.config",
                name="Configuration",
                type=CapabilityType.CORE,
                source=CAP_CORE_CONFIG,
                dependencies=[],
                provides=["config", "settings"],
                exports=["CONFIG", "HydraConfig"],
                priority=0,
                description="System configuration"
            ),
            CapabilityCodec.create_manifest(
                id="core.hardware",
                name="Hardware Probe",
                type=CapabilityType.CORE,
                source=CAP_CORE_HARDWARE,
                dependencies=[],
                provides=["hardware", "resources", "probe"],
                exports=["HARDWARE_PROBE", "RESOURCES_CLASS"],
                priority=2,
                description="Hardware detection and monitoring"
            ),
            CapabilityCodec.create_manifest(
                id="network.mesh",
                name="P2P Mesh",
                type=CapabilityType.NETWORK,
                source=CAP_NETWORK_MESH,
                dependencies=["core.identity", "core.config"],
                provides=["mesh", "p2p", "broadcast", "discovery"],
                exports=["MESH_CLASS"],
                priority=10,
                description="Peer-to-peer mesh networking"
            ),
            CapabilityCodec.create_manifest(
                id="compute.container",
                name="Container Runtime",
                type=CapabilityType.COMPUTE,
                source=CAP_COMPUTE_CONTAINER,
                dependencies=["core.config"],
                provides=["docker", "podman", "container"],
                exports=["CONTAINER_CLASS"],
                priority=20,
                description="Docker/Podman execution"
            ),
            CapabilityCodec.create_manifest(
                id="compute.python",
                name="Python Executor",
                type=CapabilityType.EXECUTOR,
                source=CAP_COMPUTE_PYTHON,
                dependencies=["core.config"],
                provides=["python", "script"],
                exports=["PYTHON_EXECUTOR"],
                priority=20,
                description="Python script execution"
            ),
            CapabilityCodec.create_manifest(
                id="compute.blender",
                name="Blender Executor",
                type=CapabilityType.COMPUTE,
                source=CAP_COMPUTE_BLENDER,
                dependencies=["core.config"],
                provides=["blender", "render"],
                exports=["BLENDER_EXECUTOR"],
                priority=20,
                description="Blender rendering"
            ),
            CapabilityCodec.create_manifest(
                id="quine.self",
                name="Quine Self-Reference",
                type=CapabilityType.QUINE,
                source=CAP_QUINE_SELF,
                dependencies=[],
                provides=["quine", "self-reference", "evolution"],
                exports=["QUINE_SELF_CLASS"],
                priority=5,
                description="Self-reference and evolution operations"
            ),
        ]

# =============================================================================
# PHASE 10: THE HYDRA KERNEL
# =============================================================================

class HydraKernel:
    """
    The Hydra Kernel: A streaming capability-based distributed OS.
    Each head of the Hydra is a capability that can be grown or severed.
    """
    
    def __init__(self, role: str = "SEED"):
        self.role = role
        self.start_time = time.time()
        
        # Core systems
        self.stream = CapabilityStream()
        self.registry = CapabilityRegistry()
        self.loader = CapabilityLoader(self.registry, self.stream)
        
        # Register and load core capabilities
        self._bootstrap_capabilities()
        
        # Get references from loaded capabilities
        self.config = self.loader.get_symbol('CONFIG')
        self.identity = self.loader.get_symbol('IDENTITY_CLASS')(self.config.data_dir)
        self.hw_probe = self.loader.get_symbol('HARDWARE_PROBE')
        
        # Initialize mesh
        mesh_class = self.loader.get_symbol('MESH_CLASS')
        self.mesh = mesh_class(self.identity, self.config, self._on_mesh_packet)
        
        # Initialize executors
        container_class = self.loader.get_symbol('CONTAINER_CLASS')
        python_exec_class = self.loader.get_symbol('PYTHON_EXECUTOR')
        self.container = container_class(self.config.work_dir)
        self.python_exec = python_exec_class(self.config.work_dir)
        
        # Quine self-reference
        quine_self_class = self.loader.get_symbol('QUINE_SELF_CLASS')
        self.quine = quine_self_class(self.loader)
        
        # Jobs
        self.jobs = {}
        self.jobs_lock = threading.RLock()
        
        # Start DNA server
        threading.Thread(target=self._run_dna_server, daemon=True).start()
        
        # Start worker
        threading.Thread(target=self._worker_loop, daemon=True).start()
        
        if role == "SEED":
            self._print_banner()
    
    def _bootstrap_capabilities(self):
        """Bootstrap the core capabilities"""
        for manifest in CapabilityFactory.create_core_capabilities():
            self.registry.register(manifest)
        
        # Activate core capabilities in order
        core_caps = ["core.config", "core.identity", "core.hardware", 
                     "network.mesh", "compute.container", "compute.python",
                     "compute.blender", "quine.self"]
        
        for cap_id in core_caps:
            try:
                self.loader.activate(cap_id)
            except Exception as e:
                print(f"[HYDRA] Failed to activate {cap_id}: {e}")
    
    def _get_ip(self) -> str:
        import psutil
        for iface, snics in psutil.net_if_addrs().items():
            for s in snics:
                if s.family == socket.AF_INET and not s.address.startswith("127."):
                    if any(x in iface.lower() for x in ['eth', 'en', 'wlan', 'wifi']):
                        return s.address
        return "127.0.0.1"
    
    def _print_banner(self):
        ip = self._get_ip()
        hw = self.hw_probe.compact()
        active_caps = len(self.loader.list_active())
        total_caps = len(self.registry.all())
        
        print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           DEEDOOP OS v13.0 — THE HYDRA                                       ║
║           © 2025 Alexis Eleanor Fagan. All Rights Reserved.                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  STREAMING CAPABILITY ARCHITECTURE                                           ║
║  DNA is not one file, but a stream of self-describing capabilities.         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  NODE:        {self.config.node_id:<62} ║
║  IP:          {ip:<62} ║
║  FINGERPRINT: {self.identity.fingerprint():<62} ║
║  HARDWARE:    {hw:<62} ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  CAPABILITIES: {active_caps} active / {total_caps} registered{' '*(47-len(str(active_caps))-len(str(total_caps)))} ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ENDPOINTS:                                                                  ║
║    curl http://{ip}:{self.config.http_port}/             → Full source{' '*(34-len(ip))}║
║    curl http://{ip}:{self.config.http_port}/capabilities → Stream manifest{' '*(30-len(ip))}║
║    curl http://{ip}:{self.config.http_port}/stream       → Capability stream{' '*(28-len(ip))}║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
        print("Commands: caps, stream, inject, nodes, run, help, exit\n")
    
    def _on_mesh_packet(self, packet: dict, addr: tuple):
        """Handle mesh packets"""
        op = packet.get('op')
        
        if op == 'CAPABILITY_ANNOUNCE':
            # Another node is announcing capabilities
            caps = packet.get('data', {}).get('capabilities', [])
            for cap_dict in caps:
                try:
                    manifest = CapabilityManifest.from_dict(cap_dict)
                    if self.registry.register(manifest):
                        print(f"[HYDRA] Discovered capability: {manifest.name}")
                except:
                    pass
        
        elif op == 'CAPABILITY_REQUEST':
            # Node requesting a capability
            cap_id = packet.get('data', {}).get('id')
            manifest = self.registry.get(cap_id)
            if manifest:
                self.mesh.broadcast('CAPABILITY_RESPONSE', 
                    capability=manifest.to_dict())
        
        elif op == 'CAPABILITY_RESPONSE':
            cap_dict = packet.get('data', {}).get('capability')
            if cap_dict:
                manifest = CapabilityManifest.from_dict(cap_dict)
                self.stream.publish(manifest)
        
        elif op == 'JOB_SUBMIT':
            job = packet.get('data', {}).get('job')
            if job:
                self._queue_job(job)
    
    def _queue_job(self, job_data: dict):
        """Queue a job for execution"""
        job_id = job_data.get('id', uuid.uuid4().hex[:12])
        with self.jobs_lock:
            self.jobs[job_id] = {
                'id': job_id,
                'type': job_data.get('type', 'python'),
                'spec': job_data.get('spec', {}),
                'status': 'pending',
                'created': time.time()
            }
        return job_id
    
    def _worker_loop(self):
        """Background job execution"""
        while True:
            job = None
            with self.jobs_lock:
                for jid, j in self.jobs.items():
                    if j['status'] == 'pending':
                        j['status'] = 'running'
                        job = j
                        break
            
            if job:
                jtype = job['type']
                spec = job['spec']
                
                try:
                    if jtype == 'python':
                        ec, out, err = self.python_exec.execute(
                            job['id'], 
                            code=spec.get('code'),
                            script=spec.get('script'),
                            args=spec.get('args')
                        )
                    elif jtype == 'container':
                        ec, out, err = self.container.run(
                            job['id'],
                            image=spec.get('image'),
                            command=spec.get('command'),
                            gpu=spec.get('gpu', False)
                        )
                    else:
                        ec, out, err = 1, "", f"Unknown job type: {jtype}"
                    
                    with self.jobs_lock:
                        job['status'] = 'completed' if ec == 0 else 'failed'
                        job['exit_code'] = ec
                        job['output'] = out
                        job['error'] = err
                    
                    print(f"[WORKER] Job {job['id'][:8]} {'✓' if ec == 0 else '✗'}")
                    
                except Exception as e:
                    with self.jobs_lock:
                        job['status'] = 'failed'
                        job['error'] = str(e)
            
            time.sleep(1)
    
    def _run_dna_server(self):
        """HTTP server for streaming capabilities"""
        kernel = self
        
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/':
                    # Full source (reconstruct from capabilities)
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    # Read our own source
                    try:
                        with open(__file__, 'r') as f:
                            self.wfile.write(f.read().encode())
                    except:
                        self.wfile.write(b"# Source unavailable")
                
                elif self.path == '/capabilities':
                    # List all capability manifests (without genome)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    caps = []
                    for m in kernel.registry.all():
                        d = m.to_dict()
                        d['genome'] = f"<{m.genome_size} bytes>"  # Don't send full genome in list
                        caps.append(d)
                    self.wfile.write(json.dumps(caps, indent=2).encode())
                
                elif self.path == '/stream':
                    # Stream all capabilities (full genome)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/x-ndjson')
                    self.end_headers()
                    for m in kernel.registry.all():
                        line = json.dumps(m.to_dict()) + '\n'
                        self.wfile.write(line.encode())
                
                elif self.path.startswith('/capability/'):
                    # Get single capability
                    cap_id = self.path.split('/')[-1]
                    manifest = kernel.registry.get(cap_id)
                    if manifest:
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(manifest.to_dict()).encode())
                    else:
                        self.send_response(404)
                        self.end_headers()
                
                elif self.path == '/cluster':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    status = {
                        'node_id': kernel.config.node_id,
                        'uptime': time.time() - kernel.start_time,
                        'peers': kernel.mesh.peer_count(),
                        'capabilities': {
                            'active': len(kernel.loader.list_active()),
                            'registered': len(kernel.registry.all())
                        }
                    }
                    self.wfile.write(json.dumps(status).encode())
                
                elif self.path == '/health':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    hw = kernel.hw_probe.snapshot()
                    self.wfile.write(json.dumps(asdict(hw)).encode())
                
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def do_POST(self):
                if self.path == '/inject':
                    # Inject a new capability
                    cl = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(cl).decode()
                    try:
                        data = json.loads(body)
                        # Create capability from posted data
                        source = data.get('source', '')
                        manifest = CapabilityCodec.create_manifest(
                            id=data.get('id', uuid.uuid4().hex[:8]),
                            name=data.get('name', 'Custom'),
                            type=CapabilityType(data.get('type', 'plugin')),
                            source=source,
                            dependencies=data.get('dependencies', []),
                            provides=data.get('provides', []),
                            exports=data.get('exports', []),
                            description=data.get('description', '')
                        )
                        kernel.registry.register(manifest)
                        kernel.stream.publish(manifest)
                        
                        # Broadcast to mesh
                        kernel.mesh.broadcast('CAPABILITY_ANNOUNCE',
                            capabilities=[manifest.to_dict()])
                        
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'id': manifest.id,
                            'hash': manifest.genome_hash
                        }).encode())
                    except Exception as e:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(str(e).encode())
                
                elif self.path == '/submit':
                    # Submit a job
                    cl = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(cl).decode()
                    try:
                        data = json.loads(body)
                        job_id = kernel._queue_job(data)
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'job_id': job_id}).encode())
                    except Exception as e:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(str(e).encode())
                
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def log_message(self, *args):
                pass
        
        socketserver.TCPServer.allow_reuse_address = True
        try:
            with socketserver.TCPServer(("", self.config.http_port), Handler) as httpd:
                httpd.serve_forever()
        except Exception as e:
            print(f"[DNA] Server error: {e}")
    
    def get_cluster_status(self) -> dict:
        return {
            'node_id': self.config.node_id,
            'uptime': time.time() - self.start_time,
            'peers': self.mesh.get_peers(),
            'capabilities': {
                'active': [(c.id, c.manifest.name) for c in self.loader.list_active()],
                'registered': len(self.registry.all())
            },
            'jobs': {
                'pending': len([j for j in self.jobs.values() if j['status'] == 'pending']),
                'running': len([j for j in self.jobs.values() if j['status'] == 'running']),
                'completed': len([j for j in self.jobs.values() if j['status'] == 'completed'])
            }
        }

# =============================================================================
# PHASE 11: CLI
# =============================================================================

def print_help():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     DEEDOOP OS v13.0 — THE HYDRA                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  CAPABILITIES                          STREAMING                             ║
║    caps                - List caps       stream              - Show stream   ║
║    cap <id>            - Cap details     inject <json>       - Inject cap    ║
║    activate <id>       - Activate cap    evolve <id> <code>  - Evolve cap    ║
║    deactivate <id>     - Deactivate                                          ║
║                                                                              ║
║  CLUSTER                               WORKLOADS                             ║
║    nodes               - List nodes      run python <code>   - Run Python    ║
║    health              - Node health     run docker <img>    - Run container ║
║    status              - Cluster status  jobs                - List jobs     ║
║                                                                              ║
║  OTHER                                                                       ║
║    help                - This help       exit                - Shutdown      ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

def cli(kernel: HydraKernel):
    while True:
        try:
            cmd = input("hydra> ").strip()
            if not cmd:
                continue
            
            parts = cmd.split(maxsplit=1)
            action = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            
            if action == 'caps':
                print("\n Active Capabilities:")
                for cap in kernel.loader.list_active():
                    print(f"   [{cap.manifest.type.value:8}] {cap.id:<24} {cap.manifest.name}")
                print(f"\n Registered: {len(kernel.registry.all())} total\n")
            
            elif action == 'cap' and args:
                manifest = kernel.registry.get(args)
                if manifest:
                    print(f"\n Capability: {manifest.id}")
                    print(f"   Name:    {manifest.name}")
                    print(f"   Type:    {manifest.type.value}")
                    print(f"   Version: {manifest.version}")
                    print(f"   Hash:    {manifest.genome_hash}")
                    print(f"   Size:    {manifest.genome_size} bytes")
                    print(f"   Deps:    {manifest.dependencies}")
                    print(f"   Exports: {manifest.exports}\n")
                else:
                    print("Not found")
            
            elif action == 'activate' and args:
                try:
                    kernel.loader.activate(args)
                    print(f"Activated: {args}")
                except Exception as e:
                    print(f"Error: {e}")
            
            elif action == 'deactivate' and args:
                kernel.loader.deactivate(args)
                print(f"Deactivated: {args}")
            
            elif action == 'stream':
                print("\n Capability Stream:")
                for m in kernel.registry.all():
                    status = "ACTIVE" if m.id in [c.id for c in kernel.loader.list_active()] else "ready"
                    print(f"   {m.id:<24} {m.genome_hash[:8]} {m.genome_size:>6}B [{status}]")
                print()
            
            elif action == 'inject':
                if not args:
                    print("Usage: inject <json>")
                    print('Example: inject {"id":"test","name":"Test","type":"plugin","source":"print(42)"}')
                else:
                    try:
                        data = json.loads(args)
                        source = data.get('source', '')
                        manifest = CapabilityCodec.create_manifest(
                            id=data.get('id', uuid.uuid4().hex[:8]),
                            name=data.get('name', 'Custom'),
                            type=CapabilityType(data.get('type', 'plugin')),
                            source=source,
                            dependencies=data.get('dependencies', []),
                            exports=data.get('exports', [])
                        )
                        kernel.registry.register(manifest)
                        kernel.stream.publish(manifest)
                        print(f"Injected: {manifest.id} (hash: {manifest.genome_hash})")
                    except Exception as e:
                        print(f"Error: {e}")
            
            elif action == 'evolve':
                parts = args.split(maxsplit=1)
                if len(parts) < 2:
                    print("Usage: evolve <capability_id> <new_source>")
                else:
                    cap_id, new_source = parts
                    result = kernel.quine.evolve(cap_id, new_source)
                    if result:
                        print(f"Evolved {cap_id} → new hash: {result}")
                    else:
                        print(f"Capability not found: {cap_id}")
            
            elif action == 'nodes':
                peers = kernel.mesh.get_peers()
                print(f"\n Cluster: {len(peers) + 1} nodes")
                print(f"   {kernel.config.node_id} (self)")
                for pid, info in peers.items():
                    print(f"   {pid} [{info['ip']}]")
                print()
            
            elif action == 'health':
                hw = kernel.hw_probe.snapshot()
                print(f"\n Hardware: {hw.cpu_total}C | {hw.ram_total}G | GPU×{hw.gpu_total}")
                print(f" Docker: {'✓' if hw.has_docker else '✗'} | NVIDIA: {'✓' if hw.has_nvidia else '✗'}\n")
            
            elif action == 'status':
                st = kernel.get_cluster_status()
                print(f"\n Cluster Status")
                print(f"   Uptime: {st['uptime']:.0f}s")
                print(f"   Peers:  {len(st['peers'])}")
                print(f"   Caps:   {st['capabilities']['registered']} registered, {len(st['capabilities']['active'])} active")
                print(f"   Jobs:   {st['jobs']['pending']} pending, {st['jobs']['running']} running\n")
            
            elif action == 'jobs':
                with kernel.jobs_lock:
                    if not kernel.jobs:
                        print("No jobs")
                    else:
                        print(f"\n {'ID':<12} {'TYPE':<10} {'STATUS':<10}")
                        for j in kernel.jobs.values():
                            print(f" {j['id'][:10]:<12} {j['type']:<10} {j['status']:<10}")
                        print()
            
            elif action == 'run':
                parts = args.split(maxsplit=1)
                if len(parts) < 2:
                    print("Usage: run <type> <spec>")
                else:
                    jtype, spec = parts
                    job_data = {
                        'id': uuid.uuid4().hex[:12],
                        'type': jtype,
                        'spec': {'code': spec} if jtype == 'python' else {'image': spec}
                    }
                    job_id = kernel._queue_job(job_data)
                    print(f"Submitted: {job_id}")
            
            elif action == 'help':
                print_help()
            
            elif action in ('exit', 'quit'):
                print("Shutting down Hydra...")
                sys.exit(0)
            
            else:
                print(f"Unknown: {action}. Type 'help'")
        
        except KeyboardInterrupt:
            print("\nUse 'exit' to quit")
        except EOFError:
            break

# =============================================================================
# PHASE 12: ENTRY POINT
# =============================================================================

def main():
    role = 'WORKER' if not sys.stdin.isatty() else 'SEED'
    kernel = HydraKernel(role)
    
    if role == 'WORKER':
        print(f"[HYDRA] Node {kernel.config.node_id} joined mesh")
        while True:
            time.sleep(60)
    else:
        cli(kernel)

if __name__ == "__main__":
    main()
