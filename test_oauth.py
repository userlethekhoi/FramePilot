import yt_dlp
import sys
import threading

class MyLogger(object):
    def debug(self, msg):
        print(f"[DEBUG] {msg}")
    def warning(self, msg):
        print(f"[WARNING] {msg}")
    def error(self, msg):
        print(f"[ERROR] {msg}")

def test_oauth():
    ydl_opts = {
        'logger': MyLogger(),
        'auth_type': 'oauth2',
        'quiet': False
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Stop after 5 seconds to prevent hanging
        timer = threading.Timer(5.0, lambda: sys.exit(0))
        timer.start()
        try:
            ydl.extract_info("https://www.youtube.com/watch?v=BaW_jenozKc", download=False)
        except SystemExit:
            pass
        timer.cancel()

if __name__ == "__main__":
    test_oauth()
