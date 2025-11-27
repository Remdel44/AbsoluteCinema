import os


def move_all_wavs_in(target_path="wav"):
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".wav"):
                source_path = os.path.join(root, file)
                print(f'Found: {source_path}')
                destination_path = os.path.join(target_path, file)
                os.rename(source_path, destination_path)
                print(f"Moved: {source_path} -> {destination_path}")

    

if __name__ == "__main__":
    move_all_wavs_in()