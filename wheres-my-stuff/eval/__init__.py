"""Model-comparison eval harness for the inventory app's vision pipeline.

Benchmarks candidate vision models (Claude Haiku/Sonnet, Amazon Nova, Rekognition)
against a gold set of hand-labeled item photos, scoring identification accuracy,
cost, and latency. See README.md in this directory.
"""
