import os
import subprocess
from pathlib import Path

def get_output_path(input_path):
    """Convert input path to expected output path."""
    # Get the filename without extension
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    # Create the output path with _basic_pitch.mid extension
    return os.path.join('out', f"{base_name}_basic_pitch.mid")

def process_new_mp3s():
    # Create out directory if it doesn't exist
    os.makedirs('out', exist_ok=True)
    
    # Get all MP3 files from data directory
    data_dir = Path('data')
    mp3_files = list(data_dir.glob('*.mp3'))
    
    if not mp3_files:
        print("No MP3 files found in data/ directory")
        return
    
    # Track which files need processing
    files_to_process = []
    
    # Check each MP3 file
    for mp3_path in mp3_files:
        output_path = get_output_path(mp3_path)
        
        # If output file doesn't exist, add to processing list
        if not os.path.exists(output_path):
            files_to_process.append(str(mp3_path))  # Convert Path to string
    
    if not files_to_process:
        print("No new MP3 files to process")
        return
    
    # Process new files
    print(f"Found {len(files_to_process)} new MP3 files to process")
    for mp3_path in files_to_process:
        print(f"Processing: {mp3_path}")
        try:
            # Use subprocess to call basic-pitch command
            result = subprocess.run(['basic-pitch', 'out', mp3_path], 
                                 capture_output=True, 
                                 text=True)
            
            if result.returncode == 0:
                print(f"Successfully converted: {mp3_path}")
            else:
                print(f"Error processing {mp3_path}: {result.stderr}")
        except Exception as e:
            print(f"Error processing {mp3_path}: {str(e)}")

if __name__ == "__main__":
    process_new_mp3s()