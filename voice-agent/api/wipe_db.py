"""
Database Wipe Script.
Drops all tables from the public schema dynamically.
"""

import asyncio
import logging
import sys
import os

# Adjust path to import database module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import database

# Setup console logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("voice-agent.api.wipe_db")


async def wipe_db() -> None:
    logger.info("Connecting to database...")
    await database.init_pool()
    
    try:
        logger.warning("Executing DROP TABLES CASCADE query...")
        
        # Loop dynamically through all public tables and drop them CASCADE
        drop_tables_sql = """
        DO $$ DECLARE
            r RECORD;
        BEGIN
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
            END LOOP;
        END $$;
        """
        
        if database.pool is None:
            logger.critical("Database pool not initialized. Aborting.")
            sys.exit(1)
            
        async with database.pool.acquire() as conn:
            await conn.execute(drop_tables_sql)
            
        logger.info("All tables dropped successfully!")
        
    except Exception as e:
        logger.exception(f"Database wipe failed: {e}")
        sys.exit(1)
    finally:
        await database.close_pool()


if __name__ == "__main__":
    asyncio.run(wipe_db())
