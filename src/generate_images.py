import pathlib
import requests
import io
from PIL import Image

import aiohttp
import os

api_key = os.environ['huggingface_api_key']

async def fetch_image(api_url, headers, inputs):
    payload = {
        "inputs": inputs,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(api_url, headers=headers, json=payload) as response:
            response.raise_for_status()  # Ensure the request was successful
            return await response.read()
        
async def generate_image(user_message: str) -> str:

    API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-3.5-large"
    headers = {"Authorization": f"Bearer {api_key}"}

    image_bytes = await fetch_image(API_URL, headers, user_message)

    # Define the file path
    generated_images_dir = pathlib.Path("generated_images")
    generated_images_dir.mkdir(exist_ok=True) 

    output_path = generated_images_dir / "generated_image.png"

    # Save the image as a PNG file
    with open(output_path, "wb") as f:
        f.write(image_bytes)
        
    string_path = str(output_path)

    return string_path
