"""usuarios y documentos

Revision ID: 0001
Revises:
Create Date: 2026-10-31
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("es_admin", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email"),
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "documentos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("titulo", sa.String(200), nullable=False),
        sa.Column("contenido", sa.JSON(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_documentos_usuario_id", "documentos", ["usuario_id"])


def downgrade() -> None:
    op.drop_table("documentos")
    op.drop_table("usuarios")
