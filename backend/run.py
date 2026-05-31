"""StockSnap 应用入口"""
import os
import sys

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

try:
    from dotenv import load_dotenv
    this_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(this_dir, '.env'), override=False)
except Exception:
    pass

from app import create_app

app = create_app()


def main():
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '5000'))
    debug = os.getenv('FLASK_ENV', 'development') == 'development'
    print(f'StockSnap API 启动: http://{host}:{port}')
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    main()
