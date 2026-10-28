"""Private TPS library, additive and reversible."""
from alembic import op
import sqlalchemy as sa

revision = "20261020_library"
down_revision = "20260912_diarios"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("library_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("path", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=False),
        sa.Column("ocr_pages", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("library_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("library_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("section", sa.Text(), nullable=False, server_default=""),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", sa.LargeBinary(), nullable=False),
        sa.UniqueConstraint("document_id", "page", "content_hash", name="uq_library_chunk_page_hash"))
    op.create_index("ix_library_chunks_document_id", "library_chunks", ["document_id"])
    op.create_index("ix_library_chunks_fts", "library_chunks", [sa.text("to_tsvector('simple', content)")], postgresql_using="gin")
    op.create_table("library_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_library_conversations_user_id", "library_conversations", ["user_id"])
    op.create_table("library_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("library_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("usage_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_library_messages_conversation_id", "library_messages", ["conversation_id"])


def downgrade():
    op.drop_table("library_messages")
    op.drop_table("library_conversations")
    op.drop_table("library_chunks")
    op.drop_table("library_documents")
