#!/usr/bin/env python3
"""
AdversarialCI Local Development Startup
========================================
Cross-platform script to start both backend and frontend servers.

Usage:
    python start_dev.py

Stops:
    Press Ctrl+C
"""

import subprocess
import sys
import os
import signal
import time
from pathlib import Path

# Colors for terminal output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color
    
    @classmethod
    def disable(cls):
        """Disable colors for Windows CMD."""
        cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = cls.NC = ''


# Disable colors on Windows if not in a compatible terminal
if sys.platform == 'win32' and 'WT_SESSION' not in os.environ:
    Colors.disable()


def print_banner():
    print(f"{Colors.BLUE}")
    print("╔═══════════════════════════════════════════════════╗")
    print("║       AdversarialCI Development Server            ║")
    print("╚═══════════════════════════════════════════════════╝")
    print(f"{Colors.NC}")


def find_project_root():
    """Find the project root directory."""
    current = Path(__file__).parent.absolute()
    
    # Check if we're already in project root
    if (current / 'server.py').exists():
        return current
    
    # Check parent directories
    for parent in current.parents:
        if (parent / 'server.py').exists():
            return parent
    
    return current


def find_frontend_dir(project_root):
    """Find the frontend directory."""
    for name in ['ui', 'frontend', 'client', 'web']:
        frontend_path = project_root / name
        if frontend_path.exists() and (frontend_path / 'package.json').exists():
            return frontend_path
    return None


def activate_venv(project_root):
    """Activate virtual environment if it exists."""
    venv_paths = [
        project_root / 'venv',
        project_root / '.venv',
    ]
    
    for venv_path in venv_paths:
        if venv_path.exists():
            if sys.platform == 'win32':
                activate_script = venv_path / 'Scripts' / 'activate.bat'
                python_path = venv_path / 'Scripts' / 'python.exe'
            else:
                activate_script = venv_path / 'bin' / 'activate'
                python_path = venv_path / 'bin' / 'python'
            
            if python_path.exists():
                print(f"{Colors.BLUE}   Activated virtual environment: {venv_path.name}{Colors.NC}")
                return str(python_path)
    
    return sys.executable


def start_backend(project_root, python_path):
    """Start the FastAPI backend server."""
    print(f"{Colors.GREEN}🚀 Starting Backend Server...{Colors.NC}")
    
    env = os.environ.copy()
    
    # Start uvicorn
    cmd = [python_path, '-m', 'uvicorn', 'server:app', '--reload', '--port', '8000']
    
    process = subprocess.Popen(
        cmd,
        cwd=str(project_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    print(f"{Colors.GREEN}   ✅ Backend starting (PID: {process.pid}){Colors.NC}")
    print(f"{Colors.BLUE}   📍 API: http://localhost:8000{Colors.NC}")
    print(f"{Colors.BLUE}   📚 Docs: http://localhost:8000/docs{Colors.NC}")
    
    return process


def start_frontend(frontend_dir):
    """Start the Vite React frontend server."""
    print(f"\n{Colors.GREEN}🚀 Starting Frontend Server...{Colors.NC}")
    
    # Check if node_modules exists
    if not (frontend_dir / 'node_modules').exists():
        print(f"{Colors.YELLOW}   📦 Installing frontend dependencies...{Colors.NC}")
        subprocess.run(['npm', 'install'], cwd=str(frontend_dir), check=True)
    
    # Start npm dev server
    if sys.platform == 'win32':
        cmd = ['npm.cmd', 'run', 'dev']
    else:
        cmd = ['npm', 'run', 'dev']
    
    process = subprocess.Popen(
        cmd,
        cwd=str(frontend_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    print(f"{Colors.GREEN}   ✅ Frontend starting (PID: {process.pid}){Colors.NC}")
    print(f"{Colors.BLUE}   📍 App: http://localhost:5173{Colors.NC}")
    
    return process


def print_summary(has_frontend=True):
    """Print running summary."""
    print(f"\n{Colors.GREEN}════════════════════════════════════════════════════{Colors.NC}")
    print(f"{Colors.GREEN}  🎯 AdversarialCI is running!{Colors.NC}")
    print(f"{Colors.GREEN}════════════════════════════════════════════════════{Colors.NC}")
    if has_frontend:
        print(f"{Colors.BLUE}  Frontend:  http://localhost:5173{Colors.NC}")
    print(f"{Colors.BLUE}  Backend:   http://localhost:8000{Colors.NC}")
    print(f"{Colors.BLUE}  API Docs:  http://localhost:8000/docs{Colors.NC}")
    print(f"{Colors.GREEN}════════════════════════════════════════════════════{Colors.NC}")
    print(f"{Colors.YELLOW}  Press Ctrl+C to stop both servers{Colors.NC}")
    print(f"{Colors.GREEN}════════════════════════════════════════════════════{Colors.NC}\n")


def stream_output(process, prefix):
    """Stream process output with prefix."""
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                print(f"[{prefix}] {line.rstrip()}")
    except:
        pass


def main():
    print_banner()
    
    project_root = find_project_root()
    os.chdir(project_root)
    print(f"{Colors.BLUE}📁 Project root: {project_root}{Colors.NC}\n")
    
    # Check for .env
    if not (project_root / '.env').exists():
        print(f"{Colors.YELLOW}⚠️  Warning: .env file not found{Colors.NC}")
    
    processes = []
    
    try:
        # Start backend
        python_path = activate_venv(project_root)
        backend_process = start_backend(project_root, python_path)
        processes.append(backend_process)
        
        # Wait for backend to initialize
        time.sleep(3)
        
        # Start frontend
        frontend_dir = find_frontend_dir(project_root)
        frontend_process = None
        
        if frontend_dir:
            frontend_process = start_frontend(frontend_dir)
            processes.append(frontend_process)
            print_summary(has_frontend=True)
        else:
            print(f"\n{Colors.YELLOW}⚠️  No frontend directory found. Running backend only.{Colors.NC}")
            print_summary(has_frontend=False)
        
        # Stream backend output
        print(f"\n{Colors.BLUE}═══ Server Logs ═══{Colors.NC}\n")
        
        while True:
            # Check if processes are still running
            if backend_process.poll() is not None:
                print(f"{Colors.RED}❌ Backend process exited{Colors.NC}")
                break
            
            if frontend_process and frontend_process.poll() is not None:
                print(f"{Colors.RED}❌ Frontend process exited{Colors.NC}")
                break
            
            # Read and print backend output
            if backend_process.stdout:
                line = backend_process.stdout.readline()
                if line:
                    print(f"[API] {line.rstrip()}")
            
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}🛑 Shutting down servers...{Colors.NC}")
    
    finally:
        # Cleanup
        for process in processes:
            try:
                if sys.platform == 'win32':
                    process.terminate()
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except:
                try:
                    process.kill()
                except:
                    pass
        
        print(f"{Colors.GREEN}✅ Servers stopped{Colors.NC}")


if __name__ == '__main__':
    main()