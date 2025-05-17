import os
import subprocess
from pathlib import Path
import shutil
import torch
from demucs.pretrained import get_model
from demucs.apply import apply_model
from demucs.audio import AudioFile, save_audio
from midiutil import MIDIFile
import mido

def get_output_path(input_path, stem_name=None):
    """Convert input path to expected output path."""
    # Get the filename without extension
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    # Create the output path with _basic_pitch.mid extension
    if stem_name:
        return os.path.join('out', f"{base_name}_{stem_name}_basic_pitch.mid")
    return os.path.join('out', f"{base_name}_basic_pitch.mid")

def combine_midi_files(midi_files, output_path):
    """Combine multiple MIDI files into one, preserving their tracks."""
    # Create a new MIDI file
    combined = MIDIFile()
    
    # Track mapping for different instruments using standard MIDI channels
    track_mapping = {
        'drums': 9,     # Channel 10 (0-based) is standard for drums
        'bass': 0,      # Channel 1 for bass
        'vocals': 1,    # Channel 2 for vocals
        'other': 2      # Channel 3 for other instruments
    }
    
    # Process each MIDI file
    for stem_name, midi_path in midi_files.items():
        if not os.path.exists(midi_path):
            print(f"Warning: MIDI file {midi_path} not found, skipping...")
            continue
            
        # Read the MIDI file
        mid = mido.MidiFile(midi_path)
        
        # Add a new track for this stem
        track = track_mapping.get(stem_name, len(track_mapping))
        combined.addTrackName(track, 0, stem_name)
        
        # Set program (instrument) for each track
        if stem_name == 'drums':
            # Drums don't need a program change as they use channel 10
            pass
        elif stem_name == 'bass':
            combined.addProgramChange(track, 0, 0, 33)  # Electric Bass
        elif stem_name == 'vocals':
            combined.addProgramChange(track, 0, 0, 53)  # Voice Oohs
        else:  # other
            combined.addProgramChange(track, 0, 0, 0)   # Acoustic Grand Piano
        
        # Copy all messages from the original file
        for msg in mid.tracks[0]:
            if msg.type == 'note_on' or msg.type == 'note_off':
                # Convert the message to the format MIDIUtil expects
                if msg.type == 'note_on':
                    combined.addNote(track, 0, msg.note, msg.time, msg.time + 100, msg.velocity)
                # Note-off messages are handled automatically by MIDIUtil
    
    # Write the combined file
    with open(output_path, 'wb') as f:
        combined.writeFile(f)
    
    print(f"Combined MIDI file saved to: {output_path}")
    print("MIDI channels used:")
    print("- Drums: Channel 10 (standard MIDI drum channel)")
    print("- Bass: Channel 1")
    print("- Vocals: Channel 2")
    print("- Other: Channel 3")

def separate_stems(input_path):
    """Separate audio into stems using Demucs."""
    # Initialize the model (using the 4-stem model)
    model = get_model('htdemucs')
    model.cpu()  # Use CPU for inference
    
    # Create a temporary directory for stems
    temp_dir = os.path.join('out', 'temp_stems')
    os.makedirs(temp_dir, exist_ok=True)
    
    # Load and process the audio
    wav = AudioFile(input_path).read(streams=0, samplerate=model.samplerate, channels=model.audio_channels)
    ref = wav.mean(0)
    wav = (wav - ref.mean()) / ref.std()
    
    # Apply the model
    sources = apply_model(model, wav[None])[0]
    sources = sources * ref.std() + ref.mean()
    
    # Get the base name of the input file
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    stems_dir = os.path.join(temp_dir, base_name)
    os.makedirs(stems_dir, exist_ok=True)
    
    # Save each stem
    stem_paths = {}
    for source, name in zip(sources, model.sources):
        stem_path = os.path.join(stems_dir, f"{name}.wav")
        save_audio(source, stem_path, model.samplerate)
        stem_paths[name] = stem_path
    
    return stem_paths

def process_new_mp3s(combine_midi=True):
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
        # Check if any of the stem MIDI files don't exist
        needs_processing = False
        for stem in ['drums', 'bass', 'vocals', 'other']:
            output_path = get_output_path(mp3_path, stem)
            if not os.path.exists(output_path):
                needs_processing = True
                break
        
        if needs_processing:
            files_to_process.append(str(mp3_path))
    
    if not files_to_process:
        print("No new MP3 files to process")
        return
    
    # Process new files
    print(f"Found {len(files_to_process)} new MP3 files to process")
    for mp3_path in files_to_process:
        print(f"Processing: {mp3_path}")
        try:
            # First separate the stems
            print(f"Separating stems for: {mp3_path}")
            stems = separate_stems(mp3_path)
            
            # Process each stem
            midi_files = {}
            for stem_name, stem_path in stems.items():
                print(f"Converting {stem_name} stem to MIDI")
                output_path = get_output_path(mp3_path, stem_name)
                midi_files[stem_name] = output_path
                
                # Use subprocess to call basic-pitch command
                result = subprocess.run(['basic-pitch', 'out', stem_path], 
                                     capture_output=True, 
                                     text=True)
                
                if result.returncode == 0:
                    print(f"Successfully converted {stem_name} stem")
                else:
                    print(f"Error processing {stem_name} stem: {result.stderr}")
            
            # Combine MIDI files if requested
            if combine_midi:
                base_name = os.path.splitext(os.path.basename(mp3_path))[0]
                combined_path = os.path.join('out', f"{base_name}_combined.mid")
                print("Combining MIDI files...")
                combine_midi_files(midi_files, combined_path)
            
            # Clean up temporary stem files
            temp_dir = os.path.join('out', 'temp_stems')
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                
        except Exception as e:
            print(f"Error processing {mp3_path}: {str(e)}")

if __name__ == "__main__":
    process_new_mp3s(combine_midi=True)  # Set to False if you don't want to combine MIDI files