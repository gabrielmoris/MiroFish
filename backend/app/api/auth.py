"""
Login endpoints (optional; see app/utils/auth.py)
"""

import logging
import time

from flask import jsonify, request

from . import auth_bp
from ..utils import auth as auth_utils
from ..utils.locale import t


logger = logging.getLogger("mirofish.auth")


@auth_bp.route('/status', methods=['GET'])
def auth_status():
    """Whether login is required, and whether the sent token is valid."""
    enabled = auth_utils.is_auth_enabled()
    authenticated = (not enabled) or auth_utils.verify_token(
        auth_utils.token_from_request(request)
    )
    return jsonify({
        "success": True,
        "data": {"enabled": enabled, "authenticated": authenticated},
    })


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Exchange the configured username and password for a bearer token.

    Request (JSON): {"username": "...", "password": "..."}
    Response: {"success": true, "data": {"token": "...", "expires_in": 604800}}
    """
    if not auth_utils.is_auth_enabled():
        return jsonify({
            "success": True,
            "data": {"enabled": False, "token": None},
        })

    data = request.get_json(silent=True) or {}
    if not auth_utils.check_credentials(data.get('username'), data.get('password')):
        # A fixed delay makes guessing slow without any per-client state.
        time.sleep(auth_utils.FAILED_LOGIN_DELAY_SECONDS)
        logger.warning("Failed login attempt from %s", request.remote_addr)
        return jsonify({
            "success": False,
            "error": t('api.invalidCredentials'),
        }), 401

    return jsonify({
        "success": True,
        "data": {
            "enabled": True,
            "token": auth_utils.issue_token(),
            "expires_in": auth_utils.TOKEN_MAX_AGE_SECONDS,
        },
    })
