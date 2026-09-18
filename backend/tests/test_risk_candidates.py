from app.risk.candidates import (
    ALGORITHMS,
    SklearnQuantileStage,
    XGBAftStage,
    XGBQuantileStage,
)


def test_xgb_quantile_stage_defaults_match_production() -> None:
    params = XGBQuantileStage()._model.get_params()

    assert params["n_estimators"] == 300
    assert params["learning_rate"] == 0.1
    assert params["max_depth"] == 6
    assert params["random_state"] == 0
    assert params["objective"] == "reg:quantileerror"


def test_xgb_quantile_stage_accepts_custom_hyperparameters() -> None:
    params = XGBQuantileStage(n_estimators=5, learning_rate=0.5, max_depth=2)._model.get_params()

    assert params["n_estimators"] == 5
    assert params["learning_rate"] == 0.5
    assert params["max_depth"] == 2


def test_xgb_aft_stage_defaults_match_production() -> None:
    stage = XGBAftStage()

    assert stage._params == {
        "objective": "survival:aft",
        "aft_loss_distribution": "normal",
        "aft_loss_distribution_scale": 1.0,
        "learning_rate": 0.1,
        "max_depth": 6,
        "seed": 0,
    }
    assert stage._num_boost_round == 300


def test_xgb_aft_stage_accepts_custom_hyperparameters() -> None:
    stage = XGBAftStage(learning_rate=0.3, max_depth=3, num_boost_round=10, seed=7)

    assert stage._params["learning_rate"] == 0.3
    assert stage._params["max_depth"] == 3
    assert stage._params["seed"] == 7
    assert stage._num_boost_round == 10


def test_sklearn_quantile_stage_defaults_match_production() -> None:
    for model in SklearnQuantileStage()._models:
        params = model.get_params()
        assert params["max_iter"] == 200
        assert params["learning_rate"] == 0.1
        assert params["random_state"] == 0
        assert params["loss"] == "quantile"


def test_sklearn_quantile_stage_accepts_custom_hyperparameters() -> None:
    for model in SklearnQuantileStage(max_iter=5, learning_rate=0.5)._models:
        params = model.get_params()
        assert params["max_iter"] == 5
        assert params["learning_rate"] == 0.5


def test_algorithms_are_zero_argument_factories() -> None:
    instantiated = {name: factory() for name, factory in ALGORITHMS.items()}

    assert set(instantiated) == {"xgboost_quantile", "xgboost_aft", "sklearn_quantile"}
