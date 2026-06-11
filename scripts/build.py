import os
import sys
import shutil
import subprocess
import platform

def run_cmd(cmd, cwd=None):
    print(f"Executing: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd)
    if result.returncode != 0:
        print(f"Error executing: {cmd}")
        sys.exit(1)

def main():
    system = platform.system()
    is_windows = system == "Windows"
    print(f"Starting Delogo build process for OS: {system}")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frontend_dir = os.path.join(base_dir, "frontend")
    backend_dir = os.path.join(base_dir, "backend")
    
    # 1. Clean previous builds
    print("--- Cleaning old builds ---")
    dist_paths = [
        os.path.join(frontend_dir, "dist"),
        os.path.join(frontend_dir, "dist-electron"),
        os.path.join(frontend_dir, "release"),
        os.path.join(backend_dir, "build"),
        os.path.join(backend_dir, "dist")
    ]
    for path in dist_paths:
        if os.path.exists(path):
            shutil.rmtree(path)
            
    # 2. Build Frontend (Vue)
    print("--- Building Frontend (Vue) ---")
    run_cmd("npm install", cwd=frontend_dir)
    run_cmd("npm run build", cwd=frontend_dir)
    
    # 3. Build Backend (PyInstaller)
    print("--- Building Backend Engine (PyInstaller) ---")
    # You MUST run this script in an active virtual environment that has pyinstaller installed
    # And we will use a spec file to bundle the model
    spec_file = "delogo.spec"
    if not os.path.exists(os.path.join(backend_dir, spec_file)):
        print("Creating default PyInstaller spec...")
        sep = ";" if is_windows else ":"
        cmd = f"pyinstaller --name delogo-engine --onedir --noconfirm --clean main.py"
        run_cmd(cmd, cwd=backend_dir)
    else:
        run_cmd(f"pyinstaller --noconfirm --clean {spec_file}", cwd=backend_dir)
        
    # 4. Copy backend engine to frontend extraResources
    print("--- Preparing Electron Resources ---")
    engine_src = os.path.join(backend_dir, "dist", "delogo-engine")
    engine_dest = os.path.join(frontend_dir, "dist-engine")
    if os.path.exists(engine_dest):
        shutil.rmtree(engine_dest)
    shutil.copytree(engine_src, engine_dest)
    
    # 5. Build Electron App
    print("--- Building Electron App ---")
    # tsc will compile main.ts to dist-electron
    # electron-builder will read package.json
    build_cmd = "npm run build:electron" if is_windows else "npm run build:mac"
    run_cmd(build_cmd, cwd=frontend_dir)
    
    print(f"🎉 Build successfully completed for {system}!")
    print(f"Check frontend/release/ directory for the installation package.")

if __name__ == "__main__":
    main()
