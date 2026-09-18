import numpy as np

from app.risk.training import metrics_at, roc_auc


def test_metrics_at_computes_accuracy_from_the_full_confusion_matrix() -> None:
    # TP=2, FP=1, FN=1, TN=1 -> accuracy 0.6, precision 2/3, recall 2/3. Số chọn có
    # chủ đích để ba chỉ số khác nhau, tránh trường hợp 0,5 đều dù công thức đảo chỗ.
    truth = np.array([True, True, True, False, False], dtype=bool)
    probabilities = np.array([0.9, 0.8, 0.1, 0.7, 0.2])
    threshold = 0.5
    # flagged = [T, T, F, T, F] -> TP={0,1}=2, FN={2}=1, FP={3}=1, TN={4}=1

    result = metrics_at(probabilities, truth, threshold)

    assert result["accuracy"] == 0.6
    assert result["precision"] == round(2 / 3, 4)
    assert result["recall"] == round(2 / 3, 4)


def test_metrics_at_accuracy_is_one_when_every_prediction_matches() -> None:
    truth = np.array([True, False], dtype=bool)
    probabilities = np.array([0.9, 0.1])

    result = metrics_at(probabilities, truth, threshold=0.5)

    assert result["accuracy"] == 1.0


def test_roc_auc_matches_the_pairwise_ranking_definition() -> None:
    # CONTEXT.md: xác suất một đơn trễ thật được xếp hạng cao hơn một đơn đúng hạn
    # thật. 4 cặp (trễ, đúng hạn): (0.35,0.1) đúng, (0.35,0.4) sai, (0.8,0.1) đúng,
    # (0.8,0.4) đúng -> 3/4 = 0.75.
    truth = np.array([False, False, True, True], dtype=bool)
    probabilities = np.array([0.1, 0.4, 0.35, 0.8])

    assert roc_auc(probabilities, truth) == 0.75


def test_roc_auc_is_none_when_the_split_has_a_single_label_class() -> None:
    truth_all_late = np.array([True, True, True], dtype=bool)
    truth_all_on_time = np.array([False, False, False], dtype=bool)
    probabilities = np.array([0.2, 0.5, 0.9])

    assert roc_auc(probabilities, truth_all_late) is None
    assert roc_auc(probabilities, truth_all_on_time) is None
