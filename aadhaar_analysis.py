import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os

# --- Configuration ---
DATA_DIR = r"c:\Users\naikn\Desktop\UU"
OUTPUT_DIR = os.path.join(DATA_DIR, "outputs")
OS_DIRS = {
    'metrics': os.path.join(OUTPUT_DIR, "metrics"),
    'visualizations': os.path.join(OUTPUT_DIR, "visualizations")
}

for d in OS_DIRS.values():
    os.makedirs(d, exist_ok=True)

# --- Data Loading ---
def load_data(pattern, type_name):
    all_files = glob.glob(os.path.join(DATA_DIR, pattern))
    print(f"[{type_name}] Found {len(all_files)} files.")
    df_list = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            # Ensure column consistency
            df.columns = [c.lower() for c in df.columns]
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
            df_list.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if not df_list:
        return pd.DataFrame()
    return pd.concat(df_list, ignore_index=True)

def main():
    print("Loading datasets...")
    # Load Enrolment
    enrol_df = load_data("data/enrolment/*.csv", "Enrolment")
    # Load Biometric
    bio_df = load_data("data/biometric/*.csv", "Biometric")
    # Load Demographic
    demo_df = load_data("data/demographic/*.csv", "Demographic")
    
    if enrol_df.empty or bio_df.empty or demo_df.empty:
        print("CRITICAL ERROR: One or more datasets could not be reflected. Check paths.")
        return

    # --- Standardize & Consolidate ---
    print("Aggregating data...")
    
    # Enrolment Totals (cols: age_0_5, age_5_17, age_18_greater)
    # Check actual column names in case of case sensitivity issues
    
    enrol_state = enrol_df.groupby('state')[['age_0_5', 'age_5_17', 'age_18_greater']].sum().reset_index()
    enrol_state['total_enrol'] = enrol_state.sum(axis=1, numeric_only=True)
    
    # Biometric Totals (cols: bio_age_5_17, bio_age_17_)
    bio_state = bio_df.groupby('state')[['bio_age_5_17', 'bio_age_17_']].sum().reset_index()
    bio_state['total_bio'] = bio_state.sum(axis=1, numeric_only=True)
    
    # Demographic Totals (cols: demo_age_5_17, demo_age_17_)
    demo_state = demo_df.groupby('state')[['demo_age_5_17', 'demo_age_17_']].sum().reset_index()
    demo_state['total_demo'] = demo_state.sum(axis=1, numeric_only=True)
    
    # Merge all
    print("Merging state data...")
    master_df = enrol_state.merge(bio_state, on='state', how='outer').merge(demo_state, on='state', how='outer').fillna(0)
    
    # Filter out small states/UTs/Unknowns for cleaner analysis (Total Enrol < 1000)
    master_df = master_df[master_df['total_enrol'] > 100].copy()
    
    # National Totals for Normalization
    national_enrol = master_df['total_enrol'].sum()
    national_bio = master_df['total_bio'].sum()
    national_demo = master_df['total_demo'].sum()
    total_national_activity = national_enrol + national_bio + national_demo
    
    print(f"National Totals: Enrol={national_enrol}, Bio={national_bio}, Demo={national_demo}")
    
    # --- CALCULATE METRICS (The 5 Pillars) ---
    print("Calculating Ecosystem Health Metrics...")
    
    # 1. Infrastructure Deficit Index (IDI)
    # IDI = Share of Enrolments - Share of Total Updates
    # Logic: If you carry 10% of India's enrolments but only 5% of updates, your infra is failing.
    master_df['enrol_share'] = (master_df['total_enrol'] / national_enrol) * 100
    master_df['update_share'] = ((master_df['total_bio'] + master_df['total_demo']) / (national_bio + national_demo)) * 100
    master_df['IDI'] = master_df['enrol_share'] - master_df['update_share']
    
    # 2. Update Balance Index (UBI)
    # UBI = Bio / (Bio + Demo)
    # Healthy range: 0.3 - 0.7. Too low = ignoring biometrics. Too high = demographic neglect.
    master_df['UBI'] = master_df['total_bio'] / (master_df['total_bio'] + master_df['total_demo'])
    
    # 3. Youth Inclusion Ratio (YIR)
    # Normalized against National Ratio
    master_df['youth_updates'] = master_df['bio_age_5_17'] + master_df['demo_age_5_17']
    master_df['adult_updates'] = master_df['bio_age_17_'] + master_df['demo_age_17_']
    
    national_youth_update_ratio = (master_df['youth_updates'].sum() / master_df['adult_updates'].sum())
    state_youth_update_ratio = master_df['youth_updates'] / master_df['adult_updates'].replace(0, 1)
    
    master_df['YIR'] = state_youth_update_ratio / national_youth_update_ratio
    
    # 4. Enrolment Maturity (EMI) (Replaces TCS for simplicity without monthly data)
    # EMI = % of enrolments that are Adults (18+). High % = Late adopters or Migrants.
    master_df['EMI'] = master_df['age_18_greater'] / master_df['total_enrol']

    # --- Composite Health Score ---
    # Convert IDI to Score (0 is ideal, large deviation is bad).
    # We use 1 / (1 + abs(IDI)) logic or linear normalization.
    
    def normalize(series):
        return (series - series.min()) / (series.max() - series.min())
    
    # Health Ingredients:
    # 1. Low IDI Magnitude (Balanced Infra)
    # 2. Balanced UBI (Closer to 0.5 is better) -> 1 - 2*|0.5 - UBI|
    # 3. High YIR (Youth Inclusion)
    
    s_idi = 1 - normalize(master_df['IDI'].abs())  # Higher is better (lower deficit/surplus gap)
    s_ubi = 1 - 2 * (0.5 - master_df['UBI']).abs() # Higher is better (balanced)
    s_yir = normalize(master_df['YIR'])            # Higher is better
    
    master_df['Health_Score'] = (0.4 * s_idi + 0.3 * s_ubi + 0.3 * s_yir) * 100
    
    # --- INSIGHT GENERATION: STATE ARCHETYPES ---
    print("Classifying States...")
    
    def get_archetype(row):
        idi = row['IDI']
        health = row['Health_Score']
        enrol_share = row['enrol_share']
        
        if health > 60:
            return "Digital Leader"
        elif idi > 1.0 and enrol_share > 5.0:
            return "Sprinter (High Growth, Lagging Infra)"
        elif idi > 0.5:
            return "Struggling (Infra Deficit)"
        elif row['YIR'] < 0.6:
            return "Exclusion Zone (Youth Left Behind)"
        elif row['UBI'] < 0.2:
            return "Biometric Laggard"
        else:
            return "Sleepwalker (Low Activity)"

    master_df['Archetype'] = master_df.apply(get_archetype, axis=1)

    print("\n--- STATE CLASSIFICATION RESULTS ---")
    print(master_df[['state', 'Archetype', 'Health_Score']].sort_values('Health_Score', ascending=False).head(10))

    # --- VISUALIZATIONS ---
    print("Generating visualizations...")
    sns.set_theme(style="whitegrid")
    
    # Plot 1: The Ecosystem Map (Scatter)
    plt.figure(figsize=(14, 10))
    # Filter for cleaner plot
    plot_df = master_df[master_df['total_enrol'] > 5000].sort_values('total_enrol', ascending=False)
    
    sns.scatterplot(
        data=plot_df, 
        x='IDI', 
        y='Health_Score', 
        size='total_enrol', 
        hue='Archetype',
        sizes=(50, 600),
        palette='viridis',
        alpha=0.8
    )
    
    # Add labels for top states
    for i, row in plot_df.head(10).iterrows():
        plt.text(
            row['IDI']+0.2, 
            row['Health_Score'], 
            row['state'], 
            fontsize=9
        )
        
    plt.axvline(0, color='gray', linestyle='--', alpha=0.5)
    plt.title('Aadhaar Ecosystem Health Map: Infrastructure Deficit vs Overall Health', fontsize=14)
    plt.xlabel('Infrastructure Deficit Index (IDI)\nPositive = Infra Gap (Lagging) | Negative = Infra Surplus (Leading)', fontsize=12)
    plt.ylabel('Composite Health Score (0-100)', fontsize=12)
    plt.legend(bbox_to_anchor=(1.01, 1), loc='upper left', borderaxespad=0)
    plt.tight_layout()
    plt.savefig(os.path.join(OS_DIRS['visualizations'], 'state_archetypes.png'))
    plt.close()
    
    # Plot 2: Infrastructure Deficit Bar Chart
    plt.figure(figsize=(12, 8))
    top_deficits = master_df.sort_values('IDI', ascending=False).head(10)
    top_surpluses = master_df.sort_values('IDI', ascending=True).head(10)
    combo = pd.concat([top_deficits, top_surpluses])
    
    sns.barplot(x='IDI', y='state', data=combo, palette='RdBu_r')
    plt.axvline(0, color='black', linewidth=1)
    plt.title('Infrastructure Deficit Index: Who is struggling to keep up?', fontsize=14)
    plt.xlabel('IDI Score (Enrol Share % - Update Share %)', fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(OS_DIRS['visualizations'], 'infrastructure_deficit.png'))
    plt.close()

    # Save Metrics
    master_df.to_csv(os.path.join(OS_DIRS['metrics'], 'state_health_metrics.csv'), index=False)
    print("Done! Analysis complete.")

if __name__ == "__main__":
    main()
