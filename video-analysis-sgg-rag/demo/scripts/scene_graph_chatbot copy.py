"""
Scene Graph Video Chatbot

This chatbot analyzes video content through scene graph data and provides insights
using FAISS vector database and Gemini AI.
"""

import json
import os
import numpy as np
import faiss
from typing import List, Dict, Any
from openai import OpenAI
from sentence_transformers import SentenceTransformer
import argparse

class SceneGraphChatbot:
    def __init__(self, api_key: str = "hihi", base_url: str = "https://kuvncdnldlxbqd-8080.proxy.runpod.net/v1", embedding_model: str = "all-MiniLM-L6-v2", model_name: str = "local-model"):
        """
        Initialize the Scene Graph Chatbot.
        
        Args:
            api_key: API key for LlamaCpp (can be any string for local models)
            base_url: Base URL for LlamaCpp API endpoint
            embedding_model: Name of the sentence transformer model for embeddings
            model_name: Model name to use for LlamaCpp
        """
        # Initialize LlamaCpp client
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model_name = model_name
        
        # Initialize sentence transformer for embeddings (force CPU to avoid CUDA errors)
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # Initialize FAISS index
        self.index = None
        self.text_chunks = []
        self.metadata = []
        
    def load_scene_graph_data(self, json_path: str, text_path: str = None):
        """
        Load scene graph data from JSON and text files.
        
        Args:
            json_path: Path to the scene graph JSON file
            text_path: Path to the text descriptions file (optional)
        """
        # Load JSON data
        with open(json_path, 'r') as f:
            self.scene_data = json.load(f)
        print(f"Loaded scene graph data from {json_path}")
        
        # Load or generate text descriptions
        if text_path and os.path.exists(text_path):
            with open(text_path, 'r') as f:
                text_content = f.read()
            self.text_chunks = [chunk.strip() for chunk in text_content.split('\n\n') if chunk.strip()]
        else:
            # Generate text descriptions from JSON
            self.text_chunks = []
            for frame_data in self.scene_data:
                text_desc = self._scene_graph_to_text(frame_data)
                self.text_chunks.append(text_desc)
        
        print(f"Loaded {len(self.text_chunks)} text descriptions")
        
        # Create metadata for each chunk
        self.metadata = []
        for i, frame_data in enumerate(self.scene_data):
            self.metadata.append({
                'frame': frame_data['frame'],
                'timestamp': frame_data['timestamp'],
                'chunk_index': i
            })
    
    def _scene_graph_to_text(self, frame_data: Dict[str, Any]) -> str:
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
    
    def build_vector_database(self):
        """Build FAISS vector database from text chunks."""
        if not self.text_chunks:
            raise ValueError("No text chunks loaded. Call load_scene_graph_data first.")
        
        # Generate embeddings
        print("Generating embeddings...")
        embeddings = self.embedding_model.encode(self.text_chunks)
        
        # Create FAISS index
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)  # Inner product (cosine similarity)
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Add embeddings to index
        self.index.add(embeddings.astype('float32'))
        
        print(f"Built FAISS index with {self.index.ntotal} vectors of dimension {dimension}")
    
    def search_similar_frames(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for frames similar to the query.
        
        Args:
            query: Search query
            top_k: Number of top results to return
            
        Returns:
            List of similar frame data with scores
        """
        if self.index is None:
            raise ValueError("Vector database not built. Call build_vector_database first.")
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode([query])
        faiss.normalize_L2(query_embedding)
        
        # Search
        scores, indices = self.index.search(query_embedding.astype('float32'), top_k)
        
        # Prepare results
        results = []
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx < len(self.text_chunks):
                result_data = {
                    'rank': i + 1,
                    'score': float(score),
                    'frame': self.metadata[idx]['frame'],
                    'timestamp': self.metadata[idx]['timestamp'],
                    'text': self.text_chunks[idx]
                }
                # Add scene data if available
                if hasattr(self, 'scene_data') and idx < len(self.scene_data):
                    result_data['scene_data'] = self.scene_data[idx]
                results.append(result_data)
        
        return results
    
    def generate_answer(self, question: str, context_frames: List[Dict[str, Any]]) -> str:
        """
        Generate an answer using Gemini AI based on the question and context frames.
        
        Args:
            question: User's question
            context_frames: Relevant frame data from vector search
            
        Returns:
            Generated answer
        """
        # Prepare context
        context_text = "Here is the relevant video scene information:\n\n"
        for frame in context_frames:
            context_text += f"Frame {frame['frame']} (at {frame['timestamp']:.2f}s):\n"
            context_text += f"- {frame['text']}\n\n"
        
        # Create prompt
        prompt = f"""You are an expert video analyst. Based on the scene graph information from a video, please answer the user's question accurately and informatively.

{context_text}

User Question: {question}

Please provide a detailed answer based on the scene information above. If the question cannot be answered from the provided information, please say so clearly."""

        try:
            # Generate response using LlamaCpp
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert video analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def chat(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Main chat function that processes a question and returns an answer.
        
        Args:
            question: User's question
            top_k: Number of top similar frames to use as context
            
        Returns:
            Dictionary containing answer and relevant frames
        """
        # Search for relevant frames
        relevant_frames = self.search_similar_frames(question, top_k)
        
        # Generate answer
        answer = self.generate_answer(question, relevant_frames)
        
        return {
            'question': question,
            'answer': answer,
            'relevant_frames': relevant_frames,
            'num_frames_used': len(relevant_frames)
        }
    
    def save_index(self, index_path: str):
        """Save FAISS index to disk."""
        if self.index is None:
            raise ValueError("No index to save. Build vector database first.")
        
        faiss.write_index(self.index, index_path)
        
        # Save metadata
        metadata_path = index_path.replace('.index', '_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump({
                'text_chunks': self.text_chunks,
                'metadata': self.metadata
            }, f, indent=2)
        
        print(f"Index saved to {index_path}")
        print(f"Metadata saved to {metadata_path}")
    
    def load_index(self, index_path: str):
        """Load FAISS index from disk."""
        self.index = faiss.read_index(index_path)
        
        # Load metadata
        metadata_path = index_path.replace('.index', '_metadata.json')
        with open(metadata_path, 'r') as f:
            data = json.load(f)
            self.text_chunks = data['text_chunks']
            self.metadata = data['metadata']
        
        print(f"Index loaded from {index_path}")
        print(f"Loaded {len(self.text_chunks)} text chunks")

def interactive_chat(chatbot: SceneGraphChatbot):
    """Run interactive chat session."""
    print("\n=== Scene Graph Video Chatbot ===")
    print("Ask questions about the video content. Type 'quit' to exit.")
    print("Example questions:")
    print("- What objects appear in the video?")
    print("- What relationships do you see between objects?")
    print("- What happens around timestamp 10 seconds?")
    print("- Describe the scene at frame 100")
    print("-" * 50)
    
    while True:
        question = input("\nYour question: ").strip()
        
        if question.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
        
        if not question:
            continue
        
        try:
            result = chatbot.chat(question)
            
            print(f"\nAnswer: {result['answer']}")
            print(f"\nBased on {result['num_frames_used']} relevant frame(s):")
            for frame in result['relevant_frames'][:3]:  # Show top 3
                print(f"  - Frame {frame['frame']} (t={frame['timestamp']:.2f}s, score={frame['score']:.3f})")
        
        except Exception as e:
            print(f"Error: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Scene Graph Video Chatbot")
    parser.add_argument('--scene_data', help='Path to scene graph JSON file')
    parser.add_argument('--text_data', help='Path to text descriptions file (optional)')
    parser.add_argument('--api_key', required=True, help='Gemini API key')
    parser.add_argument('--save_index', help='Path to save FAISS index')
    parser.add_argument('--load_index', help='Path to load existing FAISS index')
    parser.add_argument('--question', help='Single question to ask (non-interactive mode)')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.load_index and not args.scene_data:
        parser.error("Either --scene_data or --load_index must be provided")
    
    # Initialize chatbot
    chatbot = SceneGraphChatbot(args.api_key)
    
    if args.load_index and os.path.exists(args.load_index):
        # Load existing index
        chatbot.load_index(args.load_index)
    else:
        # Build new index
        chatbot.load_scene_graph_data(args.scene_data, args.text_data)
        chatbot.build_vector_database()
        
        if args.save_index:
            chatbot.save_index(args.save_index)
    
    if args.question:
        # Single question mode
        result = chatbot.chat(args.question)
        print(f"Question: {result['question']}")
        print(f"Answer: {result['answer']}")
    else:
        # Interactive mode
        interactive_chat(chatbot)

if __name__ == "__main__":
    main()
