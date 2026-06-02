import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
import base64

def create_pdf_report(results, inputs, analysis_results):
    """Create PDF report with latin-1 compatible text (no Unicode emojis)."""
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        # Title
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="FIRE Analysis Report", ln=True, align='C')
        pdf.ln(10)
        
        # Inputs
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(200, 10, txt="Input Parameters:", ln=True)
        pdf.set_font("Arial", size=10)
        for key, value in inputs.items():
            # Clean string conversions to prevent FPDF errors
            clean_key = str(key).encode('latin-1', 'ignore').decode('latin-1')
            clean_value = str(value).encode('latin-1', 'ignore').decode('latin-1')
            pdf.cell(200, 8, txt=f"{clean_key}: {clean_value}", ln=True)
        pdf.ln(5)
        
        # Results
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(200, 10, txt="Analysis Results:", ln=True)
        pdf.set_font("Arial", size=10)
        
        verdict_text = str(analysis_results.get('verdict', 'N/A')).encode('latin-1', 'ignore').decode('latin-1')
        pdf.cell(200, 8, txt=f"Verdict: {verdict_text}", ln=True)
        
        # Output as a safe byte string
        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except Exception as e:
        # Return error message as bytes if anything fails
        return f"PDF Generation Error: {str(e)}".encode('latin-1', 'ignore')

def simulate_drawdown(start_corpus, annual_expense, inflation_rate, investment_return, years):
    """Simulates a simple retirement timeline drawdown."""
    corpus_history = []
    current_corpus = start_corpus
    current_expense = annual_expense
    
    for year in range(1, years + 1):
        corpus_history.append(max(0, current_corpus))
        # Deduct expenses at start of year
        current_corpus -= current_expense
        # Grow remaining corpus
        if current_corpus > 0:
            current_corpus *= (1 + investment_return)
        else:
            current_corpus = 0
        # Inflate expenses for next year
        current_expense *= (1 + inflation_rate)
        
    return corpus_history

# --- MAIN APP LAYOUT ---
st.title("🔥 FIRE Calculator")
st.write("Determine your Financial Independence, Retire Early targets.")

# Sidebar Controls / Inputs
st.sidebar.header("Your Financial Details")
current_age = st.sidebar.slider("Current Age", 18, 70, 30)
retirement_age = st.sidebar.slider("Target Retirement Age", 30, 70, 50)
life_expectancy = st.sidebar.slider("Life Expectancy Age", 70, 100, 85)

current_corpus = st.sidebar.number_input("Current Corpus (₹)", value=5000000, step=500000)
monthly_expense = st.sidebar.number_input("Current Monthly Expense (₹)", value=50000, step=5000)

pre_ret_return = st.sidebar.slider("Pre-Retirement Annual Return (%)", 5.0, 20.0, 12.0) / 100
post_ret_return = st.sidebar.slider("Post-Retirement Annual Return (%)", 3.0, 15.0, 8.0) / 100
inflation_rate = st.sidebar.slider("Expected Inflation Rate (%)", 3.0, 12.0, 6.0) / 100

# Basic Computations
years_to_retirement = max(0, retirement_age - current_age)
retirement_years = max(1, life_expectancy - retirement_age)
annual_expense_today = monthly_expense * 12

# Project corpus at retirement point
achievable_corpus = current_corpus * ((1 + pre_ret_return) ** years_to_retirement)
future_annual_expense = annual_expense_today * ((1 + inflation_rate) ** years_to_retirement)

# Generate a mock strategy matrix for the simulation comparison
results = simulate_drawdown(achievable_corpus, future_annual_expense, inflation_rate, post_ret_return, retirement_years)

st.subheader("Your Retirement Outlook")
col1, col2 = st.columns(2)
with col1:
    st.metric("Years to Accumulate", f"{years_to_retirement} years")
    st.metric("Projected Corpus at Retirement", f"₹{achievable_corpus/100000:,.2f} Lakhs")
with col2:
    st.metric("Retirement Phase Duration", f"{retirement_years} years")
    st.metric("First Year Retirement Expense", f"₹{future_annual_expense/100000:,.2f} Lakhs")

# Generate Plotly Visualizations
df_plot = pd.DataFrame({
    "Year": np.arange(retirement_age, life_expectancy),
    "Projected Path": results
})

fig = go.Figure()
fig.add_trace(go.Scatter(x=df_plot["Year"], y=df_plot["Projected Path"], name="Your Corpus", line=dict(color="#ff4b4b", width=3)))
fig.update_layout(title="Corpus Drawdown Over Time", xaxis_title="Age", yaxis_title="Balance (₹)", template="plotly_white")
st.plotly_chart(fig, use_container_width=True)

# Withdrawal Engine Reverse Math Logic
n = retirement_years
r = post_ret_return
i = inflation_rate
q = (1 + i) / (1 + r)

if r == i:
    max_withdrawal = achievable_corpus * (1 + r) / n
else:
    max_withdrawal = achievable_corpus * (1 - q) / (1 - q**n) * (1 + r)

max_withdrawal_monthly = max_withdrawal / 12
withdrawal_rate = (max_withdrawal / achievable_corpus) * 100 if achievable_corpus > 0 else 0

st.markdown("---")
st.subheader("Safe Sustainable Withdrawal Limits")
m_col1, m_col2, m_col3 = st.columns(3)
with m_col1:
    st.metric("Annual Withdrawal Limit", f"₹{max_withdrawal/100000:,.2f} L")
with m_col2:
    st.metric("Monthly Withdrawal Limit", f"₹{max_withdrawal_monthly/100000:,.2f} L")
with m_col3:
    st.metric("Safe Withdrawal Rate", f"{withdrawal_rate:.2f}%")
        
# PDF Report Setup
st.markdown("---")
inputs = {
    "Annual Expense Today": f"₹{annual_expense_today:,.0f}",
    "Achievable Corpus": f"₹{achievable_corpus:,.0f}",
    "Years to Retirement": years_to_retirement,
    "Retirement Duration": retirement_years,
    "Inflation": f"{inflation_rate*100:.1f}%",
    "Return": f"{post_ret_return*100:.1f}%"
}

analysis_results = {
    "verdict": "Your strategy is simulated successfully. Review the drawdown graph to ensure your wealth lasts throughout your retirement lifespan."
}

# Safely create PDF bytes buffer
pdf_data_bytes = create_pdf_report(results, inputs, analysis_results)
b64 = base64.b64encode(pdf_data_bytes).decode('latin-1')

st.download_button(
    label="📥 Download PDF Financial Report",
    data=base64.b64decode(b64),
    file_name="FIRE_Consulting_Report.pdf",
    mime="application/pdf"
)