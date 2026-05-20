import logging
from sqlalchemy import text
from shared_core.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('alter_db')

def alter_database():
    sql1 = 'ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS draft_parameters JSONB;'
    sql2 = 'ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS final_parameters JSONB;'
    
    logger.info('Connecting to database and executing ALTER statements...')
    with engine.connect() as conn:
        # PostgreSQL supports ADD COLUMN IF NOT EXISTS natively in version 9.6+
        conn.execute(text(sql1))
        conn.execute(text(sql2))
        # Commit transaction explicitly if autocommit is not on
        conn.execute(text('COMMIT;'))
        
    logger.info('Database schema updated successfully!')

if __name__ == '__main__':
    alter_database()
