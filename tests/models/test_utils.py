from nuvlaedge.agent.workers.telemetry import TelemetryPayloadAttributes
from nuvlaedge.models import model_diff


def test_model_diff():
    model_1 = TelemetryPayloadAttributes()
    model_2 = TelemetryPayloadAttributes()

    assert model_diff(model_1, model_2) == (set(), set())

    model_1.hostname = "my_host"
    assert model_diff(model_1, model_2) == (set(), {'hostname'})

    model_2.hostname = "my_host_2"
    assert model_diff(model_1, model_2) == ({'hostname'}, set())