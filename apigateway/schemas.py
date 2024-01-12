import re
from dataclasses import dataclass, field
from datetime import datetime

import marshmallow.validate
import marshmallow_dataclass
from flask_marshmallow.sqla import SQLAlchemyAutoSchema, SQLAlchemySchema, auto_field
from marshmallow import ValidationError, fields, validates_schema
from marshmallow.validate import Validator

from apigateway.models import OAuth2Token, User


class PasswordValidator(Validator):
    """Validate a password."""

    PASSWORD_REGEX = re.compile(r"^(?=.*[A-Z])(?=.*\d).+$")

    def __call__(self, value: str) -> str:
        if len(value) < 8:
            raise ValidationError("Password must be at least 8 characters long")

        if not self.PASSWORD_REGEX.match(value):
            raise ValidationError(
                "Password must contain at least one uppercase letter and one digit"
            )

        return value


class UserSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = User
        include_fk = True


@dataclass
class BootstrapGetRequestSchema:
    scope: str = field(default=None)
    ratelimit: float = field(
        default=1.0, metadata={"validate": marshmallow.validate.Range(min=0.0)}
    )
    create_new: bool = field(default=False)
    redirect_uri: str = field(default=None)
    client_name: str = field(default=None)
    expires: datetime = field(default=datetime(2050, 1, 1))
    individual_ratelimits: dict = field(default=None)


class BootstrapGetResponseSchema(SQLAlchemySchema):
    class Meta:
        model = OAuth2Token
        include_fk = True
        include_relationships = True

    access_token = auto_field()
    refresh_token = auto_field()
    expire_in = auto_field("expires_in")
    token_type = fields.Constant("Bearer")
    username = fields.Str(attribute="user.email")
    scopes = auto_field("scope")
    anonymous = fields.Boolean(attribute="user.is_anonymous_bootstrap_user")
    client_id = fields.Str(attribute="client.client_id")
    client_secret = fields.Str(attribute="client.client_secret")
    ratelimit = fields.Float(attribute="client.ratelimit_multiplier")
    client_name = fields.Str(attribute="client.name")
    individual_ratelimits = fields.Dict(
        attribute="client.individual_ratelimit_multipliers", allow_none=True
    )


@dataclass
class UserAuthPostRequestSchema:
    email: str = field(metadata={"validate": marshmallow.validate.Email()})
    password: str = field()


@dataclass
class UserRegisterPostRequestSchema:
    email: str = field(metadata={"validate": marshmallow.validate.Email()})
    password1: str = field(metadata={"validate": PasswordValidator()})
    password2: str = field()
    given_name: str = None
    family_name: str = None

    @validates_schema
    def validate_passwords_equal(self, data, **kwargs):
        if data["password1"] != data["password2"]:
            raise ValidationError("Passwords do not match", field_name="password2")


@dataclass
class ChangePasswordRequestSchema:
    old_password: str = field()
    new_password1: str = field(metadata={"validate": PasswordValidator()})
    new_password2: str = field()

    @validates_schema
    def validate_passwords_equal(self, data, **kwargs):
        if data["new_password1"] != data["new_password2"]:
            raise ValidationError("Passwords do not match", field_name="new_password2")


@dataclass
class ChangeEmailRequestSchema:
    email: str = field(metadata={"validate": marshmallow.validate.Email()})
    password: str = field(metadata={"validate": PasswordValidator()})


@dataclass
class ResetPasswordRequestSchema:
    password1: str = field(metadata={"validate": PasswordValidator()})
    password2: str = field()

    @validates_schema
    def validate_passwords_equal(self, data, **kwargs):
        if data["password1"] != data["password2"]:
            raise ValidationError("Passwords do not match", field_name="password2")


@dataclass
class ClearCacheRequestSchema:
    key: str = field()
    parameters: dict = None


@dataclass
class ClearLimitRequestSchema:
    key: str = field()
    scope: str = ""

    @validates_schema
    def validate_clear_all(self, data, **kwargs):
        if data["key"] == "*" and data["scope"] != "":
            raise ValidationError(
                "Do not provide a scope when clearing ALL limits", field_name="scope"
            )


bootstrap_request = marshmallow_dataclass.class_schema(BootstrapGetRequestSchema)()
bootstrap_response = BootstrapGetResponseSchema()
user_auth_request = marshmallow_dataclass.class_schema(UserAuthPostRequestSchema)()
user_register_request = marshmallow_dataclass.class_schema(UserRegisterPostRequestSchema)()
change_password_request = marshmallow_dataclass.class_schema(ChangePasswordRequestSchema)()
change_email_request = marshmallow_dataclass.class_schema(ChangeEmailRequestSchema)()
reset_password_request = marshmallow_dataclass.class_schema(ResetPasswordRequestSchema)()
clear_cache_request = marshmallow_dataclass.class_schema(ClearCacheRequestSchema)()
clear_limit_request = marshmallow_dataclass.class_schema(ClearLimitRequestSchema)()
