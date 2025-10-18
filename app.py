import streamlit as st
from langgraph.graph import StateGraph, START, END
from typing import Dict, Any, TypedDict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from supabase import create_client, Client
import os
import re
from dotenv import load_dotenv
load_dotenv()

# --- Your Backend Logic (Unchanged) ---

class SamarthGraphState(TypedDict):
    user_query: str
    sql_query: str
    db_result: Any
    summary: str
    error: str
    verification: str
    retries: int

def process_user_query(state: SamarthGraphState) -> Dict[str, Any]:
    """
    Analyzes the user query, fetches exact values from the DB,
    and generates an aggregated SQL query using gemini-2.5-flash.
    """
    print("Node 1 : PRE-PROCESSING AND GENERATING SQL (using Gemini 2.5 Flash)")

    current_retries = state.get("retries", 0)
    user_query = state['user_query']
    potential_entities = re.findall(r"'([^']*)'|\"([^\"]*)\"|(\b[A-Z][a-zA-Z\s]+\b)", user_query)
    value_hints = []
    entities_to_check = [item for sublist in potential_entities for item in sublist if item]
    
    if entities_to_check:
        print(f"--- Found potential entities to check: {entities_to_check} ---")
        try:
            url = os.getenv("SUPABASE_PROJECT_URL")
            key = os.getenv("SUPABASE_API_KEY")
            supabase: Client = create_client(url, key)
            for entity in entities_to_check:
                query = f"SELECT DISTINCT state, district, crop, season FROM master_data_view WHERE state ILIKE '%{entity}%' OR district ILIKE '%{entity}%' OR crop ILIKE '%{entity}%' OR season ILIKE '%{entity}%' LIMIT 3"
                response = supabase.rpc('execute_sql', {'query': query}).execute()
                if response.data:
                    value_hints.append(f"Hint: For the term '{entity}', the database contains these related values: {response.data}")
        except Exception as e:
            print(f"--- Value lookup failed: {e} ---")

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"), temperature=0.2)
    
    prompt_string = """You are a world-class SQL generation expert. Your task is to convert the user's query into a precise and correct SQL query for a PostgreSQL database.

    ## Database Schema
    Table Name: master_data_view
Column Name,Data Type,Description
country,TEXT,"The country where the data was recorded (e.g., 'India')."
state,TEXT,The state or region within the country.
district,TEXT,The district within the state. Can be NULL if not available.
crop,TEXT,"The name of the crop, fruit, or vegetable."
year,TEXT,"The production year, often a range (e.g., '2019-20')."
season,TEXT,"The crop season (e.g., 'Kharif', 'Rabi'). Can be NULL."
area,NUMERIC,"The area of land used for cultivation, in hectares."
production,NUMERIC,"The volume of production, usually in tonnes."
temperature_c,NUMERIC,"The average temperature in Celsius."
humidity_percent,NUMERIC,"The average relative humidity in percent."
ph,NUMERIC,"The pH level of the soil."
rainfall_mm,NUMERIC,"The total rainfall in millimeters."
wind_speed_m_s,NUMERIC,"The average wind speed in meters per second."
solar_radiation_mj_m2_day,NUMERIC,"The solar radiation in MJ/m^2/day."
n_req_kg_per_ha,NUMERIC,"The recommended Nitrogen fertilizer amount in kg per hectare."
p_req_kg_per_ha,NUMERIC,"The recommended Phosphorus fertilizer amount in kg per hectare."
k_req_kg_per_ha,NUMERIC,"The recommended Potassium fertilizer amount in kg per hectare."
source_table,TEXT,"The original table name the data was imported from."

    ## CRITICAL AGGREGATION RULE
    If a user asks for a metric (like production, humidity, wind speed) for a broad area like a state or country, you MUST use an aggregate function (`AVG`, `SUM`) to provide a single summary value.
    - For production, use `SUM(production)`.
    - For climate data (humidity, wind speed, temperature, rainfall), use `AVG()`.
    - **Example:** If the query is "humidity in West Bengal", the correct SQL is `SELECT AVG(humidity_percent) FROM master_data_view WHERE state ILIKE 'West Bengal'`.
    - **Do NOT return multiple rows** for different districts unless the user explicitly asks for a "district-wise list" or "for a district" like that or similar.
    - Whenever you use an aggregate function like AVG(), SUM(), MAX(), etc., you MUST give the resulting column a clear name using the AS keyword. For example: SELECT AVG(production) AS average_production FROM ...
    ## Important Rules
    1.  **Use the provided hints to ensure correct spelling and capitalization.** The hints show you the real data from the database.
    2.  Always use the `ILIKE` operator for case-insensitive text comparisons.
    3.  Generate only the SQL query and nothing else. Do not wrap it in markdown.
    4.  Example - User can write query like - 'List the humidity and wind speed for Rice cultivation in West Bengal in 2012' so you have to identify either to use 'SUM' or 'SELECT' or 'AVG' based on the user query, because only state is mentioned not district in this example query.
    5. For 'text','varchar' data type columns,always use techniques like LIKE or = for filtering. Example - WHERE state LIKE '%Karnataka%', Not WHERE state = 'Karnataka'
    ## User Query
    {user_query}

    ## Data Hints (Use these for correct spelling)
    {value_hints}
    
    ## Self-Correction Info (If this is a retry)
    Previous Error: {error}
    Previous Failed Query: {sql_query}
    ## Final SQL Query:
    """
    
    prompt = PromptTemplate(
        input_variables=["user_query", "value_hints", "error", "sql_query"],
        template=prompt_string
    )
    
    chain = prompt | llm
    
    response = chain.invoke({
        "user_query": user_query,
        "value_hints": '\n'.join(value_hints) if value_hints else "No specific value hints found.",
        "error": state.get('error', 'N/A'),
        "sql_query": state.get('sql_query', 'N/A')
    })
    
    sql_query = response.content.strip()

    return {"sql_query": sql_query, "retries": current_retries + 1}

def execute_sql_via_api(state: SamarthGraphState) -> dict:
    print("Node 2 : EXECUTING SQL QUERY VIA API")

    sql_query = state.get("sql_query")
    if not sql_query:
        return {"error": "No SQL query found in state."}

    try:
        url = os.getenv("SUPABASE_PROJECT_URL")
        key = os.getenv("SUPABASE_API_KEY")
        supabase: Client = create_client(url, key)

        response = supabase.rpc('execute_sql', {'query': sql_query}).execute()
        data = response.data

        print(f"---SUCCESS: Query executed. Found {len(data) if data else 0} records.---")
        return {"db_result": data, "error": ""}

    except Exception as e:
        error_message = f"API Execution Error: {e}"
        print(f"---ERROR: {error_message}---")
        return {"db_result": None, "error": error_message}

# def verify_db_result(state: SamarthGraphState) -> Dict[str, str]:
#     llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"), temperature=0.2)
#     print("Node 3: VERIFYING DATABASE RESULT")
#     prompt_string = """You are an expert data analyst and SQL query expert, your task is to verify if the database result is relevant to the user query.
#     Databse Result: {db_result}
#     User Query: {user_query}
#     Important points to note:
#     1. If the database result is relevant to the user query, respond with "YES" only.
#     2. If the database result is not relevant to the user query, respond with "NO" and Reason for non relevance only.
#     3. If the database result is empty or null, respond with "NULL" only.
#     4. Do not provide any explanations or additional text.
#     """

#     prompt = PromptTemplate(
#         input_variables=["db_result", "user_query"],
#         template=prompt_string
#     )

#     chain = prompt | llm
    
#     response = chain.invoke({"db_result": state['db_result'], "user_query": state['user_query']})
#     verification = response.content.strip()
#     return {"verification": verification}

def generate_summary(state: SamarthGraphState) -> Dict[str, str]:
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"), temperature=0.2)
    print("Node 4 : GENERATING NATURAL LANGUAGE SUMMARY")
    prompt_string = """You are an expert data analyst and SQL query expert, your task is to generate a natural language summary from the database result.
    Databse Result: {db_result}
    User Query: {user_query}
    Important points to note:
    1. Generate a concise and informative summary based on the database result.
    2. Do not make any assumptions about the data beyond what is provided.
    3. Provide the summary in 3-10 lines.
    """

    prompt = PromptTemplate(
        input_variables=["db_result", "user_query"],
        template=prompt_string
    )

    chain = prompt | llm
    
    response = chain.invoke({"db_result": state['db_result'], "user_query": state['user_query']})
    summary = response.content.strip()
    return {"summary": summary}

def decide_after_sql_execution(state: SamarthGraphState) -> str:
    if state.get("error"):
        print("---DECISION: SQL Error detected. Revisiting query generation.---")
        return "revisit"
    else:
        print("---DECISION: SQL execution successful. Proceeding to verification.---")
        return "proceed"

def decide_after_verification(state: SamarthGraphState) -> str:
    if state.get("verification") == "YES":
        print("---DECISION: Verification successful. Proceeding to summary generation.---")
        return "proceed"
    else:
        print("---DECISION: Verification failed. Revisiting query generation.---")
        return "revisit"

workflow = StateGraph(SamarthGraphState)
workflow.add_node("process_user_query", process_user_query)
workflow.add_node("execute_sql_via_api", execute_sql_via_api)
workflow.add_node("generate_summary", generate_summary)

workflow.add_edge(START, "process_user_query")
workflow.add_edge("process_user_query", "execute_sql_via_api")

workflow.add_conditional_edges(
    "execute_sql_via_api",
    decide_after_sql_execution, 
    {
        "revisit": "process_user_query",
        "proceed": "generate_summary" 
    }
)
workflow.add_edge("generate_summary", END)

app = workflow.compile()

# --- Streamlit UI Logic ---

st.title("Samarth Q&A on Agriculture using Intelligent AI System" )

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask a question about India's agricultural data..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            initial_state = {
                "user_query": prompt,
                "sql_query": "",
                "db_result": None,
                "summary": "",
                "error": "",
                "verification": ""
            }
            final_state = app.invoke(initial_state)
            response = final_state.get("summary", "Sorry, I encountered an error and could not find an answer.")
            st.markdown(response)
    
    st.session_state.messages.append({"role": "assistant", "content": response})