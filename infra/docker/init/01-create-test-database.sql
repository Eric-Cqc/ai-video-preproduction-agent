SELECT 'CREATE DATABASE foundation_test OWNER foundation'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'foundation_test')\gexec
