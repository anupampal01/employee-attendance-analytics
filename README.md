# Employee Attendance & Analytics

A full-stack employee attendance management and analytics application built with **React, FastAPI, and MongoDB**. The system provides employee management, attendance tracking, punch-in/punch-out workflows, attendance regularization, and department-level analytics through a web dashboard and REST API.

**Developed by:** Anupam  
**GitHub:** https://github.com/anupam01  
**Email:** anupampal1307@gmail.com

---

## Table of Contents

- [Project Overview](#project-overview)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation and Setup](#installation-and-setup)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Attendance Business Rules](#attendance-business-rules)
- [Database Configuration](#database-configuration)
- [Testing and Verification](#testing-and-verification)
- [Environment Variables](#environment-variables)
- [Security and Deployment Considerations](#security-and-deployment-considerations)
- [Troubleshooting](#troubleshooting)
- [Future Enhancements](#future-enhancements)
- [Author and Contact](#author-and-contact)

---

## Project Overview

Employee Attendance & Analytics is designed to manage employee attendance records and provide meaningful workforce analytics through a centralized application.

The application consists of a React-based frontend, a FastAPI backend, and a MongoDB database. The frontend communicates with the backend through REST APIs, while the backend validates requests, applies attendance business rules, stores records, and generates analytical results.

The system is designed to support:

- Employee creation and employee directory management.
- Daily attendance tracking.
- Employee punch-in and punch-out operations.
- Attendance record regularization with an audit history.
- Employee-level monthly attendance summaries.
- Department-level attendance reporting.
- Late-arrival rankings and department attendance trends.
- Database health checks and query execution-plan inspection.

The application can be developed and run locally on Windows, Linux, or macOS without requiring Docker, provided that Python, Node.js, and a reachable MongoDB instance are available.

## Key Features

### 1. Dashboard

- View attendance and workforce analytics.
- Access employee and attendance management modules.
- Review department-level and time-based reporting.

### 2. Employee Management

- Create employee records.
- Retrieve and search employee information.
- Filter employees by department.
- Support paginated employee listings.
- Handle duplicate employee codes and invalid requests through API validation.

### 3. Attendance Management

- Record employee punch-ins.
- Record employee punch-outs.
- Retrieve attendance records using supported employee, date, and status filters.
- Support pagination for attendance listings.
- Calculate work hours, late minutes, overtime minutes, and half-day status according to the defined business rules.

### 4. Attendance Regularization

- Update eligible attendance records through the regularization API.
- Recalculate derived attendance fields after corrections.
- Maintain an append-only history of manual corrections.
- Record correction details, including the reason and the fields changed.

### 5. Employee Monthly Analytics

- Generate monthly attendance summaries for an employee.
- Account for working days, attendance status, late arrivals, overtime, and half-day records according to the API contract.

### 6. Department Analytics

- Generate department-level monthly summaries.
- Include eligible employees in headcount calculations, including employees without attendance logs.
- Provide late-arrival leaderboards with ranking and tie handling.
- Generate daily department attendance trends with missing dates filled and a seven-day moving average.

### 7. API Health and Query Inspection

- Check backend and MongoDB connectivity through the health endpoint.
- Inspect API operations using the interactive FastAPI documentation.
- Inspect MongoDB query execution statistics through the administrative explain endpoint.
- Review query plans and index usage for supported attendance and analytics queries.

---

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React |
| Frontend tooling | Vite |
| Charts and visualization | Recharts |
| Backend framework | FastAPI |
| Backend language | Python 3.11+ |
| Database | MongoDB 6.0+ |
| Database driver | PyMongo |
| API specification | OpenAPI |
| Backend testing | pytest |
| Frontend package management | npm |

---

## System Architecture

The application follows a frontend–backend–database architecture.

```text
+----------------------------------+
|          Web Browser             |
|         React + Vite             |
+----------------+-----------------+
                 |
                 | HTTP / REST API
                 v
+----------------------------------+
|          FastAPI Backend         |
|                                  |
| Employee Management              |
| Attendance Management            |
| Punch In / Punch Out             |
| Attendance Regularization        |
| Analytics and Reporting          |
| Health and Query Inspection      |
+----------------+-----------------+
                 |
                 | PyMongo
                 v
+----------------------------------+
|            MongoDB               |
|                                  |
| employees                        |
| attendance_logs                  |
+----------------------------------+
```

The frontend sends requests to the backend API. The backend validates inputs, applies the defined business rules, interacts with MongoDB, and returns the resulting data to the frontend.

Attendance and analytics information is intended to be retrieved through the live API rather than hard-coded frontend demonstration records.

---

## Project Structure

The main project directories and files are organized as follows:

```text
employee-attendance-analytics/
|
|-- app/
|   |-- main.py
|
|-- frontend/
|   |-- src/
|   |-- package.json
|   |-- .env.example
|
|-- sample_data/
|
|-- scripts/
|   |-- setup.ps1
|   |-- setup.sh
|   |-- generate_test_data.py
|   |-- verify_dataset.py
|
|-- tests/
|   |-- unit/
|   |-- integration/
|   |-- contract/
|
|-- .env.example
|-- .gitignore
|-- DATA_MODEL.md
|-- DECISIONS.md
|-- openapi.yaml
|-- README.md
|-- REVIEW.md
|-- requirements.txt
|-- requirements-dev.txt
|-- sample_seed.py
|-- VERIFICATION.md
```

The structure above summarizes the documented project layout. Some files may differ depending on the final packaged version.

---

## Prerequisites

Install the following software before running the application:

- Python 3.11 or later.
- Node.js 18 or later, preferably a supported LTS release.
- npm, included with Node.js.
- MongoDB 6.0 or later, installed locally or hosted on MongoDB Atlas.
- Git (recommended).
- A code editor such as Visual Studio Code (recommended).

Docker is optional and is not required when using a local MongoDB installation or MongoDB Atlas.

Official installation resources:

- Python: https://www.python.org/downloads/
- Node.js: https://nodejs.org/
- MongoDB Community Server: https://www.mongodb.com/try/download/community
- MongoDB Atlas: https://www.mongodb.com/atlas
- Git: https://git-scm.com/downloads

---

## Installation and Setup

### 1. Obtain the project

Clone the repository if it has been published to GitHub:

```bash
git clone https://github.com/anupam01/employee-attendance-analytics.git
cd employee-attendance-analytics
```

If the project is supplied as a ZIP archive, extract it and open a terminal in the extracted project root.

The repository URL above assumes that the project has been published under this exact repository name. Replace it with the actual repository URL if the name differs.

### 2. Configure the backend

Create a Python virtual environment:

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux or macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install backend dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

Create the local environment configuration:

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
```

**Linux or macOS**

```bash
cp .env.example .env
```

Edit `.env` and configure the MongoDB connection:

```dotenv
MONGO_URI=mongodb://localhost:27017
MONGO_DB=attendance_db
```

Preserve any additional settings already defined in `.env.example`.

For MongoDB Atlas, use the connection string provided by Atlas instead of the local MongoDB URI. Store credentials securely and never commit them to the repository.

### 3. Configure the frontend

Open a second terminal and navigate to the frontend directory:

```bash
cd frontend
```

Create the frontend environment file.

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
```

**Linux or macOS**

```bash
cp .env.example .env
```

Configure the backend URL:

```dotenv
VITE_API_URL=http://localhost:8000
```

Install the frontend dependencies:

```bash
npm install
```

---

## Running the Application

### Start MongoDB

Ensure that your local MongoDB service is running, or confirm that your Atlas database is reachable.

For Windows, check the local service with:

```powershell
Get-Service MongoDB
```

If the service is installed but stopped, start it from an elevated PowerShell terminal:

```powershell
Start-Service MongoDB
```

### Start the backend

From the project root, with the virtual environment activated, run:

```bash
python -m uvicorn app.main:app --port 8000
```

For local development, automatic reload can be enabled with:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Keep the backend terminal open.

### Start the frontend

In a separate terminal:

```bash
cd frontend
npm run dev
```

Open the frontend in your browser:

http://localhost:5173

### Application endpoints

| Resource | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 |
| Interactive API documentation | http://localhost:8000/docs |
| Alternative API documentation | http://localhost:8000/redoc |
| Health check | http://localhost:8000/health |

The health endpoint should return HTTP 200 when MongoDB is reachable. If the database is unavailable, the documented behavior is to return HTTP 503.

---

## API Documentation

The API contract is maintained in `openapi.yaml`. FastAPI also exposes interactive documentation at `/docs` when the backend is running.

### Employee APIs

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/employees` | Create an employee |
| GET | `/employees` | Retrieve employees with supported filters and pagination |

### Attendance APIs

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/attendance/punch-in` | Record employee punch-in |
| POST | `/attendance/punch-out` | Record employee punch-out |
| GET | `/attendance` | Retrieve filtered and paginated attendance records |
| PATCH | `/attendance/{emp_code}/{date}` | Regularize an attendance record |

### Analytics APIs

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/analytics/employees/{emp_code}/monthly` | Employee monthly attendance summary |
| GET | `/analytics/departments/summary` | Department attendance summary |
| GET | `/analytics/leaderboard/late` | Late-arrival leaderboard |
| GET | `/analytics/departments/{department}/trend` | Department attendance trend |

### Administrative and health APIs

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Backend and database health check |
| GET | `/admin/explain/{endpoint}` | Inspect MongoDB query execution statistics |

The supported query parameters, request schemas, response fields, validation rules, and status codes are defined by the API contract and can be inspected through the interactive documentation.

---

## Attendance Business Rules

The implementation is designed around the attendance rules defined in the project specification.

### Time and shift calculations

- Attendance dates and shift times follow Indian Standard Time (IST, UTC+05:30).
- API instants are represented as epoch milliseconds.
- Time instants are truncated to whole seconds before calculations.
- Overnight shifts are handled across calendar dates.
- Late arrivals use a ten-minute grace period.
- Overtime is counted when the qualifying time beyond shift end reaches at least 30 minutes.
- Work hours are rounded to two decimal places using half-up rounding.
- A completed attendance record is classified as a half day when rounded work hours are below 4.50.

### Attendance statuses

| Status | Meaning |
|---|---|
| `PRESENT` | Worked on site |
| `WFH` | Worked from home |
| `ON_DUTY` | Official duty away from the office |
| `ABSENT` | Did not work and had no approved leave |
| `LEAVE` | Approved leave |

### Reporting and analytics

- Working days are Monday through Friday, without a holiday calendar.
- Mid-month joiners are accounted for from their joining date.
- Half days count as 0.5 of a present day.
- Department headcount includes eligible employees without attendance logs.
- Leaderboard ties share a rank, and subsequent ranks are skipped.
- Department trends include dates without attendance records and calculate a seven-day moving average.
- Paginated list endpoints use one-based page numbers, a default page size of 20, and a maximum page size of 100.

Refer to `openapi.yaml` and `DATA_MODEL.md` for the complete API and data requirements.

---

## Database Configuration

MongoDB contains two primary collections:

- `employees`: employee identity, department, joining date, shift information, and related employee attributes.
- `attendance_logs`: attendance dates, punch timestamps, attendance status, derived calculations, and regularization history.

The backend is expected to create its required indexes idempotently at startup.

### Sample data

The project includes sample data and a seed script for development.

**Important:** `sample_seed.py` deletes both target collections before inserting sample records. Only run it against a disposable development database after checking the configured `MONGO_DB` value.

### Performance verification

The project includes a synthetic dataset generator and a dataset verification script for performance and analytics checks.

Use a dedicated test database for destructive test-data generation. Never run commands that drop collections against a production database.

---

## Testing and Verification

The repository includes test suites for different verification levels.

### Unit tests

```bash
python -m pytest tests/unit -v
```

Tests helper functions and business-rule calculations without requiring a running MongoDB instance.

### Integration tests

Configure `TEST_MONGO_URI` to point to a dedicated test MongoDB instance and run:

```bash
python -m pytest tests/integration -v -rs
```

Integration tests are intended to exercise database-backed API behavior, validation, attendance calculations, concurrency, history, analytics, and index usage.

### Contract tests

```bash
python -m pytest tests/contract -v
```

These tests compare the generated API contract with `openapi.yaml`.

### Frontend production build

From the frontend directory:

```bash
npm run build
```

The production bundle is generated in `frontend/dist`.

### Dataset verification

After generating the dedicated synthetic dataset and starting the backend:

```bash
python scripts/verify_dataset.py --api http://localhost:8000
```

This verification script is intended to compare selected live API analytics against expected results and inspect query execution plans.

**Verification status:** Run the commands above in the final delivery environment and record the actual results before describing the application as fully tested or production-ready. A successful installation or startup alone does not establish that all tests pass.

See `VERIFICATION.md` for the project's recorded verification status and known limitations.

---

## Environment Variables

| Variable | Purpose | Example |
|---|---|---|
| `MONGO_URI` | MongoDB connection URI | `mongodb://localhost:27017` |
| `MONGO_DB` | Application database name | `attendance_db` |
| `TEST_MONGO_URI` | MongoDB URI used for integration testing | `mongodb://localhost:27017` |
| `VITE_API_URL` | Backend URL used by the frontend | `http://localhost:8000` |

Only configure variables that are supported by the relevant component. The frontend environment variables must use the `VITE_` prefix to be exposed to Vite-built client code; do not place secrets in frontend variables.

Backend environment variables supplied by the execution environment should take precedence over values loaded from `.env`, as required by the project contract.

---

## Security and Deployment Considerations

Before deploying the application to a public or production environment, review the following:

- Configure authentication and role-based authorization where required.
- Restrict access to administrative and query-inspection endpoints.
- Use HTTPS and appropriate CORS settings.
- Store credentials and secrets in a secure configuration service or deployment environment.
- Use a dedicated database user with least-privilege permissions.
- Configure database backups, monitoring, and recovery procedures.
- Keep dependencies updated and review security advisories.
- Run the full test suite against the final code and target MongoDB version.
- Validate behavior under concurrent requests and representative production-scale data.
- Use a production-appropriate ASGI server configuration rather than development reload mode.
- Avoid using destructive seed or synthetic-data scripts against production data.

**Known limitation:** The supplied project documentation states that authentication is not part of the current API contract and that the `/admin/*` endpoints are open. These endpoints must be protected before exposing the application to untrusted users.

Production deployment should be approved only after the required security controls, functional tests, performance checks, and operational configuration have been completed.

---

## Troubleshooting

| Problem | Suggested action |
|---|---|
| MongoDB service cannot start | Check the Windows service status, MongoDB installation, logs, and port availability. |
| Backend cannot import `app` | Run the command from the repository root with the virtual environment activated. |
| `/health` returns 503 | Verify the MongoDB service, URI, database configuration, and network access. |
| Frontend cannot reach the backend | Confirm that FastAPI is running and `VITE_API_URL` points to the correct URL. |
| Frontend changes to `.env` are not applied | Restart the Vite development server. |
| Integration tests are skipped | Review the test output and confirm that the configured test database is reachable. |
| Analytics return no records | Check the filters, selected period, employee data, and attendance records. |
| Production build fails | Review the build output, installed Node.js version, dependencies, and frontend source errors. |

---

## Future Enhancements

Potential enhancements, depending on business requirements, include:

- Authentication, authorization, and role-based access control.
- Secure deployment and centralized monitoring.
- Automated deployment pipelines.
- Additional HR integrations and export/reporting capabilities.
- Expanded automated regression and load testing.

These are potential extensions and should not be interpreted as features already delivered.

---

## Author and Contact

**Anupam — Software Engineer**

- GitHub: https://github.com/anupam01
- Email: anupampal1307@gmail.com

For project questions, technical discussions, or collaboration, please use the contact details above.

---

*Employee Attendance & Analytics — React, FastAPI, and MongoDB.*