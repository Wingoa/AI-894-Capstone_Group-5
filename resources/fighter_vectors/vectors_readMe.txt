Fighter Vectors 
________________

Fighter performance profiles with one row per fighter. Each fighter's statistics are averaged over their last 10 fights.

________________

Files ******

fighter_vectors_train.csv   - Fighters who last fought before 2025-01-01

fighter_vectors_test.csv    - Fighters who last fought in/after 2025-01-01

fighter_vectors_all.csv     - All fighters combined

________________

Generation Steps ******

Loads cleaned fight data from training_data.csv

Calculates per-minute stats for each fight

Averages each fighter's last 10 fights into a single profile

Adds outcome statistics (win rate, total fights, current streak)

Splits by date for temporal train/test separation

________________

