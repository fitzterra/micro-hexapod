"""
Base webserver.

This module instantiates the base webserver app and all static file serving.
"""
import gc

from lib.microdot_asyncio import Microdot, send_file
from lib.microdot_cors import CORS

import ulogging as logging

# The main web app. On main app startup in main.py, after the hexapod instance has been
# created, and this web app has been imported, the hexapod instance will be
# added to the web app on the hexapod attribute.
# This will allow the web app to get access to the hexapod via the attribute:
# `request.app.hexapod` in all request handlers.
app = Microdot()
CORS(app, allowed_origins='*', allow_credentials=True)

# By default the static files will be gzipped when being served from the MCU,
# but when running from local for testing or rapid development, this will not
# be the case. When running locally via the simulator, the main startup code
# will set this to False to ensure the correct headers are sent to the browser
# for static files.
GZIPPED_STATIC = True

def staticFile(path, content_type=None, gzipped=True):
    """
    General function returning static files and ensuring the content type is
    set correctly.

    All static files are also expected to be gzipped, so we force the
    Content-Encoding header to gzip here.

    Args:
        path (str): full path to the static file. The content type will be set
            based on the file name extension, so make sure the static files
            have and extension that can be used to derive the content type.
        content_type (str): The `Content-Type` header to use in the response.
            If omitted, it is generated automatically from the file extension.
        gzipped (bool): If the file being sent is gzipped set this to True to set
            the `Content-Encoding` header to gzip. This is the default since
            all static files are gzipped, although the file name does not have
            .gz or similar extension.
            For files that are not gzipped, set this to False.

    Returns:
        A Response object ready to be returned to the web server.
    """
    gc.collect()
    # Call Microdot's send_file to create the Response object for the file.
    stat_f = send_file(path, content_type=content_type)
    if gzipped:
        stat_f.headers['Content-Encoding'] = 'gzip'
    return stat_f

@app.route('/')
async def index(request):
    """
    Web interface main entry point. We simply serve the index.html from here.
    """
    # pylint: disable=unused-argument
    gc.collect()
    logging.debug("Web request: index")
    return staticFile('static/index.html', gzipped=GZIPPED_STATIC)

@app.route('/static/<stat_file>')
async def static(request, stat_file):
    """
    Static files handler
    """
    # pylint: disable=unused-argument
    logging.debug("Web request: static file: %s", stat_file)
    # Images are never gzipped
    if stat_file.endswith('.png') or stat_file.endswith('.jpg'):
        gzipped = False
    else:
        gzipped = GZIPPED_STATIC

    gc.collect()
    return staticFile(f'static/{stat_file}', gzipped=gzipped)

async def runserver(host='0.0.0.0', port=80, debug=True):
    """
    Start the webserver.
    """
    logging.info("Starting web server on %s:%s", host, port)
    await app.start_server(host=host, port=port, debug=debug)
