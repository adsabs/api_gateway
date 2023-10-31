from datetime import datetime
from typing import Tuple
from urllib.parse import urljoin

import requests
from authlib.integrations.flask_oauth2 import current_token
from flask import current_app, request, session
from flask.views import View
from flask_login import current_user, login_required, login_user, logout_user
from flask_restful import Resource, abort
from flask_wtf.csrf import generate_csrf

from apigateway.models import User
from apigateway.schemas import (
    bootstrap_get_request_schema,
    bootstrap_get_response_schema,
    user_auth_post_request_schema,
    user_register_post_request_schema,
)
from apigateway.utils import require_non_anonymous_bootstrap_user


class Bootstrap(Resource):
    def get(self):
        params = bootstrap_get_request_schema.load(request.json)

        if not current_user.is_authenticated:
            bootstrap_user: User = User.query.filter_by(is_anonymous_bootstrap_user=True).first()
            if not login_user(bootstrap_user):
                abort(500, message="Could not login as bootstrap user")

        if current_user.is_anonymous_bootstrap_user and (
            params.scope or params.client_name or params.redirect_uri
        ):
            abort(
                401,
                message="""Sorry, you cant change scope/name/redirect_uri when creating temporary OAuth application""",
            )

        if current_user.is_anonymous_bootstrap_user:
            client_id: str = None
            if "oauth_client" in session:
                client_id = session["oauth_client"]
            elif hasattr(request, "oauth"):
                client_id = request.oauth.client_id

            if client_id:
                client, token = current_app.auth_service.load_client(client_id)

            if not client_id or client.user_id != current_user.get_id():
                client, token = current_app.auth_service.bootstrap_anonymous_user()

            session["oauth_client"] = client.client_id

        else:
            _, token = current_app.auth_service.bootstrap_user(
                params.client_name,
                scope=params.scope,
                ratelimit_multiplier=params.ratelimit,
                individual_ratelimit_multipliers=params.individual_ratelimits,
                expires=params.expires,
                create_client=params.create_new,
            )

        return bootstrap_get_response_schema.dump(token), 200


class UserAuthView(Resource):
    """Implements login and logout functionality"""

    @property
    def method_decorators(self):
        return [current_app.limiter_service.shared_limit("30/120 second")]

    def post(self):
        params = user_auth_post_request_schema.load(request.json)
        with current_app.session_scope() as session:
            user: User = session.query(User).filter_by(email=params.email).first()

            if not user or not user.validate_password(params.password):
                abort(401, message="Invalid username or password")
            if not user.confirmed_at:
                abort(401, message="The account has not been verified")

            if current_user.is_authenticated:
                logout_user()

            login_user(user)

            user.last_login_at = datetime.now()
            user.login_count = user.login_count + 1 if user.login_count else 1

            session.commit()

        return {"message": "Successfully logged in"}, 200


class ProxyView(View):
    """A view for proxying requests to a remote webservice."""

    def __init__(self, deploy_path: str, remote_base_url: str):
        """
        Initializes a ProxyView object.

        Args:
            deploy_path (str): The path to deploy the proxy view.
            remote_base_url (str): The base URL of the remote server to proxy requests to.
        """
        super().__init__()
        self._deploy_path = deploy_path
        self._remote_base_url = remote_base_url
        self._session = requests.Session()

    def dispatch_request(self, **kwargs) -> Tuple[bytes, int]:
        """
        Dispatches the request to the proxy view.

        Returns:
            Tuple[bytes, int]: A tuple containing the content of the response and the status code.
        """
        return self._proxy_request()

    def _proxy_request(self) -> Tuple[bytes, int]:
        """
        Proxies the request to the remote server.

        Returns:
            Tuple[bytes, int]: A tuple containing the content of the response and the status code.
        """
        try:
            remote_url = self._construct_remote_url()
            http_method_func = getattr(self._session, request.method.lower())

            current_app.logger.debug(
                "Proxying %s request to %s", request.method.upper(), remote_url
            )

            response: requests.Response = http_method_func(
                remote_url, data=request.get_data(), headers=request.headers
            )
            return response.content, response.status_code
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            return b"504 Gateway Timeout", 504

    def _construct_remote_url(self) -> str:
        """
        Constructs the URL of the remote server.

        Returns:
            str: The URL of the remote server.
        """
        path = request.full_path.replace(self._deploy_path, "", 1)
        path = path[1:] if path.startswith("/") else path
        return urljoin(self._remote_base_url, path)


class CSRFView(Resource):
    """
    Returns a csrf token
    """

    @property
    def method_decorators(self):
        return [current_app.limiter_service.shared_limit("50/600 second")]

    def get(self):
        """
        Returns a csrf token
        """
        return {"csrf": generate_csrf()}


class StatusView(Resource):
    """A resource that provides a health check endpoint for the API Gateway"""

    def get(self):
        return {"app": current_app.name, "status": "online"}, 200


class OAuthProtectedView(Resource):
    """A resource that checks whether the request is authorized with OAuth2.0."""

    @property
    def method_decorators(self):
        return [current_app.auth_service.require_oauth()]

    def get(self):
        return {"app": current_app.name, "oauth": current_token.user.email}


class DeleteAccountView(Resource):
    """A Resource that allows a logged in user to delete their account"""

    decorators = [login_required, require_non_anonymous_bootstrap_user]

    def post(self):
        with current_app.session_scope() as session:
            user: User = session.query(User).filter_by(fs_uniquifier=current_user.get_id()).first()
            logout_user()
            session.delete(user)
            session.commit()

        return {"message": "success"}, 200


class UserRegistrationView(Resource):
    """A Resource for user registration.

    This resource handles user registration requests. It checks if the user is already registered
    and creates a new user if not"""

    @property
    def method_decorators(self):
        return [current_app.limiter_service.shared_limit("50/600 second")]

    def post(self):
        params = user_register_post_request_schema.load(request.json)

        user = User.query.filter_by(email=params.email).first()
        if user is not None:
            error_message = f"An account is already registered for {params.email}"
            return {"error": error_message}, 409

        try:
            current_app.security_service.create_user(
                email=params.email,
                password=params.password1,
                registered_at=datetime.now(),
                login_count=0,
            )
            return {"message": "success"}, 200
        except ValueError as e:
            return {"error": str(e)}, 400


class LogoutView(Resource):
    """Logs out the current user"""

    def post(self):
        logout_user()
        return {"message": "success"}, 200
