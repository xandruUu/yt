from __future__ import annotations

from sqlalchemy import Engine, inspect, text

RUNTIME_COLUMNS: dict[str, dict[str, str]] = {
    "character_profiles": {
        "family_id": "INTEGER",
        "main_image_path": "TEXT",
        "main_thumbnail_path": "TEXT",
        "must_preserve_json": "TEXT NOT NULL DEFAULT '[]'",
        "must_avoid_json": "TEXT NOT NULL DEFAULT '[]'",
        "prompt_fragment": "TEXT NOT NULL DEFAULT ''",
        "negative_prompt_fragment": "TEXT NOT NULL DEFAULT ''",
        "obsidian_note_path": "TEXT",
        "status": "VARCHAR(48) NOT NULL DEFAULT 'active'",
    },
    "voiceover_jobs": {
        "video_project_id": "INTEGER",
        "script_draft_id": "INTEGER",
        "model_id": "VARCHAR(160)",
        "text": "TEXT NOT NULL DEFAULT ''",
        "text_hash": "VARCHAR(128)",
        "output_path": "TEXT",
        "character_count": "INTEGER NOT NULL DEFAULT 0",
        "external_request_id": "VARCHAR(240)",
        "cost_event_id": "INTEGER",
    },
    "subtitle_tracks": {
        "video_project_id": "INTEGER",
        "script_draft_id": "INTEGER",
    },
    "generated_clips": {
        "prompt_pack_id": "INTEGER",
        "external_job_id": "VARCHAR(240)",
        "asset_type": "VARCHAR(64) NOT NULL DEFAULT 'video'",
        "license_type": "VARCHAR(120)",
        "commercial_use_confirmed": "BOOLEAN NOT NULL DEFAULT FALSE",
        "notes": "TEXT",
        "metadata_json": "TEXT",
    },
    "higgsfield_jobs": {
        "model_name": "VARCHAR(120)",
        "requested_duration_seconds": "FLOAT",
        "requested_aspect_ratio": "VARCHAR(24)",
        "cost_estimate_credits": "FLOAT",
        "confirmed_credits": "BOOLEAN NOT NULL DEFAULT FALSE",
        "cli_command_json": "TEXT",
        "cli_response_json": "TEXT",
        "result_json": "TEXT",
        "output_url": "TEXT",
        "output_path": "TEXT",
        "submitted_at": "TIMESTAMP",
        "completed_at": "TIMESTAMP",
    },
    "render_jobs": {
        "metadata_json": "TEXT",
        "approved": "BOOLEAN NOT NULL DEFAULT FALSE",
        "review_notes": "TEXT",
        "reviewed_at": "TIMESTAMP",
    },
}


def ensure_runtime_schema(engine: Engine) -> None:
    if engine.dialect.name not in {"sqlite", "postgresql"}:
        return

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table_name, columns in RUNTIME_COLUMNS.items():
            if table_name not in existing_tables:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, definition in columns.items():
                if column_name in existing_columns:
                    continue
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
                )
