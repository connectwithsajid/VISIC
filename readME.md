# Project Setup Guide

This guide walks you through setting up a Python virtual environment, configuring PostgreSQL, and running the project.

---

## 1. Create and Activate Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 2. Install Dependencies

```bash
pip install sqlalchemy psycopg2-binary
pip install requests beautifulsoup4
```

---

## 3. Start PostgreSQL Service

```bash
brew services start postgresql
# OR
pg_ctl -D /usr/local/var/postgres start
```

Check running services:

```bash
brew services list
```

---

## 4. Setup Database

Login to PostgreSQL:

```bash
psql postgres
```

Run the following SQL commands:

```sql
-- Create a role with password
CREATE ROLE master_user WITH LOGIN PASSWORD 'master_user_password';

-- Create main database
CREATE DATABASE public OWNER master_user;
GRANT ALL PRIVILEGES ON DATABASE public TO master_user;

-- Create test database
CREATE DATABASE test_user;
```

Exit:

```bash
\q
```

---

## 5. Connect to Database

```bash
psql -U master_user -h localhost -p 5432 -d public
```

Enter password when prompted:

```
master_user_password
```

---

## 6. Set Environment Variable

```bash
export DATABASE_URL="postgresql+psycopg2://master_user:master_user_password@localhost:5432/public"
```

---

## 7. Run the Project

Start PostgreSQL (version-specific if needed):

```bash
brew services start postgresql@14
```

Activate virtual environment:

```bash
source venv/bin/activate
```

Run database setup scripts:

```bash
./venv/bin/python3 -m DB_connections.drop_tables
./venv/bin/python3 -m DB_connections.create_tables
```

Run main application:

```bash
./venv/bin/python3 main.py
```

---

## 8. Stop PostgreSQL

```bash
brew services stop postgresql@14
```

---

## Notes

* Ensure PostgreSQL is installed via Homebrew.
* Update credentials as needed for your environment.
* Make sure port `5432` is available.
