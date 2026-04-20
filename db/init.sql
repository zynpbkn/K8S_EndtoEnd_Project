-- AkıllıSınıf - Veritabanı Şeması

CREATE TABLE IF NOT EXISTS quizzes (
    id          VARCHAR(36)  PRIMARY KEY,
    student_id  VARCHAR(100) NOT NULL,
    topic       VARCHAR(255) NOT NULL,
    questions   JSONB        NOT NULL,
    created_at  TIMESTAMP    DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS quiz_results (
    id              SERIAL       PRIMARY KEY,
    quiz_id         VARCHAR(36)  REFERENCES quizzes(id),
    student_id      VARCHAR(100) NOT NULL,
    score           INTEGER      NOT NULL CHECK (score BETWEEN 0 AND 100),
    answers         JSONB        NOT NULL,
    wrong_questions JSONB,
    analysis        JSONB,
    completed_at    TIMESTAMP    DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quizzes_student ON quizzes(student_id);
CREATE INDEX IF NOT EXISTS idx_results_student ON quiz_results(student_id);
CREATE INDEX IF NOT EXISTS idx_results_quiz    ON quiz_results(quiz_id);
