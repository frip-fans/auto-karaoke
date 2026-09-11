"""Run the browser regression with an isolated synthetic library and ephemeral port."""
import os
from pathlib import Path
import subprocess
import tempfile
import threading

from werkzeug.serving import WSGIRequestHandler, make_server
from test_server import create_app, fixture


class QuietHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass


def main():
    with tempfile.TemporaryDirectory(prefix='karaoke-browser-') as directory:
        root = Path(directory)
        fixture(root / 'Synthetic.mp4')
        app = create_app(root)
        server = make_server('127.0.0.1', 0, app, threaded=True, request_handler=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = {**os.environ, 'KARAOKE_TEST_URL': f'http://127.0.0.1:{server.server_port}'}
            subprocess.run(['node', str(Path(__file__).with_name('browser.cjs'))],
                           env=env, check=True, timeout=90)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            app.extensions['karaoke_pool'].shutdown(wait=True)


if __name__ == '__main__':
    main()
