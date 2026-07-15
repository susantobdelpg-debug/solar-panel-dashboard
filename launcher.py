import sys
import os
import webbrowser
import threading
import time
import streamlit.web.cli as stcli

def open_browser():
    # Wait a moment for the server to start up
    time.sleep(3.5)
    webbrowser.open("http://localhost:8501")

if __name__ == "__main__":
    # Resolve the bundle directory (handles PyInstaller _internal path in v6)
    if hasattr(sys, "_MEIPASS"):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    app_path = os.path.join(base_dir, "app.py")
    
    # Start thread to open browser programmatically
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Configure Streamlit run arguments
    # Headless=true completely bypasses any credentials/email prompts in PyInstaller exe
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
        "--server.headless=true",
        "--browser.gatherUsageStats=false"
    ]
    sys.exit(stcli.main())
