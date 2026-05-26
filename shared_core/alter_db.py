import logging
from sqlalchemy import text
from shared_core.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('alter_db')

def alter_database():
    sql1 = 'ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS draft_parameters JSONB;'
    sql2 = 'ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS final_parameters JSONB;'
    sql3 = 'ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS ai_metadata JSONB;'
    sql4 = 'ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS tmcp_source_config JSONB;'
    sql5 = 'ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS draft_variants JSONB;'
    
    sql_create_folders = """
    CREATE TABLE IF NOT EXISTS media_folders (
        id VARCHAR PRIMARY KEY,
        user_id VARCHAR REFERENCES users(id) ON DELETE CASCADE,
        name VARCHAR NOT NULL,
        parent_id VARCHAR REFERENCES media_folders(id) ON DELETE CASCADE,
        is_job_folder BOOLEAN DEFAULT FALSE,
        job_id INTEGER REFERENCES video_jobs(id) ON DELETE SET NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE
    );
    """
    
    sql_asset_display = "ALTER TABLE assets ADD COLUMN IF NOT EXISTS display_name VARCHAR NOT NULL DEFAULT '';"
    sql_asset_folder = "ALTER TABLE assets ADD COLUMN IF NOT EXISTS folder_id VARCHAR REFERENCES media_folders(id) ON DELETE SET NULL;"
    sql_asset_source = "ALTER TABLE assets ADD COLUMN IF NOT EXISTS source VARCHAR NOT NULL DEFAULT 'upload';"
    
    sql_job_folder = "ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS folder_id VARCHAR REFERENCES media_folders(id) ON DELETE SET NULL;"
    sql_user_llm = "ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_preferences JSONB;"
    
    # agent_logs upgrade
    sql_agent_log_job = "ALTER TABLE agent_logs ADD COLUMN IF NOT EXISTS job_id INTEGER REFERENCES video_jobs(id) ON DELETE CASCADE;"
    sql_agent_log_node = "ALTER TABLE agent_logs ADD COLUMN IF NOT EXISTS node_name VARCHAR;"
    sql_agent_log_drop_session_not_null = "ALTER TABLE agent_logs ALTER COLUMN session_id DROP NOT NULL;"
    sql_agent_log_drop_step_not_null = "ALTER TABLE agent_logs ALTER COLUMN step DROP NOT NULL;"
    
    logger.info('Connecting to database and executing ALTER statements...')
    with engine.connect() as conn:
        # PostgreSQL supports ADD COLUMN IF NOT EXISTS natively in version 9.6+
        conn.execute(text(sql1))
        conn.execute(text(sql2))
        conn.execute(text(sql3))
        conn.execute(text(sql4))
        conn.execute(text(sql5))
        
        logger.info('Creating media_folders table if not exists...')
        conn.execute(text(sql_create_folders))
        
        logger.info('Altering assets table...')
        conn.execute(text(sql_asset_display))
        conn.execute(text(sql_asset_folder))
        conn.execute(text(sql_asset_source))
        
        logger.info('Altering video_jobs table...')
        conn.execute(text(sql_job_folder))

        logger.info('Altering users table...')
        conn.execute(text(sql_user_llm))

        logger.info('Upgrading agent_logs table...')
        try:
            conn.execute(text(sql_agent_log_job))
            conn.execute(text(sql_agent_log_node))
            conn.execute(text(sql_agent_log_drop_session_not_null))
            conn.execute(text(sql_agent_log_drop_step_not_null))
        except Exception as e:
            logger.warning(f"Error upgrading agent_logs table (possibly SQLite or already upgraded): {e}")
        
        # Commit transaction explicitly if autocommit is not on
        conn.execute(text('COMMIT;'))
        
    logger.info('Database schema updated successfully!')

if __name__ == '__main__':
    alter_database()
