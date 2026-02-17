# Scrollarr

Scrollarr is an "Arr"-style application for monitoring, downloading, and organizing web-based serial fiction from sites like Royal Road, AO3, and Questionable Questing. It provides a web interface to track your favorite stories, automatically download new chapters, and compile them into EPUB or PDF ebooks.

## About

Scrollarr is designed to run 24/7 on a server (e.g., Raspberry Pi or VPS). It handles:
- **Automatic Monitoring:** Checks for new chapters periodically.
- **Downloading:** Fetches chapter content and saves it locally.
- **Ebook Generation:** Compiles downloaded chapters into EPUB or PDF files based on customizable profiles.
- **Notifications:** Supports email and webhook notifications for downloads and updates.

## Features

- **Monitor Stories:** Add stories by URL or Search.
- **Multi-Provider Support:** Royal Road, AO3, Questionable Questing (with login support).
- **Search & Discovery:** Search for stories directly within the app.
- **Auto-Download:** Automatically checks for and downloads new chapters.
- **Ebook Compilation:** Compile downloaded chapters into EPUB volumes or PDFs with customizable styles.
- **Web Interface:** Dashboard to view progress, manage stories, and configure providers.
- **Background Tasks:** Robust job management for scheduling updates and downloads.

## Prerequisites

- **Python 3.8+**
- **System Dependencies:**
  - `python3-venv` (for virtual environment)
  - `python3-dev` (for compiling some packages)
  - `build-essential` (gcc, etc.)
  - `libxml2-dev`, `libxslt-dev` (for lxml)

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
# Install system dependencies (Debian/Ubuntu/Raspbian)
sudo apt update
sudo apt install python3-venv python3-dev build-essential libxml2-dev libxslt-dev

# Create and activate venv
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```powershell
python -m venv venv
.\venv\Scripts\Activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

## Running the Application

### Web Interface (Recommended)

The easiest way to run Scrollarr is to start the web server. This will launch the web UI and automatically start the background job manager.

```bash
# Ensure venv is activated
uvicorn app:app --host 0.0.0.0 --port 8000
```

- Access the dashboard at: `http://localhost:8000` (or `http://<pi-ip-address>:8000`)
- **Note:** The first time you run it, it will create a `library.db` file and run database migrations automatically.

### Command Line Interface (CLI)

You can also use the CLI for specific tasks.

- **Add a story:** `python cli.py add "https://site.com/story"`
- **List stories:** `python cli.py list`
- **Compile a story:** `python cli.py compile <story_id>`

## Configuration

Scrollarr uses a `config.json` file for settings, which can also be managed via the Web UI (**Settings** page).

**Key Settings:**
- `download_path`: Directory to store raw chapter files (default: `saved_stories`).
- `library_path`: Directory to store generated Ebooks (default: `library`).
- `update_interval_hours`: Frequency of update checks (default: `1`).
- `worker_sleep_min/max`: Delay between download tasks to be polite.
- `database_url`: Database connection string (default: `sqlite:///library.db`).

## Efficiency / Low Power Devices (Raspberry Pi)

For running Scrollarr on low-power devices like a Raspberry Pi Zero or older models, specific optimizations are recommended to ensure stability and performance.

**[See efficiency.md for detailed optimization instructions.](efficiency.md)**

Highlights:
- Enable SQLite WAL Mode.
- Increase Swap Space.
- Tune update intervals.

## Deployment (Production)

For a Raspberry Pi or always-on server, use `systemd`.

**Create a service file `/etc/systemd/system/scrollarr.service`:**
```ini
[Unit]
Description=Scrollarr Web Service
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/scrollarr
ExecStart=/home/pi/scrollarr/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always
# Optional: Wait for network
ExecStartPre=/bin/sleep 10

[Install]
WantedBy=multi-user.target
```

Then enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable scrollarr
sudo systemctl start scrollarr
```

## Development

**Running Tests:**
```bash
python3 -m unittest discover . -p "test_*.py"
```

## Project Structure

- `app.py`: FastAPI application entry point.
- `job_manager.py`: Background task scheduler.
- `story_manager.py`: Core logic for stories and providers.
- `database.py`: SQLAlchemy models.
- `ebook_builder.py`: EPUB/PDF generation logic.
- `alembic/`: Database migrations.
