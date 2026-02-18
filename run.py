import uvicorn
import os
import sys

# Ensure current directory is in sys.path so scrollarr package is found
sys.path.append(os.getcwd())

if __name__ == "__main__":
    uvicorn.run("scrollarr.app:app", host="0.0.0.0", port=8000, reload=True)
