# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import re
import time
import tempfile
import shutil

from google.cloud import storage
from moviepy import VideoFileClip, concatenate_videoclips

from google import genai
from google.adk.agents import Agent
from google.adk.tools import ToolContext
from google.genai import types

from .utils.utils import load_prompt_from_file

# Set up logging for debug output
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# ---------------------------------------------------------
# Configuration and Initialization
# ---------------------------------------------------------
MODEL = "gemini-2.5-flash"
# Target Vertex AI Video Generation Model (Veo)
VIDEO_MODEL = "veo-3.1-generate-001"
VIDEO_MODEL_LOCATION = "us-central1"
DESCRIPTION = "Agent responsible for creating videos based on a screenplay and storyboards"
ASPECT_RATIO = "16:9"

# Initialize Google GenAI client to interact with Veo model
client = genai.Client(
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=VIDEO_MODEL_LOCATION,
)


# ---------------------------------------------------------
# Video Generation Tool
# ---------------------------------------------------------
def video_generate(
    prompt: str,
    scene_number: int,
    image_link: str,
    screenplay: str,
    tool_context: ToolContext,
) -> list[str]:
    """
    Generate video based on the passed prompt and storyboard image.

    Args:
        prompt (str): A text prompt describing the video that should be generated and returned by the tool.
        scene_number (int): Scene number
        image_link (str): Link to the image stored in GCS bucket
        screenplay (str): Screenplay for the scene
        tool_context (): ToolContext needed by the tool

    Returns:
        str: Link to the video stored in GCS bucket.
    """
    try:
        # Get active session ID to structure GCS paths per session
        session_id = tool_context._invocation_context.session.id
        bucket_name = os.getenv("GOOGLE_CLOUD_BUCKET_NAME")
        GCS_PATH = f"gs://{bucket_name}/{session_id}"
        AUTHORIZED_URI = "https://storage.cloud.google.com/"

        # Extract spoken dialogue/actions from screenplay to enhance video prompt
        dialogue = "\n".join(
            re.findall(r"^\w+\s*\(.+\)\s*$", screenplay, re.MULTILINE)
        )
        dialogue += "\n".join(
            re.findall(r"^\s{2,}.+$", screenplay, re.MULTILINE)
        )

        if dialogue:
            prompt += f"\n\nAudio:\n{dialogue}"

        logger.info(
            f"Generating video for prompt '{prompt}' and image '{image_link}'"
        )

        # Trigger asynchronous video generation operation using the Veo model
        operation = client.models.generate_videos(
            model=VIDEO_MODEL,
            prompt=prompt,
            config=types.GenerateVideosConfig(
                aspect_ratio=ASPECT_RATIO,
                output_gcs_uri=f"{GCS_PATH}/scene_{scene_number}",
                number_of_videos=1,
                duration_seconds=8,
                person_generation="allow_adult",
            ),
        )

        # Poll the operation until video generation completes
        while not operation.done:
            time.sleep(15)
            operation = client.operations.get(operation)
            logger.info(f"Video generation operation: {operation}")

        # Parse generated videos and convert gs:// URI to web-accessible Storage URL
        if operation.response:
            logger.info(
                f"Generated {len(operation.result.generated_videos)} video(s) for prompt: {prompt}"
            )
            return [
                video.video.uri.replace("gs://", AUTHORIZED_URI)
                for video in operation.result.generated_videos
            ]
        else:
            logger.info(f"Generated no (0) video for prompt: {prompt}")
            return []
    except Exception as e:
        logger.error(f"Error generating a video for {prompt}: {e}")
        return []


# ---------------------------------------------------------
# Video Stitching Tool
# ---------------------------------------------------------
def video_stitch(video_links: list[str], tool_context: ToolContext) -> str:
    """
    Stitches a list of video clips together into a single final video and uploads it to GCS.

    Args:
        video_links (list[str]): The ordered list of GCS/HTTP links to the scene video clips.
        tool_context (): ToolContext needed by the tool.

    Returns:
        str: Link to the final stitched video stored in GCS bucket.
    """
    try:
        logger.info(f"Stitching videos: {video_links}")
        session_id = tool_context._invocation_context.session.id
        bucket_name = os.getenv("GOOGLE_CLOUD_BUCKET_NAME")
        
        # Initialize standard GCS Storage client
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)

        # Create temporary working directory for local video files
        temp_dir = tempfile.mkdtemp()
        local_clips = []
        
        # Download each video clip from GCS to local temporary directory
        for i, link in enumerate(video_links):
            gcs_path = link.replace("https://storage.cloud.google.com/", "gs://")
            if gcs_path.startswith("gs://"):
                parts = gcs_path[5:].split("/", 1)
                blob_name = parts[1]
            else:
                # Fallback parser if format differs
                blob_name = link.split(bucket_name + "/")[1]
            
            blob = bucket.blob(blob_name)
            local_path = os.path.join(temp_dir, f"clip_{i}.mp4")
            logger.info(f"Downloading {blob_name} to {local_path}")
            blob.download_to_filename(local_path)
            
            # Load video file clip using MoviePy
            clip = VideoFileClip(local_path)
            local_clips.append(clip)
        
        # Stitch all individual scene clips together using MoviePy compose method
        logger.info("Concatenating video clips...")
        final_clip = concatenate_videoclips(local_clips, method="compose")
        
        final_local_path = os.path.join(temp_dir, "final_movie.mp4")
        logger.info(f"Writing final stitched video to {final_local_path}")
        final_clip.write_videofile(final_local_path, codec="libx264", audio_codec="aac")
        
        # Upload the final stitched movie to GCS
        final_blob_name = f"{session_id}/final_movie.mp4"
        final_blob = bucket.blob(final_blob_name)
        logger.info(f"Uploading final movie to gs://{bucket_name}/{final_blob_name}")
        final_blob.upload_from_filename(final_local_path)
        
        # Release system file resources by closing clips
        for clip in local_clips:
            clip.close()
        final_clip.close()
        
        AUTHORIZED_URI = "https://storage.cloud.google.com/"
        return f"{AUTHORIZED_URI}{bucket_name}/{final_blob_name}"
        
    except Exception as e:
        logger.error(f"Error stitching videos: {e}")
        return ""
    finally:
        # Clean up temporary directory and files
        shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------
# Video Agent Initialization
# ---------------------------------------------------------
video_agent = None
try:
    # Construct the Video Agent.
    # It takes storyboards and screenplay, calls `video_generate` to create
    # clips, and provides the `video_stitch` tool to create the final movie.
    video_agent = Agent(
        model=MODEL,
        name="video_agent",
        description=(DESCRIPTION),
        instruction=load_prompt_from_file("video_agent.txt"),
        output_key="video",
        tools=[video_generate, video_stitch],
    )
    logger.info(f"✅ Agent '{video_agent.name}' created using model '{MODEL}'.")
except Exception as e:
    logger.error(
        f"❌ Could not create Video agent. Check API Key ({MODEL}). Error: {e}"
    )
