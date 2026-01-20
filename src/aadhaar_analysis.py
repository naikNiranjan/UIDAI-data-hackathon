"""
Aadhaar Ecosystem Health Analysis
=================================
Analyzes Aadhaar enrolment and update data to measure ecosystem health
and classify states into archetypes.

Author: Hackathon Team
Date: 2026-01-18
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# Set style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
VIZ_DIR = OUTPUT_DIR / "visualizations"
METRICS_DIR = OUTPUT_DIR / "metrics"

# Ensure output directories exist
VIZ_DIR.mkdir(parents=True, exist_ok=True)
METRICS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# DATA LOADING
# =============================================================================

def load_all_csvs(folder_path: Path) -> pd.DataFrame:
    """Load and concatenate all CSV files from a folder."""
    all_files = list(folder_path.glob("*.csv"))
    if not all_files:
        raise FileNotFoundError(f"No CSV files found in {folder_path}")

    dfs = []
    for f in all_files:
        df = pd.read_csv(f)
        dfs.append(df)

    combined = pd.concat(dfs, ignore_index=True)
    print(f"  Loaded {len(all_files)} files, {len(combined):,} rows from {folder_path.name}")
    return combined


def load_data():
    """Load all three datasets."""
    print("\n" + "="*60)
    print("LOADING DATA")
    print("="*60)

    enrolment = load_all_csvs(DATA_DIR / "enrolment")
    biometric = load_all_csvs(DATA_DIR / "biometric")
    demographic = load_all_csvs(DATA_DIR / "demographic")

    return enrolment, biometric, demographic


# =============================================================================
# DATA PREPROCESSING
# =============================================================================

def preprocess_data(enrolment: pd.DataFrame,
                    biometric: pd.DataFrame,
                    demographic: pd.DataFrame):
    """Clean and preprocess all datasets."""
    print("\n" + "="*60)
    print("PREPROCESSING DATA")
    print("="*60)

    # Parse dates
    enrolment['date'] = pd.to_datetime(enrolment['date'], format='%d-%m-%Y')
    biometric['date'] = pd.to_datetime(biometric['date'], format='%d-%m-%Y')
    demographic['date'] = pd.to_datetime(demographic['date'], format='%d-%m-%Y')

    # Extract month for temporal analysis
    enrolment['month'] = enrolment['date'].dt.to_period('M')
    biometric['month'] = biometric['date'].dt.to_period('M')
    demographic['month'] = demographic['date'].dt.to_period('M')

    # Standardize state names (strip whitespace, title case)
    for df in [enrolment, biometric, demographic]:
        df['state'] = df['state'].str.strip().str.title()
        df['district'] = df['district'].str.strip().str.title()

    # Calculate total columns
    enrolment['total_enrolment'] = (
        enrolment['age_0_5'] +
        enrolment['age_5_17'] +
        enrolment['age_18_greater']
    )

    biometric['total_bio'] = biometric['bio_age_5_17'] + biometric['bio_age_17_']
    demographic['total_demo'] = demographic['demo_age_5_17'] + demographic['demo_age_17_']

    print(f"  Enrolment date range: {enrolment['date'].min()} to {enrolment['date'].max()}")
    print(f"  Biometric date range: {biometric['date'].min()} to {biometric['date'].max()}")
    print(f"  Demographic date range: {demographic['date'].min()} to {demographic['date'].max()}")

    return enrolment, biometric, demographic


# =============================================================================
# AGGREGATIONS
# =============================================================================

def aggregate_by_state(enrolment: pd.DataFrame,
                       biometric: pd.DataFrame,
                       demographic: pd.DataFrame):
    """Aggregate data at state level."""
    print("\n" + "="*60)
    print("AGGREGATING BY STATE")
    print("="*60)

    # State-level enrolment
    state_enrol = enrolment.groupby('state').agg({
        'age_0_5': 'sum',
        'age_5_17': 'sum',
        'age_18_greater': 'sum',
        'total_enrolment': 'sum'
    }).reset_index()

    # State-level biometric
    state_bio = biometric.groupby('state').agg({
        'bio_age_5_17': 'sum',
        'bio_age_17_': 'sum',
        'total_bio': 'sum'
    }).reset_index()

    # State-level demographic
    state_demo = demographic.groupby('state').agg({
        'demo_age_5_17': 'sum',
        'demo_age_17_': 'sum',
        'total_demo': 'sum'
    }).reset_index()

    # Merge all
    state_data = state_enrol.merge(state_bio, on='state', how='outer')
    state_data = state_data.merge(state_demo, on='state', how='outer')
    state_data = state_data.fillna(0)

    # Calculate total updates
    state_data['total_updates'] = state_data['total_bio'] + state_data['total_demo']

    print(f"  Total states: {len(state_data)}")
    print(f"  Total enrolments: {state_data['total_enrolment'].sum():,.0f}")
    print(f"  Total bio updates: {state_data['total_bio'].sum():,.0f}")
    print(f"  Total demo updates: {state_data['total_demo'].sum():,.0f}")

    return state_data


def aggregate_by_district(biometric: pd.DataFrame,
                          demographic: pd.DataFrame):
    """Aggregate updates at district level for GCI calculation."""

    # District-level updates
    district_bio = biometric.groupby(['state', 'district']).agg({
        'total_bio': 'sum'
    }).reset_index()

    district_demo = demographic.groupby(['state', 'district']).agg({
        'total_demo': 'sum'
    }).reset_index()

    district_data = district_bio.merge(district_demo, on=['state', 'district'], how='outer')
    district_data = district_data.fillna(0)
    district_data['total_updates'] = district_data['total_bio'] + district_data['total_demo']

    return district_data


def aggregate_by_month(biometric: pd.DataFrame,
                       demographic: pd.DataFrame):
    """Aggregate updates at state-month level for TCS calculation."""

    monthly_bio = biometric.groupby(['state', 'month']).agg({
        'total_bio': 'sum'
    }).reset_index()

    monthly_demo = demographic.groupby(['state', 'month']).agg({
        'total_demo': 'sum'
    }).reset_index()

    monthly_data = monthly_bio.merge(monthly_demo, on=['state', 'month'], how='outer')
    monthly_data = monthly_data.fillna(0)
    monthly_data['total_updates'] = monthly_data['total_bio'] + monthly_data['total_demo']

    return monthly_data


# =============================================================================
# METRIC CALCULATIONS
# =============================================================================

def calculate_gini(values: np.ndarray) -> float:
    """Calculate Gini coefficient for an array of values."""
    values = np.array(values, dtype=float)
    values = values[values > 0]  # Remove zeros

    if len(values) < 2:
        return 0.0

    values = np.sort(values)
    n = len(values)
    cumsum = np.cumsum(values)
    gini = (2 * np.sum((np.arange(1, n+1) * values))) / (n * cumsum[-1]) - (n + 1) / n
    return max(0, min(1, gini))  # Clamp to [0, 1]


def calculate_metrics(state_data: pd.DataFrame,
                      district_data: pd.DataFrame,
                      monthly_data: pd.DataFrame):
    """Calculate all 5 pillar metrics + composite score."""
    print("\n" + "="*60)
    print("CALCULATING METRICS")
    print("="*60)

    # National totals
    national_enrolment = state_data['total_enrolment'].sum()
    national_updates = state_data['total_updates'].sum()
    national_bio = state_data['total_bio'].sum()
    national_demo = state_data['total_demo'].sum()

    # Youth ratios at national level
    national_bio_youth = state_data['bio_age_5_17'].sum()
    national_bio_adult = state_data['bio_age_17_'].sum()
    national_demo_youth = state_data['demo_age_5_17'].sum()
    national_demo_adult = state_data['demo_age_17_'].sum()

    national_youth_updates = national_bio_youth + national_demo_youth
    national_adult_updates = national_bio_adult + national_demo_adult
    national_youth_ratio = national_youth_updates / national_adult_updates if national_adult_updates > 0 else 0

    print(f"  National Youth Ratio: {national_youth_ratio:.4f}")

    # Calculate metrics for each state
    metrics = []

    for _, row in state_data.iterrows():
        state = row['state']

        # 1. IDI (Infrastructure Deficit Index)
        enrol_share = row['total_enrolment'] / national_enrolment if national_enrolment > 0 else 0
        update_share = row['total_updates'] / national_updates if national_updates > 0 else 0
        idi = enrol_share - update_share

        # 2. UBI (Update Balance Index)
        total_updates = row['total_bio'] + row['total_demo']
        ubi = row['total_bio'] / total_updates if total_updates > 0 else 0.5

        # 3. YIR (Youth Inclusion Ratio)
        state_youth = row['bio_age_5_17'] + row['demo_age_5_17']
        state_adult = row['bio_age_17_'] + row['demo_age_17_']
        state_youth_ratio = state_youth / state_adult if state_adult > 0 else 0
        yir = state_youth_ratio / national_youth_ratio if national_youth_ratio > 0 else 1.0

        # 4. GCI (Geographic Concentration Index)
        state_districts = district_data[district_data['state'] == state]['total_updates'].values
        gci = calculate_gini(state_districts) if len(state_districts) > 1 else 0.0

        # 5. TCS (Temporal Consistency Score)
        state_monthly = monthly_data[monthly_data['state'] == state]['total_updates'].values
        if len(state_monthly) > 1 and np.mean(state_monthly) > 0:
            cov = np.std(state_monthly) / np.mean(state_monthly)
            tcs = max(0, 1 - cov)
        else:
            tcs = 0.5

        metrics.append({
            'state': state,
            'total_enrolment': row['total_enrolment'],
            'total_updates': total_updates,
            'total_bio': row['total_bio'],
            'total_demo': row['total_demo'],
            'enrol_share': enrol_share,
            'update_share': update_share,
            'IDI': idi,
            'UBI': ubi,
            'YIR': yir,
            'GCI': gci,
            'TCS': tcs
        })

    metrics_df = pd.DataFrame(metrics)

    # Verify IDI sums to ~0
    idi_sum = metrics_df['IDI'].sum()
    print(f"  IDI Sum (should be ~0): {idi_sum:.6f}")

    return metrics_df


def calculate_health_score(metrics_df: pd.DataFrame):
    """Calculate composite health score and add to dataframe."""
    print("\n" + "="*60)
    print("CALCULATING HEALTH SCORES")
    print("="*60)

    df = metrics_df.copy()

    # Normalize IDI (invert - lower is better)
    # IDI ranges roughly from -0.1 to +0.2
    idi_min, idi_max = df['IDI'].min(), df['IDI'].max()
    df['IDI_score'] = 100 * (1 - (df['IDI'] - idi_min) / (idi_max - idi_min + 0.001))

    # Normalize UBI (distance from ideal 0.425)
    df['UBI_score'] = 100 * (1 - np.abs(df['UBI'] - 0.425) / 0.425)
    df['UBI_score'] = df['UBI_score'].clip(0, 100)

    # Normalize YIR (closer to 1 is better, cap at 1.5)
    df['YIR_score'] = 100 * np.minimum(df['YIR'], 1.5) / 1.5

    # Normalize GCI (invert - lower is better)
    df['GCI_score'] = 100 * (1 - df['GCI'])

    # Normalize TCS (higher is better)
    df['TCS_score'] = 100 * df['TCS']

    # Composite Health Score
    df['Health_Score'] = (
        0.25 * df['IDI_score'] +
        0.25 * df['GCI_score'] +
        0.20 * df['TCS_score'] +
        0.20 * df['YIR_score'] +
        0.10 * df['UBI_score']
    )

    print(f"  Health Score range: {df['Health_Score'].min():.1f} to {df['Health_Score'].max():.1f}")
    print(f"  Mean Health Score: {df['Health_Score'].mean():.1f}")

    return df


# =============================================================================
# ARCHETYPE CLASSIFICATION
# =============================================================================

def classify_archetype(row):
    """Classify a state into one of 4 archetypes."""

    # Check for EXCLUDED first (specific failures)
    if row['YIR'] < 0.6:
        return 'Excluded (Youth)'
    if row['UBI'] < 0.25 or row['UBI'] > 0.65:
        return 'Excluded (Update Imbalance)'
    if row['GCI'] > 0.6:
        return 'Excluded (Geographic)'

    # Check for SLEEPWALKER (low activity, drifting)
    if row['TCS'] < 0.4 and row['Health_Score'] < 40:
        return 'Sleepwalker'

    # Check for DIGITAL LEADER
    if (row['Health_Score'] > 70 and
        row['TCS'] > 0.6 and
        row['GCI'] < 0.4 and
        row['YIR'] > 0.8):
        return 'Digital Leader'

    # Check for SPRINTER (growing but lagging)
    if row['IDI'] > 0.03:
        return 'Sprinter'

    # Default: Moderate performer
    return 'Moderate'


def assign_archetypes(metrics_df: pd.DataFrame):
    """Assign archetypes to all states."""
    print("\n" + "="*60)
    print("ASSIGNING ARCHETYPES")
    print("="*60)

    df = metrics_df.copy()
    df['Archetype'] = df.apply(classify_archetype, axis=1)

    # Add symbols for display (ASCII-safe)
    archetype_symbol = {
        'Digital Leader': '[+]',
        'Sprinter': '[~]',
        'Sleepwalker': '[-]',
        'Excluded (Youth)': '[!]',
        'Excluded (Update Imbalance)': '[!]',
        'Excluded (Geographic)': '[!]',
        'Moderate': '[=]'
    }
    df['Archetype_Symbol'] = df['Archetype'].map(archetype_symbol)
    df['Archetype_Display'] = df['Archetype_Symbol'] + ' ' + df['Archetype']

    # Print summary
    print("\n  Archetype Distribution:")
    for archetype, count in df['Archetype'].value_counts().items():
        symbol = archetype_symbol.get(archetype, '[?]')
        print(f"    {symbol} {archetype}: {count} states")

    return df


# =============================================================================
# PROBLEM-SPECIFIC RISK CALCULATIONS
# =============================================================================

def calculate_problem_risks(state_data: pd.DataFrame, metrics_df: pd.DataFrame):
    """
    Calculate risk scores for each real-world Aadhaar problem.

    Returns DataFrame with 6 new risk columns:
    - PDS_Risk: Biometric authentication failure
    - DBT_Risk: Name/address mismatch
    - Scholarship_Risk: Youth eKYC failure
    - OTP_Risk: Minor-to-Adult transition failure
    - Banking_Risk: Financial exclusion
    - Composite_Problem_Risk: Average of all risks
    """
    print("\n" + "="*60)
    print("CALCULATING PROBLEM-SPECIFIC RISKS")
    print("="*60)

    df = metrics_df.copy()

    # Merge with raw state data for age-based calculations
    df = df.merge(state_data[['state', 'age_0_5', 'age_5_17', 'age_18_greater',
                              'bio_age_5_17', 'bio_age_17_',
                              'demo_age_5_17', 'demo_age_17_']],
                  on='state', how='left')

    # 1. PDS_Risk: Biometric authentication failure for adults
    # High risk if adults enrolled but never updated biometrics
    df['PDS_Risk'] = np.where(
        df['age_18_greater'] > 0,
        (1 - (df['bio_age_17_'] / df['age_18_greater'])) * 100,
        0
    ).clip(0, 100)

    # 2. DBT_Risk: Name/address mismatch failure
    # High risk if demographic updates lag behind enrolments
    df['DBT_Risk'] = np.where(
        df['age_18_greater'] > 0,
        (1 - (df['demo_age_17_'] / df['age_18_greater'])) * 100,
        0
    ).clip(0, 100)

    # 3. Scholarship_Risk: Youth eKYC failure
    # Maps directly to low YIR (youth not updating)
    df['Scholarship_Risk'] = ((1 - df['YIR']) * 100).clip(0, 100)

    # 4. OTP_Risk: Minor-to-Adult transition failure
    # High risk if many children enrolled but not updating demographic info
    df['OTP_Risk'] = np.where(
        df['age_5_17'] > 0,
        ((df['age_5_17'] - df['demo_age_5_17']) / df['age_5_17']) * 100,
        0
    ).clip(0, 100)

    # 5. Banking_Risk: Overall financial exclusion
    # Inverse of health score (composite measure)
    df['Banking_Risk'] = (100 - df['Health_Score']).clip(0, 100)

    # Composite Problem Risk (average of all 5)
    df['Composite_Problem_Risk'] = df[[
        'PDS_Risk', 'DBT_Risk', 'Scholarship_Risk',
        'OTP_Risk', 'Banking_Risk'
    ]].mean(axis=1)

    print(f"  PDS Risk range: {df['PDS_Risk'].min():.1f} - {df['PDS_Risk'].max():.1f}%")
    print(f"  DBT Risk range: {df['DBT_Risk'].min():.1f} - {df['DBT_Risk'].max():.1f}%")
    print(f"  Scholarship Risk range: {df['Scholarship_Risk'].min():.1f} - {df['Scholarship_Risk'].max():.1f}%")
    print(f"  OTP Risk range: {df['OTP_Risk'].min():.1f} - {df['OTP_Risk'].max():.1f}%")
    print(f"  Banking Risk range: {df['Banking_Risk'].min():.1f} - {df['Banking_Risk'].max():.1f}%")
    print(f"  Composite Problem Risk: {df['Composite_Problem_Risk'].mean():.1f}% (average)")

    return df


# =============================================================================
# INSIGHTS GENERATION
# =============================================================================

def generate_insights_report(metrics_df: pd.DataFrame):
    """Generate detailed insights report with problem analysis by archetype."""
    print("\n" + "="*60)
    print("GENERATING INSIGHTS REPORT")
    print("="*60)

    report_lines = [
        "# Aadhaar Ecosystem Health: Deep Problem Analysis Report\n",
        "---\n",
        "## Executive Summary\n",
    ]

    # Critical counts
    critical_pds = len(metrics_df[metrics_df['PDS_Risk'] > 75])
    critical_dbt = len(metrics_df[metrics_df['DBT_Risk'] > 75])
    critical_scholarship = len(metrics_df[metrics_df['Scholarship_Risk'] > 50])
    critical_otp = len(metrics_df[metrics_df['OTP_Risk'] > 75])
    critical_banking = len(metrics_df[metrics_df['Banking_Risk'] > 50])

    report_lines.append(f"- **{critical_pds} states** face critical PDS/ration shop risks (biometric gaps)\n")
    report_lines.append(f"- **{critical_dbt} states** have high DBT/payment failure risks (demographic gaps)\n")
    report_lines.append(f"- **{critical_scholarship} states** exclude youth from scholarships/eKYC\n")
    report_lines.append(f"- **{critical_otp} states** will see OTP failures for youth turning 18\n")
    report_lines.append(f"- **{critical_banking} states** face banking/financial exclusion risks\n")

    report_lines.append("\n## Problem Analysis\n")

    # 1. PDS Risk Analysis
    report_lines.append("### 1. PDS/Ration Shop Failures (Biometric Authentication)\n")
    report_lines.append("**Manifestation:** Adults enrolled but never updated biometrics → PDS authentication failures\n\n")
    top_pds = metrics_df.nlargest(10, 'PDS_Risk')[['state', 'Archetype', 'PDS_Risk', 'bio_age_17_', 'age_18_greater']]
    report_lines.append("**Critical States:**\n")
    for i, (_, row) in enumerate(top_pds.iterrows(), 1):
        report_lines.append(f"{i}. {row['state']} ({row['Archetype']}) - Risk: {row['PDS_Risk']:.1f}%\n")

    report_lines.append("\n### 2. DBT Payment Failures (Name/Address Mismatch)\n")
    report_lines.append("**Manifestation:** Low demographic update rates → payment rejections, service failures\n\n")
    top_dbt = metrics_df.nlargest(10, 'DBT_Risk')[['state', 'Archetype', 'DBT_Risk', 'demo_age_17_', 'age_18_greater']]
    report_lines.append("**Critical States:**\n")
    for i, (_, row) in enumerate(top_dbt.iterrows(), 1):
        report_lines.append(f"{i}. {row['state']} ({row['Archetype']}) - Risk: {row['DBT_Risk']:.1f}%\n")

    report_lines.append("\n### 3. Scholarship Rejections (Youth eKYC Failure)\n")
    report_lines.append("**Manifestation:** Low YIR → youth locked out of scholarships and services at 18\n\n")
    top_scholarship = metrics_df.nlargest(10, 'Scholarship_Risk')[['state', 'Archetype', 'Scholarship_Risk', 'YIR']]
    report_lines.append("**Critical States:**\n")
    for i, (_, row) in enumerate(top_scholarship.iterrows(), 1):
        report_lines.append(f"{i}. {row['state']} ({row['Archetype']}) - Risk: {row['Scholarship_Risk']:.1f}% (YIR: {row['YIR']:.2f})\n")

    report_lines.append("\n### 4. OTP Failures (Minor → Adult Transition)\n")
    report_lines.append("**Manifestation:** Children enrolled with parent mobile, not updating → OTP failures when turning 18\n\n")
    top_otp = metrics_df.nlargest(10, 'OTP_Risk')[['state', 'Archetype', 'OTP_Risk', 'age_5_17', 'demo_age_5_17']]
    report_lines.append("**Critical States:**\n")
    for i, (_, row) in enumerate(top_otp.iterrows(), 1):
        report_lines.append(f"{i}. {row['state']} ({row['Archetype']}) - Risk: {row['OTP_Risk']:.1f}%\n")

    report_lines.append("\n### 5. Banking/Financial Exclusion\n")
    report_lines.append("**Manifestation:** Overall low health score → exclusion from multiple financial services\n\n")
    top_banking = metrics_df.nlargest(10, 'Banking_Risk')[['state', 'Archetype', 'Banking_Risk', 'Health_Score']]
    report_lines.append("**Critical States:**\n")
    for i, (_, row) in enumerate(top_banking.iterrows(), 1):
        report_lines.append(f"{i}. {row['state']} ({row['Archetype']}) - Risk: {row['Banking_Risk']:.1f}% (Health: {row['Health_Score']:.1f})\n")

    # Archetype Profiles
    report_lines.append("\n## Archetype-Specific Insights\n")

    for archetype in ['Digital Leader', 'Sprinter', 'Moderate', 'Sleepwalker',
                      'Excluded (Youth)', 'Excluded (Update Imbalance)', 'Excluded (Geographic)']:
        subset = metrics_df[metrics_df['Archetype'] == archetype]
        if len(subset) > 0:
            report_lines.append(f"\n### {archetype}\n")
            report_lines.append(f"**Count:** {len(subset)} states\n")
            report_lines.append(f"**Avg Health Score:** {subset['Health_Score'].mean():.1f}\n")
            report_lines.append(f"**Primary Risks:**\n")

            avg_risks = {
                'PDS': subset['PDS_Risk'].mean(),
                'DBT': subset['DBT_Risk'].mean(),
                'Scholarship': subset['Scholarship_Risk'].mean(),
                'OTP': subset['OTP_Risk'].mean(),
                'Banking': subset['Banking_Risk'].mean()
            }
            sorted_risks = sorted(avg_risks.items(), key=lambda x: x[1], reverse=True)
            for risk_type, risk_val in sorted_risks[:3]:
                report_lines.append(f"  - {risk_type}: {risk_val:.1f}%\n")

            report_lines.append(f"**Example States:** {', '.join(subset['state'].head(3).tolist())}\n")

    # Save report
    report_path = OUTPUT_DIR / 'reports' / 'insights_report.md'
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.writelines(report_lines)

    print(f"  Saved: {report_path}")
    return '\n'.join(report_lines)


# =============================================================================
# ARCHETYPE RECOMMENDATIONS
# =============================================================================

def generate_recommendations_by_archetype(metrics_df: pd.DataFrame):
    """Generate policy recommendations by archetype."""
    print("\n" + "="*60)
    print("GENERATING ARCHETYPE RECOMMENDATIONS")
    print("="*60)

    recommendations_data = []

    # Digital Leaders
    digital_leaders = metrics_df[metrics_df['Archetype'] == 'Digital Leader']
    if len(digital_leaders) > 0:
        recommendations_data.append({
            'Archetype': 'Digital Leader',
            'State_Count': len(digital_leaders),
            'Primary_Issue': 'Maintain momentum',
            'Secondary_Issue': 'Pilot new features',
            'Recommended_Intervention': 'Share best practices; pilot e-Aadhaar expansion; mentor other states',
            'Expected_Impact': 'High visibility; national knowledge transfer',
            'Implementation_Cost': 'Low'
        })

    # Sprinters
    sprinters = metrics_df[metrics_df['Archetype'] == 'Sprinter']
    if len(sprinters) > 0:
        primary_issues = []
        for risk_type in ['PDS_Risk', 'DBT_Risk', 'OTP_Risk']:
            primary_issues.append((risk_type, sprinters[risk_type].mean()))
        primary_issues.sort(key=lambda x: x[1], reverse=True)
        primary = primary_issues[0][0].replace('_Risk', '')

        recommendations_data.append({
            'Archetype': 'Sprinter',
            'State_Count': len(sprinters),
            'Primary_Issue': f'Infrastructure lag ({primary})',
            'Secondary_Issue': 'High enrolment backlog',
            'Recommended_Intervention': f'Rapid deployment of mobile update vans; {primary}-focused camps; scaling infrastructure',
            'Expected_Impact': 'High - reduces failure rates by 30-50% within 6 months',
            'Implementation_Cost': 'High'
        })

    # Moderate Performers
    moderates = metrics_df[metrics_df['Archetype'] == 'Moderate']
    if len(moderates) > 0:
        recommendations_data.append({
            'Archetype': 'Moderate',
            'State_Count': len(moderates),
            'Primary_Issue': 'Inconsistent operations',
            'Secondary_Issue': 'Geographic concentration',
            'Recommended_Intervention': 'Standardize update camp schedules; expand district coverage; improve data quality',
            'Expected_Impact': 'Medium - improves consistency and equity',
            'Implementation_Cost': 'Medium'
        })

    # Sleepwalkers
    sleepwalkers = metrics_df[metrics_df['Archetype'] == 'Sleepwalker']
    if len(sleepwalkers) > 0:
        recommendations_data.append({
            'Archetype': 'Sleepwalker',
            'State_Count': len(sleepwalkers),
            'Primary_Issue': 'Low awareness and sporadic access',
            'Secondary_Issue': 'Limited infrastructure investment',
            'Recommended_Intervention': 'Intensive awareness campaigns; establish permanent enrollment centers; train field staff',
            'Expected_Impact': 'Medium-High - builds foundation for future growth',
            'Implementation_Cost': 'Medium'
        })

    # Excluded (Youth)
    excluded_youth = metrics_df[metrics_df['Archetype'] == 'Excluded (Youth)']
    if len(excluded_youth) > 0:
        recommendations_data.append({
            'Archetype': 'Excluded (Youth)',
            'State_Count': len(excluded_youth),
            'Primary_Issue': 'Youth severely underrepresented in updates',
            'Secondary_Issue': 'Future service failures for young adults',
            'Recommended_Intervention': 'School-based update camps at Class 10; Aadhaar integration with board exams; youth incentive programs',
            'Expected_Impact': 'Very High - prevents 18-year failure wave',
            'Implementation_Cost': 'Medium'
        })

    # Excluded (Update Imbalance)
    excluded_imbalance = metrics_df[metrics_df['Archetype'] == 'Excluded (Update Imbalance)']
    if len(excluded_imbalance) > 0:
        recommendations_data.append({
            'Archetype': 'Excluded (Update Imbalance)',
            'State_Count': len(excluded_imbalance),
            'Primary_Issue': 'Extreme imbalance between bio/demo updates',
            'Secondary_Issue': 'Type-specific infrastructure gaps',
            'Recommended_Intervention': 'Diagnostic camps to identify issue; targeted infrastructure for lagging type',
            'Expected_Impact': 'Medium - rebalances update ecosystem',
            'Implementation_Cost': 'Low-Medium'
        })

    # Excluded (Geographic)
    excluded_geo = metrics_df[metrics_df['Archetype'] == 'Excluded (Geographic)']
    if len(excluded_geo) > 0:
        recommendations_data.append({
            'Archetype': 'Excluded (Geographic)',
            'State_Count': len(excluded_geo),
            'Primary_Issue': 'High geographic concentration (urban-only access)',
            'Secondary_Issue': 'Rural population systematically underserved',
            'Recommended_Intervention': 'Mobile units for rural/remote areas; partnership with local admin; incentivize rural camp attendance',
            'Expected_Impact': 'High - dramatically improves rural access',
            'Implementation_Cost': 'High'
        })

    recommendations_df = pd.DataFrame(recommendations_data)

    # Save recommendations
    recs_path = METRICS_DIR / 'archetype_recommendations.csv'
    recommendations_df.to_csv(recs_path, index=False)
    print(f"  Saved: {recs_path}")

    return recommendations_df


# =============================================================================
# STATE PROFILE ANALYSIS
# =============================================================================

def analyze_state_profile(state_name: str, metrics_df: pd.DataFrame, state_data: pd.DataFrame):
    """Generate detailed profile for a specific state."""

    state_row = metrics_df[metrics_df['state'] == state_name]
    if len(state_row) == 0:
        print(f"State '{state_name}' not found in data.")
        return

    state_row = state_row.iloc[0]
    state_raw = state_data[state_data['state'] == state_name].iloc[0]

    # Build profile
    print("\n" + "="*70)
    print(f"STATE PROFILE: {state_name}")
    print("="*70)

    print(f"\n[ARCHETYPE & HEALTH]")
    print(f"  Archetype:           {state_row['Archetype']} {state_row['Archetype_Symbol']}")
    print(f"  Health Score:        {state_row['Health_Score']:.1f}/100")

    print(f"\n[FIVE PILLAR METRICS]")
    print(f"  IDI (Def. Index):    {state_row['IDI']*100:+.2f}% ({('Deficit' if state_row['IDI'] > 0 else 'Surplus')})")
    print(f"  UBI (Balance):       {state_row['UBI']:.3f} ({('Bio-heavy' if state_row['UBI'] > 0.5 else 'Demo-heavy')})")
    print(f"  YIR (Youth Inc.):    {state_row['YIR']:.2f} ({('Below' if state_row['YIR'] < 1 else 'Above')} national avg)")
    print(f"  GCI (Equity):        {state_row['GCI']:.3f} ({('High concentration' if state_row['GCI'] > 0.5 else 'Well distributed')})")
    print(f"  TCS (Consistency):   {state_row['TCS']:.3f} ({('Sporadic' if state_row['TCS'] < 0.4 else 'Stable')})")

    print(f"\n[PROBLEM RISK BREAKDOWN]")
    print(f"  PDS Risk:            {state_row['PDS_Risk']:.1f}% ({('CRITICAL' if state_row['PDS_Risk'] > 75 else 'HIGH' if state_row['PDS_Risk'] > 50 else 'MODERATE' if state_row['PDS_Risk'] > 25 else 'LOW')})")
    print(f"  DBT Risk:            {state_row['DBT_Risk']:.1f}% ({('CRITICAL' if state_row['DBT_Risk'] > 75 else 'HIGH' if state_row['DBT_Risk'] > 50 else 'MODERATE' if state_row['DBT_Risk'] > 25 else 'LOW')})")
    print(f"  Scholarship Risk:    {state_row['Scholarship_Risk']:.1f}% ({('CRITICAL' if state_row['Scholarship_Risk'] > 50 else 'HIGH' if state_row['Scholarship_Risk'] > 30 else 'MODERATE' if state_row['Scholarship_Risk'] > 15 else 'LOW')})")
    print(f"  OTP Risk:            {state_row['OTP_Risk']:.1f}% ({('CRITICAL' if state_row['OTP_Risk'] > 75 else 'HIGH' if state_row['OTP_Risk'] > 50 else 'MODERATE' if state_row['OTP_Risk'] > 25 else 'LOW')})")
    print(f"  Banking Risk:        {state_row['Banking_Risk']:.1f}% ({('CRITICAL' if state_row['Banking_Risk'] > 50 else 'HIGH' if state_row['Banking_Risk'] > 35 else 'MODERATE' if state_row['Banking_Risk'] > 20 else 'LOW')})")

    print(f"\n[ENROLLMENT & ACTIVITY]")
    print(f"  Total Enrolments:    {state_raw['total_enrolment']:,.0f}")
    print(f"  Child (0-5):         {state_raw['age_0_5']:,.0f}")
    print(f"  Youth (5-17):        {state_raw['age_5_17']:,.0f}")
    print(f"  Adult (18+):         {state_raw['age_18_greater']:,.0f}")
    print(f"\n  Total Updates:       {state_row['total_updates']:,.0f}")
    print(f"  Biometric Updates:   {state_row['total_bio']:,.0f}")
    print(f"  Demographic Updates: {state_row['total_demo']:,.0f}")

    print(f"\n[PRIMARY ISSUES]")
    risk_dict = {
        'PDS': state_row['PDS_Risk'],
        'DBT': state_row['DBT_Risk'],
        'Scholarship': state_row['Scholarship_Risk'],
        'OTP': state_row['OTP_Risk'],
        'Banking': state_row['Banking_Risk']
    }
    sorted_risks = sorted(risk_dict.items(), key=lambda x: x[1], reverse=True)
    for i, (risk_type, risk_val) in enumerate(sorted_risks[:3], 1):
        print(f"  {i}. {risk_type} failure risk ({risk_val:.1f}%)")

    print(f"\n[RECOMMENDED ACTIONS]")
    archetype = state_row['Archetype']
    if 'Digital Leader' in archetype:
        print(f"  > Share best practices with other states")
        print(f"  > Pilot advanced e-Aadhaar features")
        print(f"  > Mentor emerging states")
    elif 'Sprinter' in archetype:
        print(f"  > Deploy mobile update vans rapidly")
        print(f"  > Focus camps on primary risk areas")
        print(f"  > Scale infrastructure investment")
    elif 'Sleepwalker' in archetype:
        print(f"  > Launch awareness campaigns")
        print(f"  > Establish permanent enrollment centers")
        print(f"  > Train and deploy field staff")
    elif 'Youth' in archetype:
        print(f"  > Integrate with school curriculum")
        print(f"  > School-based update camps at Class 10")
        print(f"  > Youth incentive programs")
    elif 'Geographic' in archetype:
        print(f"  > Deploy mobile units to rural areas")
        print(f"  > Partner with local administration")
        print(f"  > Incentivize remote area attendance")
    elif 'Imbalance' in archetype:
        print(f"  > Diagnostic camps to identify root cause")
        print(f"  > Type-specific infrastructure development")
        print(f"  > Rebalance update camps")

    print("\n" + "="*70 + "\n")


# =============================================================================
# VISUALIZATIONS
# =============================================================================

def create_visualizations(metrics_df: pd.DataFrame,
                          monthly_data: pd.DataFrame):
    """Generate all visualizations."""
    print("\n" + "="*60)
    print("GENERATING VISUALIZATIONS")
    print("="*60)

    # Color palette for archetypes
    archetype_colors = {
        'Digital Leader': '#2ecc71',      # Green
        'Sprinter': '#f1c40f',            # Yellow
        'Sleepwalker': '#e74c3c',         # Red
        'Excluded (Youth)': '#e67e22',    # Orange
        'Excluded (Update Imbalance)': '#e67e22',
        'Excluded (Geographic)': '#e67e22',
        'Moderate': '#3498db'             # Blue
    }

    # 1. Archetype Summary
    print("  [1/10] Archetype Summary...")
    fig, ax = plt.subplots(figsize=(10, 6))
    archetype_counts = metrics_df['Archetype'].value_counts()
    colors = [archetype_colors.get(a, '#95a5a6') for a in archetype_counts.index]
    bars = ax.barh(archetype_counts.index, archetype_counts.values, color=colors)
    ax.set_xlabel('Number of States')
    ax.set_title('State Distribution by Archetype', fontsize=14, fontweight='bold')
    for bar, count in zip(bars, archetype_counts.values):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
                str(count), va='center', fontweight='bold')
    plt.tight_layout()
    plt.savefig(VIZ_DIR / '01_archetype_summary.png', dpi=150, bbox_inches='tight')
    plt.close()

    # 2. Archetype Scatter Plot
    print("  [2/10] Archetype Scatter Plot...")
    fig, ax = plt.subplots(figsize=(12, 8))
    for archetype in metrics_df['Archetype'].unique():
        subset = metrics_df[metrics_df['Archetype'] == archetype]
        ax.scatter(subset['IDI'] * 100, subset['Health_Score'],
                   c=archetype_colors.get(archetype, '#95a5a6'),
                   label=archetype, s=100, alpha=0.7, edgecolors='black')
    ax.axvline(x=0, color='gray', linestyle='--', alpha=0.5)
    ax.set_xlabel('Infrastructure Deficit Index (IDI) %', fontsize=12)
    ax.set_ylabel('Health Score', fontsize=12)
    ax.set_title('State Ecosystem: IDI vs Health Score by Archetype', fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    plt.tight_layout()
    plt.savefig(VIZ_DIR / '02_archetype_scatter.png', dpi=150, bbox_inches='tight')
    plt.close()

    # 3. Health Dashboard Heatmap
    print("  [3/10] Health Dashboard Heatmap...")
    heatmap_data = metrics_df.set_index('state')[['IDI', 'UBI', 'YIR', 'GCI', 'TCS', 'Health_Score']]
    heatmap_data = heatmap_data.sort_values('Health_Score', ascending=False).head(25)

    fig, ax = plt.subplots(figsize=(12, 14))

    # Normalize for heatmap display
    heatmap_normalized = heatmap_data.copy()
    for col in heatmap_normalized.columns:
        if col == 'IDI':
            heatmap_normalized[col] = -heatmap_normalized[col]  # Invert IDI
        if col != 'Health_Score':
            min_val = heatmap_normalized[col].min()
            max_val = heatmap_normalized[col].max()
            heatmap_normalized[col] = (heatmap_normalized[col] - min_val) / (max_val - min_val + 0.001)
        else:
            heatmap_normalized[col] = heatmap_normalized[col] / 100

    sns.heatmap(heatmap_normalized, annot=heatmap_data.round(2), fmt='',
                cmap='RdYlGn', center=0.5, ax=ax,
                cbar_kws={'label': 'Normalized Score'})
    ax.set_title('Aadhaar Ecosystem Health Dashboard (Top 25 States)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Metrics')
    ax.set_ylabel('State')
    plt.tight_layout()
    plt.savefig(VIZ_DIR / '03_health_heatmap.png', dpi=150, bbox_inches='tight')
    plt.close()

    # 4. IDI Diverging Bar Chart
    print("  [4/10] IDI Diverging Bar Chart...")
    fig, ax = plt.subplots(figsize=(12, 10))
    idi_sorted = metrics_df.sort_values('IDI')
    colors = ['#e74c3c' if x > 0 else '#2ecc71' for x in idi_sorted['IDI']]
    ax.barh(idi_sorted['state'], idi_sorted['IDI'] * 100, color=colors)
    ax.axvline(x=0, color='black', linewidth=1)
    ax.set_xlabel('Infrastructure Deficit Index (IDI) %', fontsize=12)
    ax.set_title('Infrastructure Deficit: Surplus (Green) vs Deficit (Red)', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(VIZ_DIR / '04_idi_diverging.png', dpi=150, bbox_inches='tight')
    plt.close()

    # 5. Youth Inclusion Bar
    print("  [5/10] Youth Inclusion Bar...")
    fig, ax = plt.subplots(figsize=(12, 10))
    yir_sorted = metrics_df.sort_values('YIR', ascending=True)
    colors = [archetype_colors.get(a, '#95a5a6') for a in yir_sorted['Archetype']]
    ax.barh(yir_sorted['state'], yir_sorted['YIR'], color=colors)
    ax.axvline(x=1.0, color='black', linestyle='--', linewidth=1, label='National Average')
    ax.axvline(x=0.7, color='red', linestyle='--', linewidth=1, alpha=0.5, label='Exclusion Threshold')
    ax.set_xlabel('Youth Inclusion Ratio (YIR)', fontsize=12)
    ax.set_title('Youth Inclusion Ratio by State', fontsize=14, fontweight='bold')
    ax.legend()
    plt.tight_layout()
    plt.savefig(VIZ_DIR / '05_yir_bar.png', dpi=150, bbox_inches='tight')
    plt.close()

    # 6. GCI Bar
    print("  [6/10] Geographic Equity Bar...")
    fig, ax = plt.subplots(figsize=(12, 10))
    gci_sorted = metrics_df.sort_values('GCI', ascending=False)
    colors = ['#e74c3c' if x > 0.5 else '#f1c40f' if x > 0.3 else '#2ecc71' for x in gci_sorted['GCI']]
    ax.barh(gci_sorted['state'], gci_sorted['GCI'], color=colors)
    ax.axvline(x=0.5, color='red', linestyle='--', linewidth=1, alpha=0.5)
    ax.axvline(x=0.3, color='orange', linestyle='--', linewidth=1, alpha=0.5)
    ax.set_xlabel('Geographic Concentration Index (GCI)', fontsize=12)
    ax.set_title('Geographic Concentration (Lower = More Equitable)', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(VIZ_DIR / '06_gci_bar.png', dpi=150, bbox_inches='tight')
    plt.close()

    # 7. Update Balance Stacked Bar
    print("  [7/10] Update Balance Stacked Bar...")
    fig, ax = plt.subplots(figsize=(12, 10))
    balance_data = metrics_df.sort_values('UBI', ascending=True)
    ax.barh(balance_data['state'], balance_data['UBI'], color='#3498db', label='Biometric')
    ax.barh(balance_data['state'], 1 - balance_data['UBI'], left=balance_data['UBI'],
            color='#9b59b6', label='Demographic')
    ax.axvline(x=0.425, color='green', linestyle='--', linewidth=2, label='Ideal Balance')
    ax.set_xlabel('Update Balance (Bio | Demo)', fontsize=12)
    ax.set_title('Biometric vs Demographic Update Balance', fontsize=14, fontweight='bold')
    ax.legend(loc='lower right')
    plt.tight_layout()
    plt.savefig(VIZ_DIR / '07_ubi_stacked.png', dpi=150, bbox_inches='tight')
    plt.close()

    # 8. Temporal Consistency Timeline
    print("  [8/10] Temporal Consistency Timeline...")
    fig, ax = plt.subplots(figsize=(14, 8))

    # Select representative states
    top_tcs = metrics_df.nlargest(3, 'TCS')['state'].tolist()
    bottom_tcs = metrics_df.nsmallest(3, 'TCS')['state'].tolist()
    selected_states = top_tcs + bottom_tcs

    for state in selected_states:
        state_data = monthly_data[monthly_data['state'] == state].sort_values('month')
        if len(state_data) > 0:
            months = [str(m) for m in state_data['month']]
            values = state_data['total_updates'].values
            linestyle = '-' if state in top_tcs else '--'
            ax.plot(months, values, marker='o', label=state, linestyle=linestyle)

    ax.set_xlabel('Month', fontsize=12)
    ax.set_ylabel('Total Updates', fontsize=12)
    ax.set_title('Monthly Update Trends: High TCS (solid) vs Low TCS (dashed)', fontsize=14, fontweight='bold')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(VIZ_DIR / '08_temporal_trends.png', dpi=150, bbox_inches='tight')
    plt.close()

    # 9. Radar Chart for Archetype Representatives
    print("  [9/10] Radar Chart...")
    fig, axes = plt.subplots(2, 2, figsize=(14, 14), subplot_kw=dict(projection='polar'))

    categories = ['IDI_score', 'UBI_score', 'YIR_score', 'GCI_score', 'TCS_score']
    labels = ['Low Deficit', 'Balance', 'Youth Inc.', 'Equity', 'Consistency']

    archetype_order = ['Digital Leader', 'Sprinter', 'Sleepwalker', 'Moderate']

    for idx, archetype in enumerate(archetype_order):
        ax = axes[idx // 2, idx % 2]
        subset = metrics_df[metrics_df['Archetype'].str.contains(archetype.split()[0])]
        if len(subset) > 0:
            representative = subset.iloc[0]
            values = [representative[cat] for cat in categories]
            values.append(values[0])  # Close the polygon

            angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
            angles.append(angles[0])

            ax.plot(angles, values, 'o-', linewidth=2,
                    color=archetype_colors.get(archetype, '#95a5a6'))
            ax.fill(angles, values, alpha=0.25,
                    color=archetype_colors.get(archetype, '#95a5a6'))
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(labels)
            ax.set_title(f"{archetype}\n({representative['state']})", fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig(VIZ_DIR / '09_radar_archetypes.png', dpi=150, bbox_inches='tight')
    plt.close()

    # 10. Final Rankings Table
    print("  [10/10] State Rankings Table...")
    fig, ax = plt.subplots(figsize=(16, 12))
    ax.axis('off')

    table_data = metrics_df.sort_values('Health_Score', ascending=False).head(20)
    table_data = table_data[['state', 'Archetype', 'Health_Score', 'IDI', 'UBI', 'YIR', 'GCI', 'TCS']]
    table_data['Rank'] = range(1, len(table_data) + 1)
    table_data = table_data[['Rank', 'state', 'Archetype', 'Health_Score', 'IDI', 'UBI', 'YIR', 'GCI', 'TCS']]

    # Format numbers
    table_data['Health_Score'] = table_data['Health_Score'].round(1)
    table_data['IDI'] = (table_data['IDI'] * 100).round(2).astype(str) + '%'
    table_data['UBI'] = table_data['UBI'].round(2)
    table_data['YIR'] = table_data['YIR'].round(2)
    table_data['GCI'] = table_data['GCI'].round(2)
    table_data['TCS'] = table_data['TCS'].round(2)

    table = ax.table(cellText=table_data.values,
                     colLabels=['Rank', 'State', 'Archetype', 'Health', 'IDI', 'UBI', 'YIR', 'GCI', 'TCS'],
                     cellLoc='center',
                     loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.8)

    # Color header
    for i in range(len(table_data.columns)):
        table[(0, i)].set_facecolor('#34495e')
        table[(0, i)].set_text_props(color='white', fontweight='bold')

    ax.set_title('Aadhaar Ecosystem Health Rankings (Top 20 States)',
                 fontsize=16, fontweight='bold', pad=20)
    plt.tight_layout()
    plt.savefig(VIZ_DIR / '10_state_rankings.png', dpi=150, bbox_inches='tight')
    plt.close()

    print(f"\n  All visualizations saved to: {VIZ_DIR}")


# =============================================================================
# PROBLEM-SPECIFIC VISUALIZATIONS
# =============================================================================

def create_problem_visualizations(metrics_df: pd.DataFrame):
    """Generate problem-specific visualizations."""
    print("\n" + "="*60)
    print("GENERATING PROBLEM-SPECIFIC VISUALIZATIONS")
    print("="*60)

    # 11. Problem Risk Heatmap
    print("  [11/15] Problem Risk Heatmap...")
    fig, ax = plt.subplots(figsize=(12, 14))

    heatmap_data = metrics_df.sort_values('Composite_Problem_Risk', ascending=False).head(25)
    risk_cols = ['PDS_Risk', 'DBT_Risk', 'Scholarship_Risk', 'OTP_Risk', 'Banking_Risk']
    heatmap_display = heatmap_data[risk_cols].copy()
    heatmap_display.index = heatmap_data['state'].values

    sns.heatmap(heatmap_display, annot=heatmap_display.round(1), fmt='',
                cmap='YlOrRd', ax=ax, cbar_kws={'label': 'Risk %'})
    ax.set_title('Problem Risk Heatmap: Top 25 States by Composite Risk', fontsize=14, fontweight='bold')
    ax.set_xlabel('Problem Type')
    ax.set_ylabel('State')
    plt.tight_layout()
    plt.savefig(VIZ_DIR / '11_problem_risk_heatmap.png', dpi=150, bbox_inches='tight')
    plt.close()

    # 12. Problem Severity Distribution (Box plots)
    print("  [12/15] Problem Severity Distribution...")
    fig, axes = plt.subplots(1, 5, figsize=(18, 5))

    problems = ['PDS_Risk', 'DBT_Risk', 'Scholarship_Risk', 'OTP_Risk', 'Banking_Risk']
    problem_names = ['PDS', 'DBT', 'Scholarship', 'OTP', 'Banking']
    colors_box = ['#e74c3c', '#3498db', '#f1c40f', '#2ecc71', '#9b59b6']

    for idx, (problem, name, color) in enumerate(zip(problems, problem_names, colors_box)):
        ax = axes[idx]
        bp = ax.boxplot([metrics_df[problem]], patch_artist=True)
        bp['boxes'][0].set_facecolor(color)
        ax.set_ylabel('Risk %', fontsize=10)
        ax.set_title(name, fontsize=12, fontweight='bold')
        ax.set_xticklabels([''])
        ax.grid(axis='y', alpha=0.3)

    plt.suptitle('Distribution of Problem Risks Across States', fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(VIZ_DIR / '12_problem_severity_distribution.png', dpi=150, bbox_inches='tight')
    plt.close()

    # 13. Archetype-Problem Matrix
    print("  [13/15] Archetype-Problem Matrix...")
    fig, ax = plt.subplots(figsize=(12, 6))

    archetype_risk = metrics_df.groupby('Archetype')[problems].mean()
    archetype_risk.columns = problem_names

    x = np.arange(len(problem_names))
    width = 0.12
    colors_arch = ['#2ecc71', '#f1c40f', '#e74c3c', '#3498db', '#e67e22', '#e67e22', '#e67e22']

    for i, archetype in enumerate(archetype_risk.index):
        ax.bar(x + i*width, archetype_risk.loc[archetype], width, label=archetype)

    ax.set_ylabel('Average Risk %', fontsize=12)
    ax.set_title('Problem Risks by Archetype', fontsize=14, fontweight='bold')
    ax.set_xticks(x + width * 3)
    ax.set_xticklabels(problem_names)
    ax.legend(loc='best')
    plt.tight_layout()
    plt.savefig(VIZ_DIR / '13_archetype_problem_matrix.png', dpi=150, bbox_inches='tight')
    plt.close()

    # 14. State Problem Profiles (Radar charts for top critical states)
    print("  [14/15] State Problem Profiles...")
    fig, axes = plt.subplots(2, 3, figsize=(16, 12), subplot_kw=dict(projection='polar'))

    top_critical = metrics_df.nlargest(6, 'Composite_Problem_Risk')

    for idx, (_, state_row) in enumerate(top_critical.iterrows()):
        ax = axes[idx // 3, idx % 3]

        categories = ['PDS', 'DBT', 'Scholarship', 'OTP', 'Banking']
        values = [state_row['PDS_Risk'], state_row['DBT_Risk'],
                 state_row['Scholarship_Risk'], state_row['OTP_Risk'],
                 state_row['Banking_Risk']]
        values.append(values[0])

        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        angles.append(angles[0])

        ax.plot(angles, values, 'o-', linewidth=2, color='#e74c3c')
        ax.fill(angles, values, alpha=0.25, color='#e74c3c')
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories)
        ax.set_ylim(0, 100)
        ax.set_title(f"{state_row['state']}\n({state_row['Archetype']})\nComposite Risk: {state_row['Composite_Problem_Risk']:.1f}%",
                    fontsize=11, fontweight='bold')
        ax.grid(True)

    plt.tight_layout()
    plt.savefig(VIZ_DIR / '14_state_problem_profiles.png', dpi=150, bbox_inches='tight')
    plt.close()

    # 15. Intervention Priority Map
    print("  [15/15] Intervention Priority Map...")
    fig, ax = plt.subplots(figsize=(14, 10))

    scatter = ax.scatter(metrics_df['total_enrolment'] / 1000,
                        metrics_df['Composite_Problem_Risk'],
                        c=metrics_df['Health_Score'],
                        s=metrics_df['total_updates'] / 5000,
                        cmap='RdYlGn',
                        alpha=0.6,
                        edgecolors='black',
                        linewidth=1)

    # Annotate high-priority states (high risk + high population)
    high_priority = metrics_df[
        (metrics_df['Composite_Problem_Risk'] > metrics_df['Composite_Problem_Risk'].quantile(0.75)) &
        (metrics_df['total_enrolment'] > metrics_df['total_enrolment'].quantile(0.50))
    ]

    for _, row in high_priority.iterrows():
        ax.annotate(row['state'], (row['total_enrolment'] / 1000, row['Composite_Problem_Risk']),
                   fontsize=9, alpha=0.7, xytext=(5, 5), textcoords='offset points')

    ax.set_xlabel('Total Enrolments (thousands)', fontsize=12)
    ax.set_ylabel('Composite Problem Risk %', fontsize=12)
    ax.set_title('Intervention Priority Map\n(Size = Update Volume, Color = Health Score)',
                fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)

    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Health Score', fontsize=11)

    plt.tight_layout()
    plt.savefig(VIZ_DIR / '15_intervention_priority_map.png', dpi=150, bbox_inches='tight')
    plt.close()

    print(f"\n  Problem-specific visualizations saved to: {VIZ_DIR}")


# =============================================================================
# SAVE RESULTS
# =============================================================================

def save_results(metrics_df: pd.DataFrame):
    """Save calculated metrics to CSV."""
    print("\n" + "="*60)
    print("SAVING RESULTS")
    print("="*60)

    # Save full metrics
    output_path = METRICS_DIR / 'state_ecosystem_metrics.csv'
    metrics_df.to_csv(output_path, index=False)
    print(f"  Saved: {output_path}")

    # Save summary by archetype
    archetype_summary = metrics_df.groupby('Archetype').agg({
        'state': 'count',
        'Health_Score': 'mean',
        'IDI': 'mean',
        'UBI': 'mean',
        'YIR': 'mean',
        'GCI': 'mean',
        'TCS': 'mean'
    }).round(3)
    archetype_summary.columns = ['State_Count', 'Avg_Health', 'Avg_IDI', 'Avg_UBI', 'Avg_YIR', 'Avg_GCI', 'Avg_TCS']
    archetype_summary.to_csv(METRICS_DIR / 'archetype_summary.csv')
    print(f"  Saved: {METRICS_DIR / 'archetype_summary.csv'}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main execution function."""
    print("\n" + "="*60)
    print("  AADHAAR ECOSYSTEM HEALTH ANALYSIS")
    print("  'The Aadhaar Health Check' - Deep Problem Analysis")
    print("="*60)

    # Load data
    enrolment, biometric, demographic = load_data()

    # Preprocess
    enrolment, biometric, demographic = preprocess_data(enrolment, biometric, demographic)

    # Aggregate
    state_data = aggregate_by_state(enrolment, biometric, demographic)
    district_data = aggregate_by_district(biometric, demographic)
    monthly_data = aggregate_by_month(biometric, demographic)

    # Calculate metrics
    metrics_df = calculate_metrics(state_data, district_data, monthly_data)

    # Calculate health score
    metrics_df = calculate_health_score(metrics_df)

    # Assign archetypes
    metrics_df = assign_archetypes(metrics_df)

    # ===== NEW: Deep Problem Analysis =====
    # Calculate problem-specific risks
    metrics_df = calculate_problem_risks(state_data, metrics_df)

    # Create visualizations (original 10)
    create_visualizations(metrics_df, monthly_data)

    # Create problem-specific visualizations (5 new)
    create_problem_visualizations(metrics_df)

    # Generate insights report
    generate_insights_report(metrics_df)

    # Generate archetype recommendations
    generate_recommendations_by_archetype(metrics_df)

    # Save results (enhanced with problem risks)
    save_results(metrics_df)

    # Print final summary
    print("\n" + "="*60)
    print("  DEEP PROBLEM ANALYSIS COMPLETE")
    print("="*60)
    print(f"\n  Top 5 States by Health Score:")
    top5 = metrics_df.nlargest(5, 'Health_Score')[['state', 'Archetype', 'Health_Score', 'Archetype_Display']]
    for _, row in top5.iterrows():
        print(f"    {row['Archetype_Display']}: {row['state']} ({row['Health_Score']:.1f})")

    print(f"\n  Bottom 5 States by Composite Problem Risk:")
    worst5 = metrics_df.nlargest(5, 'Composite_Problem_Risk')[['state', 'Archetype', 'Composite_Problem_Risk', 'Archetype_Display']]
    for _, row in worst5.iterrows():
        print(f"    {row['Archetype_Display']}: {row['state']} (Risk: {row['Composite_Problem_Risk']:.1f}%)")

    print(f"\n  Critical Problem Counts:")
    print(f"    PDS Risk (>75%): {len(metrics_df[metrics_df['PDS_Risk'] > 75])} states")
    print(f"    DBT Risk (>75%): {len(metrics_df[metrics_df['DBT_Risk'] > 75])} states")
    print(f"    Scholarship Risk (>50%): {len(metrics_df[metrics_df['Scholarship_Risk'] > 50])} states")
    print(f"    OTP Risk (>75%): {len(metrics_df[metrics_df['OTP_Risk'] > 75])} states")
    print(f"    Banking Risk (>50%): {len(metrics_df[metrics_df['Banking_Risk'] > 50])} states")

    print("\n" + "="*60)
    print("  OUTPUT FILES GENERATED:")
    print("="*60)
    print(f"  Visualizations: {VIZ_DIR}/")
    print(f"  Metrics: {METRICS_DIR}/")
    print(f"  Reports: {OUTPUT_DIR / 'reports'}/")
    print("="*60)

    return metrics_df


if __name__ == "__main__":
    metrics_df = main()
