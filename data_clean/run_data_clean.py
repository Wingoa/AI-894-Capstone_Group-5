import os
import sys
from pathlib import Path

# Change to the script's directory so relative paths work
script_dir = Path(__file__).parent
os.chdir(script_dir)

import process_data
import fighter_vectors

def main():

    print("\n==============")
    print("FIGHTER VECTOR PIPELINE")
    print("==============\n")
    
    print("Step 1: Clean & normalize statistics")
    process_data.main()
    
    print("\nStep 2: Create vectors & aggregations")
    fighter_vectors.main()
    
    print("\nOutputs:")
    print("  - resources/clean_data/training_data.csv")

    print("  - resources/fighter_vectors/fighter_vectors_train.csv")
    print("  - resources/fighter_vectors/fighter_vectors_test.csv")
    print("  - resources/fighter_vectors/fighter_vectors_all.csv")

    print("\nReady for training!\n")

if __name__ == '__main__':
    main()
