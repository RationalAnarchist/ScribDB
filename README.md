# Scrollarr

Scrollarr is an "Arr"-style application for monitoring, downloading, and organizing web-based serial fiction (Royal Road, AO3, etc.). It provides a web interface to track your favorite stories, automatically download new chapters, and compile them into EPUB ebooks.

## Features

- **Monitor Stories:** Add stories by URL or Search (supports Royal Road and AO3).
- **Search & Discovery:** Search for stories directly within the app.
- **Auto-Download:** Automatically checks for and downloads new chapters.
- **Ebook Compilation:** Compile downloaded chapters into EPUB volumes with customizable profiles.
- **Web Interface:** Dashboard to view progress, manage stories, and configure providers.
- **Background Tasks:** Robust job management for scheduling updates and downloads.

## Prerequisites

- Python 3.8 or higher.
- Internet connection (to scrape sites).

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/rationalanarchist/scribdb.git
cd scrollarr
```

### 2. Set up a Virtual Environment

It is recommended to use a virtual environment to manage dependencies.

**Linux / Raspberry Pi:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```powershell
python -m venv venv
.\venv\Scripts\Activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Running the Application

### Web Interface (Recommended)

The easiest way to run Scrollarr is to start the web server. This will launch the web UI and automatically start the background job manager (for downloading chapters and checking for updates).

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

- Access the dashboard at: `http://localhost:8000` (or `http://<pi-ip-address>:8000`)
- **Note:** The first time you run it, it will create a `library.db` file and a `saved_stories` directory (or wherever you configured `download_path`).

### Command Line Interface (CLI)

You can also use the CLI for specific tasks, though the Web UI is preferred for monitoring.

- **Add a story:**
  ```bash
  python cli.py add "https://www.royalroad.com/fiction/12345/story-title"
  ```

- **List stories:**
  ```bash
  python cli.py list
  ```

- **Compile a story to EPUB:**
  ```bash
  python cli.py compile <story_id>
  ```

## Configuration

- **Database:** By default, Scrollarr uses a SQLite database named `library.db`. You can change this by setting the `DATABASE_URL` environment variable.
- **Storage:** Downloaded chapters are saved in the `saved_stories/` directory by default. This can be changed in `config.json` or via the Settings page.
- **Provider Settings:** Configure specific provider settings (e.g., AO3 cookies) via the "Sources" page in the Web Interface.

## Raspberry Pi Deployment (Production)

For a Raspberry Pi or always-on server, you might want to run the application in the background.

1.  **Using `nohup` (Simple):**
    ```bash
    nohup uvicorn app:app --host 0.0.0.0 --port 8000 > logs/scrollarr.log 2>&1 &
    ```

2.  **Using Systemd (Advanced):**
    Create a service file `/etc/systemd/system/scrollarr.service`:
    ```ini
    [Unit]
    Description=Scrollarr Web Service
    After=network.target

    [Service]
    User=pi
    WorkingDirectory=/path/to/scrollarr
    ExecStart=/path/to/scrollarr/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
    Restart=always

    [Install]
    WantedBy=multi-user.target
    ```
    Then enable and start it:
    ```bash
    sudo systemctl enable scrollarr
    sudo systemctl start scrollarr
    ```

## Project Structure

- `app.py`: Main FastAPI application entry point. Starts web server and background job manager.
- `job_manager.py`: Manages background tasks (updates, downloads) using APScheduler.
- `story_manager.py`: Core logic for managing stories and providers.
- `database.py`: Database models and connection logic.
- `alembic/`: Database migration scripts.
- `cli.py`: Command-line interface.
- `ebook_builder.py`: Logic for compiling EPUBs.
- `logger.py`: Centralized logging configuration.
- `saved_stories/`: Default directory where chapter content is stored (HTML files).
- `library.db`: SQLite database file.

## Troubleshooting

- **Logs:** Check `logs/scrollarr.log` for errors.
- **Database:** If you encounter DB errors, check `alembic` migrations or try resetting `library.db` (warning: loses data).
- **Permissions:** Ensure the user running the app has write permissions to the download directory.
