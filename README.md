# Shipment Delay Analytics Dashboard

This project is a modern, full-stack web application designed to analyze and predict shipment delays using Big Data technologies. It features a React-based frontend and a FastAPI backend powered by Apache PySpark for heavy data processing and machine learning.

## 🏗️ Architecture

- **Frontend**: Vite + React (JavaScript, Tailwind/CSS)
- **Backend**: FastAPI (Python)
- **Data Processing**: Apache Spark (PySpark)
- **Storage**: Hadoop HDFS (optional/configurable)

---

## 🚀 Getting Started

### 1. Backend Setup

The backend handles the data ingestion, PySpark SQL queries, and the machine learning pipeline.

**Prerequisites:**
- Python 3.8+
- Java (Required for PySpark)
- Hadoop/Winutils (if running on Windows)

**Installation & Execution:**
Open a terminal and navigate to the project root:

```bash
# 1. Create a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # On Windows

# 2. Install the required dependencies
pip install -r requirements.txt

# 3. Navigate into the backend directory
cd backend

# 4. Start the FastAPI server
uvicorn main:app --reload
```
*The backend API will now be running at `http://localhost:8000`*


### 2. Frontend Setup

The frontend provides an interactive dashboard to run Spark SQL queries, manage saved queries, and visualize the dataset.

**Prerequisites:**
- Node.js (v16+)

**Installation & Execution:**
Open a *new* terminal and navigate to the `frontend` folder:

```bash
# 1. Navigate to the frontend directory
cd frontend

# 2. Install Node modules
npm install

# 3. Start the Vite development server
npm run dev
```
*The frontend application will now be running at `http://localhost:5173`*

---

## 📂 Project Structure
- `/backend` - Contains FastAPI application, PySpark models, and query managers.
- `/frontend` - Contains the React Vite dashboard.
- `/dataset` - (Not tracked by Git) Place your large `DataCoSupplyChainDataset.csv` here.
- `start_hdfs.py` - Utility script for local Hadoop.
