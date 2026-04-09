from pipeline.orchestrator import run_pipeline

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("folder_id")

    args = parser.parse_args()

    run_pipeline(args.folder_id)