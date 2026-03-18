import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# === LABEL MAPPING ===
LABEL_MAPPING = {
    "IJM-PWN": "Ijsselmeer",
    "PAN-PO-INF": "PSA intake",
    "PAN-MZ1-EFF": "Microsieve",
    "PAN-VV1-EFF": "Coag, Floc, Sedim",
    "PAN-VV2-EFF": "Coag, Floc, Sedim",
    "PAN-VV3-EFF": "Coag, Floc, Sedim",
    "PAN-UVK1-INF": "RSF",
    "PAN-UV1-EFF": "AOP",
    "PAN-UV3-EFF": "AOP",
    "PAN-PO-RW": "Drinking Water",
}
STAGE_ORDER = [
    "Ijsselmeer",
    "PSA intake",
    "Microsieve",
    "Coag, Floc, Sedim",
    "RSF",
    "AOP",
    "Drinking Water",
]

STAGE_COLORS = {
    "Ijsselmeer": "darkblue",
    "PSA intake": "red",
    "Microsieve": "orange",
    "Coag, Floc, Sedim": "brown",
    "RSF": "green",
    "AOP": "purple",
    "Drinking Water": "lightblue",
}

st.title("Water Quality Monitoring - Compound Analysis")

# === FILE UPLOAD ===
uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file and "df" not in st.session_state:
    df = pd.read_csv(uploaded_file, sep=",")
    df.columns = df.columns.str.strip().str.replace("\ufeff", "", regex=True)
    st.session_state.df = df

# === COMMON SETTINGS (only once) ===
if "df" in st.session_state:
    df = st.session_state.df.copy()

    df["Sampling date"] = pd.to_datetime(
        df["Sampling date"], dayfirst=True, errors="coerce"
    )
    df["Measurement"] = pd.to_numeric(df["Measurement"], errors="coerce")
    df["Sampling hour"] = pd.to_datetime(df["Sampling hour"], errors="coerce").dt.time
    df = df.dropna(
        subset=[
            "Sampling point",
            "Sampling date",
            "Sampling hour",
            "Compound",
            "Measurement",
        ]
    )

    compounds = sorted(df["Compound"].dropna().unique())
    compound_selected = st.selectbox("Select compound:", compounds, index=0)

    min_date = df["Sampling date"].min()
    max_date = df["Sampling date"].max()
    date_range = st.date_input(
        "Select date range:",
        [min_date, max_date],
        min_value=min_date,
        max_value=max_date,
    )

    if len(date_range) == 2:
        DATE1 = pd.to_datetime(date_range[0])
        DATE2 = pd.to_datetime(date_range[1])

        df["\u00b5g_priority"] = df["Unity"].str.contains("µg", na=False)
        df = df.sort_values(by="\u00b5g_priority", ascending=False)
        df = df.drop_duplicates(
            subset=["Compound", "Sampling date", "Sampling hour", "Sampling point"],
            keep="first",
        )
        df = df.drop(columns="\u00b5g_priority")

        df["Datetime"] = pd.to_datetime(
            df["Sampling date"].astype(str) + " " + df["Sampling hour"].astype(str),
            errors="coerce",
        )
        df = df.dropna(subset=["Datetime"])
        df = df[(df["Datetime"] >= DATE1) & (df["Datetime"] <= DATE2)]
        df["Month"] = df["Sampling date"].dt.to_period("M").dt.to_timestamp()
        df["Stage"] = df["Sampling point"].map(LABEL_MAPPING)
        df = df.dropna(subset=["Stage"])

        def trimmed_mean(x):
            q1, q9 = x.quantile(0.05), x.quantile(0.95)
            return x[(x >= q1) & (x <= q9)].mean()

        filtered_df = df[
            df["Compound"].str.contains(
                compound_selected, case=False, na=False, regex=False
            )
        ]

        # === FIRST PLOT ===
        st.subheader("Monthly Average Concentration")
        ma_window = st.slider(
            "Moving average window (months):", min_value=2, max_value=12, value=3
        )
        monthly_avg = (
            filtered_df.groupby(["Month", "Stage"])["Measurement"]
            .apply(trimmed_mean)
            .unstack()
        )
        monthly_count = (
            filtered_df.groupby(["Month", "Stage"])["Measurement"].count().unstack()
        )

        monthly_avg = monthly_avg.reindex(columns=STAGE_ORDER)
        monthly_count = monthly_count.reindex(columns=STAGE_ORDER)

        rolling_avg = monthly_avg.rolling(window=ma_window, min_periods=1).mean()

        fig = go.Figure()
        for stage in monthly_avg.columns:
            count_total = monthly_count[stage].sum(skipna=True)
            label = f"{stage} (n={int(count_total)})"
            fig.add_trace(
                go.Scatter(
                    x=monthly_avg.index,
                    y=monthly_avg[stage],
                    mode="markers",
                    name=label,
                    marker=dict(color=STAGE_COLORS.get(stage, "gray")),
                    connectgaps=False,
                    legendgroup=stage,
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=rolling_avg.index,
                    y=rolling_avg[stage],
                    mode="lines",
                    name=f"{stage} (MA {ma_window}m)",
                    line=dict(color=STAGE_COLORS.get(stage, "gray"), width=2),
                    connectgaps=False,
                    legendgroup=stage,
                    showlegend=True,
                )
            )

        unit_label_series = filtered_df["Unity"].dropna().unique()
        unit_label = unit_label_series[0] if len(unit_label_series) > 0 else "µg/L"
        fig.update_layout(
            title=f"MONTHLY AVERAGE CONCENTRATION OF {compound_selected.upper()}",
            xaxis_title="Month",
            yaxis_title=f"Concentration ({unit_label})",
            xaxis=dict(
                tickangle=-45,
                title_font=dict(size=16, color="black"),
                tickfont=dict(size=14, color="black"),
            ),
            yaxis=dict(
                title_font=dict(size=16, color="black"),
                tickfont=dict(size=14, color="black"),
            ),
            legend=dict(
                title="Stage",
                x=1.02,
                y=1,
                font=dict(size=14, color="black"),
                title_font=dict(size=16, color="black"),
            ),
            margin=dict(t=60, b=40, l=60, r=200),
            height=600,
            width=1000,
            font=dict(color="black"),
        )
        st.plotly_chart(fig, use_container_width=True)

        # === REMOVAL EFFICIENCY ===
        st.subheader("Average Removal Efficiency Calculator")

        monthly_avg = (
            filtered_df.groupby(["Month", "Stage"])["Measurement"]
            .apply(trimmed_mean)
            .unstack()
        )
        monthly_count = (
            filtered_df.groupby(["Month", "Stage"])["Measurement"].count().unstack()
        )
        monthly_avg = monthly_avg.reindex(columns=STAGE_ORDER)
        monthly_count = monthly_count.reindex(columns=STAGE_ORDER)

        # Find the first stage with data to use as reference
        initial_stage = None
        for s in STAGE_ORDER:
            if monthly_avg[s].notna().any():
                initial_stage = s
                break

        removal_summary = []
        last_outlet_stage = initial_stage

        for i in range(len(STAGE_ORDER) - 1):
            inlet = STAGE_ORDER[i]
            for j in range(i + 1, len(STAGE_ORDER)):
                outlet = STAGE_ORDER[j]
                # Only use months where BOTH inlet and outlet have data
                paired = monthly_avg[[inlet, outlet]].dropna()
                if len(paired) == 0:
                    continue
                paired_count_in = monthly_count.loc[paired.index, inlet].sum()
                paired_count_out = monthly_count.loc[paired.index, outlet].sum()
                avg_in = paired[inlet].mean()
                std_in = paired[inlet].std()
                avg_out = paired[outlet].mean()
                std_out = paired[outlet].std()

                eff = (
                    ((avg_in - avg_out) / avg_in) * 100 if avg_in != 0 else float("nan")
                )
                # Contribution: what this step removes relative to initial concentration
                # Use paired months between initial stage and this outlet
                if initial_stage is not None:
                    paired_init = monthly_avg[[initial_stage, outlet]].dropna()
                    init_ref = (
                        paired_init[initial_stage].mean()
                        if len(paired_init) > 0
                        else float("nan")
                    )
                    contrib = (
                        ((avg_in - avg_out) / init_ref) * 100
                        if init_ref != 0 and pd.notna(init_ref)
                        else float("nan")
                    )
                else:
                    contrib = float("nan")

                removal_summary.append(
                    {
                        "Step": f"{inlet} → {outlet}",
                        f"Avg Inlet ({unit_label})": round(avg_in, 4),
                        "SD Inlet": round(std_in, 4),
                        "Count Inlet": int(paired_count_in),
                        f"Avg Outlet ({unit_label})": round(avg_out, 4),
                        "SD Outlet": round(std_out, 4),
                        "Count Outlet": int(paired_count_out),
                        "Paired Months": len(paired),
                        "Avg Removal Efficiency (%)": round(eff, 2),
                        "Total Removal Contribution(%)": round(contrib, 2),
                    }
                )
                last_outlet_stage = outlet
                break

        # Total row: Ijsselmeer → Drinking Water (paired)
        if initial_stage is not None:
            final_stage = STAGE_ORDER[-1]
            paired_total = monthly_avg[[initial_stage, final_stage]].dropna()
            if len(paired_total) > 0:
                total_count_in = monthly_count.loc[
                    paired_total.index, initial_stage
                ].sum()
                total_count_out = monthly_count.loc[
                    paired_total.index, final_stage
                ].sum()
                total_avg_in = paired_total[initial_stage].mean()
                total_std_in = paired_total[initial_stage].std()
                total_avg_out = paired_total[final_stage].mean()
                total_std_out = paired_total[final_stage].std()
                total_eff = (
                    ((total_avg_in - total_avg_out) / total_avg_in) * 100
                    if total_avg_in != 0
                    else float("nan")
                )
                removal_summary.append(
                    {
                        "Step": f"{initial_stage} → {final_stage} (Total)",
                        f"Avg Inlet ({unit_label})": round(total_avg_in, 4),
                        "SD Inlet": round(total_std_in, 4),
                        "Count Inlet": int(total_count_in),
                        f"Avg Outlet ({unit_label})": round(total_avg_out, 4),
                        "SD Outlet": round(total_std_out, 4),
                        "Count Outlet": int(total_count_out),
                        "Paired Months": len(paired_total),
                        "Avg Removal Efficiency (%)": round(total_eff, 2),
                        "Total Removal Contribution(%)": round(total_eff, 2),
                    }
                )

        removal_table = pd.DataFrame(removal_summary)
        st.dataframe(removal_table)
