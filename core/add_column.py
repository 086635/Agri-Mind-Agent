from sqlalchemy import create_engine, text

engine = create_engine('postgresql://postgres:Ysw%4088516251@localhost:5432/agri_ai')
with engine.connect() as conn:
    conn.execute(text("ALTER TABLE chat_message_records ADD COLUMN IF NOT EXISTS chat_mode VARCHAR(16) DEFAULT 'expert'"))
    conn.commit()
    print('OK - chat_mode column added to chat_message_records table')
