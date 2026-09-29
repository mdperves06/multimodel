import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-1234")
os.environ.setdefault("ENCRYPTION_KEY", "Y7c1kQz4mQWJ3xv0tN9pR2s8uYdHf6bLaEoGiTjKcVw=")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "memory://")
os.environ.setdefault("ENABLE_MOCK_PROVIDER", "true")
os.environ.setdefault("STORAGE_LOCAL_PATH", "./.test-storage")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
