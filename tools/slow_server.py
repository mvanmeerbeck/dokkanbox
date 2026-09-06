"""A deliberately slow static server: the only way to see what a page shows while it waits.

Chrome headless makes the network instant, so the order in which things appear on a real
connection is invisible from a normal capture. Serving at a fixed rate puts it back.
"""
import http.server, os, sys, time

RATE = float(sys.argv[2]) if len(sys.argv) > 2 else 2e6      # octets par seconde
CHUNK = 16384


class Slow(http.server.SimpleHTTPRequestHandler):
    def copyfile(self, src, dst):
        while True:
            buf = src.read(CHUNK)
            if not buf:
                break
            dst.write(buf)
            try:
                dst.flush()
            except Exception:
                return
            time.sleep(len(buf) / RATE)

    def log_message(self, fmt, *a):
        sys.stderr.write('%.3f %s\n' % (time.time() - T0, fmt % a))


T0 = time.time()
http.server.ThreadingHTTPServer(('', int(sys.argv[1])), Slow).serve_forever()
