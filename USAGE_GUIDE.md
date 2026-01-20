# Deep Problem Analysis - Quick Usage Guide

## Running the Full Analysis

```bash
cd /c/Users/naikn/Desktop/UU
python src/aadhaar_analysis.py
```

This will:
1. Load and process all data (3 datasets)
2. Calculate 5 pillar metrics (IDI, UBI, YIR, GCI, TCS)
3. Calculate health scores and assign archetypes
4. **[NEW]** Calculate 5 problem-specific risks
5. Generate 15 visualizations (10 original + 5 new)
6. **[NEW]** Generate insights report
7. **[NEW]** Generate archetype recommendations
8. Save all results to outputs/

Expected runtime: 5-10 minutes

---

## Using New Functions Individually

### 1. State Profile Analysis

```python
from src.aadhaar_analysis import *

# Load and process data
enrolment, biometric, demographic = load_data()
enrolment, biometric, demographic = preprocess_data(enrolment, biometric, demographic)

state_data = aggregate_by_state(enrolment, biometric, demographic)
district_data = aggregate_by_district(biometric, demographic)
monthly_data = aggregate_by_month(biometric, demographic)

metrics_df = calculate_metrics(state_data, district_data, monthly_data)
metrics_df = calculate_health_score(metrics_df)
metrics_df = assign_archetypes(metrics_df)
metrics_df = calculate_problem_risks(state_data, metrics_df)

# Get profile for any state
analyze_state_profile('Bihar', metrics_df, state_data)
analyze_state_profile('Tamil Nadu', metrics_df, state_data)
analyze_state_profile('Kerala', metrics_df, state_data)
```

### 2. Access Problem Risk Data

```python
import pandas as pd

# Load metrics with all risk columns
metrics_df = pd.read_csv('outputs/metrics/state_ecosystem_metrics.csv')

# Filter by problem type
high_pds_risk = metrics_df[metrics_df['PDS_Risk'] > 75]
high_scholarship_risk = metrics_df[metrics_df['Scholarship_Risk'] > 50]

# Sort by composite risk
ranked_by_risk = metrics_df.sort_values('Composite_Problem_Risk', ascending=False)
print(ranked_by_risk[['state', 'Archetype', 'Composite_Problem_Risk', 'Health_Score']])
```

### 3. Access Recommendations

```python
# Load archetype recommendations
recommendations = pd.read_csv('outputs/metrics/archetype_recommendations.csv')

# Get recommendations for specific archetype
sprinter_recs = recommendations[recommendations['Archetype'] == 'Sprinter']
print(sprinter_recs[['Primary_Issue', 'Recommended_Intervention', 'Expected_Impact']])
```

### 4. Read Insights Report

```python
# Open and read insights report
with open('outputs/reports/insights_report.md', 'r', encoding='utf-8') as f:
    insights = f.read()
    print(insights)
```

---

## New Columns in state_ecosystem_metrics.csv

Original columns (still available):
- state, total_enrolment, total_updates, total_bio, total_demo
- IDI, UBI, YIR, GCI, TCS (5 pillar metrics)
- Health_Score, Archetype

**New columns:**
- PDS_Risk: Biometric authentication failure risk (0-100)
- DBT_Risk: Name/address mismatch failure risk (0-100)
- Scholarship_Risk: Youth eKYC failure risk (0-100)
- OTP_Risk: Minor-to-adult transition failure risk (0-100)
- Banking_Risk: Financial exclusion risk (0-100)
- Composite_Problem_Risk: Average of all 5 risks (0-100)

Plus age demographic columns:
- age_0_5, age_5_17, age_18_greater (enrolments by age)
- bio_age_5_17, bio_age_17_ (biometric updates by age)
- demo_age_5_17, demo_age_17_ (demographic updates by age)

---

## Risk Interpretation Guide

### PDS_Risk (Biometric Authentication)
- 0-25%: Low - Most adults updated bios
- 25-50%: Moderate - Some adults need biometric camps
- 50-75%: High - Many PDS failures likely
- 75-100%: Critical - Majority of adults at risk

### DBT_Risk (Name/Address Mismatch)
- 0-25%: Low - Most adults updated demographics
- 25-50%: Moderate - Some DBT rejections expected
- 50-75%: High - Widespread payment failures
- 75-100%: Critical - Majority face payment issues

### Scholarship_Risk (Youth eKYC)
- 0-15%: Low - Youth well represented
- 15-30%: Moderate - Some youth exclusion
- 30-50%: High - Many youth excluded
- 50-100%: Critical - Widespread youth exclusion

### OTP_Risk (Mobile Update Gap)
- 0-25%: Low - Youth updating mobiles
- 25-50%: Moderate - Some OTP issues at 18
- 50-75%: High - Many 18-year-olds will fail
- 75-100%: Critical - Majority will face OTP failures

### Banking_Risk (Overall Exclusion)
- 0-20%: Low - Healthy ecosystem
- 20-35%: Moderate - Some financial exclusion
- 35-50%: High - Widespread access issues
- 50-100%: Critical - Systemic exclusion

### Composite_Problem_Risk
- 0-15%: Good - Multiple risk categories manageable
- 15-30%: Moderate - Requires intervention
- 30-50%: High - Multiple coordinated interventions needed
- 50-100%: Critical - Comprehensive systemic overhaul needed

---

## Archetype-Specific Recommendations

### Digital Leader
Problem: None (exemplary state)
Action: Share best practices; mentor other states

### Sprinter
Problem: Infrastructure lag behind growth
Action: Rapid mobile van deployment; targeted camps

### Moderate
Problem: Inconsistent operations
Action: Standardize schedules; expand coverage

### Sleepwalker
Problem: Low activity and awareness
Action: Awareness campaigns; permanent centers

### Excluded (Youth)
Problem: Youth systematically underserved
Action: School-based camps; board exam integration

### Excluded (Update Imbalance)
Problem: Extreme bio/demo gap
Action: Diagnostic camps; type-specific infrastructure

### Excluded (Geographic)
Problem: Rural/remote areas underserved
Action: Mobile units; partnership with local admin

---

## Visualization Guide

### Original Visualizations (01-10)
- 01: Archetype distribution
- 02: IDI vs Health Score scatter
- 03: Multi-metric heatmap
- 04: IDI deficit/surplus
- 05: Youth inclusion rankings
- 06: Geographic equity
- 07: Bio vs Demo balance
- 08: Monthly trends
- 09: Multi-metric radar charts
- 10: State rankings table

### Problem-Specific Visualizations (11-15)
- 11: Problem risk heatmap (5 problems x top 25 states)
- 12: Risk distribution box plots
- 13: Archetype-problem matrix
- 14: State problem profiles (radar for top 6)
- 15: Intervention priority map (scatter)

---

## Example Queries

### Find states with youth exclusion crisis

```python
import pandas as pd

metrics = pd.read_csv('outputs/metrics/state_ecosystem_metrics.csv')
youth_crisis = metrics[metrics['Scholarship_Risk'] > 75].sort_values('Scholarship_Risk', ascending=False)
print(youth_crisis[['state', 'Scholarship_Risk', 'YIR', 'Archetype']])
```

### Find states needing mobile van deployment

```python
sprinters = metrics[metrics['Archetype'] == 'Sprinter']
needs_vans = sprinters.sort_values('PDS_Risk', ascending=False)
print(needs_vans[['state', 'PDS_Risk', 'DBT_Risk', 'total_enrolment']])
```

### Find states with best practices to share

```python
digital_leaders = metrics[metrics['Archetype'] == 'Digital Leader']
print(digital_leaders[['state', 'Health_Score', 'TCS', 'GCI']])
```

### States at highest intervention priority

```python
critical = metrics[
    (metrics['Composite_Problem_Risk'] > 40) &
    (metrics['total_enrolment'] > metrics['total_enrolment'].quantile(0.5))
].sort_values('Composite_Problem_Risk', ascending=False)
print(critical[['state', 'Composite_Problem_Risk', 'total_enrolment', 'Archetype']])
```

---

## Output File Locations

```
outputs/
├── visualizations/
│   ├── 01-10_*.png (original)
│   └── 11-15_*.png (new problem-specific)
├── metrics/
│   ├── state_ecosystem_metrics.csv (all metrics + risks)
│   ├── archetype_summary.csv
│   └── archetype_recommendations.csv (new)
└── reports/
    └── insights_report.md (new)
```

---

## Key Performance Indicators

Track these to monitor ecosystem health:

1. **Composite_Problem_Risk Trend** - Should decrease with interventions
2. **Archetype Distribution** - More "Digital Leaders" over time
3. **Health_Score Improvement** - Track state-by-state progress
4. **Risk Gap Reduction** - Focus on closing extreme scores
5. **Archetype Movement** - "Sprinters" should advance; "Sleepwalkers" should awaken

---

## Support & Questions

For detailed information:
- See CLAUDE.md for project context
- See IMPLEMENTATION_SUMMARY.md for technical details
- Check src/aadhaar_analysis.py for docstrings
- Run with --verbose flag (if implemented) for debug output

---

Last Updated: 2026-01-19
