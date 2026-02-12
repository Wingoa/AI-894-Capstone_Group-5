import sys
import subprocess
from pathlib import Path

def run_step(step_num: int, module: str, label: str) -> bool:
    try:
        subprocess.run([sys.executable, '-m', module], cwd=Path(__file__).parent, check=True)
        print(f"Step {step_num}: {label}")
        return True
    except subprocess.CalledProcessError:
        print(f"Step {step_num}: {label} failed")
        return False

def main():
    print("\n==============")
    print("FIGHTER VECTOR PIPELINE")
    print("==============\n")
    
    steps = [
        (1, 'process_data', 'Clean & normalize statistics'),
        (2, 'fighter_vectors', 'Create vectors & aggregations'),
        (3, 'analyze_fighter_vectors', 'Validate outputs'),
    ]
    
    failed = []
    for step_num, module, label in steps:
        if not run_step(step_num, module, label):
            failed.append(label)
    
    print("\n==============")

    if not failed:
        print("COMPLETE")
        print("==============")
        print("\nOutputs: resources/clean_data/ & resources/fighter_vectors/")
        print("Ready training!\n")
        return 0
    else:
        print(f"FAILED: {', '.join(failed)}")
        print("==============\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
