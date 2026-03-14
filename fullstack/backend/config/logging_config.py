from pathlib import Path


def resolve_log_dir(base_dir: Path, raw_value: str | None) -> Path:
    if not raw_value:
        return base_dir / "logs"

    candidate = Path(raw_value)
    if candidate.is_absolute():
        return candidate

    return base_dir / candidate


def build_logging_config(
    *,
    level: str,
    log_dir: Path,
    rotation_when: str,
    rotation_interval: int,
    backup_count: int,
) -> dict[str, object]:
    log_dir.mkdir(parents=True, exist_ok=True)

    backend_log_file = log_dir / "backend.log"
    backend_error_log_file = log_dir / "backend-error.log"

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "[%(asctime)s] %(levelname)s %(name)s %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
            },
            "backend_file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "formatter": "standard",
                "filename": str(backend_log_file),
                "when": rotation_when,
                "interval": rotation_interval,
                "backupCount": backup_count,
                "encoding": "utf-8",
            },
            "backend_error_file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "formatter": "standard",
                "filename": str(backend_error_log_file),
                "when": rotation_when,
                "interval": rotation_interval,
                "backupCount": backup_count,
                "encoding": "utf-8",
                "level": "ERROR",
            },
        },
        "loggers": {
            "django": {
                "handlers": ["console", "backend_file", "backend_error_file"],
                "level": level,
                "propagate": False,
            },
            "celery": {
                "handlers": ["console", "backend_file", "backend_error_file"],
                "level": level,
                "propagate": False,
            },
            "apps": {
                "handlers": ["console", "backend_file", "backend_error_file"],
                "level": level,
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["console", "backend_file", "backend_error_file"],
            "level": level,
        },
    }
