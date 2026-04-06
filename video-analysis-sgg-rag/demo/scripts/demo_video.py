import cv2
import argparse
import json
import numpy as np

from demo_model import SGG_Model
import os
from sgg_benchmark.utils.miscellaneous import get_path
import time

# main
def extract_scene_graph_data(bboxes, rels, stats, frame_number, timestamp):
    """Extract scene graph data from model predictions"""
    frame_data = {
        "frame": frame_number,
        "timestamp": timestamp,
        "objects": [],
        "relationships": []
    }
    
    # Extract objects
    if bboxes is not None and len(bboxes) > 0:
        for i, bbox in enumerate(bboxes):
            if len(bbox) >= 6:  # Ensure we have all required data
                obj_data = {
                    "id": i,
                    "name": stats['obj_classes'][int(bbox[5])],
                    "confidence": float(bbox[4]),
                    "bbox": [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
                }
                frame_data["objects"].append(obj_data)
    
    # Extract relationships
    if rels is not None and len(rels) > 0:
        for rel in rels:
            if len(rel) >= 4:  # Ensure we have all required data
                rel_data = {
                    "subject_id": int(rel[0]),
                    "object_id": int(rel[1]),
                    "predicate": stats['rel_classes'][int(rel[2])],
                    "confidence": float(rel[3])
                }
                # Add subject and object names
                if (rel_data["subject_id"] < len(bboxes) and 
                    rel_data["object_id"] < len(bboxes) and
                    bboxes is not None):
                    rel_data["subject"] = stats['obj_classes'][int(bboxes[rel_data["subject_id"]][5])]
                    rel_data["object"] = stats['obj_classes'][int(bboxes[rel_data["object_id"]][5])]
                    frame_data["relationships"].append(rel_data)
    
    return frame_data

def scene_graph_to_text(frame_data):
    """Convert scene graph data to natural language text description."""
    frame_num = frame_data["frame"]
    timestamp = frame_data["timestamp"]
    
    # Start with frame information
    text = f"Frame {frame_num} (at {timestamp:.2f}s): "
    
    # Add objects
    if frame_data["objects"]:
        object_names = [obj["name"] for obj in frame_data["objects"]]
        text += f"Objects detected: {', '.join(object_names)}. "
    
    # Add relationships
    if frame_data["relationships"]:
        relationships = []
        for rel in frame_data["relationships"]:
            subject = rel["subject"]
            predicate = rel["predicate"] 
            object_name = rel["object"]
            relationships.append(f"{subject} {predicate} {object_name}")
        text += f"Relationships: {'; '.join(relationships)}."
    
    return text

def convert_scene_graph_to_text_file(json_path, output_text_path=None):
    """Convert entire scene graph JSON to text file."""
    if output_text_path is None:
        output_text_path = json_path.replace('.json', '.txt')
    
    with open(json_path, 'r') as f:
        scene_data = json.load(f)
    
    with open(output_text_path, 'w') as f:
        for frame_data in scene_data:
            text_description = scene_graph_to_text(frame_data)
            f.write(text_description + '\n\n')
    
    print(f"Text descriptions saved to: {output_text_path}")
    return output_text_path

def main(args):
    config_path = args.config
    weights = args.weights
    tracking = args.tracking
    rel_conf = args.rel_conf
    box_conf = args.box_conf
    video_path = args.video
    dcs = args.dcs
    save_path = args.save_path
    window_width = args.window_width
    window_height = args.window_height

    # Initialize scene graph data collection
    scene_graph_data = []

    # this will create and load the model according to the config file
    # please make sure that the path in MODEL.WEIGHT in the config file is correct
    model = SGG_Model(config_path, weights, dcs=dcs, tracking=tracking, rel_conf=rel_conf, box_conf=box_conf)

    # Open the video
    cap = cv2.VideoCapture(video_path)
    
    # Check if video file was opened successfully
    if not cap.isOpened():
        print(f"Error: Could not open video file: {video_path}")
        return

    video_size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    frame_rate = cap.get(cv2.CAP_PROP_FPS)
    
    # Check if video properties are valid
    if frame_rate <= 0:
        print("Warning: Invalid frame rate detected, using default 30 FPS")
        frame_rate = 30.0
    
    print(f"Video info: {video_size[0]}x{video_size[1]} @ {frame_rate:.2f} FPS")

    # video_fps = cap.get(cv2.CAP_PROP_FPS)
    video_out = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*'XVID'), fps=frame_rate, frameSize=video_size)
    
    # Check if output video writer was created successfully
    if not video_out.isOpened():
        print(f"Error: Could not create output video file: {save_path}")
        cap.release()
        return

    frame_count = 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Processing {total_frames} frames...")

    cv2.namedWindow('Bbox detection', cv2.WINDOW_NORMAL)  # Make window resizable
    cv2.resizeWindow('Bbox detection', window_width, window_height)  # Set window size using args

    while True:
        t = time.time()
        # Capture frame-by-frame
        ret, frame = cap.read()
        
        # Check if frame was read successfully (video end or error)
        if not ret or frame is None:
            print("End of video or failed to read frame")
            break
        
        frame_count += 1
        if frame_count % 30 == 0:  # Print progress every 30 frames
            print(f"Processing frame {frame_count}/{total_frames} ({frame_count/total_frames*100:.1f}%)")
        
        # Make prediction
        img, graph = model.predict(frame, visu_type='video')
        
        # Extract scene graph data for chatbot
        if graph is not None:
            timestamp = frame_count / frame_rate
            frame_data = extract_scene_graph_data(
                graph["bboxes"], 
                graph["rels"], 
                graph["stats"], 
                frame_count, 
                timestamp
            )
            
            # Save frame image for UI display
            frames_dir = save_path.replace('.avi', '_frames')
            os.makedirs(frames_dir, exist_ok=True)
            frame_filename = f"frame_{frame_count:06d}.jpg"
            frame_path = os.path.join(frames_dir, frame_filename)
            cv2.imwrite(frame_path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            
            # Add frame path to data
            frame_data["frame_path"] = frame_path
            scene_graph_data.append(frame_data)

        # avg_fps.append(fps)

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Display the resulting frame
        cv2.imshow('Bbox detection', img)

        next_frame = (time.time() - t) * frame_rate
        cap.set(cv2.CAP_PROP_POS_FRAMES, cap.get(cv2.CAP_PROP_POS_FRAMES) + next_frame)

        if next_frame > 1:
            for i in range(int(next_frame)):
                video_out.write(img)
        else:
            video_out.write(img)
            
        # Check for user quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("User quit requested")
            break
    
    print(f"Video processing completed! Processed {frame_count} frames.")
    print(f"Output saved to: {save_path}")
    
    # Save scene graph data for chatbot
    if scene_graph_data:
        json_path = save_path.replace('.avi', '_scene_graph.json')
        with open(json_path, 'w') as f:
            json.dump(scene_graph_data, f, indent=2)
        print(f"Scene graph data saved to: {json_path}")
        print(f"Collected {len(scene_graph_data)} frames of scene graph data")
        
        # Convert to text descriptions
        text_path = convert_scene_graph_to_text_file(json_path)
        print(f"Text descriptions generated: {text_path}")
    
    # compute the latency of each component
    print("Latency: \n", model.get_latency())

    # release the video
    video_out.release()

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Webcam demo")

    parser.add_argument('--config', default="configs/VG150/baseline/e2e_relation_X_101_32_8_FPN_1x.yaml", type=str, required=True, help='Path to the config file, e.g. config.yml')
    parser.add_argument('--weights', type=str, required=True, help='Path to the weights file, e.g. model.pth')
    parser.add_argument('--tracking', action="store_true", help='Object tracking or not')
    parser.add_argument('--rel_conf', type=float, default=0.01, help='Relation confidence threshold')
    parser.add_argument('--box_conf', type=float, default=0.001, help='Box confidence threshold')
    parser.add_argument('--video', default=".", type=str, help='Path to the video file')
    parser.add_argument('--save_path', default="./demo/output.avi", type=str, help='Path to save the output video')
    parser.add_argument('--dcs', type=int, default=100, help='Dynamic Candidate Selection')
    parser.add_argument('--window_width', type=int, default=1280, help='Width of the display window')
    parser.add_argument('--window_height', type=int, default=720, help='Height of the display window')

    args = parser.parse_args()

    # change all relative path
    # GEMINI_API_KEY=AIzaSyDeMAgRP8wZPgZ-5-q3v4G5VR5nC7p7V7Ahs to absolute
    if not os.path.isabs(args.config):
        args.config = os.path.join(get_path(), args.config)
    if not os.path.isabs(args.weights):
        args.weights = os.path.join(get_path(), args.weights)

    main(args)