.PHONY: eval eval-stub test test-lambdas install

# Live model comparison (needs AWS creds + boto3 + photos in eval/gold/).
eval:
	python3 -m eval.run_eval --models haiku,sonnet,nova,rekognition \
		--out-md eval/scorecard.md --out-csv eval/scorecard.csv

# Offline smoke test of the harness with the stub model (no AWS, no photos).
eval-stub:
	python3 -m eval.run_eval --models stub \
		--gold eval/tests/fixtures/gold.jsonl \
		--fixtures eval/tests/fixtures/stub_predictions.json

test:
	python3 -m pytest eval backend/functions -q

install:
	python3 -m pip install -r eval/requirements.txt
