import streamlit as st
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.tools import tool
import os
from dotenv import load_dotenv
from supabase_client import supabase

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# Define tools
from langchain.tools import tool
from supabase_client import supabase

@tool
def get_employee_by_name(name: str) -> str:
    """
    Searches employee by exact name,
    Args:
        name , text
    Output:
    -employee_id , uuid
    -first_name , text
    -last_name , text
    -email , text
    -phone , text
    -date_of_joining , date
    -department , text
    -location , text
    -manager_id , uuid (can be Null)
    -status , text    

    """
    try:
        res = (
            supabase
            .table("EmployeeDetail")
            .select("*")
            .eq("first_name", name.strip())    # Fixed: added parentheses to call the method
            .execute()
        )

        return res.data
    except Exception as e:
        return f"Error: {e}"  # Fixed: return proper error message instead of raising string

@tool
def get_schema(table_name: str) -> str:
    """
    Returns the schema of the table
    """
    try:
        response = supabase.table(table_name).select("*").limit(1).execute()
        return response
    except Exception as e:
        return f"Error: {e}"


@tool
def advanced_empolyee_search(name: str = None, department: str = None, location: str = None,
                              position: str = None, columns: str = "*", limit: int = 50) -> str:
    """
    Searches employee by similar name,department,location , postion , columns , limits
    Args:
        name , text
        department , text
        location , text
        positon , text 
        columns , text
        limit , int
    Output:
    if columns not given
    -employeed_id , uuid
    -first_name , text
    -last_name , text
    -email , text
    -phone , text
    -date_of_joining , date
    -department , text
    -location , text
    -manager_id , uuid (can be Null)
    -status , text
    if columns given 
    returns only the given columns
    """
    try:
        query = supabase.table('EmployeeDetail').select(columns)
        
        if name:
            query = query.ilike('name', f'%{name}%')
        if department:
            query = query.ilike('department', f'%{department}%')
        if position:
            query = query.ilike('position', f'%{position}%')
        if location:
            query = query.ilike('location', f'%{location}%')
            
        response = query.limit(limit).execute()
        return response
    except Exception as e:
        return f"Error in employee search: {str(e)}"


@tool
def search_employees_by_salary(min_salary: int = None, max_salary: int = None, 
                                currency: str = "INR", department: str = None) -> str:
    """
    Search employees by salary range with department filter
    Returns employee details with current salary information
    """
    try:
        from datetime import datetime
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        salary_query = supabase.table('EmployeePositionSalaryDetail').select(
            "employee_id,position_title,salary_amount,salary_currency"
        ).or_(f"effective_to.is.null,effective_to.gt.{current_date}")
        
        if min_salary:
            salary_query = salary_query.gte('salary_amount', min_salary)
        if max_salary:
            salary_query = salary_query.lte('salary_amount', max_salary)
        if currency:
            salary_query = salary_query.eq('salary_currency', currency)
            
        salary_data = salary_query.execute()
        
        if department:
            employee_ids = [record['employee_id'] for record in salary_data.data]
            if employee_ids:
                emp_query = supabase.table('EmployeeDetail').select(
                    "employee_id,first_name,last_name,email,department,location"
                ).in_('employee_id', employee_ids).ilike('department', f'%{department}%')
                
                result = emp_query.execute()
                return result
        
        return salary_data
    except Exception as e:
        return f"Error in salary search: {str(e)}"


@tool
def get_department_analytics(department: str = None) -> str:
    """
    Get department-wise analytics including headcount and position distribution
    """
    try:
        if department:
            emp_query = supabase.table('EmployeeDetail').select(
                "employee_id,first_name,last_name,department,status"
            ).ilike('department', f'%{department}%').execute()
            
            employee_ids = [emp['employee_id'] for emp in emp_query.data]
            if employee_ids:
                position_query = supabase.table('EmployeePositionSalaryDetail').select(
                    "position_title,employment_type"
                ).in_('employee_id', employee_ids).execute()
                
                return {
                    "employee_count": len(emp_query.data),
                    "employees": emp_query.data,
                    "position_distribution": position_query.data
                }
            return emp_query
        else:
            query = supabase.table('EmployeeDetail').select(
                "department,status"
            ).execute()
            
            from collections import defaultdict
            dept_stats = defaultdict(lambda: defaultdict(int))
            
            for emp in query.data:
                dept_stats[emp['department']][emp['status']] += 1
                dept_stats[emp['department']]['total'] += 1
                
            return dict(dept_stats)
    except Exception as e:
        return f"Error in department analytics: {str(e)}"


# Initialize LLM and tools
@st.cache_resource
def initialize_agent():
    llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=openai_api_key)
    tools = [
        get_employee_by_name,
        get_schema,
        # advanced_empolyee_search,
        search_employees_by_salary,
        get_department_analytics
    ]
    
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt="""
        answer the query using the tools 
        Do NOT call RPC or database functions directly.
        use tools only
        if no info found say "not found"
        there are two tables only in the database :
        1. **EmployeeDetail**
        - `employee_id`: UUID
        - `first_name`: Text
        - `last_name`: Text
        - `email`: Text
        - `phone`: Text
        - `date_of_joining`: Date
        - `department`: Text
        - `location`: Text
        - `manager_id`: UUID (can be Null)
        - `status`: Text

        2. **EmployeePositionSalaryDetail**
        - `record_id`: UUID
        - `employee_id`: UUID
        - `position_title`: Text
        - `grade`: Text
        - `salary_currency`: Text
        - `salary_amount`: Integer
        - `effective_from`: Date
        - `effective_to`: Date (can be Null)
        - `employment_type`: Text

        if asked for details about the table answer
        if asked about a person by name use "get_employee_by_name"
        use tools only
        if no information found say "not found"
        """,
    )
    return agent


# Streamlit UI
st.set_page_config(page_title="Employee Search Agent", page_icon="🔍", layout="wide")

st.title("🔍 Employee Search Agent")
st.markdown("Ask questions about employees, departments, salaries, and more!")

# Initialize agent
agent = initialize_agent()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask about employees (e.g., 'total employees in each department')"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Display assistant response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # Stream agent response
        with st.spinner("Thinking..."):
            try:
                for chunks in agent.stream(
                    {"messages": [{"role": "user", "content": prompt}]},
                    stream_mode="updates",
                ):
                    for step, data in chunks.items():
                        if 'messages' in data and len(data['messages']) > 0:
                            content = data['messages'][-1].content
                            if content:
                                full_response = content
                                message_placeholder.markdown(full_response)
                
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                message_placeholder.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

# Sidebar with example queries
with st.sidebar:
    st.header("📋 Example Queries")
    st.markdown("""
    - Total employees in each department
    - Find employee named John
    - Show employees in Engineering department
    - Search employees with salary above 50000
    - Get schema of EmployeeDetail table
    - Department analytics for Sales
    - List all employees in Mumbai location
    """)
    
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()