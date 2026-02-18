import json
import os
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    _instance = None
    CONFIG_FILE = "config/config.json"
    DEFAULT_CONFIG = {
        "download_path": "saved_stories",
        "min_delay": 2.0,
        "max_delay": 5.0,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "update_interval_hours": 1,
        "worker_sleep_min": 30.0,
        "worker_sleep_max": 60.0,
        "database_url": "sqlite:///library.db",
        "log_level": "INFO",
        "library_path": "library",
        "story_folder_format": "{Title} ({Id})",
        "chapter_file_format": "{Index} - {Title}",
        "volume_folder_format": "Volume {Volume}",
        "compiled_filename_pattern": "{Title} - {Volume}"
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.config = cls._instance.load_config()
        return cls._instance

    def load_config(self):
        """Loads configuration from file or creates default if missing."""
        config = self.DEFAULT_CONFIG.copy()

        if not os.path.exists(self.CONFIG_FILE):
            logger.info(f"Config file not found. Creating default at {self.CONFIG_FILE}")
            self.save_config(config)
            return config

        try:
            with open(self.CONFIG_FILE, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)

            # Migration: filename_pattern -> compiled_filename_pattern
            if 'filename_pattern' in file_config and 'compiled_filename_pattern' not in file_config:
                 config['compiled_filename_pattern'] = file_config['filename_pattern']

        except Exception as e:
            logger.error(f"Failed to load config file: {e}. Using defaults.")

        # Override with Environment Variables
        for key, default_value in self.DEFAULT_CONFIG.items():
            env_key = f"SCROLLARR_{key.upper()}"
            env_val = os.getenv(env_key)
            if env_val is not None:
                # Type conversion
                if isinstance(default_value, bool):
                     config[key] = env_val.lower() in ('true', '1', 'yes')
                elif isinstance(default_value, int):
                    try:
                        config[key] = int(env_val)
                    except ValueError:
                        pass
                elif isinstance(default_value, float):
                    try:
                        config[key] = float(env_val)
                    except ValueError:
                        pass
                else:
                    config[key] = env_val

        return config

    def save_config(self, config=None):
        """Saves configuration to file."""
        if config is None:
            config = self.config

        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
            self.config = config
            logger.info("Configuration saved.")
        except Exception as e:
            logger.error(f"Failed to save config file: {e}")

    def get(self, key, default=None):
        """Gets a configuration value."""
        return self.config.get(key, default)

    def set(self, key, value):
        """Sets a configuration value and saves to file."""
        self.config[key] = value
        self.save_config()

# Global instance
config_manager = ConfigManager()
