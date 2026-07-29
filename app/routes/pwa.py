from flask import Blueprint, send_from_directory, make_response, current_app

pwa_bp = Blueprint('pwa', __name__)


@pwa_bp.route('/manifest.json')
def pwa_manifest():
    return send_from_directory(
        current_app.static_folder, 'manifest.json', mimetype='application/manifest+json'
    )


@pwa_bp.route('/sw.js')
def pwa_service_worker():
    resp = make_response(send_from_directory(current_app.static_folder, 'sw.js'))
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp
