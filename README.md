# Project Samarth: Intelligent Q&A for Indian Agricultural Data

Project Samarth is an intelligent Q&A system that provides natural language answers to complex questions about India's agricultural and climate data. It leverages a multi-dataset knowledge base synthesized from various Indian Government data portals (data.gov.in) and uses a Text-to-SQL agent to provide real-time, data-backed insights.

This system is built to serve policymakers, researchers, and analysts by transforming thousands of disparate, complex datasets into a single, queryable, and intelligent source of truth.

## Table of Contents
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Local Setup and Installation](#local-setup-and-installation)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Create your Environment File](#2-create-your-environment-file)
  - [3. Install Dependencies](#3-install-dependencies)
- [How to Run](#how-to-run)
- [Deployment](#deployment)

---

## Architecture

The system is built as a self-correcting agentic workflow using **LangGraph**. This architecture allows the agent to reason, act, and reflect on its actions to achieve a correct answer.

1.  **User Interface (Streamlit):** The user submits a natural language query (e.g., "Compare rainfall and rice production in West Bengal in 2012").
2.  **Node 1: Pre-Processing & SQL Generation:**
    * The user's query is analyzed to extract key entities (e.g., "Rice", "West Bengal", "2012").
    * A quick lookup is performed on the database to find the *exact* spelling of these entities (e.g., "West Bengal" -> "WEST BENGAL").
    * These hints, along with the query, schema, and any past errors, are fed into an LLM (like `gemini-2.5-flash` or `mistralai/codestral`) to generate a robust SQL query.
3.  **Node 2: SQL Execution:**
    * The generated SQL query is securely sent to a Supabase PostgreSQL database.
    * Instead of allowing direct query execution, the agent calls a specific, safe PostgreSQL function (`execute_sql`) that runs the query and returns the data as a JSON object.
4.  **Error Handling Loop:**
    * If the SQL execution fails, the database error is caught and fed back to Node 1. The agent is then prompted to "fix its mistake," creating a self-correction loop.
    * A retry limit is in place to prevent infinite loops and API quota exhaustion.
5.  **Node 3: Summary Generation:**
    * The JSON data from the database is passed to a final LLM call.
    * The LLM synthesizes this raw data into a natural, human-readable summary that directly answers the user's original question.
6.  **Response:** The final summary is displayed to the user in the Streamlit chat interface.

This entire process is managed as a state machine within LangGraph, tracking the `user_query`, `sql_query`, `db_result`, and `error` state.

---

## Features

* **Natural Language Querying:** Ask complex, cross-domain questions about agriculture and climate in plain English.
* **Data Synthesis:** Answers are synthesized from six different datasets, including district-level production, climate data, and soil nutrient requirements.
* **Self-Correction:** The agent automatically attempts to fix its own SQL errors, increasing reliability.
* **Robust Querying:** Uses case-insensitive matching (`ILIKE`) and value lookups to handle inconsistencies in the source data.
* **Smart Aggregation:** Automatically provides summary statistics (like `AVG` or `SUM`) for broad queries (e.g., for a whole state) instead of returning thousands of rows.

---

## Tech Stack

* **Frontend:** Streamlit
* **Backend & Agent:** LangGraph
* **LLMs:** Google Gemini (`gemini-2.5-flash`)
* **Database:** Supabase (PostgreSQL)
* **Core Libraries:** `langchain`, `supabase-py`, `openai` (for OpenRouter), `psycopg2`, `langgraph`

---

## Local Setup and Installation

### 1. Clone the Repository
```bash
git clone [https://github.com/your-username/your-repo-name.git](https://github.com/your-username/your-repo-name.git)
cd your-repo-name
```

### 2. Create your Environment File
Create a file named `.env` in the root of the project and add your API keys.

```.env
# .env file
GOOGLE_API_KEY="your-google-api-key"
OPENROUTER_API_KEY="sk-or-your-openrouter-key"
SUPABASE_PROJECT_URL="[https://your-project-id.supabase.co](https://your-project-id.supabase.co)"
SUPABASE_API_KEY="your-supabase-anon-key"
```

### 3. Install Dependencies
Create a virtual environment and install the required packages.
```bash
python -m venv myenv
source myenv/bin/activate  # On Windows, use `myenv\Scripts\activate`
pip install -r requirements.txt
```

---

## How to Run

Execute the Streamlit application from your terminal:

```bash
streamlit run app.py
```

This will open the chatbot interface in your web browser.

---

## Deployment

This application is already deployed on streamlit Cloud - https://samarth-q-a-on-agriculture-using-intelligent-ai-system.streamlit.app/
