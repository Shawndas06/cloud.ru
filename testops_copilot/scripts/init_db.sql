-- ============================================
-- TestOps Copilot Database Schema
-- PostgreSQL 15+ with pgvector extension
-- ============================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================
-- ENUM Types
-- ============================================
CREATE TYPE request_status AS ENUM (
    'pending', 'started', 'reconnaissance', 'generation', 
    'validation', 'optimization', 'completed', 'failed', 'cancelled'
);

CREATE TYPE test_type AS ENUM ('ui', 'api', 'manual', 'automated');

CREATE TYPE validation_status AS ENUM ('passed', 'failed', 'warning');

CREATE TYPE safety_risk_level AS ENUM ('SAFE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL');

CREATE TYPE security_layer AS ENUM ('static', 'ast', 'behavioral', 'sandbox');

CREATE TYPE action_taken AS ENUM ('allowed', 'blocked', 'warning', 'regenerate');

-- ============================================
-- Table: users
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255),
    full_name VARCHAR(255),
    organization VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    api_key VARCHAR(64) UNIQUE,
    api_quota_daily INTEGER DEFAULT 100,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);

-- ============================================
-- Table: requests
-- ============================================
CREATE TABLE IF NOT EXISTS requests (
    request_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    url TEXT NOT NULL,
    requirements JSONB NOT NULL DEFAULT '[]',
    test_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    result_summary JSONB DEFAULT '{}',
    error_message TEXT,
    celery_task_id VARCHAR(255),
    langgraph_thread_id TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
CREATE INDEX IF NOT EXISTS idx_requests_user_id ON requests(user_id);
CREATE INDEX IF NOT EXISTS idx_requests_created_at ON requests(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_requests_celery_task_id ON requests(celery_task_id);
CREATE INDEX IF NOT EXISTS idx_requests_langgraph_thread_id ON requests(langgraph_thread_id);
CREATE INDEX IF NOT EXISTS idx_requests_requirements ON requests USING GIN(requirements);

-- ============================================
-- Table: test_cases
-- ============================================
CREATE TABLE IF NOT EXISTS test_cases (
    test_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID NOT NULL REFERENCES requests(request_id) ON DELETE CASCADE,
    test_name VARCHAR(255) NOT NULL,
    test_code TEXT NOT NULL,
    test_type VARCHAR(20) NOT NULL,
    allure_feature VARCHAR(255),
    allure_story VARCHAR(255),
    allure_title TEXT,
    allure_severity VARCHAR(20),
    allure_tags JSONB DEFAULT '[]',
    code_hash VARCHAR(64) NOT NULL,
    ast_hash VARCHAR(64),
    semantic_embedding VECTOR(768),
    covered_requirements JSONB DEFAULT '[]',
    priority INTEGER DEFAULT 5,
    validation_status VARCHAR(20) DEFAULT 'passed',
    validation_issues JSONB DEFAULT '[]',
    safety_risk_level VARCHAR(20) DEFAULT 'SAFE',
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_of UUID REFERENCES test_cases(test_id) ON DELETE SET NULL,
    similarity_score DECIMAL(5,4),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_test_cases_request_id ON test_cases(request_id);
CREATE INDEX IF NOT EXISTS idx_test_cases_test_type ON test_cases(test_type);
CREATE INDEX IF NOT EXISTS idx_test_cases_code_hash ON test_cases(code_hash);
CREATE INDEX IF NOT EXISTS idx_test_cases_ast_hash ON test_cases(ast_hash);
CREATE INDEX IF NOT EXISTS idx_test_cases_is_duplicate ON test_cases(is_duplicate);
CREATE INDEX IF NOT EXISTS idx_test_cases_allure_feature ON test_cases(allure_feature);
CREATE INDEX IF NOT EXISTS idx_test_cases_allure_severity ON test_cases(allure_severity);
CREATE INDEX IF NOT EXISTS idx_test_cases_created_at ON test_cases(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_test_cases_allure_tags ON test_cases USING GIN(allure_tags);
CREATE INDEX IF NOT EXISTS idx_test_cases_covered_requirements ON test_cases USING GIN(covered_requirements);

-- ============================================
-- Table: generation_metrics
-- ============================================
CREATE TABLE IF NOT EXISTS generation_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID NOT NULL REFERENCES requests(request_id) ON DELETE CASCADE,
    agent_name VARCHAR(50) NOT NULL,
    step_number INTEGER NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP NOT NULL,
    duration_ms INTEGER NOT NULL,
    llm_model VARCHAR(100),
    llm_tokens_input INTEGER,
    llm_tokens_output INTEGER,
    llm_tokens_total INTEGER,
    llm_cost_usd DECIMAL(10,6),
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    agent_metrics JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gen_metrics_request_id ON generation_metrics(request_id);
CREATE INDEX IF NOT EXISTS idx_gen_metrics_agent_name ON generation_metrics(agent_name);
CREATE INDEX IF NOT EXISTS idx_gen_metrics_created_at ON generation_metrics(created_at DESC);

-- ============================================
-- Table: coverage_analysis
-- ============================================
CREATE TABLE IF NOT EXISTS coverage_analysis (
    coverage_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID NOT NULL REFERENCES requests(request_id) ON DELETE CASCADE,
    requirement_text TEXT NOT NULL,
    requirement_index INTEGER NOT NULL,
    is_covered BOOLEAN DEFAULT FALSE,
    covering_tests JSONB DEFAULT '[]',
    coverage_count INTEGER DEFAULT 0,
    coverage_score DECIMAL(5,4),
    coverage_details JSONB DEFAULT '{}',
    has_gap BOOLEAN DEFAULT TRUE,
    gap_description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_coverage_request_id ON coverage_analysis(request_id);
CREATE INDEX IF NOT EXISTS idx_coverage_is_covered ON coverage_analysis(is_covered);
CREATE INDEX IF NOT EXISTS idx_coverage_has_gap ON coverage_analysis(has_gap);

-- ============================================
-- Table: security_audit_log
-- ============================================
CREATE TABLE IF NOT EXISTS security_audit_log (
    audit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID NOT NULL REFERENCES requests(request_id) ON DELETE CASCADE,
    test_id UUID REFERENCES test_cases(test_id) ON DELETE SET NULL,
    security_layer VARCHAR(20) NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    issues JSONB DEFAULT '[]',
    blocked_patterns JSONB DEFAULT '[]',
    action_taken VARCHAR(50) NOT NULL,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_security_audit_request_id ON security_audit_log(request_id);
CREATE INDEX IF NOT EXISTS idx_security_audit_risk_level ON security_audit_log(risk_level);
CREATE INDEX IF NOT EXISTS idx_security_audit_action_taken ON security_audit_log(action_taken);
CREATE INDEX IF NOT EXISTS idx_security_audit_created_at ON security_audit_log(created_at DESC);

-- ============================================
-- Triggers for updated_at
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_requests_updated_at
    BEFORE UPDATE ON requests
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_test_cases_updated_at
    BEFORE UPDATE ON test_cases
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

