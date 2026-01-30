"""add_global_jump_indexes

Revision ID: g1h2i3j4k5l6
Revises: f9a0b1c2d3e4
Create Date: 2026-01-30 14:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g1h2i3j4k5l6"
down_revision: str | Sequence[str] | None = "f9a0b1c2d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Add composite indexes for global jump navigation query optimization.
    These indexes support cross-video artifact search with efficient
    timeline ordering based on file_created_at.

    Requirements: 9.2, 9.3, 9.5
    """
    # Index for global jump object label queries
    # Optimizes: SELECT ... FROM object_labels WHERE label = ?
    # ORDER BY asset_id, start_ms
    # Supports requirement 9.2: composite index on (label, asset_id, start_ms)
    op.create_index(
        "idx_object_labels_label_global",
        "object_labels",
        ["label", "asset_id", "start_ms"],
    )

    # Index for global jump face cluster queries
    # Optimizes: SELECT ... FROM face_clusters WHERE cluster_id = ?
    # ORDER BY asset_id, start_ms
    # Supports requirement 9.3: composite index on (cluster_id, asset_id, start_ms)
    op.create_index(
        "idx_face_clusters_cluster_global",
        "face_clusters",
        ["cluster_id", "asset_id", "start_ms"],
    )

    # Index for global timeline ordering on videos table
    # Optimizes: ORDER BY file_created_at, video_id for cross-video navigation
    # Supports requirement 9.5: composite index on (file_created_at, video_id)
    op.create_index(
        "idx_videos_created_at_id",
        "videos",
        ["file_created_at", "video_id"],
    )


def downgrade() -> None:
    """Downgrade schema.

    Remove composite indexes for global jump navigation.
    """
    # Drop indexes in reverse order
    op.drop_index("idx_videos_created_at_id", "videos")
    op.drop_index("idx_face_clusters_cluster_global", "face_clusters")
    op.drop_index("idx_object_labels_label_global", "object_labels")
