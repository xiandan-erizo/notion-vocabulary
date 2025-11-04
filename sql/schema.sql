-- Schema definition for the Notion Vocabulary project.

CREATE TABLE IF NOT EXISTS words (
    id INT AUTO_INCREMENT PRIMARY KEY,
    word VARCHAR(255) NOT NULL UNIQUE,
    frequency INT DEFAULT 1,
    status ENUM('unmastered', 'learning', 'mastered') NOT NULL DEFAULT 'unmastered',
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_word (word),
    INDEX idx_frequency (frequency),
    INDEX idx_status (status)
);

CREATE TABLE IF NOT EXISTS contexts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    word_id INT NOT NULL,
    sentence TEXT NOT NULL,
    CONSTRAINT fk_contexts_words FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE,
    UNIQUE KEY uk_word_sentence (word_id, sentence(255))
);
