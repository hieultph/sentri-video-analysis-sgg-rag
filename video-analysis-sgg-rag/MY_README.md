python demo/scripts/demo_video.py --config checkpoint\my_react_PSG\config.yml --weights checkpoint\my_react_PSG\best_model_epoch_5.pth --video "demo\videos\v2.mp4" --save_path "demo/v2.avi"

python demo/scripts/demo_video.py --config checkpoint\react_PSG\config.yml --weights checkpoint\react_PSG\best_model_epoch_11.pth --video "demo\videos\v2.mp4" --save_path "demo/v2.avi"

# Code to run

## webcam_demo.py

```
python demo/webcam_demo.py --config checkpoint\react_PSG\config.yml --weights checkpoint\react_PSG\best_model_epoch_11.pth --window_width 1280 --window_height 720 --rel_conf 0.1 --box_conf 0.1
```

export PYTHONPATH="F:\gdrive\Takeout\Drive\School\4 Fourth year\BCTN\code\video-analysis-sgg-rag:$PYTHONPATH"

## demo_video.py

```
python demo/demo_video.py --config checkpoint\react_PSG\config.yml --weights checkpoint\react_PSG\best_model_epoch_11.pth --video "demo\Security camera in kitchen.mp4" --save_path "demo/output_kitchen.avi"

python demo/demo_video.py --config checkpoint\react_PSG\config.yml --weights checkpoint\react_PSG\best_model_epoch_11.pth --video "demo\Kitchen Security Camera sample.mp4" --save_path "demo/output_kitchen_2.avi"

python demo/demo_video.py --config checkpoint\react_PSG\config.yml --weights checkpoint\react_PSG\best_model_epoch_11.pth --video "demo\car vs bike accident cctv video in pollachi.mp4" --save_path "demo/output_kitchen_8.avi"

python demo/scripts/demo_video.py --config checkpoint\my_react_PSG\config.yml --weights checkpoint\my_react_PSG\best_model_epoch_5.pth --video "demo\videos\car_vs_bike.mp4" --save_path "demo/output_kitchen_8.avi"

---

python demo/demo_video.py --config checkpoint\react_final\config.yml --weights checkpoint\react_final\best_model_epoch_9.pth --video "demo\IP Bullet CCTV Camera (Day Vision) - Revlight Security.mp4" --save_path "demo/output_kitchen.avi"
```

## Chatbot

```
python demo/scene_graph_chatbot.py --load_index demo/video_index.index --api_key AIzaSyDeMAgRP8wZPgZ-5-q3v4G5VR5nC7p7V7A --question "What happens in the first 10 seconds of the video?"
```

## explore_faiss.py

```
python demo/explore_faiss.py --index demo/video_index.index --search "truck driving on road" --top_k 3

```

## gradio_chat_ui.py

```
C:/Users/Andrew/miniconda3/Scripts/conda.exe run -p H:\conda_envs\anaconda\sgg_benchmark --no-capture-output python demo/gradio_chat_ui.py --port 7860

python demo/scripts/gradio_chat_ui.py --port 7860
```

# Error:

## Can run on VG150

The VG150 dataset is missing the required .h5 file. Since you want to run a demo on a video file, you don't actually need to load the full dataset statistics. The easiest solution is to use the react_PSG config instead, which we know works:
