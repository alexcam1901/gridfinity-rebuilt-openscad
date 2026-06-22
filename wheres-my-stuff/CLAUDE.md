# Where's My Stuff — Claude Code context

Voice + image home/garage inventory app. Ask "where are my wire nuts?" → get
the exact shelf and bin. Snap a photo, Claude Haiku pre-fills what it is,
confirm, done.

## Confirmed decisions

| Decision | Choice |
|---|---|
| Platform | Flutter (iOS + Android) |
| Backend | AWS Amplify Gen 2 (Cognito + AppSync + DynamoDB + S3) |
| Vision AI | Claude Haiku 4.5 via Amazon Bedrock (primary) |
| OCR fallback | Rekognition DetectText (optional pre-pass) |
| Voice | Amazon Transcribe (server) + speech_to_text (on-device for query) |
| Multi-user | owner-based auth now; `householdId` ready for group swap later |

## Repository layout

```
/
├─ eval/            # Model-comparison harness (Haiku vs Sonnet vs Nova vs Rekognition)
│  ├─ adapters/     # bedrock.py, rekognition.py, stub.py
│  ├─ tests/        # 12 tests — run with `make test`
│  └─ gold/         # Add labeled photos + gold.jsonl to run real eval
├─ backend/
│  ├─ amplify/      # Amplify Gen 2 TypeScript backend
│  │  ├─ auth/      # Cognito user pool
│  │  ├─ data/      # AppSync schema: Location, Item, Photo + searchItems query
│  │  ├─ storage/   # S3 photo bucket
│  │  └─ functions/search/  # TypeScript Lambda: synonym-aware DynamoDB search
│  └─ functions/    # Python Lambdas (share shared/synonyms.json with eval)
│     ├─ query/     # "where is X" search (synonym-aware, rank_matches)
│     ├─ ingest_photo/  # Bedrock Claude Haiku → structured item JSON
│     └─ transcribe/   # Amazon Transcribe voice→text
├─ app/             # Flutter app
│  ├─ lib/
│  │  ├─ main.dart          # 3-tab shell: Find / Browse / Add
│  │  ├─ models/            # Location, Item
│  │  ├─ data/              # MockDb (seeded), LocationRepository, ItemRepository
│  │  └─ features/
│  │     ├─ search/         # Find tab — synonym search, tap → item detail
│  │     ├─ locations/      # Browse tab — room→shelf→bin tree, add/edit/delete
│  │     ├─ items/          # Item detail + add/edit form
│  │     └─ capture/        # Add tab — photo stub → confirm screen → item form
└─ shared/
   └─ synonyms.json  # Single source of truth for both eval scorer and query Lambda
```

## Build phases and status

| Phase | Status |
|---|---|
| 1. Repo + backend skeleton | ✅ Done |
| 2. Manual CRUD + hierarchy (location tree, item add/edit) | ✅ Done |
| 3. Search (synonym-aware, wired to mock DB + AppSync TS Lambda) | ✅ Done |
| 4. Eval harness (Haiku/Sonnet/Nova/Rekognition scorer) | ✅ Done, 33 tests passing |
| 5. Image recognition (camera → S3 → ingest_photo Lambda → confirm screen) | 🔲 TODO |
| 6. Voice (speech_to_text → search; Transcribe → add flow) | 🔲 TODO |
| 7. Amplify deploy + Amplify.configure() wiring | 🔲 TODO |
| 8. Polish (barcode, gridfinity bin link, offline SQLite, multi-user flip) | 🔲 TODO |

## Quick start (no AWS needed)

```bash
python3 -m pip install -r eval/requirements.txt
make test          # 33 Python tests
make eval-stub     # offline scorecard demo
```

## Deploy backend

```bash
cd backend
npm install
npx ampx sandbox   # provisions Cognito + AppSync/DynamoDB + S3 + search Lambda
```

Generates `amplify_outputs.json` → copy/convert to `app/amplify_outputs.dart`,
then enable `Amplify.configure(...)` in `app/lib/main.dart`.

## Run the Flutter app

```bash
cd app
flutter pub get
flutter run        # works immediately against seeded mock DB, no AWS needed
```

## Key implementation notes

### Synonym matching
`shared/synonyms.json` is the single source of truth. Both the Python
`eval/synonyms.py` + `backend/functions/query/handler.py` AND the TypeScript
`backend/amplify/functions/search/handler.ts` implement the same normalize +
group-expand algorithm so eval results predict production behaviour.

### Mock DB → Amplify swap path
`app/lib/data/mock_db.dart` is a singleton seeded with 11 items. All
repositories (`LocationRepository`, `ItemRepository`, `InventoryRepository`)
delegate to it. To wire Amplify: replace each repository method body with an
`Amplify.API.query/mutate` call — the signatures stay the same.

### Photo ingest flow (Phase 5)
1. `camera` package → photo bytes
2. `Amplify.Storage.uploadFile(s3Key, file)` → S3
3. AppSync mutation `ingestPhoto(s3Key:)` → `ingest_photo` Lambda
4. Lambda: optional Rekognition OCR pre-pass → Bedrock Claude Haiku → `{name, tags, ocr_text}`
5. Navigate to `ConfirmScreen(result: IngestResult(...))` → `ItemFormScreen`
   with pre-filled name/tags → save

### Voice flow (Phase 6)
- **Find**: `speech_to_text` package (on-device) → text → `InventoryRepository.search()`
- **Add**: `speech_to_text` or record clip → S3 → `transcribe` Lambda → text → confirm flow

### Multi-user migration (Phase 8)
Currently: `allow.owner()` in `backend/amplify/data/resource.ts`.
To share with household: swap to `allow.groupDefinedIn("householdId")`, add
a Cognito group per household, invite members. No DynamoDB reshape — every
record already carries `householdId`.

### Vision model config
`VISION_MODEL_ID` env var on the `ingest_photo` Lambda (default:
`anthropic.claude-haiku-4-5`). Change to switch model in production without
a code deploy. The eval harness (`make eval`) measures Haiku vs Sonnet vs
Nova 2 Lite vs Rekognition to confirm the choice.
