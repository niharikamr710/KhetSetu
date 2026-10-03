# KhetSetu (खेतसेतु) — Smart Crop Health & Market Assistant for Farmers

A mobile-first web app (with a WhatsApp channel) that lets a farmer photograph a crop leaf and get
a disease result with a confidence gate, farmer-friendly guidance in English and Hindi (with Hindi
text-to-speech), a downloadable PDF scan report, mandi prices, and a scan history — built to work on slow networks and for users
with limited technical literacy.

**This is a real trained model, not a placeholder.** A MobileNetV2 classifier trained on a documented
PlantVillage subset ships in `model/`. The backend uses it by default; simulated "Demo Mode" is only
a fallback for when the model files are missing.

---

## 1. Project overview

```
khetsetu/
├── frontend/            React + TypeScript + Vite + Tailwind CSS (PWA)
├── backend/             FastAPI REST API + SQLite (aggregate scan log)
├── ml/                  dataset prep / training / evaluation pipeline
│   ├── dataset/          PlantVillage subset used for this model (see SOURCE.md)
│   ├── dataset_split/    generated train/val/test split (git-ignored)
│   ├── cache/            generated numpy image cache (git-ignored)
│   ├── training/          prepare_dataset.py, common.py, train.py, export_model.py
│   └── evaluation/        evaluate.py, benchmark_backend.py, results/
├── model/               the trained model actually used by the backend (khetsetu.tflite/.keras,
│                        class_config.json, model_meta.json)
├── data/                guidance.json, crops.json (agricultural knowledge, separate from the model)
├── tests/               pytest suite + 16 sample test photos
├── .env.example
├── .gitignore
└── README.md
```

## 2. Features

- Photo upload or camera capture -> crop, disease/healthy status, confidence, plain-language
  explanation, symptoms, care, prevention, watering, nutrients, when to consult an expert, what to
  avoid — in English and Hindi, with a Hindi listen button; reports can be downloaded as PDFs.
- Server-enforced confidence gate: below 70% confidence the backend returns **no crop or disease
  name at all**, only "Photo unclear — please retake the photo."
- A simple leaf-colour check rejects obvious non-leaf photos (sky, walls, screenshots) before they
  reach the classifier.
- Mandi prices: live data.gov.in/Agmarknet when `MARKET_API_KEY` is set, else the last successful
  live response (clearly marked "last saved prices"), else clearly labelled demo data. Never shown
  as live when it isn't.
- WhatsApp Cloud API webhook: send a leaf photo for the same analysis, or `BHAV TOMATO` /
  `PRICE POTATO` / `भाव आलू` for prices — in English and Hindi.
- Works as an installable PWA; the app shell, translations and crop/disease knowledge base are
  cached for offline use. Live prices and photo scanning correctly show "offline" rather than
  pretending to work.
- Local, on-device scan history (no login needed); optional server-side aggregate log with no
  images or farmer identity.
- The signed-in workspace has a Home dashboard with farm overview, saved scan activity, the latest
  diagnosis, and shortcuts to market prices and crop advisory. Desktop navigation uses a sidebar;
  mobile navigation uses a bottom bar. The light-green workspace background includes a subtle grass
  illustration, and the sidebar profile control shows the signed-in user's name and email.

## 3. Architecture

```
Photo (web upload/camera OR WhatsApp)
   -> validate (type, size, decodable)
   -> leaf-colour check (rejects obvious non-leaf photos)
   -> preprocess (EXIF-rotate, RGB, resize 224x224)
   -> MobileNetV2 model (loaded ONCE at backend start-up)
   -> confidence >= 0.70 ?
        no  -> "Photo unclear / please retake" (no crop/disease name returned)
        yes -> prediction {class_name, crop, disease, confidence, is_healthy}
               + guidance.json lookup (general advice, kept separate, never alters the prediction)
   -> JSON response -> web UI or WhatsApp reply composer
```

## 4. Dataset

**The uploaded dataset was used, not replaced.** It originally has 14 classes (Apple x4, Corn x2,
Pepper x2, Potato x3, Tomato x3), ~17,000 images. Apple and Pepper are not part of this MVP's scope
and were left out — see the class-selection note below. The remaining images were audited:

- 16,977 images found across the 8 kept classes' folders; **0 unreadable files**.
- Near-duplicate detection (perceptual hashing, 8 rotations/flips per image, per class): several
  hundred duplicate/near-duplicate clusters were found and each whole cluster was kept together in
  one split, so no near-duplicate leaks across train/val/test. The split script's own leakage
  self-check reports **0 clusters spanning multiple splits**.
- Split: 70% train / 15% val / 15% test by cluster (not by raw image count), stratified per class.

### Dataset classes actually used (8 classes)

| class_name | crop | condition | why |
|---|---|---|---|
| `Corn___Common_rust` | Corn (Maize) | Common Rust | **substituted** — see below |
| `Corn___healthy` | Corn (Maize) | Healthy | added, so a healthy corn leaf isn't forced into a disease |
| `Potato___Early_blight` | Potato | Early Blight | in scope |
| `Potato___Late_blight` | Potato | Late Blight | in scope |
| `Potato___healthy` | Potato | Healthy | added companion class |
| `Tomato___Early_blight` | Tomato | Early Blight | added — see below |
| `Tomato___Late_blight` | Tomato | Late Blight | in scope |
| `Tomato___healthy` | Tomato | Healthy | in scope |

**Class-selection decision (documented, not invented):** a 5-class scope of *Tomato Late Blight,
Tomato Healthy, Potato Early Blight, Potato Late Blight, Corn Northern Leaf Blight* was requested.
**Corn Northern Leaf Blight does not exist in the uploaded dataset** — the only corn class present
is Corn Common Rust, so that was used in its place. Tomato Early Blight and Potato Healthy were
added as companion classes: without them, a healthy potato leaf or a tomato leaf with early blight
would have been forced into one of the 5 original labels, which would have meant claiming the
model could tell apart diseases it never saw. Apple and Pepper images remain in your original ZIP
and can be reintroduced later; the training scripts skip any folder not listed in
`model/class_config.json`.

`model/class_config.json` is the single source of truth for class order and names — the training
scripts, the backend and the tests all read it, so it can never silently drift out of sync.

## 5. ML training pipeline

```
ml/dataset (original, untouched)
   -> training/prepare_dataset.py   (dedupe + leakage-safe 70/15/15 split -> ml/dataset_split)
   -> training/train.py             (MobileNetV2, ImageNet weights, class-weighted, augmented)
   -> evaluation/evaluate.py        (held-out TEST split only)
   -> training/export_model.py      (Keras -> TFLite)
```

**Model:** MobileNetV2 (alpha=1.0), ImageNet-pretrained, input 224x224x3, a `GlobalAveragePooling2D`
+ `Dropout(0.3)` + `Dense(8, softmax)` head. Rescaling to `[-1, 1]` is built into the model, so both
training and the backend feed it raw 0-255 pixel values.

**Training that actually produced the shipped model:** 3 epochs with the ImageNet base frozen,
`Adam(1e-3)`, class weights balanced from the train split, augmentation (flips, rotation, zoom,
brightness, contrast) applied to the training data only. `ModelCheckpoint` (best `val_accuracy`),
`EarlyStopping` and `ReduceLROnPlateau` were configured. **A second fine-tuning phase (unfreezing
the last ~34 base layers) was attempted and overfit** (train accuracy rose to ~96% while validation
fell to ~86%) and that run was interrupted before finishing; the shipped model is the best
checkpoint from the frozen-base phase, not the fine-tuned one. This is recorded in
`model/model_meta.json` (`training_note`). Re-running fine-tuning with a lower learning rate or more
regularization is a reasonable next step but was not completed here.

**Confidence:** raw softmax is calibrated with temperature scaling (T=0.744, fit on the validation
set only) before it is compared against `CONFIDENCE_THRESHOLD` (0.70).

**Imbalance handling:** class counts ranged from ~5,600 (Tomato Late Blight) to ~3,500 (Potato
classes) after de-duplication. Balanced class weights (`n_samples / (n_classes * n_class_samples)`)
were applied as per-sample loss weights during training, rather than resampling, so no images were
duplicated or discarded.

## 6. Model evaluation (held-out TEST split, 1,479 images — never used in training or calibration)

Full results: `ml/evaluation/results/EVALUATION_REPORT.md`,
`ml/evaluation/results/metrics.json`, `ml/evaluation/results/confusion_matrix.png`.

| metric | value |
|---|---|
| Accuracy | **0.9304** |
| Macro precision / recall / F1 | 0.9308 / 0.9397 / 0.9335 |
| Weighted precision / recall / F1 | 0.9336 / 0.9304 / 0.9298 |
| Model size | 9.66 MB (.keras) / **8.91 MB (.tflite, shipped)** |
| Avg inference, batch 1 (this dev machine, CPU) | 109.7 ms (Keras) / **5.4 ms (TFLite)** |
| End-to-end `/api/predict` latency (this dev machine) | mean 12.1 ms, p95 13.1 ms (see `ml/evaluation/results/latency_end_to_end.json`) |
| Calibration (ECE) | 0.0414 -> 0.0221 after temperature scaling |

At the shipped 0.70 threshold, the model answers 90.9% of test images and is **97.8% accurate when
it answers**; the rest are correctly withheld as low-confidence. Per-class F1 ranges from 1.000
(Corn Common Rust) down to 0.806 (Tomato Early Blight) — the main confusion is between Tomato Early
Blight and Tomato Late Blight, and between Tomato Late Blight and Potato Late Blight (visually
similar diseases). Full per-class numbers and the confusion matrix are in the report above.

**Honest limitations found during evaluation (please read):**
- The test set is from the same lab-style photo collection as training (plain background, similar
  lighting). Real farm photos will likely score lower — this is stated in `metrics.json` as a caveat.
- Robustness check on artificially degraded copies of test photos: accuracy drops from 93% to
  67-89% depending on the degradation (worst: a small/cropped leaf photographed from far away, 67%;
  best: brightened photos, 94%). See the "Robustness" table in the evaluation report.
- The non-leaf guard (a simple leaf-colour heuristic) is a partial safeguard, not a solved problem:
  on 200 synthetic non-leaf images (noise, solid colours, gradients, checkerboards, sky/skin-tone
  blocks) it rejected 134 outright, but 51 still passed the guard **and** the confidence threshold,
  producing a confident but meaningless disease label. Do not present this guard as a complete
  "is this a leaf" detector.

## 7. Backend setup (Windows PowerShell)

```powershell
cd khetsetu\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
Copy-Item ..\.env.example .env
uvicorn app.main:app --reload
```

Backend runs at `http://127.0.0.1:8000`. Check `http://127.0.0.1:8000/api/health` — it should show
`"model": {"mode": "real", "format": "tflite"}` since `model/khetsetu.tflite` ships in this ZIP.

(macOS/Linux: `python3 -m venv venv && source venv/bin/activate` instead of the two `venv\Scripts...` lines.)

## 8. Frontend setup (Windows PowerShell)

```powershell
cd khetsetu\frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://127.0.0.1:8000` (see
`frontend/vite.config.ts`), so start the backend first.

After signing in and completing onboarding, the app opens the Home dashboard. Use the sidebar on
desktop or the bottom navigation on mobile to open Scan, Market, Advisory, History, and Settings.
The Home dashboard's scan button opens the same crop scanner as the Scan navigation item.

Production build: `npm run build` (output in `frontend/dist/`, a full installable PWA).

## 9. WhatsApp setup

1. Create a Meta developer app with the WhatsApp product, get a test phone number.
2. In `backend/.env` set `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, and a
   `WHATSAPP_VERIFY_TOKEN` you invent yourself.
3. Expose your local backend publicly for the webhook (e.g. `ngrok http 8000`) and in the Meta
   console set the webhook URL to `https://<your-tunnel>/webhook` with that same verify token,
   subscribed to the `messages` field.
4. Optional but recommended: set `WHATSAPP_APP_SECRET` (your Meta app secret) — this turns on
   `X-Hub-Signature-256` verification of incoming webhook calls.
5. Send a leaf photo, or text `BHAV TOMATO` / `PRICE POTATO` / `भाव आलू`, to your test number.

Without these variables set, the webhook still runs (useful for local testing) but replies are only
logged, not sent to WhatsApp.

## 10. Mandi price setup

Register at data.gov.in for the "Current daily price of commodities" API and put the key in
`MARKET_API_KEY`. Without a key, `/api/market-prices` and the WhatsApp price replies return clearly
labelled **demo data** (never presented as live). With a key, if a live call fails, the last
successful response for that query is served and marked "last saved prices"; if nothing was ever
cached for that query, the app says prices are unavailable rather than guessing.

## 11. Environment variables

See `.env.example` at the project root — copy it to `backend/.env`. Never commit the real `.env`.
Key variables:

| variable | purpose | default |
|---|---|---|
| `MODEL_PATH` | force a specific model file; empty = auto-detect in `model/` | *(empty)* |
| `CONFIDENCE_THRESHOLD` | minimum calibrated confidence to show a diagnosis | `0.70` |
| `DEMO_MODE` | `auto` (real model if present, else labelled demo) / `true` (force demo) / `false` (real model required) | `false` |
| `ALLOWED_ORIGINS` | CORS allow-list for the frontend origin | `http://localhost:5173,...` |
| `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` | WhatsApp Cloud API | *(empty = not configured)* |
| `MARKET_API_KEY` | data.gov.in key for live mandi prices | *(empty = demo data)* |
| `SARVAM_API_KEY`, `GEMINI_API_KEY` | optional extras, app works fully without them | *(empty)* |

## 12. Demo Mode vs Real Model

- `DEMO_MODE=false` (the shipped default): the backend requires the real trained model
  (`model/khetsetu.tflite`, falling back to `model/khetsetu.keras`). Both files are included in this
  ZIP, so the real model is used out of the box. Every `/api/predict` response includes
  `"demo_mode": false` and `"model": {"mode": "real", ...}`. If the model files are ever missing or
  fail to load, `/api/predict` returns a clear HTTP 503 error — it never silently substitutes a fake
  prediction.
- Set `DEMO_MODE=auto` during early UI development if you want the backend to fall back to clearly
  labelled simulated predictions (`"demo_mode": true`, a visible "Demo Mode" banner) when no model
  files are present, instead of returning 503. Not recommended for anything a farmer will see.
- `DEMO_MODE=true` forces simulated predictions even if a real model is present (useful for UI-only
  demos without ML dependencies installed).

## 13. Gemini LLM explanation layer (optional, additive only)

```
image -> ML classifier (MobileNetV2, model/khetsetu.tflite)
      -> crop + disease + confidence   <-- ALWAYS decided here, never by Gemini
      -> data/guidance.json            <-- trusted, human-written agricultural guidance
      -> [optional] Gemini             <-- rewrites the guidance above into 2-3 simple sentences
      -> existing UI (Result page, WhatsApp reply)
```

- Gemini is called from `backend/app/services/ai_explanation_service.py`, only if
  `GEMINI_API_KEY` is set in `.env`. It receives the crop/disease/confidence the classifier already
  decided, plus the matching `guidance.json` symptoms/cause/care text, and is instructed to use
  *only* facts from that text, never invent a diagnosis, and never give pesticide dosages.
- Its output is purely additive: the API response's `guidance` object (symptoms, possible cause,
  what to do, prevention) always comes straight from `guidance.json` and is shown regardless of
  Gemini. If Gemini succeeds, an extra `extra_explanation` field is added and
  `explanation_source` becomes `"guidance+llm"`; otherwise `explanation_source` stays `"guidance"`.
- **Fallback is automatic and silent to the user**: missing key, network failure, quota limit, or
  any exception from the Gemini SDK all result in `generate_extra_explanation()` returning `None`
  and logging a warning — the ML prediction, confidence, and guidance are completely unaffected.
  This was verified by running the full test suite and `test_model.py` with `GEMINI_API_KEY` unset.
- Supports English and Hindi (the same `language` the request already carries for guidance text).

### PDF scan reports

The Result screen downloads a report through `POST /api/report/pdf` with the current uploaded image
and selected English/Hindi language. The endpoint re-runs the server-side image pipeline; it never
accepts a client disease, confidence, or cached result as report authority. A below-threshold or
not-a-leaf image produces a safe photo-unclear report with no diagnosis. Reports include the image,
fresh result, confidence, available guidance, report ID, timestamp, source disclaimer, and a KhetSetu
header/footer watermark. PDF generation is local via `fpdf2` and HarfBuzz with bundled SIL OFL Noto
fonts.

The existing app, guidance catalog, LLM, and PDF report translations currently support English and
Hindi only. PDF font assets can shape six Indian scripts, but that font capability is not a substitute
for complete translated UI and agricultural guidance; Kannada, Telugu, Tamil, and Malayalam are not
presented as supported app languages.



## 14. Testing

```powershell
cd khetsetu
pip install -r backend\requirements.txt      # if not already installed
pytest tests -v
```

49 tests, all passing against the shipped model: `/api/health`, class-config consistency, guidance
completeness and no pesticide dosages/brand names, model-loaded-once behaviour, Demo Mode fallback
and labelling, the confidence gate (including the exact 0.70 boundary and that no disease/crop name
leaks below it), healthy-crop results, non-leaf rejection, invalid/corrupted/empty/oversized images,
supported formats (JPG/PNG/WEBP), a smoke test against 16 real held-out sample photos
(`tests/samples/`, >=85% correct among the ones it answers), PDF current-result/redaction checks,
six-script font shaping, crops/market/history endpoints, and the
full WhatsApp flow (verification handshake, signature checking, price parsing in English/Hindi,
photo replies, retries, download failures, unsupported messages). Frontend: `npm run typecheck` and
`npm run build` both pass (Chrome/Android/mobile-width manual testing was not performed in this
environment).

### Testing a single image from the command line

```powershell
cd backend
python test_model.py ..\tests\samples\Tomato___Late_blight\sample_1.jpg
python test_model.py path\to\your\photo.jpg --topk 5
```

This calls the exact same `app.preprocessing` + `app.model.classifier` code the API uses (not a
separate copy), so its output always matches what `/api/predict` would return for that image,
including the leaf-detection guard and the 0.70 confidence gate.

## 15. Deployment notes

- Backend: any host that can run Uvicorn/Gunicorn + Python 3.10-3.12 (e.g. a small VM, Render,
  Railway). Serve `model/` alongside the backend code.
- Frontend: `npm run build` output in `frontend/dist/` is static and can be served by any static
  host or CDN; set `VITE_API_BASE_URL` to your deployed backend's URL before building.
- SQLite (`backend/khetsetu.db`) is fine for a single-instance demo; move to Postgres
  (`DATABASE_URL`) for multiple backend instances.

## 16. Troubleshooting

- **`/api/health` shows `"mode": "unavailable"`** — `model/` files are missing or failed to load;
  check the backend startup log for the exact reason (`load_error` field).
- **Frontend can't reach the backend** — confirm the backend is running on port 8000 and
  `ALLOWED_ORIGINS` includes your frontend's origin.
- **WhatsApp webhook verification fails** — `WHATSAPP_VERIFY_TOKEN` in `.env` must exactly match the
  value entered in the Meta console.
- **Market prices always show "Demo market data"** — `MARKET_API_KEY` is empty; this is intentional,
  not a bug.
- **`pip install` fails on `tensorflow`** — use Python 3.10-3.12 (TensorFlow 2.16 does not support
  3.13 at the time of writing).

## 17. Re-running the ML pipeline (optional — a trained model already ships in `model/`)

```powershell
cd khetsetu
python ml\training\prepare_dataset.py --input ml\dataset --output ml\dataset_split
python ml\training\train.py --data ml\dataset_split --weights imagenet --epochs-head 3 --epochs-finetune 2 --fine-tune-from 120 --batch-size 32 --out model
python ml\training\export_model.py
python ml\evaluation\evaluate.py --data ml\dataset_split
```

The eight supported class folders are included in `ml\dataset\`; source attribution and the license
are in `ml/dataset/SOURCE.md`.

## 18. Dataset and retraining

The project includes 9,006 original PlantVillage RGB images from the eight supported tomato,
potato, and corn classes. Source repository, Hugging Face dataset, declared CC BY-SA 3.0 license,
research citation, original class names, and per-class counts are recorded in
`ml/dataset/SOURCE.md`. `model/class_names.json` is the canonical model-output order and is checked
against `model/class_config.json` by the training and backend code.

The split script groups near duplicates before assigning 70/15/15 train/validation/test splits.
Training uses train-split class weights, mild train-only geometric and camera-artifact augmentation,
early stopping, best-validation checkpoint selection, and temperature calibration on validation data.
The held-out test images are not used for training, checkpoint selection, or calibration.
