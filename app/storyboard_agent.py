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

import vertexai
from google.adk.agents import Agent
from google.adk.tools import ToolContext
from vertexai.preview.vision_models import ImageGenerationModel

from .utils.utils import load_prompt_from_file

# Set up logging for debug output
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# ---------------------------------------------------------
# Configuration and Initialization
# ---------------------------------------------------------
MODEL = "gemini-2.5-flash"
DESCRIPTION = (
    "Agent responsible for creating storyboards based on a screenplay and story"
)

# Target Vertex AI Image Generation Model (Imagen 3.0)
IMAGEN_MODEL = "imagen-3.0-generate-002"

# Resolve target Google Cloud region (defaulting to us-central1 if global or not set)
location = os.getenv("GOOGLE_CLOUD_LOCATION")
if not location or location == "global":
    location = "us-central1"

# Initialize Vertex AI SDK
vertexai.init(
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=location,
)
# Load pretrained Imagen model
generation_model = ImageGenerationModel.from_pretrained(IMAGEN_MODEL)


# ---------------------------------------------------------
# Agent Tools
# ---------------------------------------------------------
def storyboard_generate(
    prompt: str, scene_number: int, tool_context: ToolContext
) -> list[str]:
    """
    Generate storyboard image representing the passed prompt.

    Args:
        prompt (str): A text prompt describing the storyboard image that should be generated and returned by the tool.
        scene_number (int): Scene number
        tool_context (): ToolContext needed by the tool

    Returns:
        str: Link to the image stored in GCS bucket.
    """
    try:
        # Get active session ID to structure GCS paths per session
        session_id = tool_context._invocation_context.session.id
        bucket_name = os.getenv("GOOGLE_CLOUD_BUCKET_NAME")
        GCS_PATH = f"gs://{bucket_name}/{session_id}"
        AUTHORIZED_URI = "https://storage.cloud.google.com/"

        logger.info(
            f"Generating image for scene {scene_number} with prompt: {prompt}"
        )
        
        # Call the Vertex AI Imagen API to generate a 1:1 aspect ratio image
        # and store the output directly to the specified Google Cloud Storage bucket path.
        response = generation_model.generate_images(
            prompt=prompt,
            number_of_images=1,
            output_gcs_uri=f"{GCS_PATH}/scene_{scene_number}",
            aspect_ratio="1:1",
            negative_prompt="",
            person_generation="allow_adult",
            safety_filter_level="block_few",
            add_watermark=True,
        )

        # Parse output images and convert gs:// URI to web-accessible Storage URL
        if response.images:
            logger.info(
                f"Generated {len(response.images)} image(s) for prompt: {prompt}"
            )
            return [
                image._gcs_uri.replace("gs://", AUTHORIZED_URI)
                for image in response.images
            ]
        else:
            logger.info(f"Generated no (0) images for prompt: {prompt}")
            return []
    except Exception as e:
        logger.error(f"Error generating an image for {prompt}: {e}")
        return []


# ---------------------------------------------------------
# Storyboard Agent Initialization
# ---------------------------------------------------------
storyboard_agent = None
try:
    # Construct the Storyboard Agent.
    # It takes the screenplay output and calls the `storyboard_generate` tool
    # to create storyboard illustrations for each scene.
    storyboard_agent = Agent(
        model=MODEL,
        name="storyboard_agent",
        description=(DESCRIPTION),
        instruction=load_prompt_from_file("storyboard_agent.txt"),
        output_key="storyboard",
        tools=[storyboard_generate],
    )
    logger.info(
        f"✅ Agent '{storyboard_agent.name}' created using model '{MODEL}'."
    )
except Exception as e:
    logger.error(
        f"❌ Could not create Storyboard agent. Check API Key ({MODEL}). Error: {e}"
    )
