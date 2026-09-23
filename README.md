# Predictive Shipment Delay Analytics for Logistics Decision Support
**Course:** BCSE402L – Big Data Analytics  
**Academic Semester:** Winter / Fall 2026  

---

## Project Overview
This repository contains the end-to-end Big Data and Machine Learning pipeline for **Predictive Shipment Delay Analytics for Logistics Decision Support**. The system leverages **Apache Hadoop HDFS**, **Apache PySpark**, **Spark SQL**, and **Scikit-Learn** to ingest, clean, explore, and predict delivery delays on global supply chain orders.

### Team Members
- **Pranav Satish Khadse** – 23BLC1237
- **Abhinav Kumar Singh** – 23BLC1209
- **Rishi Jain** – 23BLC1242
- **Anmol Kapil** – 23BLC1229

---

## Repository Structure
```
├── dataset/
│   ├── DataCoSupplyChainDataset.csv     # Kaggle supply chain records (180,519 rows)
│   └── DescriptionDataCoSupplyChain.csv # Column definitions & metadata
├── DA2_Report_Final.docx                # Digital Assignment 2 Progress Report
├── DA2_Study_and_Viva_Preparation_Guide.md # Comprehensive handbook & viva preparation guide
├── DA_23BLC1229_shipment_delay_analytics.pdf # Digital Assignment 1 Planning Report
├── eda_q1_distribution.png              # EDA: Overall delay distribution plot
├── eda_q2_shipping_mode.png             # EDA: Delay rate by shipping mode
├── eda_q3_region.png                    # EDA: Top 10 regional delay rates
├── requirements.txt                     # Python package dependencies
├── run_da2_project.py                   # Main PySpark processing & ML execution script
├── update_word_report.py                # Automated docx report generation script
└── download_java.ps1                    # Optional script to download OpenJDK 17
```

---

## Big Data Architecture & Pipeline

1. **Storage (Hadoop HDFS):**
   - Distributed ingestion of the raw dataset under `/user/logistics/project_data/`.
2. **Distributed Processing (PySpark):**
   - Full schema deduplication (`dropDuplicates`).
   - Missing value imputation for categorical attributes & dropping of unroutable rows.
   - Domain filtering to exclude canceled orders and non-positive sales transactions.
3. **Feature Engineering (Spark SQL Functions):**
   - `Shipping_Speed_Tier`: Express ($\le 1\text{d}$), Fast ($2\text{d}$), Standard ($3\text{--}4\text{d}$).
   - `Order_Volume_Tier`: Single Item, Medium, Bulk.
   - `Order_Value_Segment`: High Value ($\ge \$200$), Standard Value ($< \$200$).
   - `Weekend_Order`: Temporal dispatch flag (Weekend vs. Weekday).
4. **Exploratory Data Analysis (Spark SQL):**
   - Registered temporary view `shipments` to analyze delay distribution, shipping mode risks, and regional patterns.
5. **Machine Learning Pipeline (Scikit-Learn Baseline):**
   - `ColumnTransformer` with `OneHotEncoder(handle_unknown="ignore")`.
   - Stratified 80/20 train/test split (`random_state=42`).
   - `LogisticRegression(max_iter=1000)` baseline classifier.
   - Achieved: **69.67% Accuracy**, **84.30% Precision**, **54.91% Recall**, and **74.09% ROC-AUC**.

---

## Installation & Execution

### 1. Prerequisites
- Python 3.9+
- Java Runtime Environment (JRE / JDK 11 or 17). Ensure `JAVA_HOME` is set.
- Optional: Local Hadoop 3.3.6 installation with HDFS active on port 9000. (The pipeline automatically falls back to local dataset storage if HDFS is offline).

### 2. Setup Virtual Environment
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Run the Pipeline
```bash
python run_da2_project.py
```

### 4. Regenerate Word Progress Report
```bash
python update_word_report.py
```
