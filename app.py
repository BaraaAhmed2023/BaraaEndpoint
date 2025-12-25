from flask import Flask, jsonify, render_template, abort, request, g, session
from flask_cors import CORS
from healingherb import healingherb_bp
import os, json, time, traceback, threading, atexit, uuid, re
from data.apps import APPS
from healingherb.config import Config as healingherbConfig
from dotenv import load_dotenv
import logging
from flask.json.provider import DefaultJSONProvider
from datetime import datetime
from logging.handlers import RotatingFileHandler

class CustomJSONProvider(DefaultJSONProvider):
    def dumps(self, obj, **kwargs):
        kwargs.setdefault("ensure_ascii", False)
        return super().dumps(obj, **kwargs)

    def loads(self, s, **kwargs):
        return super().loads(s, **kwargs)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# ========== SIMPLE & RELIABLE LOGGING SYSTEM ==========
class SimpleSessionLogger:
    def __init__(self):
        self.log_file = '/tmp/flask_live_logs.log'
        self.active_sessions = set()
        self.lock = threading.Lock()
        self.heartbeats = {}  # session_id -> last_heartbeat
        
        # Create log directory if needed
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        # Start heartbeat cleaner
        self.cleaner_thread = threading.Thread(target=self._cleanup_old_sessions, daemon=True)
        self.cleaner_thread.start()
        
        print("📊 SimpleSessionLogger initialized")
    
    def start_logging(self, session_id, ip=None):
        """Start logging for this session"""
        with self.lock:
            self.active_sessions.add(session_id)
            self.heartbeats[session_id] = time.time()
            
            # Clear log file if first session
            if len(self.active_sessions) == 1:
                try:
                    with open(self.log_file, 'w') as f:
                        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 📊 Logging STARTED\n")
                    print(f"✅ Logging STARTED for session {session_id[:8]}")
                except:
                    pass
    
    def stop_logging(self, session_id):
        """Stop logging for this session"""
        with self.lock:
            if session_id in self.active_sessions:
                self.active_sessions.remove(session_id)
            
            if session_id in self.heartbeats:
                del self.heartbeats[session_id]
            
            # If no more sessions, clear logs
            if not self.active_sessions:
                self._clear_logs()
                print("📊 Logging STOPPED - All sessions ended")
    
    def update_heartbeat(self, session_id):
        """Update heartbeat for session"""
        with self.lock:
            if session_id in self.active_sessions:
                self.heartbeats[session_id] = time.time()
                return True
        return False
    
    def is_logging_active(self):
        """Check if logging is active"""
        with self.lock:
            return len(self.active_sessions) > 0
    
    def log_request(self, method, path, status, duration_ms, ip, agent):
        """Log a HTTP request - SIMPLE AND RELIABLE"""
        if not self.is_logging_active():
            return
        
        # Skip logs viewer requests
        if path.startswith('/admin/http-logs'):
            return
        
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Simple status icon
            if 200 <= status < 300:
                icon = "✅"
            elif 300 <= status < 400:
                icon = "🔄"
            elif status == 401:
                icon = "🔒"
            elif status == 404:
                icon = "❓"
            elif 400 <= status < 500:
                icon = "⚠️"
            else:
                icon = "🔥"
            
            # Simple log format: [TIME] ICON METHOD PATH STATUS DURATION | IP | AGENT
            log_line = f"[{timestamp}] {icon} {method} {path} -> {status} ({duration_ms:.1f}ms) | IP:{ip} | AGENT:{agent}\n"
            
            with self.lock:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(log_line)
            
            # Also print to console for debugging
            print(f"📝 {icon} {method} {path} -> {status} ({duration_ms:.1f}ms)")
            
        except Exception as e:
            print(f"Error logging request: {e}")
    
    def get_logs(self, limit=200):
        """Get logs - SIMPLE PARSING"""
        try:
            with self.lock:
                if not os.path.exists(self.log_file):
                    return []
                
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Get last N lines
                lines = lines[-limit:] if limit else lines
                
                parsed_logs = []
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Parse the simple format
                    try:
                        # Extract timestamp between [ and ]
                        timestamp_match = re.search(r'\[(.*?)\]', line)
                        if not timestamp_match:
                            continue
                        
                        timestamp = timestamp_match.group(1)
                        rest = line[timestamp_match.end():].strip()
                        
                        # Extract icon and method
                        parts = rest.split()
                        if len(parts) < 4:
                            continue
                        
                        icon = parts[0]
                        method = parts[1]
                        
                        # Find path (everything before "->")
                        arrow_idx = rest.find('->')
                        if arrow_idx == -1:
                            continue
                        
                        path_part = rest[len(icon)+len(method)+2:arrow_idx].strip()
                        
                        # Find status and duration
                        status_duration = rest[arrow_idx+2:].split('|')[0].strip()
                        
                        # Extract status number
                        status_match = re.search(r'(\d{3})', status_duration)
                        if not status_match:
                            continue
                        
                        status = int(status_match.group(1))
                        
                        # Extract duration
                        duration_match = re.search(r'\(([\d.]+)ms\)', status_duration)
                        duration = float(duration_match.group(1)) if duration_match else 0
                        
                        # Extract IP and Agent
                        ip = "N/A"
                        agent = "N/A"
                        
                        ip_match = re.search(r'IP:(.*?)(\||$)', line)
                        if ip_match:
                            ip = ip_match.group(1).strip()
                        
                        agent_match = re.search(r'AGENT:(.*?)(\||$)', line)
                        if agent_match:
                            agent = agent_match.group(1).strip()
                        
                        parsed_logs.append({
                            'timestamp': timestamp,
                            'icon': icon,
                            'method': method,
                            'path': path_part,
                            'status': status,
                            'duration': duration,
                            'ip': ip,
                            'agent': agent[:50],  # Limit agent length
                            'raw': line
                        })
                    except Exception as e:
                        # If parsing fails, add raw line
                        parsed_logs.append({
                            'timestamp': datetime.now().strftime('%H:%M:%S'),
                            'icon': '❓',
                            'method': 'PARSE',
                            'path': 'error',
                            'status': 0,
                            'duration': 0,
                            'ip': '0.0.0.0',
                            'agent': 'Parser',
                            'raw': line
                        })
                
                return parsed_logs
                
        except Exception as e:
            print(f"Error getting logs: {e}")
            return []
    
    def clear_logs(self):
        """Clear all logs"""
        with self.lock:
            try:
                open(self.log_file, 'w').close()
                print("🗑️ Logs cleared")
                return True
            except:
                return False
    
    def _clear_logs(self):
        """Internal: Clear logs when no sessions"""
        try:
            if os.path.exists(self.log_file):
                os.remove(self.log_file)
                print("🗑️ Logs file deleted (no active sessions)")
        except:
            pass
    
    def _cleanup_old_sessions(self):
        """Clean up sessions that haven't sent heartbeat in 20 seconds"""
        while True:
            try:
                with self.lock:
                    now = time.time()
                    to_remove = []
                    
                    for session_id, last_beat in list(self.heartbeats.items()):
                        if now - last_beat > 20:  # 20 seconds timeout
                            to_remove.append(session_id)
                    
                    for session_id in to_remove:
                        print(f"⏹️ Session {session_id[:8]} timeout")
                        self.stop_logging(session_id)
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                print(f"Heartbeat cleaner error: {e}")
                time.sleep(10)

# Create global logger instance
session_logger = SimpleSessionLogger()

def create_app():
    app = Flask(__name__)
    app.json_provider_class = CustomJSONProvider
    app.json = app.json_provider_class(app)
    
    # Set secret key for sessions
    app.secret_key = os.getenv('JWT_SECRET', 'your-secret-key-change-in-production') or 'dev-key-' + str(uuid.uuid4())
    
    # Configuration
    app.config['JWT_SECRET'] = os.getenv('JWT_SECRET', 'your-secret-key-change-in-production')
    app.config['JWT_EXPIRY'] = int(os.getenv('JWT_EXPIRY', 86400))
    app.config['DATABASE_URL'] = os.getenv('DATABASE_URL', 'postgresql://postgres:BaraaAhmed2012@db.qxjtkkwhhsphcecoewmg.supabase.co:5432/postgres')
    app.config['OPENROUTER_API_KEY'] = os.getenv('OPENROUTER_API_KEY', '')
    app.config['OPENROUTER_BASE_URL'] = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
    app.config['DEFAULT_AI_MODEL'] = os.getenv('DEFAULT_AI_MODEL', 'openai/gpt-3.5-turbo')
    app.config['AI_MAX_TOKENS'] = int(os.getenv('AI_MAX_TOKENS', 1000))
    app.config['AI_MAX_HISTORY'] = int(os.getenv('AI_MAX_HISTORY', 10))
    app.config['AI_RATE_LIMIT'] = int(os.getenv('AI_RATE_LIMIT', 60))
    app.config['AI_TEMPERATURE'] = float(os.getenv('AI_TEMPERATURE', 0.7))
    app.config['JSON_AS_ASCII'] = False

    # Enable CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"]
        }
    })
    
    # Register blueprint with URL prefix
    app.register_blueprint(healingherb_bp, url_prefix='/apis/healing-herbs')
    
    # ========== SIMPLE REQUEST LOGGING MIDDLEWARE ==========
    @app.before_request
    def before_request():
        """Store request start time"""
        g.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        """Log EVERY request - SIMPLE AND RELIABLE"""
        try:
            # Calculate duration
            duration = 0
            if hasattr(g, 'start_time'):
                duration = (time.time() - g.start_time) * 1000
            
            # Get request info
            method = request.method
            path = request.path
            status = response.status_code
            ip = request.remote_addr or '0.0.0.0'
            agent = request.user_agent.string if request.user_agent else 'No-Agent'
            
            # Log the request
            session_logger.log_request(method, path, status, duration, ip, agent)
            
        except Exception as e:
            # Don't crash the app if logging fails
            print(f"Logging error: {e}")
        
        return response
    
    # ========== SIMPLE & MODERN LOGS VIEWER ==========
    @app.route('/')
    def index():
        return render_template("index.html", apps=APPS)
    
    @app.route('/admin/http-logs')
    def http_logs_viewer():
        """Modern logs viewer"""
        # Create session ID
        if 'log_session_id' not in session:
            session['log_session_id'] = str(uuid.uuid4())
            session.permanent = True
        
        session_id = session['log_session_id']
        ip = request.remote_addr or 'unknown'
        
        # Start logging
        session_logger.start_logging(session_id, ip)
        
        return f'''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Live HTTP Logs</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <style>
                @keyframes pulse {{
                    0%, 100% {{ opacity: 1; }}
                    50% {{ opacity: 0.5; }}
                }}
                .log-entry {{
                    transition: all 0.2s;
                }}
                .log-entry:hover {{
                    background-color: rgba(255, 255, 255, 0.05);
                }}
                .scrollbar-hide::-webkit-scrollbar {{
                    display: none;
                }}
                .scrollbar-hide {{
                    -ms-overflow-style: none;
                    scrollbar-width: none;
                }}
            </style>
        </head>
        <body class="bg-gray-900 text-gray-100 min-h-screen">
            <div class="container mx-auto px-4 py-8">
                <!-- Header -->
                <div class="bg-gradient-to-r from-blue-900 to-purple-900 rounded-2xl p-8 mb-8 shadow-2xl">
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-center">
                        <div>
                            <h1 class="text-3xl md:text-4xl font-bold mb-2">
                                <i class="fas fa-satellite mr-3"></i>Live HTTP Logs Monitor
                            </h1>
                            <p class="text-blue-200 mb-4">
                                Real-time monitoring of all HTTP requests. Logging is <span class="font-bold text-green-300">ACTIVE</span>.
                            </p>
                            <div class="flex flex-wrap gap-4 items-center">
                                <div class="bg-green-900/30 text-green-300 px-4 py-2 rounded-full text-sm font-semibold flex items-center">
                                    <div class="w-2 h-2 bg-green-400 rounded-full mr-2 animate-pulse"></div>
                                    <span id="statusText">LIVE</span>
                                </div>
                                <div class="bg-blue-900/30 text-blue-300 px-4 py-2 rounded-full text-sm">
                                    Session: <span id="sessionId" class="font-mono">{session_id[:8]}...</span>
                                </div>
                                <div class="bg-purple-900/30 text-purple-300 px-4 py-2 rounded-full text-sm">
                                    <i class="fas fa-heartbeat mr-1"></i>
                                    <span id="heartbeatStatus">Active</span>
                                </div>
                            </div>
                        </div>
                        <div class="mt-4 md:mt-0">
                            <button onclick="testLogs()" class="bg-yellow-500 hover:bg-yellow-600 text-white px-6 py-3 rounded-xl font-semibold flex items-center transition">
                                <i class="fas fa-bolt mr-2"></i>
                                Test Logs
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Controls -->
                <div class="bg-gray-800 rounded-xl p-6 mb-8">
                    <div class="flex flex-wrap gap-4">
                        <button onclick="loadLogs()" id="refreshBtn" class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold flex items-center transition">
                            <i class="fas fa-sync-alt mr-2"></i>
                            Refresh Logs
                        </button>
                        
                        <button onclick="toggleAutoRefresh()" id="autoRefreshBtn" class="bg-green-600 hover:bg-green-700 text-white px-6 py-3 rounded-lg font-semibold flex items-center transition">
                            <i class="fas fa-play mr-2"></i>
                            Auto Refresh (3s)
                        </button>
                        
                        <button onclick="clearLogs()" class="bg-yellow-600 hover:bg-yellow-700 text-white px-6 py-3 rounded-lg font-semibold flex items-center transition">
                            <i class="fas fa-trash-alt mr-2"></i>
                            Clear Logs
                        </button>
                        
                        <button onclick="stopLogging()" class="bg-red-600 hover:bg-red-700 text-white px-6 py-3 rounded-lg font-semibold flex items-center transition">
                            <i class="fas fa-stop-circle mr-2"></i>
                            Stop Logging
                        </button>
                        
                        <div class="ml-auto flex items-center">
                            <span class="text-sm text-gray-400 mr-4">
                                <span id="logCount">0</span> logs
                            </span>
                            <div class="w-32">
                                <div class="h-2 bg-gray-700 rounded-full overflow-hidden">
                                    <div id="memoryBar" class="h-full bg-green-500" style="width: 0%"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Stats -->
                <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                    <div class="bg-gray-800 rounded-xl p-6">
                        <div class="text-3xl font-bold text-green-400" id="totalRequests">0</div>
                        <div class="text-gray-400 text-sm uppercase tracking-wider">Total Requests</div>
                    </div>
                    <div class="bg-gray-800 rounded-xl p-6">
                        <div class="text-3xl font-bold text-blue-400" id="successRequests">0</div>
                        <div class="text-gray-400 text-sm uppercase tracking-wider">Success (2xx)</div>
                    </div>
                    <div class="bg-gray-800 rounded-xl p-6">
                        <div class="text-3xl font-bold text-yellow-400" id="clientErrors">0</div>
                        <div class="text-gray-400 text-sm uppercase tracking-wider">Client Errors</div>
                    </div>
                    <div class="bg-gray-800 rounded-xl p-6">
                        <div class="text-3xl font-bold text-red-400" id="serverErrors">0</div>
                        <div class="text-gray-400 text-sm uppercase tracking-wider">Server Errors</div>
                    </div>
                </div>

                <!-- Logs Table -->
                <div class="bg-gray-800 rounded-xl overflow-hidden">
                    <div class="px-6 py-4 border-b border-gray-700 flex justify-between items-center">
                        <h2 class="text-xl font-semibold">Recent HTTP Requests</h2>
                        <div class="text-sm text-gray-400">
                            Updated: <span id="lastUpdate">--:--:--</span>
                        </div>
                    </div>
                    
                    <div class="overflow-x-auto">
                        <table class="w-full">
                            <thead class="bg-gray-900">
                                <tr>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Time</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Method</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Status</th>
                                    <th class="px6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Path</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Duration</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">IP Address</th>
                                </tr>
                            </thead>
                            <tbody id="logsTable" class="divide-y divide-gray-700">
                                <tr id="noLogsRow">
                                    <td colspan="6" class="px-6 py-12 text-center text-gray-500">
                                        <div class="flex flex-col items-center">
                                            <i class="fas fa-stream text-4xl mb-4 opacity-30"></i>
                                            <p class="text-lg mb-2">No logs yet</p>
                                            <p class="text-sm">Make requests to your application to see logs here</p>
                                            <button onclick="testLogs()" class="mt-4 text-blue-400 hover:text-blue-300">
                                                <i class="fas fa-bolt mr-1"></i>Click here to generate test logs
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Footer -->
                <div class="mt-8 text-center text-gray-500 text-sm">
                    <p>Logging will automatically stop when you close this tab or after 20 seconds of inactivity.</p>
                    <p class="mt-2">Server Time: <span id="serverTime">--:--:--</span></p>
                </div>
            </div>

            <!-- Toast Notification -->
            <div id="toast" class="fixed bottom-4 right-4 bg-gray-800 border-l-4 border-green-500 text-white px-6 py-4 rounded-lg shadow-xl transform translate-x-full transition-transform duration-300">
                <div class="flex items-center">
                    <i class="fas fa-check-circle mr-3 text-green-400"></i>
                    <span id="toastMessage">Operation successful</span>
                </div>
            </div>

            <script>
            // Configuration
            const SESSION_ID = '{session_id}';
            let autoRefreshInterval = null;
            let heartbeatInterval = null;
            
            // Toast notification
            function showToast(message, type = 'success') {{
                const toast = document.getElementById('toast');
                const toastMsg = document.getElementById('toastMessage');
                const toastIcon = toast.querySelector('i');
                
                toastMsg.textContent = message;
                
                // Set color based on type
                if (type === 'success') {{
                    toast.className = toast.className.replace(/border-\w+-\d+/g, 'border-green-500');
                    toastIcon.className = 'fas fa-check-circle mr-3 text-green-400';
                }} else if (type === 'error') {{
                    toast.className = toast.className.replace(/border-\w+-\d+/g, 'border-red-500');
                    toastIcon.className = 'fas fa-exclamation-circle mr-3 text-red-400';
                }} else if (type === 'warning') {{
                    toast.className = toast.className.replace(/border-\w+-\d+/g, 'border-yellow-500');
                    toastIcon.className = 'fas fa-exclamation-triangle mr-3 text-yellow-400';
                }}
                
                // Show toast
                toast.classList.remove('translate-x-full');
                toast.classList.add('translate-x-0');
                
                // Hide after 3 seconds
                setTimeout(() => {{
                    toast.classList.remove('translate-x-0');
                    toast.classList.add('translate-x-full');
                }}, 3000);
            }}
            
            // Heartbeat system
            function startHeartbeat() {{
                heartbeatInterval = setInterval(() => {{
                    fetch(`/admin/http-logs/heartbeat/${{SESSION_ID}}`, {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ timestamp: Date.now() }})
                    }})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            document.getElementById('heartbeatStatus').textContent = 'Active';
                            document.getElementById('heartbeatStatus').className = 'text-green-400';
                        }}
                    }})
                    .catch(error => {{
                        console.warn('Heartbeat failed:', error);
                        document.getElementById('heartbeatStatus').textContent = 'Failed';
                        document.getElementById('heartbeatStatus').className = 'text-red-400';
                    }});
                }}, 5000); // Every 5 seconds
                
                console.log('Heartbeat started for session:', SESSION_ID);
            }}
            
            function stopHeartbeat() {{
                if (heartbeatInterval) {{
                    clearInterval(heartbeatInterval);
                    heartbeatInterval = null;
                    console.log('Heartbeat stopped');
                }}
            }}
            
            // Load logs from server
            function loadLogs() {{
                // Show loading state
                const refreshBtn = document.getElementById('refreshBtn');
                const originalHTML = refreshBtn.innerHTML;
                refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Loading...';
                refreshBtn.disabled = true;
                
                fetch('/admin/http-logs/data')
                    .then(response => {{
                        if (!response.ok) throw new Error('HTTP ' + response.status);
                        return response.json();
                    }})
                    .then(data => {{
                        updateStats(data);
                        displayLogs(data.logs || []);
                        updateUI(data);
                        
                        // Restore button
                        refreshBtn.innerHTML = originalHTML;
                        refreshBtn.disabled = false;
                        
                        // Show success
                        const count = data.logs?.length || 0;
                        if (count > 0) {{
                            showToast(`Loaded ${{count}} logs`, 'success');
                        }}
                    }})
                    .catch(error => {{
                        console.error('Error loading logs:', error);
                        showToast('Error loading logs', 'error');
                        
                        // Restore button
                        refreshBtn.innerHTML = originalHTML;
                        refreshBtn.disabled = false;
                    }});
            }}
            
            // Update statistics
            function updateStats(data) {{
                const logs = data.logs || [];
                const total = logs.length;
                const success = logs.filter(l => l.status >= 200 && l.status < 300).length;
                const clientError = logs.filter(l => l.status >= 400 && l.status < 500).length;
                const serverError = logs.filter(l => l.status >= 500).length;
                
                document.getElementById('totalRequests').textContent = total;
                document.getElementById('successRequests').textContent = success;
                document.getElementById('clientErrors').textContent = clientError;
                document.getElementById('serverErrors').textContent = serverError;
                document.getElementById('logCount').textContent = total;
                
                // Update memory bar (fake for now)
                const memoryPercent = Math.min(total * 0.5, 100);
                document.getElementById('memoryBar').style.width = memoryPercent + '%';
            }}
            
            // Display logs in table
            function displayLogs(logs) {{
                const tableBody = document.getElementById('logsTable');
                const noLogsRow = document.getElementById('noLogsRow');
                
                if (logs.length === 0) {{
                    noLogsRow.style.display = '';
                    return;
                }}
                
                noLogsRow.style.display = 'none';
                
                // Clear existing rows (except noLogsRow)
                const existingRows = tableBody.querySelectorAll('tr:not(#noLogsRow)');
                existingRows.forEach(row => row.remove());
                
                // Add new rows
                logs.forEach(log => {{
                    const row = document.createElement('tr');
                    row.className = 'log-entry';
                    
                    // Determine status color
                    let statusColor = 'text-green-400';
                    if (log.status >= 500) statusColor = 'text-red-400';
                    else if (log.status >= 400) statusColor = 'text-yellow-400';
                    else if (log.status >= 300) statusColor = 'text-blue-400';
                    
                    // Determine method color
                    let methodColor = 'text-blue-400';
                    if (log.method === 'POST') methodColor = 'text-green-400';
                    else if (log.method === 'PUT') methodColor = 'text-yellow-400';
                    else if (log.method === 'DELETE') methodColor = 'text-red-400';
                    
                    // Format time (show only time part)
                    const timeOnly = log.timestamp.split(' ')[1] || log.timestamp;
                    
                    row.innerHTML = `
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-300">${{timeOnly}}</td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <span class="px-3 py-1 rounded-full text-xs font-semibold ${{methodColor}} bg-gray-900">
                                ${{log.method}}
                            </span>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <span class="px-3 py-1 rounded-full text-xs font-semibold ${{statusColor}} bg-gray-900">
                                ${{log.status}} ${{log.icon}}
                            </span>
                        </td>
                        <td class="px-6 py-4 text-sm text-gray-300 max-w-xs truncate" title="${{log.path}}">
                            ${{log.path}}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm ${{log.duration > 1000 ? 'text-red-400' : 'text-gray-300'}}">
                            ${{log.duration.toFixed(1)}}ms
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-400 font-mono">
                            ${{log.ip}}
                        </td>
                    `;
                    
                    tableBody.appendChild(row);
                }});
            }}
            
            // Update UI elements
            function updateUI(data) {{
                // Update last update time
                const now = new Date();
                document.getElementById('lastUpdate').textContent = 
                    now.getHours().toString().padStart(2, '0') + ':' +
                    now.getMinutes().toString().padStart(2, '0') + ':' +
                    now.getSeconds().toString().padStart(2, '0');
                
                // Update server time
                document.getElementById('serverTime').textContent = new Date().toLocaleTimeString();
                
                // Update status text
                const logs = data.logs || [];
                if (logs.length > 0) {{
                    document.getElementById('statusText').textContent = `LIVE - ${{logs.length}} logs`;
                }}
            }}
            
            // Auto-refresh control
            function toggleAutoRefresh() {{
                const btn = document.getElementById('autoRefreshBtn');
                if (autoRefreshInterval) {{
                    clearInterval(autoRefreshInterval);
                    autoRefreshInterval = null;
                    btn.innerHTML = '<i class="fas fa-play mr-2"></i>Auto Refresh (3s)';
                    btn.className = btn.className.replace('bg-red-600', 'bg-green-600');
                    showToast('Auto-refresh stopped', 'warning');
                }} else {{
                    autoRefreshInterval = setInterval(loadLogs, 3000);
                    btn.innerHTML = '<i class="fas fa-pause mr-2"></i>Stop Auto Refresh';
                    btn.className = btn.className.replace('bg-green-600', 'bg-red-600');
                    showToast('Auto-refresh started', 'success');
                }}
            }}
            
            function stopAutoRefresh() {{
                if (autoRefreshInterval) {{
                    clearInterval(autoRefreshInterval);
                    autoRefreshInterval = null;
                }}
            }}
            
            // Clear logs
            function clearLogs() {{
                if (confirm('Clear all logs? This cannot be undone.')) {{
                    fetch('/admin/http-logs/clear', {{ 
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }}
                    }})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            loadLogs();
                            showToast('Logs cleared successfully', 'warning');
                        }}
                    }})
                    .catch(error => {{
                        showToast('Error clearing logs', 'error');
                    }});
                }}
            }}
            
            // Stop logging
            function stopLogging() {{
                if (confirm('Stop logging and leave this page?')) {{
                    stopHeartbeat();
                    stopAutoRefresh();
                    
                    fetch(`/admin/http-logs/stop/${{SESSION_ID}}`, {{ 
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }}
                    }})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            showToast('Logging stopped. Redirecting...', 'success');
                            setTimeout(() => {{
                                window.location.href = '/';
                            }}, 1500);
                        }}
                    }})
                    .catch(error => {{
                        showToast('Error stopping logging', 'error');
                    }});
                }}
            }}
            
            // Test logs - generate test requests
            function testLogs() {{
                showToast('Generating test logs...', 'success');
                
                // Make multiple test requests
                const testEndpoints = [
                    '/admin/test',
                    '/admin/test?type=success',
                    '/admin/test?type=error',
                    '/admin/test?type=slow'
                ];
                
                let completed = 0;
                testEndpoints.forEach(endpoint => {{
                    fetch(endpoint)
                        .then(() => completed++)
                        .catch(() => completed++)
                        .finally(() => {{
                            if (completed === testEndpoints.length) {{
                                setTimeout(loadLogs, 500);
                                showToast('Test logs generated!', 'success');
                            }}
                        }});
                }});
            }}
            
            // Initialize everything
            function init() {{
                // Start heartbeat
                startHeartbeat();
                
                // Load logs immediately
                loadLogs();
                
                // Start auto-refresh
                toggleAutoRefresh();
                
                // Show welcome message
                setTimeout(() => {{
                    showToast('Live logging started! Open other tabs to generate logs.', 'success');
                }}, 1000);
                
                // Update time every second
                setInterval(() => {{
                    document.getElementById('serverTime').textContent = new Date().toLocaleTimeString();
                }}, 1000);
                
                console.log('Live logs monitor initialized');
            }}
            
            // Clean up on page unload
            window.addEventListener('beforeunload', () => {{
                stopHeartbeat();
                stopAutoRefresh();
                
                // Try to send stop request
                navigator.sendBeacon(`/admin/http-logs/stop/${{SESSION_ID}}`);
            }});
            
            // Start when page loads
            window.addEventListener('DOMContentLoaded', init);
            </script>
        </body>
        </html>
        '''
    
    @app.route('/admin/http-logs/data')
    def http_logs_data():
        """Get logs data - SIMPLE AND RELIABLE"""
        try:
            logs = session_logger.get_logs(100)
            
            return jsonify({
                'success': True,
                'logs': logs,
                'count': len(logs),
                'is_logging': session_logger.is_logging_active(),
                'timestamp': time.time()
            })
        except Exception as e:
            print(f"Error in http_logs_data: {e}")
            return jsonify({
                'success': False,
                'logs': [],
                'error': str(e),
                'timestamp': time.time()
            })
    
    @app.route('/admin/http-logs/heartbeat/<session_id>', methods=['POST'])
    def heartbeat(session_id):
        """Heartbeat endpoint"""
        success = session_logger.update_heartbeat(session_id)
        return jsonify({
            'success': success,
            'timestamp': time.time(),
            'session_id': session_id[:8]
        })
    
    @app.route('/admin/http-logs/stop/<session_id>', methods=['POST'])
    def stop_logging(session_id):
        """Stop logging"""
        session_logger.stop_logging(session_id)
        return jsonify({
            'success': True,
            'message': 'Logging stopped',
            'timestamp': time.time()
        })
    
    @app.route('/admin/http-logs/clear', methods=['POST'])
    def clear_http_logs():
        """Clear logs"""
        success = session_logger.clear_logs()
        return jsonify({
            'success': success,
            'message': 'Logs cleared' if success else 'Failed to clear logs'
        })
    
    @app.route('/admin/test')
    def test_endpoint():
        """Test endpoint to generate logs"""
        # Simulate some processing time
        time.sleep(0.1 + (request.args.get('type') == 'slow') * 0.5)
        
        if request.args.get('type') == 'error':
            return jsonify({
                'success': False,
                'error': 'Test error'
            }), 400
        
        return jsonify({
            'success': True,
            'message': 'Test request for logs monitoring',
            'timestamp': datetime.now().isoformat(),
            'data': {
                'test': True,
                'random': os.urandom(4).hex()
            }
        })
    
    # ========== ERROR HANDLERS ==========
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "success": False,
            "error": "الصفحة غير موجودة"
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            "success": False,
            "error": "الطريقة غير مسموحة"
        }), 405
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        logger.error(f"🔥 UNHANDLED EXCEPTION: {str(e)}")
        logger.error(traceback.format_exc())
        
        return jsonify({
            "success": False,
            "error": "حدث خطأ في الخادم"
        }), 500
    
    # Configure logging
    print("🚀 Application starting with SIMPLE logging system...")
    
    return app

# Create the app
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)