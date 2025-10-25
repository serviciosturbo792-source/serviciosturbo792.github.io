# Wrapper created to allow running with `python app.py`.
# It imports server.py and runs the Flask app defined there.
import importlib, sys
try:
    import server
except Exception as e:
    print('Error importing server.py:', e, file=sys.stderr)
    raise
# If server defines 'app', run it
if hasattr(server, 'app'):
    app = server.app
elif hasattr(server, 'create_app'):
    app = server.create_app()
else:
    # Try to find a variable named 'application'
    app = getattr(server, 'application', None)
if app is None:
    raise RuntimeError('server.py does not expose a Flask app variable named app or application.')
if __name__ == '__main__':
    # respect debug/run settings in server.py if any; default to debug=True on 127.0.0.1:5000
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        print('Error running app:', e, file=sys.stderr)
        raise
