"""
Scene Graph Video Chatbot - Gradio UI

A web interface for chatting about video content using scene graphs.
Left panel: Chat conversation
Right panel: Related frames display
"""

import gradio as gr
import json
import os
import sys
import cv2
import numpy as np
from PIL import Image
from typing import List, Dict, Any, Tuple

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scene_graph_chatbot import SceneGraphChatbot

class GradioVideoChat:
    def __init__(self, api_key: str):
        """Initialize the Gradio interface."""
        self.api_key = api_key
        self.chatbot = None
        self.scene_data_path = None
        self.frames_dir = None
        self.chat_history = []
        
    def load_video_data(self, scene_data_file, index_file=None):
        """Load video scene graph data and frames."""
        try:
            self.scene_data_path = scene_data_file.name
            
            # Initialize chatbot
            self.chatbot = SceneGraphChatbot(self.api_key)
            
            # Determine frames directory - always use the demo folder
            # Extract just the filename (e.g., "accident_video_scene_graph.json")
            scene_filename = os.path.basename(self.scene_data_path)
            
            # Get the base name without _scene_graph.json
            base_name = scene_filename.replace('_scene_graph.json', '')
            
            # Construct path in demo folder
            demo_dir = os.path.dirname(os.path.abspath(__file__))
            parent_demo_dir = os.path.dirname(demo_dir)  # Go up from scripts to demo
            
            # Try multiple possible locations
            possible_paths = [
                os.path.join(parent_demo_dir, f"{base_name}_frames"),  # demo/accident_video_frames
                os.path.join(demo_dir, f"{base_name}_frames"),  # demo/scripts/accident_video_frames
                os.path.join(os.path.dirname(parent_demo_dir), f"{base_name}_frames"),  # root/accident_video_frames
            ]
            
            self.frames_dir = None
            for path in possible_paths:
                if os.path.exists(path) and os.path.isdir(path):
                    self.frames_dir = path
                    break
            
            if not self.frames_dir:
                self.frames_dir = possible_paths[0]  # Default to first option
            
            print(f"Scene data path: {self.scene_data_path}")
            print(f"Calculated frames dir: {self.frames_dir}")
            
            if index_file and os.path.exists(index_file.name):
                # Load existing index
                self.chatbot.load_index(index_file.name)
                status = f"✅ Loaded existing index from {index_file.name}"
            else:
                # Build new index
                self.chatbot.load_scene_graph_data(self.scene_data_path)
                self.chatbot.build_vector_database()
                status = f"✅ Built new index from {self.scene_data_path}"
                
            # Check if frames directory exists
            if os.path.exists(self.frames_dir):
                frame_count = len([f for f in os.listdir(self.frames_dir) if f.endswith('.jpg')])
                status += f"\\n📁 Found {frame_count} frames in {self.frames_dir}"
            else:
                status += f"\\n⚠️ Frames directory not found: {self.frames_dir}"
                status += "\\nNote: Run demo_video.py first to generate frames"
                
            return status, gr.update(interactive=True)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"❌ Error loading data: {str(e)}", gr.update(interactive=False)
    
    def get_frame_image(self, frame_number: int, highlight_objects: bool = True) -> Image.Image:
        """Get frame image, optionally with object highlighting."""
        try:
            if not self.frames_dir or not os.path.exists(self.frames_dir):
                print(f"Frames directory not found: {self.frames_dir}")
                return None
                
            frame_filename = f"frame_{frame_number:06d}.jpg"
            frame_path = os.path.join(self.frames_dir, frame_filename)
            print(f"Looking for frame: {frame_path}")
            
            if not os.path.exists(frame_path):
                print(f"Frame file not found: {frame_path}")
                return None
                
            # Load image
            image = cv2.imread(frame_path)
            if image is None:
                print(f"Failed to load image: {frame_path}")
                return None
                
            # Convert BGR to RGB
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # If highlighting is requested and we have scene data
            if highlight_objects and hasattr(self.chatbot, 'scene_data'):
                # Find frame data
                frame_data = None
                for data in self.chatbot.scene_data:
                    if data['frame'] == frame_number:
                        frame_data = data
                        break
                
                if frame_data and 'objects' in frame_data:
                    # Draw bounding boxes
                    for obj in frame_data['objects']:
                        if 'bbox' in obj:
                            x1, y1, x2, y2 = map(int, obj['bbox'])
                            # Draw rectangle
                            cv2.rectangle(image_rgb, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            # Draw label
                            label = f"{obj['name']} ({obj['confidence']:.2f})"
                            cv2.putText(image_rgb, label, (x1, y1-10), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            return Image.fromarray(image_rgb)
            
        except Exception as e:
            print(f"Error loading frame {frame_number}: {e}")
            return None
    
    def chat_with_frames(self, message: str, history: List[List[str]]) -> Tuple[List[List[str]], List[Image.Image], str]:
        """Process chat message and return relevant frames."""
        if not self.chatbot:
            return history + [[message, "⚠️ Please load video data first"]], [], ""
        
        try:
            print(f"Processing query: {message}")
            # Get chatbot response
            result = self.chatbot.chat(message, top_k=5)
            answer = result['answer']
            relevant_frames = result['relevant_frames']
            
            print(f"Found {len(relevant_frames)} relevant frames")
            
            # Collect frame images
            frame_images = []
            frame_info = []
            
            for i, frame in enumerate(relevant_frames[:3]):  # Show top 3 frames
                frame_num = frame['frame']
                timestamp = frame['timestamp']
                score = frame['score']
                
                print(f"Processing frame {frame_num} (score: {score:.3f})")
                
                # Get frame image
                img = self.get_frame_image(frame_num, highlight_objects=True)
                if img:
                    frame_images.append(img)
                    frame_info.append(f"Frame {frame_num} (t={timestamp:.2f}s, score={score:.3f})")
                    print(f"Successfully loaded frame {frame_num}")
                else:
                    print(f"Failed to load frame {frame_num}")
            
            print(f"Loaded {len(frame_images)} frame images")
            
            # Format response with frame information
            response = answer
            if frame_info:
                response += f"\\n\\n📸 **Relevant frames:**\\n" + "\\n".join(f"• {info}" for info in frame_info)
            
            # Update history
            new_history = history + [[message, response]]
            
            return new_history, frame_images, "\\n".join(frame_info)
            
        except Exception as e:
            print(f"Error in chat_with_frames: {e}")
            import traceback
            traceback.print_exc()
            error_msg = f"❌ Error: {str(e)}"
            return history + [[message, error_msg]], [], ""
    
    def create_interface(self):
        """Create the Gradio interface."""
        
        with gr.Blocks(title="Scene Graph Video Chatbot", theme=gr.themes.Soft()) as interface:
            gr.Markdown("# 🎥 Scene Graph Video Chatbot")
            gr.Markdown("Chat about video content using AI-powered scene graph analysis")
            
            with gr.Row():
                # Left column: Data loading and status
                with gr.Column(scale=1):
                    gr.Markdown("## 📁 Data Loading")
                    
                    scene_data_file = gr.File(
                        label="Scene Graph JSON File",
                        file_types=[".json"],
                        type="filepath"
                    )
                    
                    index_file = gr.File(
                        label="FAISS Index File (optional)",
                        file_types=[".index"],
                        type="filepath"
                    )
                    
                    load_btn = gr.Button("🔄 Load Data", variant="primary")
                    status_text = gr.Textbox(
                        label="Status", 
                        interactive=False,
                        lines=4
                    )
            
            with gr.Row():
                # Left panel: Chat interface
                with gr.Column(scale=2):
                    gr.Markdown("## 💬 Chat")
                    chatbot_interface = gr.Chatbot(
                        label="Conversation",
                        height=500,
                        show_copy_button=True
                    )
                    
                    with gr.Row():
                        msg_input = gr.Textbox(
                            label="Your question",
                            placeholder="Ask about the video content (e.g., 'What vehicles appear?', 'Are there any accidents?')",
                            scale=4,
                            interactive=False
                        )
                        send_btn = gr.Button("Send", variant="primary", scale=1, interactive=False)
                    
                    # Example questions
                    gr.Markdown("**💡 Example questions:**")
                    example_questions = [
                        "What objects appear in this video?",
                        "Are there any accidents or incidents?", 
                        "What vehicles are present?",
                        "Describe what happens in the first 10 seconds",
                        "What relationships do you see between objects?"
                    ]
                    
                    for i, question in enumerate(example_questions):
                        example_btn = gr.Button(question, size="sm")
                        example_btn.click(
                            lambda q=question: q,
                            outputs=msg_input
                        )
                
                # Right panel: Frame display
                with gr.Column(scale=2):
                    gr.Markdown("## 🖼️ Relevant Frames")
                    
                    frame_info = gr.Textbox(
                        label="Frame Information",
                        lines=3,
                        interactive=False
                    )
                    
                    # Gallery for displaying multiple frames
                    frame_gallery = gr.Gallery(
                        label="Related Frames",
                        columns=1,
                        rows=3,
                        height="auto",
                        object_fit="contain"
                    )
            
            # Event handlers
            load_btn.click(
                fn=self.load_video_data,
                inputs=[scene_data_file, index_file],
                outputs=[status_text, msg_input]
            )
            
            # Chat functionality
            def process_message(message, history):
                return self.chat_with_frames(message, history)
            
            send_btn.click(
                fn=process_message,
                inputs=[msg_input, chatbot_interface],
                outputs=[chatbot_interface, frame_gallery, frame_info]
            ).then(
                lambda: "",  # Clear input
                outputs=msg_input
            )
            
            # Enter key support
            msg_input.submit(
                fn=process_message,
                inputs=[msg_input, chatbot_interface],
                outputs=[chatbot_interface, frame_gallery, frame_info]
            ).then(
                lambda: "",  # Clear input
                outputs=msg_input
            )
            
            # Enable send button when data is loaded
            def update_send_button(status):
                return gr.update(interactive="✅" in status)
            
            status_text.change(
                fn=update_send_button,
                inputs=status_text,
                outputs=send_btn
            )
        
        return interface

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Scene Graph Video Chatbot - Gradio UI")
    parser.add_argument("--api_key", default="AIzaSyCQldQQvFYeACvMJZAF1hqrB6NGmJTpEeI", help="Gemini API key")
    parser.add_argument("--port", type=int, default=7860, help="Port to run the server")
    parser.add_argument("--share", action="store_true", help="Create public link")
    
    args = parser.parse_args()
    
    # Create the app
    app = GradioVideoChat(args.api_key)
    interface = app.create_interface()
    
    # Launch the interface
    print("🚀 Starting Scene Graph Video Chatbot...")
    print(f"🌐 Server will run on port {args.port}")
    if args.share:
        print("🔗 Public link will be created")
    
    interface.launch(
        server_port=args.port,
        share=args.share,
        inbrowser=True
    )

if __name__ == "__main__":
    main()
