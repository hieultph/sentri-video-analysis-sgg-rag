# Scene Graph Video Chatbot

An AI-powered chatbot that analyzes video content through scene graph generation and provides intelligent insights using FAISS vector database and Google Gemini AI.

## Features

- **Scene Graph Extraction**: Automatically extracts objects and relationships from video frames
- **Natural Language Processing**: Converts scene graphs to readable text descriptions
- **Vector Database**: Uses FAISS for efficient similarity search across video content
- **AI-Powered Insights**: Leverages Google Gemini AI for intelligent question answering
- **Interactive Chat**: Supports both single questions and interactive chat sessions

## Installation

1. Install the required dependencies:

```bash
pip install faiss-cpu google-generativeai sentence-transformers
```

2. Set up your Gemini API key:
   - Get an API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Replace `YOUR_API_KEY` in the scripts with your actual key

## Usage

### Step 1: Process Video to Generate Scene Graph Data

First, process your video using the modified demo_video.py:

```bash
python demo_video.py \
  --config configs/PSG/e2e_relation_X_101_32_8_FPN_1x.yaml \
  --weights checkpoint/react_PSG/react_final.pth \
  --video path/to/your/video.mp4 \
  --save_path output/video_result.avi
```

This will generate:

- `output/video_result.avi` - Processed video with scene graph visualizations
- `output/video_result_scene_graph.json` - Scene graph data in JSON format
- `output/video_result_scene_graph.txt` - Text descriptions of scene graphs

### Step 2: Use the Chatbot

#### Method 1: Interactive Chatbot

```bash
python scene_graph_chatbot.py \
  --scene_data output/video_result_scene_graph.json \
  --api_key YOUR_GEMINI_API_KEY
```

#### Method 2: Single Question

```bash
python scene_graph_chatbot.py \
  --scene_data output/video_result_scene_graph.json \
  --api_key YOUR_GEMINI_API_KEY \
  --question "What objects appear in the video?"
```

#### Method 3: Test Script

```bash
python test_chatbot.py
```

### Step 3: Save/Load Vector Database (Optional)

To save processing time, you can save and reuse the vector database:

```bash
# Save index during first run
python scene_graph_chatbot.py \
  --scene_data output/video_result_scene_graph.json \
  --api_key YOUR_GEMINI_API_KEY \
  --save_index output/vector_index.index

# Load existing index for faster startup
python scene_graph_chatbot.py \
  --load_index output/vector_index.index \
  --api_key YOUR_GEMINI_API_KEY
```

## Example Questions

The chatbot can answer various types of questions about your video content:

### Object Detection

- "What objects appear in the video?"
- "How many people are in the scene?"
- "Are there any cars in the video?"

### Relationship Analysis

- "What relationships do you see between objects?"
- "What is the person doing?"
- "How do objects interact with each other?"

### Temporal Queries

- "What happens around timestamp 10 seconds?"
- "Describe the scene at frame 100"
- "What changes throughout the video?"

### Scene Understanding

- "Describe what happens in the video"
- "What is the main activity in the scene?"
- "What is the setting or environment?"

## Architecture

```
Video Input → Scene Graph Generation → Text Conversion → Vector Embeddings → FAISS Database
                                                                                    ↓
Question Input → Query Embedding → Similarity Search → Context Retrieval → Gemini AI → Answer
```

## Components

### 1. Scene Graph Extraction (`demo_video.py`)

- Processes video frames using trained scene graph models
- Extracts objects, their attributes, and relationships
- Saves structured data in JSON format

### 2. Text Conversion

- Converts scene graph data to natural language descriptions
- Creates readable text for each frame's content

### 3. Vector Database (`SceneGraphChatbot`)

- Uses SentenceTransformers for text embeddings
- FAISS for efficient similarity search
- Stores and retrieves relevant frame information

### 4. AI Question Answering

- Google Gemini AI for intelligent response generation
- Context-aware answers based on relevant video frames

## Data Formats

### Scene Graph JSON Structure

```json
[
  {
    "frame": 1,
    "timestamp": 0.033,
    "objects": [
      {
        "name": "person",
        "confidence": 0.95,
        "bbox": [x1, y1, x2, y2]
      }
    ],
    "relationships": [
      {
        "subject": "person",
        "predicate": "holding",
        "object": "book",
        "confidence": 0.87
      }
    ]
  }
]
```

### Text Description Format

```
Frame 1 (at 0.03s): Objects detected: person, book. Relationships: person holding book.
```

## Configuration

### Model Configuration

The system uses the PSG (Panoptic Scene Graph) model by default. You can modify:

- Model weights: `checkpoint/react_PSG/react_final.pth`
- Config file: `configs/PSG/e2e_relation_X_101_32_8_FPN_1x.yaml`
- Confidence thresholds: `--rel_conf` and `--box_conf`

### Embedding Model

The default embedding model is `all-MiniLM-L6-v2`. You can change it in the SceneGraphChatbot constructor:

```python
chatbot = SceneGraphChatbot(api_key, embedding_model="all-mpnet-base-v2")
```

## Performance Tips

1. **Vector Database**: Save the FAISS index to avoid rebuilding it each time
2. **Batch Processing**: Process multiple videos and combine their scene graphs
3. **Frame Sampling**: Process every N frames instead of every frame for faster processing
4. **Confidence Thresholds**: Adjust thresholds to balance accuracy vs. detection rate

## Troubleshooting

### Common Issues

1. **ImportError**: Make sure all dependencies are installed

   ```bash
   pip install faiss-cpu google-generativeai sentence-transformers
   ```

2. **API Key Error**: Verify your Gemini API key is correct and has quota

3. **Memory Issues**: For large videos, consider processing in smaller chunks

4. **Model Loading**: Ensure model weights and config files are in the correct paths

### Error Messages

- `"No scene graph data found"`: Run demo_video.py first to generate data
- `"Vector database not built"`: Call `build_vector_database()` before searching
- `"Error generating response"`: Check API key and internet connection

## License

This project is part of the SGG-Benchmark framework. Please refer to the main project's license.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Citation

If you use this chatbot system in your research, please cite the original SGG-Benchmark paper and mention this extension.
