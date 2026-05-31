"""日志工具"""
import logging, os

def setup_logger():
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logging.basicConfig(level=getattr(logging, log_level.upper()),
                        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
