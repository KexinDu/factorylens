import numpy as np
from matplotlib import pyplot as plt
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


def metrics(y_true, probability, threshold: float) -> dict[str, object]:
    prediction = (np.asarray(probability) >= threshold).astype(int)
    return {
        "precision": float(precision_score(y_true, prediction, zero_division=0)),
        "recall": float(recall_score(y_true, prediction, zero_division=0)),
        "f1": float(f1_score(y_true, prediction, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, probability)),
        "pr_auc": float(average_precision_score(y_true, probability)),
        "confusion_matrix": confusion_matrix(y_true, prediction).tolist(),
    }


def select_threshold(y_true, probability) -> float:
    scored = []
    for threshold in np.arange(0.10, 0.61, 0.01):
        p = precision_score(y_true, probability >= threshold, zero_division=0)
        r = recall_score(y_true, probability >= threshold, zero_division=0)
        f2 = 5 * p * r / (4 * p + r) if p + r else 0
        scored.append((f2, r, p, threshold))
    return float(max(scored)[3])


def curves(y_true, probability) -> dict[str, list[dict[str, float]]]:
    fpr, tpr, _ = roc_curve(y_true, probability)
    precision, recall, _ = precision_recall_curve(y_true, probability)
    return {
        "roc": [{"x": float(x), "y": float(y)} for x, y in zip(fpr, tpr, strict=True)],
        "precision_recall": [
            {"x": float(x), "y": float(y)} for x, y in zip(recall, precision, strict=True)
        ],
    }


def save_evaluation_plots(
    metadata: dict[str, object], output_dir, feature_importance: list[dict[str, object]]
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix = np.asarray(metadata["metrics"]["confusion_matrix"])
    figure, axis = plt.subplots(figsize=(5, 4))
    image = axis.imshow(matrix, cmap="Blues")
    for row in range(2):
        for column in range(2):
            axis.text(column, row, matrix[row, column], ha="center", va="center")
    axis.set(xlabel="Predicted", ylabel="Actual", title="Held-out confusion matrix")
    figure.colorbar(image)
    figure.tight_layout()
    figure.savefig(output_dir / "confusion_matrix.png", dpi=150)
    plt.close(figure)

    for key, title, filename in [
        ("roc", "ROC curve", "roc_curve.png"),
        ("precision_recall", "Precision–recall curve", "precision_recall_curve.png"),
    ]:
        points = metadata["curves"][key]
        figure, axis = plt.subplots(figsize=(5, 4))
        axis.plot([point["x"] for point in points], [point["y"] for point in points])
        axis.set(
            xlabel="False positive rate" if key == "roc" else "Recall",
            ylabel="True positive rate" if key == "roc" else "Precision",
            title=title,
        )
        axis.grid(alpha=0.25)
        figure.tight_layout()
        figure.savefig(output_dir / filename, dpi=150)
        plt.close(figure)

    top = feature_importance[:10][::-1]
    figure, axis = plt.subplots(figsize=(7, 4.5))
    axis.barh([item["feature"] for item in top], [item["importance"] for item in top])
    axis.set(title="Global feature importance", xlabel="Importance")
    figure.tight_layout()
    figure.savefig(output_dir / "feature_importance.png", dpi=150)
    plt.close(figure)
