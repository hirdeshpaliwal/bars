import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
import base64

def create_pdf_report(results, inputs, analysis_results):
    """Create PDF report with latin-1 compatible text (no Unicode emojis)."""
    
    def sanitize_text(text):
        """Replace Unicode characters with latin-1 compatible equivalents."""
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
        pdf.cell(200, 8, txt=f"{key}: {value}", ln=True)
    pdf.ln(5)
    
    # Results
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Analysis Results:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 8, txt=f"Verdict: {analysis_results['verdict']}", ln=True)
    pdf.cell(200, 8, txt=f"Success Probability: {analysis_results['success_prob']}%", ln=True)
    
    return pdf.output(dest='S').encode('latin-1')

@st.cache_data
def simulate_drawdown(start_corpus, annual_expense, inflation_rate, investment_return, years, creep_rate=0.0, creep_start_year=10):
    data = []
    corpus = start_corpus
    expense = annual_expense
    
    for year in range(1, years + 1):
        # Apply lifestyle creep if applicable
        if year >= creep_start_year:
            expense *= (1 + creep_rate)
            
        # Withdraw expense (beginning of year)
        corpus -= expense
        
        # Grow remaining corpus
        if corpus > 0:
            corpus *= (1 + investment_return)
        
        # Apply inflation for next year's expense
        expense *= (1 + inflation_rate)
        
        data.append([year, expense, max(0, corpus)])
        
        if corpus <= 0:
            # Fill remaining years with 0
            for y in range(year + 1, years + 1):
                expense *= (1 + inflation_rate)
                data.append([y, expense, 0])
            break
            
    return pd.DataFrame(data, columns=["Year", "Expense", "Corpus"])

def render():
    st.markdown("# 🔥 FIRE Calculator")
    st.markdown("### Financial Independence, Retire Early Analysis")
    
    st.markdown("---")
    
    # Data Source Toggle
    use_historical = st.toggle("Use Historical NAV Data (Requires Internet)", value=False)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 💰 Financial Status")
        current_age = st.number_input("Current Age", value=35, step=1)
        retirement_age = st.number_input("Retirement Age", value=45, step=1)
        current_corpus = st.number_input("Current Corpus / Portfolio Value (₹)", value=5000000, step=100000, help="Your current savings that will grow until retirement")
        monthly_expense = st.number_input("Monthly Expense (₹)", value=50000, step=5000)
        
    with col2:
        st.markdown("### 📈 Assumptions")
        inflation = st.number_input("Inflation Rate (%)", value=6.0, step=0.5) / 100
        
        if use_historical:
            amfi_code = st.text_input("AMFI Code (Proxy for Portfolio)", value="122640", help="Parag Parikh Flexi Cap Fund")
            return_rate = 0.0 # Placeholder
        else:
            return_rate = st.number_input("Expected Post-Retirement Return (%)", value=10.0, step=0.5, help="Conservative return during withdrawal phase") / 100
            amfi_code = None
        
        pre_retirement_return = st.number_input("Pre-Retirement Growth Rate (%)", value=12.0, step=0.5, help="Expected return during accumulation phase (typically higher)") / 100
        life_expectancy = st.number_input("Life Expectancy", value=85, step=1)

    st.markdown("---")
    
    if st.button("🚀 Calculate FIRE Scenarios", use_container_width=True):
        
        # Calculate years to retirement and retirement duration
        years_to_retirement = retirement_age - current_age
        retirement_years = life_expectancy - retirement_age
        
        # Calculate annual expense today
        annual_expense_today = monthly_expense * 12
        
        # Calculate expense at retirement (inflated)
        annual_expense_retirement = annual_expense_today * ((1 + inflation) ** years_to_retirement)
        
        # Investment return
        if use_historical and amfi_code:
            with st.spinner("Fetching Historical Data..."):
                from utils.data_engine import DataEngine
                df = DataEngine.fetch_fund_history(amfi_code)
                if df is not None:
                    df_indexed = df.set_index('date')
                    cagr, vol = DataEngine.calculate_metrics(df_indexed['nav'])
                    return_rate = cagr
                    st.success(f"Using Historical Return: {cagr*100:.2f}%")
                else:
                    st.error("Failed to fetch data. Using manual input.")
                    return_rate = 0.10
        
        investment_return = return_rate
        inflation_rate = inflation
        
        # Calculate required corpus for different FIRE levels
        # Using Present Value of Growing Annuity formula
        r = investment_return
        i = inflation_rate
        n = retirement_years
        P1 = annual_expense_retirement
        
        # q = (1+i)/(1+r)
        q = (1 + i) / (1 + r)
        
        if abs(r - i) < 0.0001:
            # Special case
            exact_needed_corpus = P1 * n / (1 + r)
        else:
            # Withdrawals at start of year (annuity due)
            exact_needed_corpus = P1 * (1 - q**n) / (r - i) * (1 + r)
        
        # Define FIRE scenarios
        corpus_values = {
            "LeanFIRE (1x)": exact_needed_corpus,
            "FIRE (1.25x)": exact_needed_corpus * 1.25,
            "FatFIRE (3x)": exact_needed_corpus * 3.0
        }
        
        # Calculate achievable corpus (current corpus grown to retirement using pre-retirement rate)
        achievable_corpus = current_corpus * ((1 + pre_retirement_return) ** years_to_retirement)
        corpus_values["Achievable Corpus"] = achievable_corpus
        
        # Run simulations for each scenario
        results = {}
        for name, corpus in corpus_values.items():
            df_sim = simulate_drawdown(corpus, annual_expense_retirement, inflation_rate, investment_return, retirement_years)
            results[name] = df_sim
        
        # Display Results
        st.markdown("## 🎯 FIRE Corpus Requirements")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("LeanFIRE (1x)", f"₹{corpus_values['LeanFIRE (1x)']/10000000:.2f} Cr",
                     delta="Minimum")
            
        with col2:
            st.metric("FIRE (1.25x)", f"₹{corpus_values['FIRE (1.25x)']/10000000:.2f} Cr",
                     delta="Comfortable")
            
        with col3:
            st.metric("FatFIRE (3x)", f"₹{corpus_values['FatFIRE (3x)']/10000000:.2f} Cr",
                     delta="Luxurious")
            
        with col4:
            coverage = achievable_corpus / exact_needed_corpus
            st.metric("Your Corpus", f"₹{achievable_corpus/10000000:.2f} Cr",
                     delta=f"Coverage: {coverage:.0%}")
            
        # Plot scenarios
        st.markdown("---")
        st.markdown("## 📊 Corpus Drawdown Projections")
        
        fig = go.Figure()
        
        colors= {
            "LeanFIRE (1x)": "#ff7f0e",
            "FIRE (1.25x)": "#2ca02c",
            "FatFIRE (3x)": "#9467bd",
            "Achievable Corpus": "#d62728"
        }
        
        for name, df in results.items():
            fig.add_trace(go.Scatter(
                x=df["Year"],
                y=df["Corpus"] / 10000000,
                mode='lines',
                name=name,
                line=dict(width=3 if name == "Achievable Corpus" else 2, color=colors.get(name, "gray"))
            ))
        
        # Add Expense Line on Secondary Y-Axis
        expense_df = list(results.values())[0]
        fig.add_trace(go.Scatter(
            x=expense_df["Year"],
            y=expense_df["Expense"] / 100000, # In Lakhs
            mode='lines',
            name='Annual Expense (Lakhs)',
            line=dict(color='red', width=2, dash='dash'),
            yaxis='y2'
        ))

        fig.add_hline(y=0, line_dash="dash", line_color="black", annotation_text="Corpus Depleted")
        
        fig.update_layout(
            title=f"FIRE Corpus Drawdown ({investment_return*100:.1f}% return, {inflation_rate*100:.1f}% inflation, {retirement_years} years)",
            xaxis_title="Year of Retirement",
            yaxis_title="Corpus Remaining (₹ Crores)",
            yaxis2=dict(
                title="Annual Expense (₹ Lakhs)",
                overlaying='y',
                side='right',
                showgrid=False
            ),
            template="plotly_white",
            height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Sustainability check
        st.markdown("---")
        st.markdown("## ✅ Sustainability Analysis")
        
        analysis_results = []
        
        for name, target_corpus in corpus_values.items():
            if name == "Achievable Corpus":
                continue
            
            if achievable_corpus >= target_corpus:
                status = "✅ Achieved"
            else:
                gap = target_corpus - achievable_corpus
                status = f"❌ Shortfall: ₹{gap/10000000:.2f} Cr"
            
            coverage_pct = achievable_corpus / target_corpus
            
            analysis_results.append({
                "Scenario": name,
                "Required Corpus": f"₹{target_corpus/10000000:.2f} Cr",
                "Coverage": f"{coverage_pct:.0%}",
                "Status": status
            })
        
        # Achievable corpus status
        df_achievable = results["Achievable Corpus"]
        final_corpus = df_achievable["Corpus"].iloc[-1]
        
        if (df_achievable["Corpus"] < 0).any():
            depletion_year = df_achievable[df_achievable["Corpus"] < 0].iloc[0]["Year"]
            achievable_status = f"⚠️ Depletes in Year {int(depletion_year)}"
        elif final_corpus <= 0:
            achievable_status = "⚠️ Sustainable (just lasts the duration)"
        else:
            achievable_status = f"✅ Sustainable with surplus (~₹{final_corpus/10000000:.1f} Cr left)"
        
        analysis_results.append({
            "Scenario": "Achievable Corpus",
            "Required Corpus": f"₹{achievable_corpus/10000000:.2f} Cr",
            "Coverage": "N/A",
            "Status": achievable_status
        })
        
        analysis_df = pd.DataFrame(analysis_results)
        st.dataframe(analysis_df, use_container_width=True)
        
        st.info(f"""
        **Key Insights:**
        - Expense at Retirement (after {years_to_retirement} years): ₹{annual_expense_retirement:,.0f} per year
        - To maintain current lifestyle with {inflation_rate*100:.1f}% inflation
        - Pre-retirement growth rate: {pre_retirement_return*100:.1f}% (accumulation phase)
        - Post-retirement returns: {investment_return*100:.1f}% (withdrawal phase)
        - Duration: {retirement_years} years
        
        **Verdict:** {achievable_status}
        """)

        # Coast FIRE Analysis
        st.markdown("---")
        st.markdown("## 🏖️ Coast FIRE Analysis")
        
        # Coast FIRE: Formula -> Needed_Today * (1+r_pre)^T = Needed_At_Retirement
        # Using pre-retirement growth rate for accumulation phase
        coast_fire_target_retirement = exact_needed_corpus # This is the target at retirement
        coast_fire_needed_today = coast_fire_target_retirement / ((1 + pre_retirement_return) ** years_to_retirement)
        
        # Calculate what current corpus will grow to using pre-retirement rate
        coast_fire_projected_corpus = current_corpus * ((1 + pre_retirement_return) ** years_to_retirement)
        
        coast_status_delta = current_corpus - coast_fire_needed_today
        coast_status_pct = current_corpus / coast_fire_needed_today if coast_fire_needed_today > 0 else 0
        
        c_col1, c_col2, c_col3 = st.columns(3)
        with c_col1:
            st.metric("Coast FIRE Target (at Ret. Age)", f"₹{coast_fire_target_retirement/10000000:.2f} Cr", help="Corpus needed at retirement to cover expenses")
            
        with c_col2:
            st.metric("Required Corpus Today", f"₹{coast_fire_needed_today/10000000:.2f} Cr", help="Amount needed TODAY to grow to Target without further savings")
            
        with c_col3:
            if coast_status_delta >= 0:
                st.metric("Coast FIRE Status", "✅ Achieved", delta=f"+₹{coast_status_delta/100000:.2f} L Surplus")
            else:
                st.metric("Coast FIRE Status", "❌ Not Yet", delta=f"-₹{abs(coast_status_delta)/100000:.2f} L Shortfall", delta_color="inverse")

        if coast_status_delta >= 0:
            st.success(f"🎉 **You are Coast FIRE!** \n\nIf you stop saving today, your current corpus of **₹{current_corpus/100000:.2f} L** is projected to grow to **₹{coast_fire_projected_corpus/10000000:.2f} Cr** by age {retirement_age} (at {pre_retirement_return*100:.1f}% growth rate), exceeding your requirement of **₹{coast_fire_target_retirement/10000000:.2f} Cr**.")
        else:
            st.warning(f"**Keep Pushing!** \n\nYou are **{coast_status_pct:.1%}** of the way to Coast FIRE. \nYour current corpus will grow to approximately **₹{coast_fire_projected_corpus/10000000:.2f} Cr** by retirement (at {pre_retirement_return*100:.1f}% growth rate), which is short of the required **₹{coast_fire_target_retirement/10000000:.2f} Cr**. The shortfall must be bridged by future SIPs/contributions.")

        # Max Sustainable Withdrawal
        st.markdown("---")
        st.markdown("## 💰 Max Sustainable Withdrawal with Achievable Corpus")
        
        if r == i:
            max_withdrawal = achievable_corpus * (1 + r) / n
        else:
            max_withdrawal = achievable_corpus * (1 - q) / (1 - q**n) * (1 + r)

        max_withdrawal_monthly = max_withdrawal / 12
        withdrawal_rate = (max_withdrawal / achievable_corpus) * 100
        
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.metric("Annual Withdrawal Limit", f"₹{max_withdrawal/100000:.2f} L")
        with m_col2:
            st.metric("Monthly Withdrawal Limit", f"₹{max_withdrawal_monthly/100000:.2f} L")
        with m_col3:
            st.metric("Safe Withdrawal Rate", f"{withdrawal_rate:.2f}%")
                
        # PDF Report
        st.markdown("---")
        inputs = {
            "Annual Expense Today": f"₹{annual_expense_today:,.0f}",
            "Achievable Corpus": f"₹{achievable_corpus:,.0f}",
            "Years to Retirement": years_to_retirement,
            "Retirement Duration": retirement_years,
            "Inflation": f"{inflation_rate*100:.1f}%",
            "Return": f"{investment_return*100:.1f}%"
        }
        
        pdf_bytes = create_pdf_report(results, inputs, analysis_results)
        b64 = base64.b64encode(pdf_bytes).decode()
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="FIRE_Analysis_Report.pdf" class="stButton"><button style="width:100%">📄 Download PDF Report</button></a>'
        st.markdown(href, unsafe_allow_html=True)
