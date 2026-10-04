import io
import json
from pathlib import Path

import pytest

from conftest import ROOT, SAMPLES, make_image_bytes

MODEL_DIR = ROOT / "model"
HAVE_MODEL = (MODEL_DIR / "khetsetu.tflite").exists() or (MODEL_DIR / "khetsetu.keras").exists()


def post_image(client, data, name="leaf.jpg", ctype="image/jpeg", lang="en"):
    return client.post("/api/predict", files={"image": (name, io.BytesIO(data), ctype)}, data={"language": lang})


# ------------------------------------------------------------------ health / config
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    b = r.json()
    assert b["status"] == "ok" and "model" in b and b["confidence_threshold"] == 0.70


def test_class_config_is_consistent():
    from app.disease_info import class_names, get_guidance, all_crops
    cfg = json.loads((MODEL_DIR / "class_config.json").read_text(encoding="utf-8"))
    idx = [c["index"] for c in cfg["classes"]]
    assert idx == list(range(len(idx)))                              # contiguous, no reordering
    configured_names = [c["class_name"] for c in sorted(cfg["classes"], key=lambda c: c["index"])]
    assert json.loads((MODEL_DIR / "class_names.json").read_text(encoding="utf-8")) == configured_names
    assert class_names() == configured_names
    for c in cfg["classes"]:                                          # every class has full bilingual guidance
        g = get_guidance(c["class_name"])
        for key in ("symptoms", "prevention", "basic_care", "watering_care", "nutrient_guidance", "consult_expert_when", "avoid"):
            assert g[key]["en"] and g[key]["hi"], (c["class_name"], key)
        assert g["what_is_it"]["en"] and g["what_is_it"]["hi"]
        assert c["crop"] in all_crops()
    meta_path = MODEL_DIR / "model_meta.json"
    if meta_path.exists():                                            # class order used in training == config
        assert json.loads(meta_path.read_text())["class_names"] == class_names()


def test_guidance_has_no_dosages_or_brands():
    text = (ROOT / "data" / "guidance.json").read_text(encoding="utf-8").lower()
    for bad in (" ml/", " ml per", "grams per", " g/l", "mg/", "kg/ha", "ppm", "mancozeb", "chlorothalonil", "metalaxyl", "copper oxychloride"):
        assert bad not in text, bad


# ------------------------------------------------------------------ model loading
@pytest.mark.skipif(not HAVE_MODEL, reason="no trained model in model/")
def test_real_model_loads_once_and_is_default(client):
    from app.model import classifier
    assert classifier.mode == "real" and classifier.format in ("tflite", "keras")
    before = id(classifier._interp or classifier._keras)
    post_image(client, make_image_bytes())
    post_image(client, make_image_bytes())
    assert id(classifier._interp or classifier._keras) == before      # not reloaded per request


def test_demo_fallback_is_labelled_when_model_missing(monkeypatch, tmp_path):
    from app.config import settings
    from app.model import Classifier
    monkeypatch.setattr(settings, "MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "MODEL_PATH", "")
    monkeypatch.setattr(settings, "DEMO_MODE", "auto")
    c = Classifier(); c.load()
    assert c.mode == "demo" and c.is_demo
    monkeypatch.setattr(settings, "DEMO_MODE", "false")
    c2 = Classifier(); c2.load()
    assert c2.mode == "unavailable" and not c2.available


def test_demo_result_is_flagged(client, monkeypatch, leaf_bytes):
    from app.model import classifier
    monkeypatch.setattr(classifier, "mode", "demo")
    body = post_image(client, leaf_bytes).json()
    assert body["demo_mode"] is True


# ------------------------------------------------------------------ prediction + confidence gate
def test_confident_disease_prediction(client, fake_model, leaf_bytes):
    fake_model("Tomato___Late_blight", 0.94)
    r = post_image(client, leaf_bytes)
    assert r.status_code == 200
    b = r.json()
    assert b["status"] == "ok" and b["is_confident"] is True
    prediction = b["prediction"]
    assert {key: prediction[key] for key in (
        "class_name", "crop", "disease", "confidence", "is_healthy", "crop_hi", "disease_hi",
    )} == {
        "class_name": "Tomato___Late_blight", "crop": "Tomato", "disease": "Late Blight",
        "confidence": 0.94, "is_healthy": False, "crop_hi": "टमाटर",
        "disease_hi": prediction["disease_hi"],
    }
    assert prediction["crop_i18n"] == {"en": "Tomato", "hi": "टमाटर"}
    assert prediction["disease_i18n"]["en"] == "Late Blight"
    assert b["guidance"]["symptoms"]["hi"] and b["guidance"]["urgency"] == "act_fast"
    assert b["message"] is None


def test_guidance_never_changes_prediction(client, fake_model, leaf_bytes):
    fake_model("Potato___Early_blight", 0.81)
    b = post_image(client, leaf_bytes).json()
    assert b["prediction"]["class_name"] == b["guidance"]["class_name"] == "Potato___Early_blight"


def test_low_confidence_hides_diagnosis(client, fake_model, leaf_bytes):
    fake_model("Tomato___Late_blight", 0.55)
    b = post_image(client, leaf_bytes).json()
    assert b["status"] == "low_confidence" and b["is_confident"] is False
    assert b["prediction"] is None and b["guidance"] is None
    assert b["message"]["title"]["en"] == "Photo unclear"
    assert "Please take another clear photo" in b["message"]["body"]["en"]
    raw = json.dumps(b)
    assert "Late_blight" not in raw and "Tomato" not in raw          # no disease/crop name leaks below the threshold


def test_threshold_boundary(client, fake_model, leaf_bytes):
    fake_model("Corn___Common_rust", 0.70)
    assert post_image(client, leaf_bytes).json()["status"] == "ok"
    fake_model("Corn___Common_rust", 0.6999)
    assert post_image(client, leaf_bytes).json()["status"] == "low_confidence"


def test_healthy_crop_result(client, fake_model, leaf_bytes):
    fake_model("Tomato___healthy", 0.97)
    b = post_image(client, leaf_bytes).json()
    assert b["status"] == "ok" and b["prediction"]["is_healthy"] is True
    assert b["guidance"]["is_healthy"] is True and b["guidance"]["urgency"] == "none"


def test_disease_specific_advisory_changes_by_class(client, fake_model, leaf_bytes):
    fake_model("Tomato___Early_blight", 0.94)
    early = post_image(client, leaf_bytes).json()
    assert early["status"] == "ok"
    assert early["advisory"]["crop"] == "Tomato"
    assert "early blight" in early["advisory"]["what_we_found"]["en"].lower()
    assert "alternaria" in " ".join(early["advisory"]["why_it_happened"]["en"]).lower()

    fake_model("Tomato___Late_blight", 0.96)
    late = post_image(client, leaf_bytes).json()
    assert late["status"] == "ok"
    assert late["advisory"]["disease"] == "Late Blight"
    assert late["advisory"]["what_we_found"]["en"] != early["advisory"]["what_we_found"]["en"]
    assert "late blight" in late["advisory"]["what_we_found"]["en"].lower()
    assert late["advisory"]["management"]["en"] != early["advisory"]["management"]["en"]

    fake_model("Tomato___healthy", 0.97)
    healthy = post_image(client, leaf_bytes).json()
    assert healthy["status"] == "ok"
    assert healthy["advisory"]["is_healthy"] is True
    assert "healthy" in healthy["advisory"]["what_we_found"]["en"].lower()


def test_disease_info_has_required_fields_for_all_supported_classes():
    from app.disease_info import list_supported_classes, validate_supporting_data
    classes = list_supported_classes()
    assert classes
    missing = validate_supporting_data()
    assert not missing, missing


def test_non_leaf_image_is_rejected(client, fake_model):
    fake_model("Tomato___Late_blight", 0.99)                          # even a "confident" model must not be asked
    b = post_image(client, make_image_bytes(color=(128, 128, 128))).json()
    assert b["status"] == "not_a_leaf" and b["prediction"] is None


# ------------------------------------------------------------------ input validation
def test_invalid_file_type(client):
    r = post_image(client, b"hello", "notes.txt", "text/plain")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_image"


def test_corrupted_image(client):
    r = post_image(client, b"\xff\xd8\xff\xe0not really a jpeg", "bad.jpg")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_image"
    assert "Traceback" not in r.text


def test_empty_file(client):
    assert post_image(client, b"").status_code == 422


def test_large_image_rejected(client):
    r = post_image(client, b"\x00" * (5 * 1024 * 1024 + 10))
    assert r.status_code == 413 and r.json()["detail"]["code"] == "image_too_large"


def test_missing_file_field(client):
    r = client.post("/api/predict", data={"language": "en"})
    assert r.status_code == 422 and "message" in r.json()["detail"]


@pytest.mark.parametrize("fmt,ctype", [("PNG", "image/png"), ("WEBP", "image/webp"), ("JPEG", "image/jpeg")])
def test_supported_formats(client, fake_model, fmt, ctype):
    fake_model("Tomato___healthy", 0.9)
    assert post_image(client, make_image_bytes(fmt=fmt), f"x.{fmt.lower()}", ctype).status_code == 200


# ------------------------------------------------------------------ real model on sample photos (smoke test)
@pytest.mark.skipif(not HAVE_MODEL or not SAMPLES.exists(), reason="needs trained model + tests/samples")
def test_real_model_on_sample_photos(client):
    """Smoke test on 16 random held-out test images. NOT an accuracy benchmark (see ml/evaluation/results)."""
    from app.model import classifier
    assert classifier.mode == "real"
    total = correct = shown = 0
    for cls_dir in sorted(SAMPLES.iterdir()):
        for f in sorted(cls_dir.iterdir()):
            b = post_image(client, f.read_bytes(), f.name, "image/jpeg").json()
            total += 1
            assert b["demo_mode"] is False
            if b["status"] == "ok":
                shown += 1
                correct += b["prediction"]["class_name"] == cls_dir.name
    assert total == 16 and shown >= 12
    assert correct / shown >= 0.85


# ------------------------------------------------------------------ crops / market / history
def test_crops_endpoint(client):
    b = client.get("/api/crops").json()
    assert {c["crop"] for c in b["crops"]} == {"Tomato", "Potato", "Corn"} and len(b["classes"]) == 8
    assert client.get("/api/crops/apple").status_code == 404          # unsupported crops are not claimed


def test_market_demo_is_labelled(client):
    b = client.get("/api/market-prices", params={"crop": "Tomato", "state": "Karnataka"}).json()
    assert b["is_demo"] is True and b["source"] == "demo" and "Demo" in b["message"]["en"] and b["rows"]


def test_market_live_then_cached_fallback(monkeypatch, tmp_path):
    from app.config import settings
    from app.services import market_service as ms
    monkeypatch.setattr(settings, "MARKET_API_KEY", "test-key")
    monkeypatch.setattr(settings, "ALLOW_DEMO_MARKET", False)
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    ms._mem.clear()
    rec = [{"state": "Karnataka", "district": "Bengaluru", "market": "Bengaluru", "commodity": "Tomato",
            "arrival_date": "24/09/2026", "min_price": "1500", "max_price": "2100", "modal_price": "1800"},
           {"state": "X", "market": "bad", "commodity": "Tomato", "modal_price": "NA"}]
    monkeypatch.setattr(ms, "_fetch_live", lambda *a, **k: ms.parse_live_records(rec))
    live = ms.get_market_prices("Tomato", "Karnataka")
    assert live["source"] == "live" and live["is_demo"] is False and len(live["rows"]) == 1
    assert live["rows"][0]["modal_price"] == 1800

    ms._mem.clear()
    def boom(*a, **k): raise RuntimeError("network down")
    monkeypatch.setattr(ms, "_fetch_live", boom)
    cached = ms.get_market_prices("Tomato", "Karnataka")
    assert cached["source"] == "cached" and cached["stale"] is True and cached["rows"]

    other = ms.get_market_prices("Potato", "Punjab")                 # nothing cached for this query
    assert other["source"] == "unavailable" and other["rows"] == [] and other["is_demo"] is False


def test_history_records_scans(client, fake_model, leaf_bytes):
    fake_model("Tomato___healthy", 0.9)
    post_image(client, leaf_bytes)
    rows = client.get("/api/history").json()
    assert rows and {"crop", "disease", "confidence", "date"} <= set(rows[0])


# In tests/test_backend.py

def test_admin_stats(client):
    headers = {"Authorization": "Bearer admin_test_token"}
    response = client.get("/api/admin/stats", headers=headers)
    assert response.status_code == 200
    assert "total_scans" in response.json()
