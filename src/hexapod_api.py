"""
Hexapod Web API module.

This module imports the web app from the webserver module and then extends the
main app with all the API endpoints exposed for the Hexapod.
"""
from webserver import gc, app, logging
from webserver import runserver # Convenience import for main @pylint: disable=unused-import
import ws_controller

#pylint: disable=broad-except

@app.before_request
async def requestHook(request):
    """
    Hook that is called before every request.

    This is helpful to log the request details for all requests.
    """
    logging.info(
        "HTTP: %s %s, Args: %s, JSON: %s",
        request.method,
        request.path,
        request.args,
        request.json
    )
    gc.collect()

@app.route('/get_params')
async def getParams(request):
    """
    Endpoint to return the current hexapod parameters and values as a JSON
    structure.

    GET Response:
    {
        "servo": {
            "mid": {
                "amplitude": (int),
                "phase_shift": (int),
                "trim": (int)
            },
            "left": {
                "amplitude": (int),
                "phase_shift": (int),
                "trim": (int)
            },
            "right": {
                "amplitude": (int),
                "phase_shift": (int),
                "trim": (int)
            }
        },
        "paused": (bool),
        "period": (int),
        "speed": (float),   # Period as a % of min and max periods
    }
    """
    return request.app.hexapod.params
