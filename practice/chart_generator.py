"""Chart generator"""
import os
import re
import json

from utils.chart_utils import load_and_prepare_data, print_html, get_model_response, encode_image_b64, ensure_execute_python_tags, image_anthropic_call




def generate_chart_code(instruction: str, model: str, out_path_v1: str) -> str:
    """Generate Python code to make a plot with matplotlib using tag-based wrapping."""

    prompt = f"""
    You are a data visualization expert.

    Return your answer *strictly* in this format:

    <execute_python>
    # valid python code here
    </execute_python>

    Do not add explanations, only the tags and the code.

    The code should create a visualization from a DataFrame 'df' with these columns:
    - player_id	(string)
    - player_name (string)
    - minutes_played (number)
    - goals	(number)
    - player_rating (number)

    User instruction: {instruction}

    Requirements for the code:
    1. Assume the DataFrame is already loaded as 'df'.
    2. Use matplotlib for plotting.
    3. Add clear title, axis labels, and legend if needed.
    4. Save the figure as '{out_path_v1}' with dpi=300.
    5. Do not call plt.show().
    6. Close all plots with plt.close().
    7. Add all necessary import python statements
    8. CRITICAL: 'date' is datetime64 — never use string concatenation on it.
       Filter by year/quarter using the 'year' and 'quarter' integer columns.
    
    Return ONLY the code wrapped in <execute_python> tags.
    """

    response = get_model_response(prompt)
    return response

def reflect_on_image_and_regenerate(
    chart_path: str,
    instruction: str,
    model_name: str,
    out_path_v2: str,
    code_v1: str,  
) -> tuple[str, str]:
    """
    Critique the chart IMAGE and the original code against the instruction, 
    then return refined matplotlib code.
    Returns (feedback, refined_code_with_tags).
    Supports OpenAI and Anthropic (Claude).
    """
    media_type, b64 = encode_image_b64(chart_path)
    

    prompt = f"""
    You are a data visualization expert.
    Your task: critique the attached chart and the original code against the given instruction,
    then return improved matplotlib code.

    Original code (for context):
    {code_v1}

    OUTPUT FORMAT (STRICT):
    1) First line: a valid JSON object with ONLY the "feedback" field.
    Example: {{"feedback": "The legend is unclear and the axis labels overlap."}}

    2) After a newline, output ONLY the refined Python code wrapped in:
    <execute_python>
    ...
    </execute_python>

    3) Import all necessary libraries in the code. Don't assume any imports from the original code.

    HARD CONSTRAINTS:
    - Do NOT include Markdown, backticks, or any extra prose outside the two parts above.
    - Use pandas/matplotlib only (no seaborn).
    - Assume df already exists; do not read from files.
    - Save to '{out_path_v2}' with dpi=300.
    - Always call plt.close() at the end (no plt.show()).
    - Include all necessary import statements.

    Schema (columns available in df):
    - player_id	(string)
    - player_name (string)
    - minutes_played (number)
    - goals	(number)
    - player_rating (number)

    Instruction:
    {instruction}
    """


    # In case the name is "Claude" or "Anthropic", use the safe helper
    lower = model_name.lower()
    content = image_anthropic_call(model_name, prompt, media_type, b64)

    # --- Parse ONLY the first JSON line (feedback) ---
    lines = content.strip().splitlines()
    json_line = lines[0].strip() if lines else ""

    try:
        obj = json.loads(json_line)
    except Exception as e:
        # Fallback: try to capture the first {...} in all the content
        m_json = re.search(r"\{.*?\}", content, flags=re.DOTALL)
        if m_json:
            try:
                obj = json.loads(m_json.group(0))
            except Exception as e2:
                obj = {"feedback": f"Failed to parse JSON: {e2}", "refined_code": ""}
        else:
            obj = {"feedback": f"Failed to find JSON: {e}", "refined_code": ""}

    # --- Extract refined code from <execute_python>...</execute_python> ---
    m_code = re.search(r"<execute_python>([\s\S]*?)</execute_python>", content)
    refined_code_body = m_code.group(1).strip() if m_code else ""
    refined_code = ensure_execute_python_tags(refined_code_body)

    feedback = str(obj.get("feedback", "")).strip()
    return feedback, refined_code

def chart_generator_agent():
    # Standard code 
    df = load_and_prepare_data(os.path.join("data", "fifa_player_goals.csv"))
    print_html(df.sample(n=5), title="FIFA World Cup 2026 Player Performance")

    output_path_v1 = os.path.join("output", "player_stats_v1.png")
    output_path_v2 = os.path.join("output", "player_stats_v2.png")

    # Direct generation
    code_v1 = generate_chart_code(
        instruction="""
        Create a chart for FIFA Player performance in 2026 using the fifa_player_goals.csv file
        """,
        model="claude-haiku-4-5",
        out_path_v1=output_path_v1
    )
    print_html(code_v1, title="FIFA 2026 Player stats")

    match = re.search(r"<execute_python>([\s\S]*?)</execute_python>", code_v1)
    if match:
        initial_code = match.group(1).strip()
        print_html(initial_code, title="Extracted Code to Execute")
        exec_globals = {"df": df}
        exec(initial_code, exec_globals)

    # If code run successfully, the file chart_v1.png should have been generated
    print_html(
        content=output_path_v1,
        title="Generated Chart (V1)",
        is_image=True
        )

    # Generate feedback alongside reflected code
    feedback, code_v2 = reflect_on_image_and_regenerate(
        chart_path=output_path_v1,            
        # instruction="Create a plot comparing Q1 coffee sales in 2024 and 2025 using the data in coffee_sales.csv.", 
        instruction="""
            Create a plot for FIFA Player performance in 2026 using the fifa_player_goals.csv file
        """,
        model_name="claude-haiku-4-5",
        out_path_v2=output_path_v2,
        code_v1=code_v1,   # pass in the original code for context        
    )

    print_html(feedback, title="Feedback on V1 Chart")
    print_html(code_v2, title="Regenerated Code Output (V2)")

    match = re.search(r"<execute_python>([\s\S]*?)</execute_python>", code_v2)
    if match:
        initial_code = match.group(1).strip()
        print_html(initial_code, title="Extracted Code to Execute")
        exec_globals = {"df": df}
        exec(initial_code, exec_globals)

    # If code run successfully, the file chart_v1.png should have been generated
    print_html(
        content=output_path_v2,
        title="Generated Chart (V1)",
        is_image=True
        )



if __name__=="__main__":
    chart_generator_agent()
