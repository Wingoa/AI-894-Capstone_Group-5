import pandas as pd
import os
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

CLEAN_DATA_PATH = "../resources/clean_data/training_data.csv"
PLOT_DIR = "../resources/plots/cleaned/"
os.makedirs(PLOT_DIR, exist_ok=True)

def load_clean_data():
    df = pd.read_csv(CLEAN_DATA_PATH)
    return df

if __name__ == "__main__":
    df = load_clean_data()
    print(f"Loaded cleaned data: {df.shape}")

    # 1. Histograms for key stats
    hist_cols = [
        'sig_str_landed', 'sig_str_per_min', 'td_landed', 'td_per_min',
        'ctrl_seconds', 'sub_att', 'rev', 'sig_str_accuracy', 'td_success', 'ctrl_pct'
    ]
    for col in hist_cols:
        if col in df.columns:
            data = pd.to_numeric(df[col], errors='coerce').dropna()
            if data.count() < 10 or (data != 0).sum() < 5:
                continue
            q_low = data.quantile(0.01)
            q_high = data.quantile(0.99)
            data_clip = data[(data >= q_low) & (data <= q_high)]
            plt.figure(figsize=(6, 3))
            plt.hist(data_clip, bins=30, color='skyblue', edgecolor='black')
            plt.title(f'Histogram of {col}')
            plt.xlabel(col)
            plt.ylabel('Frequency')
            plt.tight_layout()
            plt.savefig(os.path.join(PLOT_DIR, f"histogram_{col}.png"))
            plt.close()

    # 2. Scatterplots for important relationships
    scatter_pairs = [
        ('sig_str_landed', 'td_landed'),
        ('sig_str_per_min', 'td_per_min'),
        ('ctrl_seconds', 'td_landed'),
        ('sig_str_accuracy', 'td_success')
    ]
    for x_col, y_col in scatter_pairs:
        if x_col in df.columns and y_col in df.columns:
            x = pd.to_numeric(df[x_col], errors='coerce').dropna()
            y = pd.to_numeric(df[y_col], errors='coerce').dropna()
            min_len = min(len(x), len(y), 500)
            if min_len > 10:
                sample_idx = np.random.choice(np.arange(min_len), size=min_len, replace=False)
                plt.figure(figsize=(6, 4))
                plt.scatter(x.iloc[sample_idx], y.iloc[sample_idx], alpha=0.5, s=10)
                plt.title(f'Scatterplot: {x_col} vs {y_col}')
                plt.xlabel(x_col)
                plt.ylabel(y_col)
                plt.tight_layout()
                plt.savefig(os.path.join(PLOT_DIR, f"scatter_{x_col}_vs_{y_col}.png"))
                plt.close()

    # 3. Boxplots by outcome (if available)
    if 'outcome' in df.columns:
        for col in ['sig_str_per_min', 'td_per_min', 'ctrl_seconds']:
            if col in df.columns:
                data = pd.to_numeric(df[col], errors='coerce')
                plt.figure(figsize=(7, 4))
                sns.boxplot(x=df['outcome'], y=data)
                plt.title(f'Boxplot: {col} by Outcome')
                plt.xlabel('Outcome')
                plt.ylabel(col)
                plt.tight_layout()
                plt.savefig(os.path.join(PLOT_DIR, f"boxplot_{col}_by_outcome.png"))
                plt.close()

    # 4. Boxplots by weight_class (if available)
    if 'weight_class' in df.columns:
        for col in ['sig_str_per_min', 'td_per_min', 'ctrl_seconds']:
            if col in df.columns:
                data = pd.to_numeric(df[col], errors='coerce')
                plt.figure(figsize=(10, 4))
                sns.boxplot(x=df['weight_class'], y=data)
                plt.title(f'Boxplot: {col} by Weight Class')
                plt.xlabel('Weight Class')
                plt.ylabel(col)
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                plt.savefig(os.path.join(PLOT_DIR, f"boxplot_{col}_by_weight_class.png"))
                plt.close()

    # 5. Bar plots for class balance
    if 'weight_class' in df.columns:
        plt.figure(figsize=(8, 4))
        df['weight_class'].value_counts().plot(kind='bar')
        plt.title('Number of Fights per Weight Class')
        plt.xlabel('Weight Class')
        plt.ylabel('Count')
        plt.tight_layout()
        plt.savefig(os.path.join(PLOT_DIR, "bar_fights_per_weight_class.png"))
        plt.close()
    if 'outcome_type' in df.columns:
        plt.figure(figsize=(7, 4))
        df['outcome_type'].value_counts().plot(kind='bar')
        plt.title('Number of Fights by Outcome Type')
        plt.xlabel('Outcome Type')
        plt.ylabel('Count')
        plt.tight_layout()
        plt.savefig(os.path.join(PLOT_DIR, "bar_fights_by_outcome_type.png"))
        plt.close()

    # 6. Correlation heatmap for all numeric columns
    numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(pd.to_numeric(df[col], errors='coerce'))]
    if len(numeric_cols) > 1:
        corr = df[numeric_cols].apply(pd.to_numeric, errors='coerce').corr()
        plt.figure(figsize=(max(8, len(numeric_cols)), 6))
        sns.heatmap(corr, annot=True, cmap='coolwarm', fmt='.2f')
        plt.title('Correlation Heatmap of Numeric Features')
        plt.tight_layout()
        plt.savefig(os.path.join(PLOT_DIR, "correlation_heatmap.png"))
        plt.close()

    print("\nComplete! Plots saved to:", PLOT_DIR)
