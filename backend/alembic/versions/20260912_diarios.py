"""Tablas aditivas del reporte diario; compatible con bases creadas por seed."""
from alembic import op
import sqlalchemy as sa

revision = "20260912_diarios"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "diarios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("datos", sa.JSON(), nullable=False),
        sa.Column("estado", sa.String(12), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(50), nullable=False),
        sa.Column("client_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "versiones_diario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("diario_id", sa.String(36), sa.ForeignKey("diarios.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("datos", sa.JSON(), nullable=False),
        sa.Column("png_path", sa.String(255), nullable=False),
        sa.Column("png_sha256", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("generado_por", sa.String(50), nullable=False),
        sa.Column("fecha_generacion", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("diario_id", "version", name="uq_diario_version"),
    )
    op.create_index("ix_versiones_diario_diario_id", "versiones_diario", ["diario_id"])


def downgrade():
    op.drop_table("versiones_diario")
    op.drop_table("diarios")
