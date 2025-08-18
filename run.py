# run.py
import os
import sys
from gunicorn.app.wsgiapp import WSGIApplication

def main():
    # This is the key fix: Add the current directory to Python's path
    sys.path.insert(0, os.getcwd())

    # Define Gunicorn configuration
    options = {
        "bind": "0.0.0.0:8000",
        "workers": 4,
        "worker_class": "uvicorn.workers.UvicornWorker",
        "proc_name": "telegram_crawler",
    }

    # Create and run the Gunicorn application
    WSGIApplication("%(prog)s [OPTIONS] [APP_MODULE]").run(
        app_uri="app.main:app",
        config_update=options
    )

if __name__ == "__main__":
    main()
