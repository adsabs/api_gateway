"""updating indexes

Revision ID: fc5e2283de94
Revises: 6b45dbb33d43
Create Date: 2025-01-03 10:45:53.583462

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fc5e2283de94"
down_revision: Union[str, None] = "6b45dbb33d43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f("ix_oauth2client_user_id"), "oauth2client", ["user_id"], unique=False)
    op.create_index(op.f("ix_oauth2token_client_id"), "oauth2token", ["client_id"], unique=False)

    op.create_index(op.f("ix_oauth2token_user_id"), "oauth2token", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_oauth2token_is_personal"), "oauth2token", ["is_personal"], unique=False
    )
    op.drop_index(op.f("ix_oauth2token_refresh_token"), table_name="oauth2token")

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_oauth2token_is_personal"), table_name="oauth2token")
    op.drop_index(op.f("ix_oauth2token_client_id"), table_name="oauth2token")
    op.drop_index(op.f("ix_oauth2token_user_id"), table_name="oauth2token")

    op.drop_index(op.f("ix_oauth2client_user_id"), table_name="oauth2client")
    op.create_index(
        op.f("ix_oauth2token_refresh_token"), "oauth2token", ["refresh_token"], unique=False
    )
    # ### end Alembic commands ###
