"""Bản giả của RiskPredictor cho test tuyến tạo đơn.

Khác FakePredictor của test_risk_dependency.py, vốn chỉ mang model_version để kiểm
riêng cơ chế dependency override: tuyến tạo đơn gọi thật .predict(order) và đọc kết
quả, nên bản giả ở đây phải trả đúng kiểu RiskPrediction — "trả phân phối cố định để
biết trước mức rủi ro và nguyên nhân", đúng #31 yêu cầu.
"""

from app.risk.predictor import OrderInput, RiskCause, RiskPrediction, StageForecast

STAGES = ("payment_approval", "seller_handling", "carrier_transit")

# Trung vị lịch sử cố định, cùng bậc độ lớn với báo cáo đánh giá thật (models/evaluation_
# report.json): không cần khớp chính xác, chỉ cần khác 0 để excess_days có ý nghĩa.
HISTORICAL_MEDIAN_DAYS = {
    "payment_approval": 0.01,
    "seller_handling": 1.82,
    "carrier_transit": 7.10,
}


class FakePredictor:
    model_version = "fake-risk-model"

    def __init__(
        self,
        *,
        late_probability: float = 0.05,
        risk_cause_stage: str = "carrier_transit",
        risk_cause_seller_id: str | None = None,
        excess_days: float = 1.0,
    ) -> None:
        self.late_probability = late_probability
        self.risk_cause_stage = risk_cause_stage
        self.risk_cause_seller_id = risk_cause_seller_id
        self.excess_days = excess_days

    def predict(self, order: OrderInput) -> RiskPrediction:
        stages = tuple(
            StageForecast(
                stage=stage,
                actual_days=None,
                median_days=HISTORICAL_MEDIAN_DAYS[stage]
                + (self.excess_days if stage == self.risk_cause_stage else 0.0),
                historical_median_days=HISTORICAL_MEDIAN_DAYS[stage],
                excess_days=self.excess_days if stage == self.risk_cause_stage else 0.0,
            )
            for stage in STAGES
        )
        return RiskPrediction(
            checkpoint="order_placed",
            late_probability=self.late_probability,
            risk_cause=RiskCause(
                stage=self.risk_cause_stage,
                excess_days=self.excess_days,
                seller_id=self.risk_cause_seller_id,
            ),
            stages=stages,
            model_version=self.model_version,
        )
