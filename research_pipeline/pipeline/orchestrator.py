"""Orchestrator."""
from ingestion.ingest_engine import run_ingestion

def run_pipeline(folder_id):

    print("\n🔥 RUNNING FULL PIPELINE")

    ingestion_result = run_ingestion(folder_id)

    # Later you will add:
    # validation
    # processing
    # aggregation

    return {
        "ingestion": ingestion_result
    }