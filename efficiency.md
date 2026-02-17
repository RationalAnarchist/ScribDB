# Efficiency and Low-Power Device Optimization

Scrollarr can be optimized for low-power devices like Raspberry Pi. Follow these steps to improve performance and reduce resource usage.

## 1. Database Optimization

### Enable WAL Mode (Write-Ahead Logging) for SQLite
SQLite's default journaling mode can be slow and cause locking issues with concurrent accesses (web server + background jobs). WAL mode improves concurrency.

**Action:**
Run the following Python script once to enable WAL mode:

```python
import sqlite3
conn = sqlite3.connect('library.db')
conn.execute('PRAGMA journal_mode=WAL;')
conn.close()
```

## 2. Configuration Tuning

Edit `config.json` (or use the Settings page) to reduce the frequency of background tasks.

**Recommended Settings:**
*   `update_interval_hours`: Increase to `4` or `6` (default is 1). This reduces how often the system checks for new chapters.
*   `worker_sleep_min`: Increase to `60` (seconds).
*   `worker_sleep_max`: Increase to `120`.

## 3. System Level

### Swap Space
Compiling large EPUBs requires loading chapter content into memory. On a Pi with 1GB or 2GB RAM, this can cause crashes.
**Action:** Increase swap size to at least 2GB.
```bash
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Set CONF_SWAPSIZE=2048
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

### Process Management
Run the application using a process manager like `systemd` (as described in README) rather than just a shell background process.

## 4. Application Improvements (Developers)

*   **Streaming Ebook Generation:** The current `EbookBuilder` loads all chapters into memory. Refactoring this to write chapters to the zip file incrementally would significantly reduce memory usage.
*   **Staggered Updates:** Instead of checking all stories at once every X hours, the scheduler could spread checks over the interval.
