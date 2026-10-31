import sys
import os

# Ensure server module is discoverable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn

if __name__ == "__main__":
    print("Starting Project ByteClass Backend Engine on http://127.0.0.1:8000...")
    uvicorn.run("server.main:app", host="127.0.0.1", port=8000, reload=True)
