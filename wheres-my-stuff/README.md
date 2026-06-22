# Where's My Stuff — voice + image home/garage inventory

Catalog everything in your house/garage and find it by asking — *"where are my
wire nuts?"* → **Garage › Wall shelf B › Bin 3**. Snap a photo, a vision model
pre-fills what it is, confirm, done. Add and find things by voice.

This is the initial scaffold for the approved plan
(`/root/.claude/plans/try-again-system-reminder-message-sent-recursive-codd.md`).

## What's here

```
wheres-my-stuff/
├─ eval/        # ✅ runnable model-comparison harness (Haiku vs Sonnet vs Nova vs Rekognition)
├─ backend/     # Amplify Gen 2 backend (multi-tenant data model) + Python Lambdas
│  ├─ amplify/  #   auth, data (owner-based auth + householdId), storage, backend.ts
│  └─ functions/#   query (synonym "where is X") + ingest_photo (Bedrock Haiku)
├─ app/         # Flutter app shell (Find / Add tabs)
└─ shared/      # synonyms.json — single source of truth for fuzzy matching
```

## Status

| Piece | State |
|---|---|
| Eval harness + scorer + report | **Complete, tested** (`make eval-stub`, `make test`) |
| Shared synonym map | **Complete** |
| Backend data model (multi-user-ready) | Defined (Amplify Gen 2 TS) — deploy with `ampx sandbox` |
| `query` + `ingest_photo` Lambdas | Core logic complete + tested; AWS glue stubbed |
| Flutter app | Shell + screens; camera/voice/Amplify wiring is TODO |

## Quick start

### Run the tests (no AWS needed)
```bash
cd wheres-my-stuff
python3 -m pip install -r eval/requirements.txt   # or just `pip install pytest`
make test            # eval + backend Lambda unit tests
make eval-stub       # offline scorecard demo with the stub model
```

### Compare real models (needs AWS creds + boto3 + photos)
1. Put hand-labeled photos in `eval/gold/` and add lines to `eval/gold.jsonl`.
2. Set `AWS_REGION` and ensure your account has Bedrock + Rekognition access.
3. `make eval` → writes `eval/scorecard.md` and `eval/scorecard.csv`.

Haiku is the chosen default; the harness exists to confirm that and to check
whether Nova 2 Lite (cheaper) is close enough to switch. The vision model is a
single env var (`VISION_MODEL_ID`) in `ingest_photo`.

### Deploy the backend
```bash
cd backend
npm install
npx ampx sandbox        # provisions Cognito + AppSync/DynamoDB + S3
```
Then wire the Python Lambdas (`backend/functions/query`, `ingest_photo`) as
custom functions / AppSync resolvers — they're plain handlers so they can share
`shared/synonyms.json` with the eval harness.

### Run the app
```bash
cd app
flutter pub get
flutter run
```
The app runs against placeholder data until `ampx sandbox` generates
`amplify_outputs.dart`; then enable `Amplify.configure(...)` in `lib/main.dart`.

## Design notes

- **Multi-user-ready from day one.** Every record carries `owner` + `householdId`
  and uses Amplify owner-based auth, so isolation works with one account and
  going to a shared household is a rule swap, not a data migration. See
  `backend/amplify/data/resource.ts`.
- **One prompt everywhere.** `eval/prompt.py` and `ingest_photo` use the same
  identification prompt, so the model the eval picks behaves identically in prod.
- **Synonyms are shared data.** `shared/synonyms.json` drives both the eval
  fuzzy-match scorer and the production search ranking.
