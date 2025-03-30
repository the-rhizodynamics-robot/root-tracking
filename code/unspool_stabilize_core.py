#!/usr/bin/env python3
"""
Script for unspooling videos into image sequences.
Refactored from transfer_unspool_stabilize.ipynb.
"""

import os
import gc
import sys
import argparse
from matplotlib import pyplot as plt
sys.path.append('/app/')

# Import local modules
from src.myutilities.util import listdir_nohidden, unspool_video
import src.retnet.model as model

def main():
    """
    Main function to process videos from input_path and save to output_path.
    """
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Unspool videos into image sequences.')
    parser.add_argument('--input_path', type=str, required=True, 
                        help='Directory containing input videos to process')
    parser.add_argument('--output_path', type=str, required=True, 
                        help='Directory where processed image sequences will be saved')
    args = parser.parse_args()
    
    # Get input and output paths from arguments
    input_path = args.input_path
    output_path = args.output_path
    
    # Check if input directory exists
    if not os.path.exists(input_path):
        print(f"Error: Input directory '{input_path}' not found.")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    if not os.path.exists(output_path):
        os.makedirs(output_path)
        print(f"Created output directory: {output_path}")
    
    # Get list of videos to process
    video_list = listdir_nohidden(input_path)
    
    print(f"Found {len(video_list)} videos to process.")
    
    for video_file in video_list:
        print(f"Processing: {video_file}")
        video_path = os.path.join(input_path, video_file)
        
        # Create output directory based on video filename without extension
        video_name = os.path.splitext(video_file)[0]
        unspool_path = os.path.join(output_path, video_name)
        
        # Unspool the video into a sequence of images
        # Remove the original video file after processing
        unspool_video(video_path, unspool_path, remove=True)
        
    print("Finished processing all videos.")

if __name__ == "__main__":
    main()