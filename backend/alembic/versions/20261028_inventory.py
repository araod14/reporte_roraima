"""Index material inventory for the private library."""
from alembic import op
import sqlalchemy as sa

revision = "20261028_inventory"
down_revision = "20261020_library"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("inventory_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("inventory_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sheet", sa.String(100), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("part_number", sa.Text(), nullable=False),
        sa.Column("sap_pz", sa.Text(), nullable=False),
        sa.Column("sap_pdvsa", sa.Text(), nullable=False),
        sa.Column("manufacturer", sa.Text(), nullable=False),
        sa.Column("quantity", sa.String(60), nullable=False),
        sa.Column("equipment", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("shelf", sa.Text(), nullable=False),
        sa.UniqueConstraint("sheet", "row_number", name="uq_inventory_sheet_row"))
    op.create_index("ix_inventory_items_part_number", "inventory_items", ["part_number"])
    op.create_index("ix_inventory_items_sap_pz", "inventory_items", ["sap_pz"])
    op.create_index("ix_inventory_items_sap_pdvsa", "inventory_items", ["sap_pdvsa"])


def downgrade():
    op.drop_table("inventory_items")
    op.drop_table("inventory_state")
