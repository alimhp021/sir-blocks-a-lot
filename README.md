Database Setup
Before running the application, you need to set up the necessary tables in your PostgreSQL database. Connect to your database (e.g., with psql -U myuser -d telegram_data) and run the following SQL commands:

-- Create the table to store raw messages from Telegram
CREATE TABLE IF NOT EXISTS bare_messages (
id SERIAL PRIMARY KEY,
channel_name VARCHAR(255) NOT NULL,
message_id BIGINT NOT NULL UNIQUE,
message_text TEXT NOT NULL,
message_timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
crawled_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create the table to track the last crawled message ID for each channel
CREATE TABLE IF NOT EXISTS channel_states (
channel_name VARCHAR(255) PRIMARY KEY,
last_message_id BIGINT DEFAULT 0,
updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Grant necessary permissions to your database user (replace 'myuser' if needed)
GRANT ALL PRIVILEGES ON TABLE bare_messages, channel_states TO myuser;
GRANT USAGE, SELECT ON SEQUENCE bare_messages_id_seq TO myuser;
