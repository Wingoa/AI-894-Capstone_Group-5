import os
import sys
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import roc_curve, auc, confusion_matrix
import torch

# ensure repo root on path for imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

FIG_DIR = os.path.join(PROJECT_ROOT, "reports", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

def fig1_style_loss():
    path = os.path.join(PROJECT_ROOT, "resources", "fighter_vectors", "style_training_history.csv")
    if not os.path.exists(path):
        print("Style training history not found:", path)
        return
    df = pd.read_csv(path)
    plt.figure(figsize=(6,4))
    plt.plot(df['epoch'], df['train_loss'], label='train')
    plt.plot(df['epoch'], df['val_loss'], label='val')
    plt.xlabel('Epoch')
    plt.ylabel('KL Loss')
    plt.title('StyleNet Training and Validation Loss')
    plt.legend()
    out = os.path.join(FIG_DIR, 'figure1_stylenet_loss.png')
    plt.tight_layout()
    plt.savefig(out)
    print('Wrote', out)

def fig2_outcome_loss():
    path = os.path.join(PROJECT_ROOT, "model", "fight", "outcome_artifacts", "training_history.csv")
    if not os.path.exists(path):
        print("Outcome training history not found:", path)
        return
    df = pd.read_csv(path)
    plt.figure(figsize=(6,4))
    plt.plot(df['epoch'], df['train_loss'], label='train')
    plt.plot(df['epoch'], df['test_loss'], label='test')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.title('OutcomeNet Training and Test Loss')
    plt.legend()
    out = os.path.join(FIG_DIR, 'figure2_outcomenet_loss.png')
    plt.tight_layout()
    plt.savefig(out)
    print('Wrote', out)

def load_outcome_model_and_data():
    from model.fight.OutcomeNet import OutcomeNet
    cfg_meta = os.path.join(PROJECT_ROOT, 'model', 'fight', 'outcome_artifacts', 'metadata.json')
    meta = json.load(open(cfg_meta))
    csv_path = os.path.join(PROJECT_ROOT, 'model', 'fight', 'fight_matchups.csv')
    df = pd.read_csv(csv_path)
    FEATURE_ORDER = meta['feature_order']
    A_cols = [f + '_A' for f in FEATURE_ORDER]
    B_cols = [f + '_B' for f in FEATURE_ORDER]
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=['y'])
    df[A_cols + B_cols] = df[A_cols + B_cols].fillna(0.0)
    # load scaler
    import joblib
    scaler = joblib.load(os.path.join(PROJECT_ROOT, 'model', 'fight', 'outcome_artifacts', 'scaler.pkl'))
    XA = df[A_cols].to_numpy(dtype=np.float32)
    XB = df[B_cols].to_numpy(dtype=np.float32)
    y = df['y'].to_numpy(dtype=np.float32)
    XA = scaler.transform(XA).astype(np.float32)
    XB = scaler.transform(XB).astype(np.float32)
    # load model
    d = len(FEATURE_ORDER)
    model = OutcomeNet(d_fighter=d, hidden=meta['train_config']['hidden'], dropout=meta['train_config']['dropout'])
    state = torch.load(os.path.join(PROJECT_ROOT, 'model', 'fight', 'outcome_artifacts', 'outcome_model.pt'), map_location='cpu')
    model.load_state_dict(state)
    model.eval()
    return model, XA, XB, y

def fig3_roc_and_fig4_confusion():
    model, XA, XB, y = load_outcome_model_and_data()
    with torch.no_grad():
        XA_t = torch.tensor(XA)
        XB_t = torch.tensor(XB)
        logits = model(XA_t, XB_t).numpy().reshape(-1)
        probs = 1.0/(1.0 + np.exp(-logits))
    fpr, tpr, _ = roc_curve(y, probs)
    roc_auc = auc(fpr, tpr)
    plt.figure(figsize=(6,5))
    plt.plot(fpr, tpr, label=f'AUC = {roc_auc:.3f}')
    plt.plot([0,1],[0,1], '--', color='gray')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('OutcomeNet ROC Curve')
    plt.legend()
    out1 = os.path.join(FIG_DIR, 'figure3_outcomenet_roc.png')
    plt.tight_layout(); plt.savefig(out1)
    print('Wrote', out1)

    # confusion matrix
    preds = (probs >= 0.5).astype(int)
    cm = confusion_matrix(y, preds)
    plt.figure(figsize=(5,4))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
    plt.xlabel('Predicted'); plt.ylabel('True')
    plt.title('OutcomeNet Confusion Matrix')
    out2 = os.path.join(FIG_DIR, 'figure4_outcomenet_confusion.png')
    plt.tight_layout(); plt.savefig(out2)
    print('Wrote', out2)

def fig5_shap():
    try:
        import shap
    except Exception:
        print('shap not installed; skipping SHAP plot')
        return
    model, XA, XB, y = load_outcome_model_and_data()
    # prepare z = [fA, fB, fA-fB, fA*fB]
    fA = XA; fB = XB
    diff = fA - fB
    inter = fA * fB
    Z = np.concatenate([fA, fB, diff, inter], axis=1)
    # wrap model
    def predict_fn(z_array):
        # z_array is [N, 4d]
        z_tensor = torch.tensor(z_array, dtype=torch.float32)
        # split back into fA,fB
        d = XA.shape[1]
        fA = z_tensor[:, :d]
        fB = z_tensor[:, d:2*d]
        with torch.no_grad():
            logits = model(fA, fB).numpy().reshape(-1)
            probs = 1.0/(1.0 + np.exp(-logits))
        return probs
    # use a small background
    background = Z[np.random.choice(Z.shape[0], min(100, Z.shape[0]), replace=False)]
    explainer = shap.KernelExplainer(predict_fn, background)
    shap_vals = explainer.shap_values(Z[:200], nsamples=100)
    plt.figure()
    shap.summary_plot(shap_vals, Z[:200], show=False)
    out = os.path.join(FIG_DIR, 'figure5_outcomenet_shap.png')
    plt.savefig(out, bbox_inches='tight')
    print('Wrote', out)

def fig6_style_composition():
    path = os.path.join(PROJECT_ROOT, 'resources', 'fighter_vectors', 'fighter_style_predictions-test.csv')
    if not os.path.exists(path):
        print('Style predictions file not found:', path)
        return
    df = pd.read_csv(path)
    buckets = ['MuayThai','Boxing','Wrestling','Grappling']
    # pick top 30 fighters by appearance
    sample = df.sample(n=min(50, len(df)), random_state=42)
    comp = sample[buckets].to_numpy()
    plt.figure(figsize=(8,6))
    sns.heatmap(comp, cmap='viridis', yticklabels=sample['fighter'].values)
    plt.title('Style composition heatmap (sample)')
    out = os.path.join(FIG_DIR, 'figure6_style_composition.png')
    plt.tight_layout(); plt.savefig(out)
    print('Wrote', out)

def main():
    fig1_style_loss()
    fig2_outcome_loss()
    fig3_roc_and_fig4_confusion()
    fig5_shap()
    fig6_style_composition()

if __name__ == '__main__':
    main()
