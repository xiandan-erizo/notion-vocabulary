好的，使用MySQL数据库是一个非常好的选择，这能让系统更健壮、更持久化，也便于未来进行更复杂的数据查询。

我们来更新一下文档，将数据存储层从“键值对”改为“MySQL”。

-----

## 📄 智能单词本系统 - 需求与设计文档 (MySQL版)

### 1\. 项目目标

(与之前相同) 本项目旨在创建一个智能的、自动化的单词本系统...

### 2\. 核心功能需求

(与之前相同)

1.  **自动化词汇处理:** ...
2.  **智能单词本 (Update or Create):** ...
3.  **高频词统计:** ...
4.  **学习状态管理:** ...
5.  **上下文例句收集 (Context):** ...

### 3\. 技术选型与实现

  * **编程语言:** Python
  * **核心NLP库:** **spaCy**
      * (用途与之前相同: 分词、停用词过滤、标点过滤、词形还原)
  * **数据库:** **MySQL**
      * **理由:** 提供持久化存储、支持事务、数据结构清晰、便于未来扩展查询和统计。
      * **Python连接库:** 将使用如 `mysql-connector-python` 或 `SQLAlchemy` 库来连接和操作数据库。

-----

### 4\. 数据库 Schema 设计 (MySQL)

为了高效地存储数据并避免冗余，我们将设计两个核心表：一个用于存储单词条目 (Words)，另一个用于存储例句 (Contexts)。

#### 表 1: `words` (单词主表)

这个表存储每个核心词汇的独一无二的条目及其统计数据。

```sql
CREATE TABLE words (
    id INT AUTO_INCREMENT PRIMARY KEY,
    word VARCHAR(255) NOT NULL UNIQUE,  -- 单词本身 (词形还原后), 设为 UNIQUE 确保唯一性
    frequency INT DEFAULT 1,            -- 出现总次数
    status ENUM('unmastered', 'learning', 'mastered') NOT NULL DEFAULT 'unmastered', -- 学习状态
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 首次添加时间
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, -- 最近更新时间
    INDEX(word),  -- 为高频查询的 word 字段添加索引
    INDEX(frequency), -- 为按频率排序添加索引
    INDEX(status)     -- 为按状态查询添加索引
);
```

#### 表 2: `contexts` (例句表)

这个表通过外键关联到 `words` 表，存储每个单词出现过的所有例句。

```sql
CREATE TABLE contexts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    word_id INT NOT NULL,                  -- 关联到 words 表的 ID
    sentence TEXT NOT NULL,                -- 完整的例句
    
    -- 设置外键约束，当 words 表中的词被删除时，相关例句也一并删除
    FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE,
    
    -- (可选) 我们可以添加一个唯一约束防止完全相同的例句被重复添加给同一个词
    UNIQUE KEY uk_word_sentence (word_id, sentence(255)) 
    -- 注意: TEXT 字段做 UNIQUE 索引时必须指定前缀长度
);
```

-----

### 5\. 核心工作流程 (Workflow)

当用户输入一段字幕时，系统将执行以下步骤：

1.  **(准备阶段)**:

      * 加载 `spaCy` 模型 (`nlp = spacy.load(...)`)。
      * 建立到 MySQL 数据库的连接。

2.  **(输入与处理)**:

      * `text = "I was looking at different perspectives. ..."`
      * `doc = nlp(text)`

3.  **(遍历、过滤、提取)**:

      * (与之前相同) 遍历 `token`，跳过停用词和标点。
      * 提取 `core_word = token.lemma_` (如 "perspective")。
      * 提取 `context_sentence = token.sent.text` (如 "I was looking at different perspectives.")。

4.  **(数据库操作: Update or Create)**:

      * 系统使用 `core_word` (如 "perspective") 作为 Key 查询数据库。

      * **A. 查找单词 (SELECT):**

        ```sql
        SELECT id, frequency FROM words WHERE word = %s;
        ```

        (使用 `core_word` 作为参数)

      * **B. 判断结果:**

          * **情况一：[Create] 词不存在 (SELECT 结果为空)**

              * **步骤 B1: 插入新单词 (INSERT to words):**
                ```sql
                INSERT INTO words (word, frequency, status, first_seen, last_seen) 
                VALUES (%s, 1, 'unmastered', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                ```
              * 获取刚插入的 `new_word_id`。
              * **步骤 B2: 插入新例句 (INSERT to contexts):**
                ```sql
                INSERT INTO contexts (word_id, sentence) VALUES (%s, %s);
                ```
                (使用 `new_word_id` 和 `context_sentence` 作为参数)

          * **情况二：[Update] 词已存在 (SELECT 返回了 id 和 frequency)**

              * **步骤 C1: 更新词频 (UPDATE words):**
                ```sql
                UPDATE words SET frequency = frequency + 1, last_seen = CURRENT_TIMESTAMP
                WHERE id = %s;
                ```
                (使用查到的 `id` 作为参数)
              * **步骤 C2: 尝试插入新例句 (INSERT to contexts):**
                ```sql
                -- 使用 INSERT IGNORE (或 ON DUPLICATE KEY UPDATE) 来自动处理重复的例句
                INSERT IGNORE INTO contexts (word_id, sentence) VALUES (%s, %s);
                ```
                (使用查到的 `id` 和 `context_sentence` 作为参数。`INSERT IGNORE` 会在触发 `UNIQUE` 约束（例句已存在）时自动跳过，不会报错。)

5.  **(结束)**: 提交数据库事务 (Transaction Commit)。

-----

这个基于 MySQL 的设计在结构上更加清晰和可扩展。

接下来，我们是讨论如何用 Python (例如 `mysql-connector-python` 库) 来编写实现这个数据库连接和操作的代码，还是您想对这个数据库 Schema（表结构）进行调整？