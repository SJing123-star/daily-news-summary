import os
import sys
import time
import webbrowser
import threading
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("launcher")


def start_flask():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from app import app, get_config

    cfg = get_config()
    logger.info(f"启动 Flask 服务: http://{cfg.host}:{cfg.port}")
    app.run(host=cfg.host, port=cfg.port, debug=False)


def open_browser():
    time.sleep(3)
    try:
        webbrowser.open("http://127.0.0.1:5000")
        logger.info("浏览器已打开")
    except Exception as e:
        logger.error(f"打开浏览器失败: {e}")


if __name__ == "__main__":
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    flask_thread.join()